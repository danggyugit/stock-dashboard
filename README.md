# AI Quant Lab — Stock Dashboard

미국 주식 투자자를 위한 통합 리서치·퀀트 분석 플랫폼.
**Live**: https://aiquantlab.streamlit.app

![App](https://img.shields.io/badge/Streamlit-1.42+-red)
![DB](https://img.shields.io/badge/Turso-libsql-teal)
![ML](https://img.shields.io/badge/ML-RF·XGB·LGBM·HMM-green)
![Data](https://img.shields.io/badge/Data-yfinance·SEC_EDGAR·FRED-blue)

## 주요 기능

### 📊 Market Overview
- **Dashboard** — 지수·시장 요약·포트폴리오 스냅샷·뉴스
- **Heatmap** — S&P 1500 섹터 트리맵 (시총·등락률)
- **Macro / Sentiment / Calendar** — 매크로 지표, Fear & Greed, 실적·경제 캘린더

### 🔍 Stock Research
- **Stock Detail** — 차트·재무·밸류에이션·내부자 거래
- **Screener** — 펀더멘털 필터 (PER·PBR·ROE·배당 …)
- **RS Screener** — IBD식 상대강도 랭킹
- **Breakout Screener** — 월봉 회귀 추세채널 상단 돌파 스캔 (조회기간·채널폭·돌파범위 조절)
- **Compare / Watchlist**

### 🧪 Analysis Tools
- **AI Quant Lab** — RandomForest·XGBoost·LightGBM 앙상블 종목 랭킹 + walk-forward 백테스트
  (21일 embargo · PIT 재무 · 생존편향/상폐손실 보정) + HMM 레짐·변동성 타게팅 현금비중.
  매일 자동 실행되는 프리셋 결과 로드 지원
- **Factor Lab** — 룰 기반 팩터 백테스트 **23개 전략** (모멘텀·52주신고가·듀얼모멘텀·가치·성장·F-Score·배당·주주환원·EBIT/EV 매직포뮬러 …)
- **SEC Intelligence** — 13F 고래(버핏 등 20인) 포트폴리오 추적 · 내부자 대량매수 스캔 · 공시 AI 요약
- **Stock Lab** — 12-에이전트 심층 리포트 (외부: aiquantlab-stocklab.pages.dev)

### 💼 Portfolio
- 매매 기록·보유 현황·손익 (Turso 클라우드 DB, Google 로그인 + 승인제)

### 🤖 자동화 (로컬 스케줄러 + GitHub Actions)
| 자동화 | 주기 | 출력 |
|---|---|---|
| 프리셋 백테스트 5종 | 매일 11:00 KST | 캐시 JSON + Telegram TOP10 |
| 가격·펀더멘털 캐시 (S&P1500) | 매일 13:00 KST | heatmap/fundamentals JSON |
| SEC 내부자 스캔·13F | 매일 11:30 KST | Telegram 알림 |
| 포트폴리오 과열 점검 | 매일 07:00 KST | Telegram (리스크 고지) |
| 월간 리밸런싱 알림 | 매월 1일 | Telegram |
| Valuation 캐시 | 매일 (GH Actions) | 종목별 JSON |

## 프로젝트 구조

```
stock_dashboard/
├── streamlit_app/          # 앱 본체 (Streamlit Cloud가 app.py 실행)
│   ├── app.py              # 진입점 — st.navigation 페이지 등록
│   ├── database.py         # Turso/SQLite 연결
│   ├── app_pages/          # 18개 페이지
│   ├── services/           # 도메인 로직 19모듈
│   ├── core/               # data/llm/news provider
│   ├── components/         # 공용 UI
│   ├── scripts/            # 스케줄러·CI 스크립트 (.py + .bat + .ps1)
│   └── data/cache/         # git 추적 캐시 JSON (서버가 raw로 읽음)
├── mcp_server/             # Claude Desktop용 MCP 서버 (services 재사용)
├── docs/                   # PRD/TRD(현행) + *_legacy_react.md(구버전) + instagram 카드
└── .github/workflows/      # valuation 캐시 (매일) + 가격 캐시 (수동 폴백)
```

## 실행

```bash
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

### Secrets (`streamlit_app/.streamlit/secrets.toml`)

```toml
[turso]                     # 없으면 로컬 SQLite로 폴백
url = "libsql://..."
auth_token = "..."

APPROVE_SECRET = "..."      # 사용자 승인 HMAC
ANTHROPIC_API_KEY = "..."   # 선택 — AI 요약 (수동 트리거만)
FINNHUB_API_KEY = "..."     # 선택 — 뉴스
GEMINI_API_KEY = "..."      # 선택
# [auth] — st.login용 Google OIDC 설정 (Streamlit Cloud secrets에 동일 구성)
```

스케줄러 알림용 환경변수는 워크스페이스의 `stock_briefing/.env`를 공유:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `QUANT_LAB_CHAT_ID`

## 배포

- **Streamlit Cloud**: main 브랜치 `streamlit_app/app.py` 자동 배포
- 캐시 데이터는 로컬 스케줄러가 git push → 앱이 GitHub raw로 로드 (TTL 15분)
- 상세 아키텍처·스케줄·주의사항: [docs/TRD.md](docs/TRD.md)

## 이력

- 초기 버전은 React 19 + FastAPI 구성이었으며 Streamlit으로 전환됨.
  구버전 코드는 git 태그 `archive/react-fastapi-v1`, 스펙은 `docs/*_legacy_react.md` 참고.

> ⚠️ 본 프로젝트의 모든 분석·백테스트·알림은 투자 참고용이며 투자 권유가 아닙니다.
