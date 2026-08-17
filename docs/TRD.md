# TRD — AI Quant Lab (Stock Dashboard)

> 현행 버전 기준 (Streamlit). 구버전(React+FastAPI) 스펙은 `TRD_legacy_react.md` 참고.

## 1. 아키텍처 개요

```
┌─ 로컬 PC (Windows Task Scheduler) ──────────────┐
│  run_preset_backtests / fetch_cache /            │
│  fetch_sec_intelligence / portfolio_risk_alert / │
│  send_rebalancing_alert                          │
│        │ 데이터 수집·계산 → data/cache/*.json     │
│        └── git commit + push ──────────┐         │
└────────────────────────────────────────┼─────────┘
                                         ▼
┌─ GitHub (danggyugit/stock-dashboard) ───────────┐
│  · 캐시 JSON 저장소 (raw URL로 서빙)              │
│  · Actions: update_valuation_cache (매일)        │
└───────────────┬─────────────────────────────────┘
                ▼ (재배포/raw fetch)
┌─ Streamlit Cloud (aiquantlab.streamlit.app) ────┐
│  streamlit_app/app.py — st.navigation 18페이지    │
│  services/ 19모듈 · core/ 3 provider             │
└───────────────┬─────────────────────────────────┘
                ▼
┌─ Turso (libsql) ── 사용자·포트폴리오·워치리스트 DB │
└─────────────────────────────────────────────────┘
```

- **로컬 SQLite 캐시** (git 미추적): `data/price_cache.db`(월봉), `data/historical_cache.db`(S&P500 멤버십·PIT 재무·배당), `data/stock_dashboard.db`(로컬 폴백 DB)
- **MCP 서버**: `mcp_server/server.py` — streamlit_app services를 재사용해 Claude Desktop에 시세·밸류에이션 도구 제공 (stdio)

## 2. 기술 스택

| 계층 | 기술 |
|---|---|
| 앱 | Streamlit ≥1.42 (multipage, `st.navigation`), Plotly |
| 인증 | `st.login` (Google OIDC, Authlib) + 소유자 승인(HMAC 토큰) |
| DB | Turso(libsql, 클라우드) / SQLite(로컬 폴백·캐시) |
| ML | scikit-learn(RF), XGBoost, LightGBM, hmmlearn(HMM), scipy |
| 데이터 | yfinance, SEC EDGAR API, Finnhub, FRED, Wikipedia(S&P500 변경이력) |
| LLM | Anthropic Claude(공시 요약·센티먼트, 수동 트리거), Google Gemini |
| 알림 | Telegram Bot API |
| 배포 | Streamlit Cloud (`streamlit_app/app.py`) |

## 3. 핵심 모듈

### streamlit_app/services/
| 모듈 | 책임 |
|---|---|
| auth_service | 로그인·승인·사이드바 계정 UI |
| market_service | 지수·히트맵(로컬 DB 벌크 쿼리) |
| portfolio_service / watchlist_service | 매매·보유·관심종목 (Turso) |
| cache_loader | GitHub raw → 로컬 → tmp 3단 캐시 로더 + 신선도 배너 |
| factor_backtest_service | 팩터 백테스트 엔진 (멤버십 복원·PIT·상폐손실·듀얼모멘텀 오버레이) |
| factor_strategies | 23개 전략 정의 (rank_fn·requires·enabled) |
| historical_data_service | S&P500 변경이력·PIT 재무·배당 SQLite 캐시 |
| price_history_service | 월봉 종가 캐시 (prefetch / load_monthly_prices) |
| breakout_service | 회귀 추세채널 돌파 계산 |
| rs_service | IBD식 RS 랭킹 |
| sec_intelligence_service | 13F 파싱·QoQ diff·내부자 스캔·공시 조회 |
| insider_service | Form 4 파싱 (CIK 매핑 공용) |
| valuation_service / ai_valuation_service | 밸류에이션·시나리오 밴드 |
| sentiment_service / macro_service / calendar_service | 센티먼트·매크로·캘린더 |
| i18n | 한/영 문자열 + 토글 |

### 백테스트 무결성 규칙 (수정 시 반드시 유지)
- **PIT**: 재무 데이터는 보고 지연(연간 90일) 반영, 스냅샷은 `date` 이전 데이터만
- **Embargo**: ML 학습·검증 사이 21일 갭
- **생존편향**: Wikipedia 변경이력으로 과거 멤버십 복원, 상폐 종목은 마지막 거래가/-30% 청산
- **min_history**: 평가일 기준 263개월봉(12M 모멘텀 유효성) 강제

## 4. 데이터 파이프라인 (스케줄)

| Task (Windows) | 시각 | 스크립트 | 산출물 |
|---|---|---|---|
| StockDashboard-PresetBacktests | 매일 11:00 | run_preset_backtests.py | backtests/*.json + Telegram |
| StockDashboard-Fundamentals | 매일 13:00 | fetch_cache.py (가격→재무 2단계) | heatmap/stocks/fundamentals/meta.json |
| StockDashboard-SecIntelligence | 매일 11:30 | fetch_sec_intelligence.py | sec/*.json + Telegram |
| StockDashboard-PortfolioRiskAlert | 매일 07:00 | portfolio_risk_alert.py | Telegram (플래그 시만) |
| StockDashboard-RebalancingAlert | 매월 1일 11:30 | send_rebalancing_alert.py | Telegram |
| (GitHub Actions) update_valuation_cache | 매일 03:00 UTC | build_valuation_cache.py | valuation/*.json |

**git push 패턴**: 스크립트는 `fetch → merge -X ours origin/main → push`로 원격 커밋을 흡수.
⚠️ 이 패턴은 캐시 전용이다 — 신규 기능 커밋이 로컬에만 있는 상태에서 원격과 분기되면 rebase로 보존할 것 (과거 `merge -s ours`로 기능 커밋 유실 사고 있었음).

**Windows 특이사항**: `valuation/CON.json`(예약어)은 로컬 체크아웃 불가 →
이 저장소는 `core.protectNTFS=false` + sparse-checkout(valuation 제외)로 운영.

## 5. 환경 설정

### streamlit_app/.streamlit/secrets.toml
```toml
[turso]            # 클라우드 DB
url = "libsql://..."
auth_token = "..."

[auth]             # st.login OIDC (Streamlit Cloud에는 클라우드 secrets로)
# redirect_uri, client_id, client_secret, server_metadata_url, cookie_secret

APPROVE_SECRET = "..."     # 사용자 승인 HMAC 키
ANTHROPIC_API_KEY = "..."  # 공시 요약 등 (수동 트리거만)
FINNHUB_API_KEY = "..."
GEMINI_API_KEY = "..."
```

### 스케줄러 환경변수 (stock_briefing/.env 공유)
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `QUANT_LAB_CHAT_ID`

## 6. 실행

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

배치 스크립트 수동 실행: `python scripts/run_preset_backtests.py` 등 (streamlit_app 디렉터리에서).
