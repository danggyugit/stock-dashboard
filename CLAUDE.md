# Stock Dashboard (AI Quant Lab) — 프로젝트 규칙

## 프로젝트 개요
미국 주식 통합 리서치·퀀트 분석 Streamlit 앱.
**운영**: https://aiquantlab.streamlit.app (Streamlit Cloud가 `streamlit_app/app.py` 실행)

> 구버전(React+FastAPI)은 폐기됨 — git 태그 `archive/react-fastapi-v1`에 보존.

## 기술 스택
- **앱**: Streamlit ≥1.42 (`st.navigation` 멀티페이지), Plotly
- **DB**: Turso(libsql, 클라우드 — 사용자·포트폴리오) / SQLite(로컬 캐시: price_cache.db, historical_cache.db)
- **ML**: scikit-learn, XGBoost, LightGBM, hmmlearn
- **데이터**: yfinance, SEC EDGAR, Finnhub, FRED, Wikipedia(S&P500 멤버십)
- **LLM**: Anthropic Claude·Google Gemini (사용자 수동 트리거만 — 자동 호출 금지, 비용 관리)
- **알림**: Telegram Bot

## 디렉터리 구조
```
streamlit_app/
├── app.py            # 진입점 · st.navigation PAGES dict — 새 페이지는 여기 등록
├── database.py       # Turso/SQLite 연결 (get_connection)
├── app_pages/        # 페이지 (등록된 18개 + _quant_lab_i18n.py 헬퍼)
├── services/         # 도메인 로직 — 페이지는 서비스만 호출 (페이지에 로직 넣지 말 것)
├── core/             # data_provider(yfinance 경유) · llm_provider · news_provider
├── components/ui.py  # 공용 CSS·헤더·사이드바
├── scripts/          # 스케줄러 (.py+.bat 쌍) + CI 스크립트 — 아래 '삭제 금지' 참고
└── data/cache/       # git 추적 캐시 JSON — 서버가 GitHub raw로 읽는 운영 데이터
mcp_server/server.py  # Claude Desktop MCP — streamlit_app/services를 import (경로 의존)
docs/                 # PRD.md·TRD.md(현행) · *_legacy_react.md(구버전) · instagram/
```

## 데이터 흐름 (핵심)
로컬 Windows 스케줄러가 데이터 수집·계산 → `data/cache/*.json` → **git push** → Streamlit Cloud 앱이 GitHub raw로 로드(15분 TTL).
Turso는 사용자 데이터(포트폴리오·워치리스트)만. 상세: `docs/TRD.md`.

## 활성 스케줄 태스크 (Windows Task Scheduler)
| 태스크 | 시각 | 스크립트 |
|---|---|---|
| StockDashboard-PresetBacktests | 매일 11:00 | run_preset_backtests.py |
| StockDashboard-SecIntelligence | 매일 11:30 | fetch_sec_intelligence.py |
| StockDashboard-Fundamentals | 매일 13:00 | fetch_cache.py |
| StockDashboard-PortfolioRiskAlert | 매일 07:00 | portfolio_risk_alert.py |
| StockDashboard-RebalancingAlert | 매월 1일 | send_rebalancing_alert.py |
| (GitHub Actions) update_valuation_cache | 매일 | build_valuation_cache.py |

## ⛔ 절대 삭제/이동 금지
- `streamlit_app/scripts/`의 모든 `.py`·`.bat` (위 태스크가 절대경로로 호출)
- `streamlit_app/data/cache/**` (운영 데이터 — 서버가 읽음)
- `.github/workflows/update_valuation_cache.yml` (활성 CI)
- `mcp_server/server.py` (사용 중, 추가 개발 예정)
- `streamlit_app/migrate_to_turso.py` (Turso 재해복구 도구)

## 새 기능 추가 절차
1. 로직은 `services/새서비스.py`에, UI는 `app_pages/N_이름.py`에 작성
2. `app.py`의 PAGES dict에 `st.Page(...)` 한 줄 등록 (섹션 선택)
3. **사이드바는 app.py가 전역 렌더링** — 페이지에서 `render_user_sidebar()` 재호출 금지 (중복 키 에러)
4. 무거운 연산은 버튼 트리거 + `st.session_state` 캐시, 조회성은 `@st.cache_data(ttl=...)`
5. 정기 배치가 필요하면 scripts/에 .py+.bat 쌍 추가 후 schtasks 등록

## 백테스트 무결성 (수정 시 반드시 유지)
- **PIT**: 재무는 보고지연(연간 90일) 반영, 스냅샷은 평가일 이전 데이터만
- **Embargo**: ML 학습·검증 21일 갭 / **min_history**: 평가일 기준 263봉
- **생존편향**: 멤버십 복원 + 상폐 종목 마지막가/-30% 청산 반영
- 근거 없는 수치·기능 날조 금지 (인스타 카드 포함)

## Git 규칙
- 커밋 메시지 영문, conventional commits
- `.env`·`secrets.toml`·`*.db`·로그는 커밋 금지 (.gitignore 확인)
- **캐시 스크립트의 push 패턴**(`fetch → merge -X ours → push`)은 캐시 전용.
  기능 커밋이 원격과 분기되면 **rebase로 보존** — 과거 `-s ours` 병합으로 기능 커밋 유실 사고 있었음
- ⚠️ Windows: `valuation/CON.json`(예약어) 때문에 이 저장소는 `core.protectNTFS=false` + sparse-checkout(valuation 제외). 이 설정을 되돌리면 merge가 깨짐

## Python 코딩 규칙
- 함수 type hint 필수, 파일 경로는 `pathlib.Path`
- `print()` 대신 `logging.getLogger(__name__)`
- public 함수/클래스 Google-style docstring
- 파일 I/O `encoding="utf-8"` 명시, pandas 벡터 연산 우선
- yfinance 호출은 `core/data_provider.py` 경유 (스크립트·백테스트 서비스의 배치 다운로드는 예외)
- Python 파일 `snake_case.py`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE_CASE`

## 배포 주의
- Streamlit Cloud는 main push 시 자동 재배포 — 단, **앱이 에러로 멈춘 상태면 수동 Reboot 필요**
- `secrets.toml`은 로컬용, 배포 환경은 Streamlit Cloud secrets에 동일 키 구성
- 월봉 캐시(price_cache.db)는 **종가만** 저장 — 고가 기반 지표는 스키마 확장 필요

## 인스타그램 카드 제작 규칙

### 데이터 원칙
- 임의 날조 금지: 자기 앱(AI Quant Lab) 기능을 없는 기능으로 소개하는 것은 절대 금지
- 어닝/주가/애널리스트 목표가 등 시장 데이터는 웹 검색으로 확인 후 사용 OK
- 확인되지 않은 숫자는 카드에 넣지 말고 반드시 웹 검색 후 실제 데이터 기입

### 카드 구성 표준 (8장 고정)
새 어닝 카드를 만들기 전에 기존 카드(`docs/instagram/01_earnings/*.html`)를 **반드시 먼저 읽고** 디자인·구성 방향을 맞출 것.

| Card | 제목 | 주요 컴포넌트 |
|------|------|-------------|
| 1 | Cover | c1-mid 구조 (logo → ticker → c1-chg 주가변동 → c1-momentum 3박스) |
| 2 | Earnings | mgrid 2×2 (매출·EPS·마진·성장률) + banner |
| 3 | Highlights | hl-list 5항목 (hl-item.good) |
| 4 | Drivers / Mixed | driver-list 3항목 + insight-banner |
| 5 | Outlook | out-grid 2×2 (가이던스 수치) + insight-banner |
| 6 | Valuation | val-grid bull/bear (각 5행) + insight-banner |
| 7 | **Analyst Targets** | 바차트 (회사명 + 목표가) + current-line + insight-banner |
| 8 | CTA | AI QUANT LAB 브랜드 (diamond logo + feat-c8 × 4 + cta-box) |

### 로고 규칙
- 로고 파일 위치: `docs/instagram/_shared/logos/{TICKER}.svg`
- **반드시 최신 공식 로고 사용**: 새 종목 카드 제작 시 웹 검색(Wikimedia Commons, Brandfetch 등)으로 공식 SVG path 확인 후 저장
- **SVG는 path 기반으로 작성** (text 요소 금지): 폰트 환경에 무관하게 정확히 렌더링되어야 함
- fill 색상: 회사 공식 브랜드 컬러 사용 (로고 배경은 흰색 박스이므로 브랜드 컬러 또는 짙은 색)
- 기존 로고 목록: PLTR(자체 path), AMD(#E8211A 레드), AMZN, WDC, SNDK, GOOGL, STX, NVDA

### 디자인 기준
- CSS 변수: `--text-dim:#CBD5E1`, `--border:rgba(203,213,225,0.16)`, `--bg-card:#0F172A`, `--bg-card-alt:#131F38`
- badge font-size: 14px / counter: JetBrains Mono, `01 / 08` 형식
- card-title: 30px (Card 7은 24px으로 축소해 차트 공간 확보)
- mbox .ml/.me/.ms: 14px / card-label: `position:absolute; top:-28px; left:0`
- 종목 고유 accent 색상은 유지하되, 구조·폰트·간격은 기존 카드와 동일하게 맞출 것
