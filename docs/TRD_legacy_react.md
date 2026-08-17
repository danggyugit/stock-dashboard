# TRD: Stock Dashboard (기술 설계 문서)

## 1. 기술 스택

### 1.1 선정 결과

| 영역 | 기술 | 버전 | 선정 근거 |
|---|---|---|---|
| **프론트엔드** | React + TypeScript | 19.x / 5.9 | 기존 경험, 컴포넌트 생태계 |
| **빌드** | Vite | 6.x | 빠른 HMR, 기존 경험 |
| **라우팅** | React Router | v7 | 기존 경험, 파일 기반 불필요 |
| **상태관리** | Zustand + TanStack Query | 5.x / 5.x | 서버 상태(TQ) + 클라이언트 상태(Zustand) 분리 |
| **스타일링** | Tailwind CSS + shadcn/ui | 4.x | 빠른 개발, 일관된 디자인 시스템 |
| **차트 (일반)** | Recharts | 2.x | React 친화적, 파이/라인/바 차트 |
| **차트 (트리맵)** | D3.js | 7.x | 트리맵 히트맵 커스터마이징에 최적 |
| **차트 (캔들)** | lightweight-charts | 4.x | TradingView 오픈소스, 금융 차트 특화 |
| **테이블** | TanStack Table | 8.x | 정렬/필터/페이지네이션 내장 |
| **날짜** | date-fns | 4.x | 트리쉐이킹, 배당 캘린더 |
| **백엔드** | FastAPI | 0.115+ | 비동기, 타입 안전, 기존 경험 |
| **DB** | DuckDB | 1.2+ | 로컬 분석용, 서버 불필요 |
| **데이터** | yfinance + finnhub | - | 무료, 포괄적 미국 시장 데이터 |
| **LLM** | Anthropic Claude API | SDK 0.86+ | 감성분석, 시장 요약 |
| **스케줄러** | APScheduler | 3.10+ | 데이터 갱신 자동화 |
| **검증** | Pydantic v2 | 2.x | 요청/응답 스키마 |
| **테스트** | pytest + Vitest | - | 백/프론트 각각 |

### 1.2 스택 선정 이유 (Next.js 대신 Vite+React)
- SSR/SEO 불필요 (단일 사용자 대시보드)
- 기존 QuantScope 패턴 재활용 가능
- FastAPI 백엔드와 명확한 역할 분리
- 빌드 속도 우위

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────┐
│                   Frontend (Vite + React)        │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Market   │ │Portfolio │ │ Sentiment        │ │
│  │ Heatmap  │ │ Tracker  │ │ Dashboard        │ │
│  │ Screener │ │ Trades   │ │ Fear&Greed       │ │
│  │ Compare  │ │ Dividend │ │ AI Report        │ │
│  └────┬─────┘ └────┬─────┘ └───────┬──────────┘ │
│       │             │               │            │
│       └─────────────┼───────────────┘            │
│                     │ Axios (API Client)         │
└─────────────────────┼───────────────────────────-┘
                      │ HTTP (localhost:8001)
┌─────────────────────┼───────────────────────────-┐
│                FastAPI Backend                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ /market  │ │/portfolio│ │ /sentiment       │ │
│  │ routers  │ │ routers  │ │ routers          │ │
│  └────┬─────┘ └────┬─────┘ └───────┬──────────┘ │
│       │             │               │            │
│  ┌────┴─────────────┴───────────────┴──────────┐ │
│  │              Service Layer                   │ │
│  │  MarketService  PortfolioService  Sentiment  │ │
│  └────┬─────────────┬───────────────┬──────────┘ │
│       │             │               │            │
│  ┌────┴─────┐ ┌─────┴────┐ ┌───────┴──────────┐ │
│  │DataProvider│ │  DuckDB  │ │ Claude API      │ │
│  │(yfinance) │ │ (Local)  │ │ (LLM)           │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │ APScheduler (데이터 갱신 스케줄러)             ││
│  └──────────────────────────────────────────────┘│
└──────────────────────────────────────────────────┘
```

### 2.1 데이터 흐름

1. **시장 데이터**: APScheduler → yfinance/finnhub → DuckDB 캐시 → API → Frontend
2. **포트폴리오**: Frontend → API → DuckDB (CRUD) → 현재가 조인 → Frontend
3. **센티먼트**: 수동 트리거 → finnhub News → Claude API (감성분석) → DuckDB → Frontend

---

## 3. 프로젝트 디렉토리 구조

```
stock_dashboard/
├── docs/
│   ├── PRD.md
│   └── TRD.md
├── backend/
│   ├── main.py                  # FastAPI app 진입점
│   ├── config.py                # Pydantic Settings
│   ├── db.py                    # DuckDB 연결 관리
│   ├── scheduler.py             # APScheduler 설정
│   ├── routers/
│   │   ├── market.py            # 히트맵, 스크리너, 종목 상세
│   │   ├── portfolio.py         # 포트폴리오 CRUD, 손익
│   │   └── sentiment.py         # 센티먼트, Fear&Greed, AI 리포트
│   ├── services/
│   │   ├── market_service.py    # 시장 데이터 비즈니스 로직
│   │   ├── portfolio_service.py # 포트폴리오 계산 로직
│   │   └── sentiment_service.py # 감성분석, F&G 계산
│   ├── providers/
│   │   ├── data_provider.py     # yfinance 래퍼
│   │   ├── news_provider.py     # 뉴스 데이터 수집
│   │   └── llm_provider.py      # Claude API 래퍼
│   ├── models/
│   │   ├── market.py            # 시장 데이터 Pydantic 모델
│   │   ├── portfolio.py         # 포트폴리오 Pydantic 모델
│   │   └── sentiment.py         # 센티먼트 Pydantic 모델
│   ├── tests/
│   │   └── ...
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   ├── client.ts        # Axios 인스턴스
│   │   │   ├── market.ts        # 시장 API 호출
│   │   │   ├── portfolio.ts     # 포트폴리오 API 호출
│   │   │   └── sentiment.ts     # 센티먼트 API 호출
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui 컴포넌트
│   │   │   ├── layout/          # Header, Sidebar, Layout
│   │   │   ├── market/          # Heatmap, Screener, StockCard
│   │   │   ├── portfolio/       # Holdings, TradeForm, AllocationChart
│   │   │   └── sentiment/       # FearGreedGauge, NewsList, SentimentChart
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Market.tsx
│   │   │   ├── Screener.tsx
│   │   │   ├── StockDetail.tsx
│   │   │   ├── Compare.tsx
│   │   │   ├── Portfolio.tsx
│   │   │   ├── Trades.tsx
│   │   │   ├── Dividends.tsx
│   │   │   ├── Tax.tsx
│   │   │   ├── Sentiment.tsx
│   │   │   └── AIReport.tsx
│   │   ├── stores/
│   │   │   └── app-store.ts     # Zustand 글로벌 상태
│   │   ├── hooks/
│   │   │   └── ...              # 커스텀 훅
│   │   ├── lib/
│   │   │   └── utils.ts         # 유틸리티 함수
│   │   └── types/
│   │       └── index.ts         # 공유 TypeScript 타입
│   └── components.json          # shadcn/ui 설정
├── data/                        # DuckDB 파일 저장 위치
│   └── stock_dashboard.duckdb
├── .env.example
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## 4. DB 스키마 (DuckDB)

### 4.1 시장 데이터

```sql
-- 종목 마스터
CREATE TABLE stocks (
    ticker       VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    sector       VARCHAR,
    industry     VARCHAR,
    market_cap   BIGINT,
    exchange     VARCHAR,          -- NYSE / NASDAQ
    updated_at   TIMESTAMP DEFAULT current_timestamp
);

-- 일별 OHLCV (캐시)
CREATE TABLE daily_prices (
    ticker       VARCHAR NOT NULL,
    date         DATE NOT NULL,
    open         DOUBLE,
    high         DOUBLE,
    low          DOUBLE,
    close        DOUBLE,
    adj_close    DOUBLE,
    volume       BIGINT,
    PRIMARY KEY (ticker, date)
);

-- 기업 재무 지표 (캐시)
CREATE TABLE fundamentals (
    ticker              VARCHAR PRIMARY KEY,
    pe_ratio            DOUBLE,
    pb_ratio            DOUBLE,
    ps_ratio            DOUBLE,
    eps                 DOUBLE,
    roe                 DOUBLE,
    debt_to_equity      DOUBLE,
    dividend_yield      DOUBLE,
    beta                DOUBLE,
    fifty_two_week_high DOUBLE,
    fifty_two_week_low  DOUBLE,
    avg_volume          BIGINT,
    updated_at          TIMESTAMP DEFAULT current_timestamp
);

-- 배당 데이터
CREATE TABLE dividends (
    ticker       VARCHAR NOT NULL,
    ex_date      DATE NOT NULL,
    payment_date DATE,
    amount       DOUBLE,
    PRIMARY KEY (ticker, ex_date)
);
```

### 4.2 포트폴리오

```sql
-- 포트폴리오
CREATE TABLE portfolios (
    id           INTEGER PRIMARY KEY,
    name         VARCHAR NOT NULL,
    description  VARCHAR,
    created_at   TIMESTAMP DEFAULT current_timestamp
);

-- 거래 내역
CREATE TABLE trades (
    id           INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id),
    ticker       VARCHAR NOT NULL,
    trade_type   VARCHAR NOT NULL,  -- 'BUY' / 'SELL'
    quantity     DOUBLE NOT NULL,
    price        DOUBLE NOT NULL,
    commission   DOUBLE DEFAULT 0,
    trade_date   DATE NOT NULL,
    note         VARCHAR,
    created_at   TIMESTAMP DEFAULT current_timestamp
);

-- 포트폴리오 일별 스냅샷 (성과 추적용)
CREATE TABLE portfolio_snapshots (
    portfolio_id INTEGER NOT NULL,
    date         DATE NOT NULL,
    total_value  DOUBLE,
    total_cost   DOUBLE,
    PRIMARY KEY (portfolio_id, date)
);
```

### 4.3 센티먼트

```sql
-- 뉴스 기사
CREATE TABLE news_articles (
    id           INTEGER PRIMARY KEY,
    ticker       VARCHAR,           -- NULL이면 시장 전체 뉴스
    headline     VARCHAR NOT NULL,
    summary      VARCHAR,
    source       VARCHAR,
    url          VARCHAR,
    published_at TIMESTAMP,
    sentiment    DOUBLE,            -- -1.0 ~ 1.0
    sentiment_label VARCHAR,        -- 'Very Bearish' ~ 'Very Bullish'
    ai_summary   VARCHAR,
    analyzed_at  TIMESTAMP
);

-- Fear & Greed 일별 기록
CREATE TABLE fear_greed_history (
    date              DATE PRIMARY KEY,
    score             DOUBLE,           -- 0 ~ 100
    label             VARCHAR,          -- 'Extreme Fear' ~ 'Extreme Greed'
    vix_score         DOUBLE,
    momentum_score    DOUBLE,
    put_call_score    DOUBLE,
    high_low_score    DOUBLE,
    volume_score      DOUBLE
);

-- AI 일일 리포트
CREATE TABLE daily_reports (
    date         DATE PRIMARY KEY,
    content      TEXT,
    generated_at TIMESTAMP
);

-- DuckDB 시퀀스 (auto-increment 대체)
CREATE SEQUENCE seq_news_id START 1;
CREATE SEQUENCE seq_trade_id START 1;
CREATE SEQUENCE seq_portfolio_id START 1;
```

---

## 5. API 설계

### 5.1 Market API

| Method | Endpoint | 설명 | 주요 파라미터 |
|---|---|---|---|
| GET | `/api/market/heatmap` | 히트맵 데이터 | `period` (1d/1w/1m/3m/ytd/1y) |
| GET | `/api/market/screener` | 스크리너 결과 | `sector`, `min_cap`, `max_pe`, `sort`, `page` |
| GET | `/api/market/indices` | 주요 지수 현황 | - |
| GET | `/api/market/stock/{ticker}` | 종목 상세 | - |
| GET | `/api/market/stock/{ticker}/chart` | 종목 차트 데이터 | `period`, `interval` |
| GET | `/api/market/stock/{ticker}/financials` | 재무 지표 | - |
| GET | `/api/market/compare` | 종목 비교 | `tickers` (쉼표 구분) |
| GET | `/api/market/search` | 종목 검색 (자동완성) | `q` |
| POST | `/api/market/refresh` | 데이터 수동 갱신 | - |

### 5.2 Portfolio API

| Method | Endpoint | 설명 | 주요 파라미터 |
|---|---|---|---|
| GET | `/api/portfolio` | 포트폴리오 목록 | - |
| POST | `/api/portfolio` | 포트폴리오 생성 | `name`, `description` |
| GET | `/api/portfolio/{id}` | 포트폴리오 상세 (보유현황+손익) | - |
| DELETE | `/api/portfolio/{id}` | 포트폴리오 삭제 | - |
| GET | `/api/portfolio/{id}/trades` | 거래 내역 | `page` |
| POST | `/api/portfolio/{id}/trades` | 거래 추가 | Trade 객체 |
| PUT | `/api/portfolio/{id}/trades/{tid}` | 거래 수정 | Trade 객체 |
| DELETE | `/api/portfolio/{id}/trades/{tid}` | 거래 삭제 | - |
| POST | `/api/portfolio/{id}/trades/import` | CSV 가져오기 | CSV 파일 |
| GET | `/api/portfolio/{id}/allocation` | 자산배분 데이터 | - |
| GET | `/api/portfolio/{id}/performance` | 수익률 추이 | `period` |
| GET | `/api/portfolio/{id}/dividends` | 배당 일정 | `year` |
| GET | `/api/portfolio/{id}/tax` | 세금 계산 | `year` |

### 5.3 Sentiment API

| Method | Endpoint | 설명 | 주요 파라미터 |
|---|---|---|---|
| GET | `/api/sentiment/fear-greed` | Fear & Greed 현재값 | - |
| GET | `/api/sentiment/fear-greed/history` | F&G 추이 | `days` (30/90) |
| GET | `/api/sentiment/news` | 뉴스 목록 (감성 포함) | `ticker`, `page` |
| POST | `/api/sentiment/analyze` | 뉴스 감성분석 실행 (수동) | `ticker` (선택) |
| GET | `/api/sentiment/trend/{ticker}` | 종목 센티먼트 트렌드 | `days` |
| GET | `/api/sentiment/report` | 오늘의 AI 리포트 | - |
| POST | `/api/sentiment/report/generate` | AI 리포트 생성 (수동) | - |

---

## 6. 프론트엔드 핵심 컴포넌트

### 6.1 차트 라이브러리 분담

| 차트 유형 | 라이브러리 | 사용처 |
|---|---|---|
| 트리맵 히트맵 | D3.js | Market Heatmap |
| 캔들스틱 + 볼륨 | lightweight-charts | Stock Detail |
| 라인/바/에어리어 | Recharts | 수익률 추이, 센티먼트 트렌드, F&G 히스토리 |
| 파이/도넛 | Recharts | 자산배분, 섹터 비중 |
| 게이지 | 커스텀 SVG | Fear & Greed 게이지 |
| 캘린더 | 커스텀 그리드 | 배당 캘린더 |

### 6.2 주요 공유 컴포넌트

| 컴포넌트 | 설명 |
|---|---|
| `TickerSearch` | 종목 검색 자동완성 (debounce) |
| `PriceChange` | 가격 변동 표시 (색상 + 화살표 + %) |
| `DataTable` | TanStack Table 래퍼 (정렬/필터/페이지네이션) |
| `ChartContainer` | 차트 공통 래퍼 (로딩/에러/빈 상태) |
| `MetricCard` | 지표 카드 (라벨 + 값 + 변화량) |
| `SentimentBadge` | 감성 태그 (Bullish/Bearish/Neutral) |

---

## 7. 구현 단계 (Phase)

### Phase 1: 프로젝트 셋업 + 시장 데이터 기반
1. 프로젝트 초기화 (Vite, FastAPI, DuckDB)
2. 종목 마스터 데이터 수집 파이프라인
3. 일별 가격 데이터 수집 + 캐싱
4. 기본 API (indices, search, stock detail)
5. 기본 레이아웃 + 라우팅

### Phase 2: 마켓 히트맵 + 스크리너
1. D3 트리맵 히트맵 구현
2. 스크리너 필터 + 테이블
3. 종목 상세 페이지 (캔들 차트, 재무)
4. 종목 비교

### Phase 3: 포트폴리오 트래커
1. 포트폴리오/거래 CRUD API
2. 거래 입력 폼 + 내역 관리
3. 보유현황 + 손익 계산
4. 자산배분 차트
5. 배당 캘린더 + 세금 계산

### Phase 4: 센티먼트 대시보드
1. 뉴스 수집 파이프라인
2. Claude API 감성분석 연동
3. Fear & Greed 지표 계산 + 게이지
4. 종목별 센티먼트 트렌드
5. AI 일일 리포트

### Phase 5: 통합 + 폴리시
1. 대시보드 홈 (시장 요약 + 포트폴리오 요약 + 센티먼트 요약)
2. APScheduler 자동 갱신
3. 에러 처리, 로딩 상태
4. 반응형 조정
5. README + 스크린샷

---

## 8. 외부 API 제한사항 및 대응

| API | 무료 제한 | 대응 전략 |
|---|---|---|
| yfinance | 비공식 API, rate limit 있음 | DuckDB 캐싱, 배치 요청, 15분 간격 |
| Finnhub | 60 calls/min (무료) | 뉴스만 사용, 캐싱 |
| Claude API | 유료 (토큰 기반) | 수동 트리거만, 배치 분석 |
| Alpha Vantage | 25 calls/day (무료) | 보조 소스로만 사용 |

---

## 9. 환경 변수

```env
# Backend
DUCKDB_PATH=./data/stock_dashboard.duckdb
ANTHROPIC_API_KEY=sk-ant-...
FINNHUB_API_KEY=...

# 선택적
ALPHA_VANTAGE_API_KEY=...

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8001
```
