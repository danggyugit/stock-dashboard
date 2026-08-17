# PRD — AI Quant Lab (Stock Dashboard)

> 현행 버전 기준 (Streamlit). 구버전(React+FastAPI) 스펙은 `PRD_legacy_react.md` 참고.

## 1. 제품 개요

**AI Quant Lab** (aiquantlab.streamlit.app)은 미국 주식 투자자를 위한 통합 리서치·퀀트 분석 플랫폼이다.
시장 현황 파악 → 종목 탐색/스크리닝 → 퀀트 백테스트 → 포트폴리오 관리까지 하나의 앱에서 제공한다.

- **대상 사용자**: 개인 투자자 (소유자 + 승인제 소수 사용자)
- **접근 제어**: Google OIDC 로그인(`st.login`) + 소유자 승인 기반
- **비용 원칙**: 무료 데이터 소스(yfinance, SEC EDGAR, FRED, Finnhub 무료 티어) 중심,
  LLM 호출은 사용자 수동 트리거만 (자동 호출 금지)

## 2. 제공 기능 (페이지별)

### Market Overview
| 페이지 | 기능 |
|---|---|
| Dashboard | 주요 지수·시장 요약·보유 포트폴리오 스냅샷·종목 뉴스 |
| Heatmap | S&P 1500 섹터 트리맵 (시총·등락률) |
| Macro | 금리·달러·원자재 등 매크로 지표 |
| Sentiment | Fear & Greed, 뉴스 센티먼트 |
| Calendar | 실적·경제지표 캘린더 |

### Stock Research
| 페이지 | 기능 |
|---|---|
| Stock Detail | 개별 종목 차트·재무·밸류에이션·내부자 거래 |
| Screener | 펀더멘털 필터 스크리너 (PER·PBR·ROE·배당 등) |
| RS Screener | IBD식 상대강도(RS) 랭킹 스크리너 |
| Breakout Screener | 월봉 로그가격 회귀 추세채널 상단 돌파 스캔 (조회기간·채널폭·돌파범위 조절) |
| Compare | 다종목 성과 비교 |
| Watchlist | 관심종목 관리 |

### Analysis Tools
| 페이지 | 기능 |
|---|---|
| AI Quant Lab | ML 앙상블(RF+XGB+LGBM) 종목 랭킹 + walk-forward 백테스트 + HMM 레짐/현금비중. 프리셋 결과 로드 지원 |
| Factor Lab | 룰 기반 팩터 백테스트 23개 전략 (모멘텀·가치·성장·배당·주주환원·듀얼모멘텀 등). S&P500 멤버십 복원(생존편향 보정)·PIT 재무·상폐 손실 반영 |
| Stock Lab | 외부 12-에이전트 심층 리포트 서비스(aiquantlab-stocklab.pages.dev) 소개/링크 |
| SEC Intelligence | 13F 고래 포트폴리오 추적(20개 매니저)·내부자 대량매수 스캔·공시 AI 요약 |

### Portfolio / 기타
| 페이지 | 기능 |
|---|---|
| Portfolio | 매매 기록·보유 현황·손익 |
| Guide | 사용 가이드 |
| Admin (owner 전용) | 사용자 승인 관리 |

## 3. 자동화 (앱 외부)

| 자동화 | 주기 | 내용 |
|---|---|---|
| 프리셋 백테스트 | 매일 11:00 KST | 5개 프리셋 백테스트 → 캐시 JSON → git push → Telegram TOP10 알림 |
| 가격+펀더멘털 캐시 | 매일 13:00 KST | S&P1500 가격/시총/재무 갱신 → git push |
| SEC Intelligence | 매일 11:30 KST | 내부자 매수 스캔 + (분기) 13F 수집 → Telegram 알림 |
| 포트폴리오 과열 점검 | 매일 07:00 KST | 보유종목 이격 백분위 기반 리밸런싱 리스크 고지 → Telegram |
| 월간 리밸런싱 알림 | 매월 1일 | 프리셋 추천 종목 Telegram 발송 |
| Valuation 캐시 | 매일 (GitHub Actions) | 종목별 밸류에이션 JSON 갱신 |

## 4. 비기능 요구사항

- **데이터 정직성**: 백테스트는 lookahead 금지(PIT·embargo), 생존편향 보정, 근거 없는 수치 날조 금지
- **가용성**: Streamlit Cloud 무료 티어 — cold start 허용, 캐시는 GitHub raw로 로드
- **보안**: secrets는 `secrets.toml`/환경변수만, 저장소에 커밋 금지
