# Stock Dashboard (Streamlit Edition)

US 주식 시장 통합 대시보드 — Heatmap, 포트폴리오, 센티먼트, 캘린더, 스크리너, Watchlist까지.

## Features

- **Dashboard** — 시장 인덱스 + 인트라데이 차트 + 히트맵 + 포트폴리오 요약
- **Heatmap** — S&P 500 섹터 트리맵 (Treemap / Card Grid 토글)
- **Stock Detail** — 캔들스틱 차트 + 기술적 지표(BB/MA/RSI/MACD) + TradingView 위젯
- **Portfolio** — 다중 포트폴리오 + 보유종목 카드 + 성과/배당/세금 + 상관관계 매트릭스
- **Sentiment** — Fear & Greed Index + 뉴스 워드클라우드 + AI 분석 (선택)
- **Calendar** — 경제 지표 + 어닝스 캘린더
- **Screener** — Finviz 스타일 펀더멘털 필터
- **Compare** — 2~5종목 동시 비교 (Normalized chart, Radar, 펀더멘털)
- **Watchlist** — 관심 종목 추적 + 가격 알림

## Tech Stack

- **Streamlit** — 웹 UI
- **yfinance** — 시장 데이터 (무료, 비공식)
- **Finnhub** — 뉴스 + 어닝스 (무료 60req/min)
- **Anthropic Claude** — AI 감성분석 (선택, 사용자 키 필요)
- **SQLite** — 로컬 영속 저장소
- **Plotly** — 인터랙티브 차트

## 설치

```bash
# Python 3.11+ 권장
cd streamlit_app
pip install -r requirements.txt
```

## API 키 설정

`.streamlit/secrets.toml` 파일을 만들고 다음을 입력:

```toml
FINNHUB_API_KEY = "your_finnhub_key_here"
ANTHROPIC_API_KEY = ""  # 선택 (AI 분석 사용 시)
```

- **Finnhub**: https://finnhub.io 에서 무료 가입 (60 req/min)
- **Anthropic**: https://console.anthropic.com (선택)

## 실행

```bash
streamlit run app.py
```

브라우저가 자동으로 `http://localhost:8501` 을 엽니다.

## 처음 사용 시

1. **Heatmap** 페이지 → "Refresh Data" 클릭 (1분 소요, S&P 500 가격/시총 캐싱)
2. **Screener** 페이지 → "Refresh Data" 클릭 (3-5분 소요, 펀더멘털 캐싱)
3. **Portfolio** 페이지 → 사이드바에서 새 포트폴리오 생성 → 거래 추가
4. **Watchlist** 페이지 → 관심 종목 추가, 알림 설정

캐시는 SQLite (`data/stock_dashboard.db`) 에 저장되어 영속됩니다.

## 디렉토리 구조

```
streamlit_app/
├── app.py                # 메인 진입점
├── database.py           # SQLite 스키마 + 연결
├── requirements.txt
├── .streamlit/
│   ├── config.toml       # 다크 테마
│   └── secrets.toml      # API 키 (gitignore)
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Heatmap.py
│   ├── 3_Stock_Detail.py
│   ├── 4_Portfolio.py
│   ├── 5_Sentiment.py
│   ├── 6_Calendar.py
│   ├── 7_Screener.py
│   ├── 8_Compare.py
│   └── 9_Watchlist.py
├── core/                 # 외부 데이터 provider
│   ├── data_provider.py  # yfinance wrapper
│   ├── news_provider.py  # Finnhub + yfinance
│   └── llm_provider.py   # Claude API
├── services/             # 비즈니스 로직
│   ├── market_service.py
│   ├── portfolio_service.py
│   ├── sentiment_service.py
│   ├── calendar_service.py
│   └── watchlist_service.py
├── components/
│   └── ui.py             # 공통 UI (CSS, 사이드바, 헤더)
└── data/
    └── stock_dashboard.db  # SQLite (gitignore)
```

## 배포 (Streamlit Cloud — 무료)

1. GitHub에 코드 업로드 (`secrets.toml`, `data/` 제외)
2. https://share.streamlit.io 접속 → "New app"
3. 저장소 + 브랜치 + `streamlit_app/app.py` 선택
4. **Advanced settings → Secrets** 에 API 키 입력:
   ```toml
   FINNHUB_API_KEY = "..."
   ANTHROPIC_API_KEY = ""
   ```
5. Deploy 클릭

**제한사항**:
- Streamlit Cloud 무료 티어: 1GB RAM, 슬립 후 콜드 스타트
- SQLite 파일은 컨테이너 재시작 시 초기화될 수 있음 (포트폴리오 데이터 손실 위험)
- 영속 저장이 중요하면 **Turso** (libSQL) 같은 무료 클라우드 SQLite로 전환 고려

## 알려진 한계

- **yfinance rate limit**: `.info` 호출 시 가끔 차단됨 → `fast_info` + `history()` fallback 적용
- **Finnhub free tier**: 일부 데이터 (실적 캘린더)는 premium 전용 → 내장 schedule fallback
- **Streamlit 단일 사용자**: 멀티 유저 인증 없음
- **백그라운드 작업 없음**: 캐시 갱신은 사용자 수동 트리거 (페이지 방문 시 stale 표시)

## 트러블슈팅

### "Too Many Requests" 에러
yfinance가 일시적으로 차단됨. 1-2분 후 페이지 새로고침. 주요 데이터는 `fast_info`로 fallback되어 차트는 계속 표시됨.

### 히트맵에 데이터 없음
Heatmap 페이지에서 "Refresh Data" 버튼 클릭 (첫 1회 필수).

### 뉴스가 안 나옴
1. `secrets.toml`에 `FINNHUB_API_KEY` 설정 확인
2. Finnhub 무료 한도(60 req/min) 초과 가능 — 잠시 후 재시도

### Word Cloud 안 나옴
`pip install wordcloud matplotlib` 실행 (일부 환경에서 누락)

## 라이선스

개인/학습용. yfinance, Finnhub 등 외부 데이터 소스의 ToS 준수 필요.
