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

## 테스트
- Backend: `pytest` — `backend/tests/`
- Frontend: `vitest` — `frontend/src/**/*.test.ts(x)`

## Git 규칙
- `.env`, `data/*.duckdb` 는 `.gitignore`에 포함
- 커밋 메시지는 영문, conventional commits 스타일
