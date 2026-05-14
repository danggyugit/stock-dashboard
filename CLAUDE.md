# Stock Dashboard — 프로젝트 규칙

## 프로젝트 개요
미국 주식 시장 통합 대시보드 (마켓 히트맵 + 포트폴리오 트래커 + 센티먼트 분석)

## 기술 스택
- Frontend: React 19 + TypeScript + Vite 6 + Tailwind CSS + shadcn/ui
- Backend: FastAPI + Python 3.11+
- DB: DuckDB (로컬)
- 차트: D3.js (트리맵), lightweight-charts (캔들), Recharts (일반)
- 상태: Zustand (클라이언트) + TanStack Query (서버)

## 문서
- PRD: `docs/PRD.md`
- TRD: `docs/TRD.md`

## 디렉토리 규칙
- `backend/` — FastAPI 백엔드 (Python)
- `frontend/` — React 프론트엔드 (TypeScript)
- `data/` — DuckDB 파일 (git 무시)
- `docs/` — PRD, TRD 등 문서

## Python 코딩 규칙
- 모든 함수에 type hint 필수
- 파일 경로는 `pathlib.Path` 사용
- `print()` 대신 `logging.getLogger(__name__)` 사용
- public 함수/클래스에 Google-style docstring
- 설정값은 `backend/config.py` (Pydantic BaseSettings) 경유
- 파일 I/O 시 `encoding="utf-8"` 명시
- pandas 벡터 연산 우선 (for 루프 지양)

## TypeScript 코딩 규칙
- 컴포넌트는 함수형 + 화살표 함수로 작성
- API 호출은 반드시 `api/` 디렉토리의 함수 경유 (컴포넌트에서 직접 axios 호출 금지)
- 서버 상태는 TanStack Query, 클라이언트 상태는 Zustand
- 타입은 `types/index.ts`에 중앙 관리
- shadcn/ui 컴포넌트 우선 사용

## 네이밍 규칙
- Python: 파일 `snake_case.py`, 클래스 `PascalCase`, 함수/변수 `snake_case`, 상수 `UPPER_SNAKE_CASE`
- TypeScript: 파일 `PascalCase.tsx` (컴포넌트), `camelCase.ts` (유틸), 컴포넌트 `PascalCase`, 변수/함수 `camelCase`
- API 엔드포인트: `kebab-case` 대신 `snake_case` (FastAPI 컨벤션)

## 데이터 규칙
- yfinance 호출은 반드시 `providers/data_provider.py` 경유
- DuckDB 쓰기는 서비스 레이어에서만 (라우터에서 직접 DB 접근 금지)
- 외부 API 응답은 DuckDB에 캐싱 후 캐시에서 읽기
- Claude API 호출은 사용자 수동 트리거 시에만 (자동 호출 금지, 비용 관리)

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
- 기존 로고 목록: PLTR(자체 path), AMD(#E8211A 레드), AMZN, WDC, SNDK, GOOGL, STX

### 디자인 기준
- CSS 변수: `--text-dim:#CBD5E1`, `--border:rgba(203,213,225,0.16)`, `--bg-card:#0F172A`, `--bg-card-alt:#131F38`
- badge font-size: 14px / counter: JetBrains Mono, `01 / 08` 형식
- card-title: 30px (Card 7은 24px으로 축소해 차트 공간 확보)
- mbox .ml/.me/.ms: 14px / card-label: `position:absolute; top:-28px; left:0`
- 종목 고유 accent 색상은 유지하되, 구조·폰트·간격은 기존 카드와 동일하게 맞출 것

## 테스트
- Backend: `pytest` — `backend/tests/`
- Frontend: `vitest` — `frontend/src/**/*.test.ts(x)`

## Git 규칙
- `.env`, `data/*.duckdb` 는 `.gitignore`에 포함
- 커밋 메시지는 영문, conventional commits 스타일
