# Stock Dashboard — 에이전트팀 구성

## 팀 개요

총 5개 에이전트가 Phase별로 병렬/순차 실행하여 대시보드를 구축한다.

```
┌─────────────────────────────────────────────────────┐
│                    Orchestrator (메인)                │
│         전체 흐름 조율, 품질 검증, 사용자 소통          │
├──────────┬──────────┬──────────┬────────────────────-┤
│ Backend  │ Frontend │  Data    │  Integration        │
│  Agent   │  Agent   │  Agent   │  Agent              │
│          │          │          │                     │
│ FastAPI  │ React    │ yfinance │ E2E 연결            │
│ Services │ Pages    │ DuckDB   │ 통합 테스트          │
│ Models   │ Charts   │ 파이프라인 │ 에러 처리           │
└──────────┴──────────┴──────────┴─────────────────────┘
```

---

## 에이전트 정의

### 1. Backend Agent
- **역할**: FastAPI 백엔드 전체 구현
- **담당 파일**: `backend/` 하위 전체
- **작업 범위**:
  - `main.py` — FastAPI 앱 설정, CORS, 라우터 등록
  - `config.py` — Pydantic Settings (환경변수)
  - `db.py` — DuckDB 연결 관리, 테이블 초기화
  - `routers/` — API 엔드포인트 (market, portfolio, sentiment)
  - `services/` — 비즈니스 로직
  - `providers/` — 외부 API 래퍼 (yfinance, finnhub, Claude)
  - `models/` — Pydantic 요청/응답 모델
- **규칙**:
  - 라우터 → 서비스 → 프로바이더/DB 순서 엄수 (라우터에서 직접 DB 접근 금지)
  - 모든 함수에 type hint, Google-style docstring
  - 외부 API 호출 결과는 반드시 DuckDB에 캐싱
  - Claude API는 수동 트리거 엔드포인트에서만 호출
- **의존성**: Data Agent가 DB 스키마를 먼저 생성해야 함

### 2. Frontend Agent
- **역할**: React 프론트엔드 전체 구현
- **담당 파일**: `frontend/` 하위 전체
- **작업 범위**:
  - 프로젝트 초기화 (Vite, Tailwind, shadcn/ui)
  - `api/` — Axios 클라이언트, API 호출 함수
  - `pages/` — 11개 페이지 컴포넌트
  - `components/` — UI 컴포넌트 (layout, market, portfolio, sentiment)
  - `stores/` — Zustand 스토어
  - `types/` — TypeScript 타입 정의
  - 라우팅 설정 (React Router v7)
- **규칙**:
  - shadcn/ui 컴포넌트 우선 사용
  - API 호출은 `api/` 함수 경유만 허용
  - 서버 상태 = TanStack Query, 클라이언트 상태 = Zustand
  - D3.js는 트리맵 히트맵에만 사용, 나머지는 Recharts
  - 캔들스틱 차트는 lightweight-charts
- **의존성**: Backend Agent의 API가 먼저 정의되어야 타입/호출 함수 작성 가능

### 3. Data Agent
- **역할**: 데이터 파이프라인 및 DB 설정
- **담당 파일**: `backend/db.py`, `backend/providers/`, `backend/scheduler.py`
- **작업 범위**:
  - DuckDB 테이블 생성 스크립트 (TRD 스키마 기반)
  - yfinance 데이터 수집 로직 (`data_provider.py`)
  - Finnhub 뉴스 수집 (`news_provider.py`)
  - Claude API 감성분석 래퍼 (`llm_provider.py`)
  - APScheduler 갱신 스케줄 설정
  - 종목 마스터 데이터 초기 로드 (S&P 500 + 주요 종목)
- **규칙**:
  - yfinance 배치 요청 (단건 호출 최소화)
  - Rate limit 준수 (yfinance: 요청 간 sleep, Finnhub: 60/min)
  - 캐시 만료 로직 포함 (시장 데이터: 15분, 재무: 1일)
  - 에러 시 fallback (빈 DataFrame 반환, 로깅)
- **의존성**: 없음 (가장 먼저 실행 가능)

### 4. Integration Agent
- **역할**: 프론트/백엔드 연결, 통합 검증
- **담당 파일**: 전체 (읽기 위주, 수정은 연결 부분만)
- **작업 범위**:
  - Vite 프록시 설정 (`vite.config.ts` → `localhost:8001`)
  - API 응답 ↔ 프론트엔드 타입 일치 검증
  - CORS 설정 확인
  - 대시보드 홈 페이지 (3개 Feature 요약 통합)
  - `.env.example`, `.gitignore`, `README.md` 생성
  - 에러/로딩 상태 처리 통일
- **규칙**:
  - Backend/Frontend Agent가 완료한 후 실행
  - 타입 불일치 발견 시 해당 에이전트 파일 수정
  - E2E 동작 확인 (서버 기동 → 페이지 로드 → API 호출 → 데이터 표시)
- **의존성**: Backend Agent + Frontend Agent 완료 후

---

## 실행 워크플로우

### Phase 1: 프로젝트 셋업 + 데이터 기반
```
[Data Agent]     → DB 스키마 생성, 종목 마스터 로드, Provider 구현
[Backend Agent]  → 프로젝트 초기화, config, main.py, 기본 라우터
[Frontend Agent] → 프로젝트 초기화, Vite+Tailwind+shadcn, 레이아웃, 라우팅
                   ↑ 3개 병렬 실행 가능
```

### Phase 2: Feature A (마켓 히트맵 + 스크리너)
```
[Backend Agent]  → market 라우터 + 서비스 구현
[Frontend Agent] → Heatmap(D3), Screener, StockDetail, Compare 페이지
                   ↑ 2개 병렬 (API 스펙 공유 후)
[Integration Agent] → 연결 테스트
```

### Phase 3: Feature B (포트폴리오 트래커)
```
[Backend Agent]  → portfolio 라우터 + 서비스 구현
[Frontend Agent] → Portfolio, Trades, Dividends, Tax 페이지
                   ↑ 2개 병렬
[Integration Agent] → 연결 테스트
```

### Phase 4: Feature C (센티먼트 대시보드)
```
[Data Agent]     → 뉴스 수집 + LLM 감성분석 파이프라인
[Backend Agent]  → sentiment 라우터 + 서비스 구현
[Frontend Agent] → Sentiment, AIReport 페이지, FearGreedGauge
                   ↑ 3개 병렬
[Integration Agent] → 연결 테스트
```

### Phase 5: 통합 + 폴리시
```
[Integration Agent] → 대시보드 홈, 전체 E2E 검증, README
[Frontend Agent]    → 반응형, 에러 상태, 최종 UI 정리
                      ↑ 2개 병렬
```

---

## Agent 실행 프롬프트 템플릿

### Data Agent 호출 예시
```
subagent_type: "general-purpose"
prompt: |
  Stock Dashboard 프로젝트의 Data Agent 역할을 수행하라.
  
  [작업]: DuckDB 테이블 생성 + yfinance 데이터 수집 Provider 구현
  [참조]: docs/TRD.md (DB 스키마), CLAUDE.md (코딩 규칙), AGENTS.md (역할 범위)
  [파일]: backend/db.py, backend/providers/data_provider.py
  [규칙]: CLAUDE.md의 Python 코딩 규칙 + 데이터 규칙 준수
```

### Backend Agent 호출 예시
```
subagent_type: "general-purpose"
prompt: |
  Stock Dashboard 프로젝트의 Backend Agent 역할을 수행하라.
  
  [작업]: Market API 라우터 + 서비스 구현
  [참조]: docs/TRD.md (API 설계), docs/PRD.md (기능 요구사항), CLAUDE.md, AGENTS.md
  [파일]: backend/routers/market.py, backend/services/market_service.py, backend/models/market.py
  [규칙]: 라우터→서비스→프로바이더 레이어 분리 엄수
```

### Frontend Agent 호출 예시
```
subagent_type: "general-purpose"
prompt: |
  Stock Dashboard 프로젝트의 Frontend Agent 역할을 수행하라.
  
  [작업]: 마켓 히트맵 페이지 + D3 트리맵 컴포넌트 구현
  [참조]: docs/TRD.md, docs/PRD.md (A-1 히트맵 수용기준), CLAUDE.md, AGENTS.md
  [파일]: frontend/src/pages/Market.tsx, frontend/src/components/market/Heatmap.tsx
  [API]: GET /api/market/heatmap → { sectors: [{ name, stocks: [{ ticker, name, market_cap, change_pct }] }] }
  [규칙]: shadcn/ui 우선, TanStack Query로 데이터 페칭
```
