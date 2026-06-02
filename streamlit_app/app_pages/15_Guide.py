"""사용자 가이드 — 메뉴별 기능 및 사용법."""

from __future__ import annotations

import streamlit as st
from components.ui import inject_css

inject_css()

# ── 스타일 ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .guide-hero {
        background: radial-gradient(ellipse at top left,
                    rgba(59,130,246,0.15) 0%, rgba(15,23,42,0) 55%),
                    radial-gradient(ellipse at bottom right,
                    rgba(139,92,246,0.12) 0%, rgba(15,23,42,0) 55%);
        border: 1px solid rgba(59,130,246,0.20);
        border-radius: 16px; padding: 28px 32px; margin-bottom: 24px;
    }
    .guide-hero h1 {
        font-size: 2rem; font-weight: 800; margin: 0 0 6px 0;
        background: linear-gradient(135deg, #60A5FA 0%, #A78BFA 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .guide-hero .sub { font-size: 0.95rem; color: #94A3B8; margin: 0; }

    .menu-tag {
        display: inline-block; font-size: 0.7rem; font-weight: 700;
        padding: 2px 9px; border-radius: 999px; margin-right: 6px;
        vertical-align: middle;
    }
    .tag-overview { background:rgba(34,197,94,0.15); color:#4ADE80; border:1px solid rgba(34,197,94,0.3); }
    .tag-analysis { background:rgba(59,130,246,0.15); color:#60A5FA; border:1px solid rgba(59,130,246,0.3); }
    .tag-invest  { background:rgba(234,179,8,0.15);  color:#FCD34D; border:1px solid rgba(234,179,8,0.3); }
    .tag-research{ background:rgba(139,92,246,0.15); color:#C4B5FD; border:1px solid rgba(139,92,246,0.3); }
    .tag-login   { background:rgba(239,68,68,0.12);  color:#FCA5A5; border:1px solid rgba(239,68,68,0.25); }

    .feature-list li { margin: 4px 0; color: #CBD5E1; line-height: 1.6; }
    .step-block {
        background: rgba(30,41,59,0.5);
        border-left: 3px solid #60A5FA;
        border-radius: 4px 10px 10px 4px;
        padding: 10px 14px; margin: 8px 0;
        font-size: 0.88rem; color: #CBD5E1; line-height: 1.6;
    }
    .tip-block {
        background: rgba(234,179,8,0.08);
        border: 1px solid rgba(234,179,8,0.25);
        border-radius: 8px; padding: 10px 14px; margin-top: 10px;
        font-size: 0.85rem; color: #FCD34D;
    }
</style>
""", unsafe_allow_html=True)

# ── 히어로 ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="guide-hero">
  <h1>📖 사용자 가이드</h1>
  <p class="sub">Stock Dashboard 메뉴별 기능 및 사용법 안내 — 탭을 선택해 원하는 섹션을 확인하세요.</p>
</div>
""", unsafe_allow_html=True)

# ── 탭 구성 ────────────────────────────────────────────────────────────────
tab_ov, tab_an, tab_inv, tab_res = st.tabs([
    "🌐 Market Overview",
    "🔍 Analysis",
    "💼 My Investing",
    "📈 Research",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1: Market Overview
# ════════════════════════════════════════════════════════════════════════════
with tab_ov:
    st.markdown('<span class="menu-tag tag-overview">Market Overview</span> 시장 전반 현황을 빠르게 파악하는 페이지 모음입니다.', unsafe_allow_html=True)
    st.markdown("")

    with st.expander("🏠 Home — 대시보드 메인 화면", expanded=True):
        st.markdown("""
**한 줄 요약**: 앱 진입 시 가장 먼저 보이는 요약 페이지로, 핵심 시장 지표와 빠른 이동 링크를 제공합니다.

**주요 기능**
- 주요 지수(S&P 500 / Nasdaq / Dow) 현재 시세 및 등락률
- Fear & Greed Index 현재 수치 (공포/탐욕 시장 심리)
- 포트폴리오 요약 카드 (로그인 시)
- 어닝 캘린더 주요 일정 미리보기
- 각 메뉴로 바로 이동하는 퀵 액션 카드
""")
        st.markdown('<div class="tip-block">💡 매일 앱을 열면 Home에서 시장 분위기를 30초 안에 파악할 수 있습니다.</div>', unsafe_allow_html=True)

    with st.expander("📊 Dashboard — 시장 종합 현황"):
        st.markdown("""
**한 줄 요약**: 지수 차트, 섹터 히트맵, 포트폴리오 요약, 뉴스 피드를 한 화면에서 확인합니다.

**주요 기능**
- 주요 4대 지수(S&P 500 / Nasdaq / Dow / VIX) 메트릭 + 당일 인트라데이 미니 차트
- 기간 선택: 1D / 5D / 1M 차트 전환
- 섹터별 자금 흐름 히트맵 (11개 GICS 섹터)
- 포트폴리오 보유 종목 현황 (로그인 필요)
- 실시간 시장 뉴스 피드

**사용법**
""")
        st.markdown('<div class="step-block">① 상단 지수 카드에서 오늘 주요 지수 흐름 확인<br>② 섹터 히트맵으로 자금이 몰리는 섹터 파악<br>③ 뉴스 피드에서 시장 이슈 스캔</div>', unsafe_allow_html=True)

    with st.expander("🗺️ Heatmap — S&P 500 트리맵"):
        st.markdown("""
**한 줄 요약**: S&P 500 전 종목을 섹터별 트리맵으로 시각화해 종목별 등락률을 한눈에 비교합니다.

**주요 기능**
- 섹터별 색상 코딩 트리맵 (초록=상승, 빨강=하락, 크기=시가총액)
- 기간 선택: 1D / 1W / 1M / 3M / YTD / 1Y
- 종목 로고 그리드 뷰 (트리맵 대안)
- 캐시 상태 표시 및 수동 새로고침

**사용법**
""")
        st.markdown('<div class="step-block">① 기간 버튼으로 원하는 기간 선택<br>② 트리맵에서 큰 블록(=대형주)의 색상으로 시장 흐름 파악<br>③ 캐시가 오래됐다면 새로고침 버튼 클릭 (약 30초 소요)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 1D 기준 트리맵에서 대부분 빨간색 → 전반적 하락장 신호. 특정 섹터만 초록 → 순환매 포착.</div>', unsafe_allow_html=True)

    with st.expander("📅 Calendar — 경제 지표 & 어닝 일정"):
        st.markdown("""
**한 줄 요약**: 예정된 경제 지표 발표(CPI, 금리 결정 등)와 기업 실적 발표 일정을 달력으로 확인합니다.

**주요 기능**
- 경제 이벤트 탭: Fed 금리, CPI, PMI, 고용지표 등 중요도별 필터
- 어닝 캘린더 탭: 기업 실적 발표 예정일 및 심볼
- 날짜 범위 선택 (연/월)
- 중요도 배지 (High / Medium / Low)

**사용법**
""")
        st.markdown('<div class="step-block">① 경제 이벤트 탭 → 이번 주 High 중요도 이벤트 확인<br>② 어닝 탭 → 보유 종목의 실적 발표일 체크<br>③ 날짜를 변경해 다음 달 일정도 미리 확인 가능</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 CPI, FOMC 발표일 전후는 변동성이 커집니다. 미리 캘린더에서 확인하고 포지션을 점검하세요.</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: Analysis
# ════════════════════════════════════════════════════════════════════════════
with tab_an:
    st.markdown('<span class="menu-tag tag-analysis">Analysis</span> 개별 종목 분석, 스크리닝, 비교, 심리 지표를 다루는 페이지 모음입니다.', unsafe_allow_html=True)
    st.markdown("")

    with st.expander("📈 Stock Detail — 개별 종목 상세 분석", expanded=True):
        st.markdown("""
**한 줄 요약**: 종목 검색 후 캔들 차트, 기술적 지표, 밸류에이션, 애널리스트 목표가, AI 분석까지 한 페이지에서 확인합니다.

**주요 기능**
- 인터랙티브 캔들스틱 차트 (기간 선택 가능)
- 기술 지표: RSI / MACD / 볼린저 밴드 오버레이
- 밸류에이션: P/E, P/B, 배당수익률, 시가총액 등
- 애널리스트 컨센서스 목표가 및 Bull/Bear 시나리오 밴드
- AI 시나리오 분석 (Gemini Flash 연동, 선택적 실행)
- 내부자 거래 및 기관 보유 현황
- 최근 뉴스 센티먼트

**사용법**
""")
        st.markdown('<div class="step-block">① 검색창에 티커 입력 (예: AAPL, NVDA)<br>② 캔들 차트에서 기간 선택 후 추세 확인<br>③ 기술 지표 토글로 RSI/MACD 추가<br>④ 하단 밸류에이션 카드에서 현재 가격 매력도 파악<br>⑤ AI 분석 버튼 → Gemini가 Bull/Bear 시나리오 요약</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 AI 분석은 API를 호출하므로 필요할 때만 실행하세요. 결과는 세션 내에서 캐시됩니다.</div>', unsafe_allow_html=True)

    with st.expander("🔎 Screener — 펀더멘털 종목 스크리너"):
        st.markdown("""
**한 줄 요약**: P/E, 배당수익률, 시가총액, 섹터 등 펀더멘털 기준으로 S&P 500 종목을 필터링합니다.

**주요 기능**
- 필터: 섹터 / 시가총액 / P/E 범위 / 배당수익률 / RS Rating
- 펀더멘털 캐시 기반 (약 500종목, 수동 새로고침 가능)
- 정렬 가능한 결과 테이블 (종목 로고 포함)
- 캐시 상태 및 마지막 업데이트 시각 표시

**사용법**
""")
        st.markdown('<div class="step-block">① 섹터, 시가총액 등 원하는 조건 설정<br>② 결과 테이블에서 종목 확인<br>③ 데이터가 오래됐으면 새로고침 버튼 클릭 (약 5분 소요)</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 처음 사용 시 펀더멘털 캐시가 비어 있을 수 있습니다. 새로고침 후 사용하세요.</div>', unsafe_allow_html=True)

    with st.expander("📊 RS Screener — 상대 강도 스크리너"):
        st.markdown("""
**한 줄 요약**: IBD-style RS Rating(1~99)으로 현재 시장에서 모멘텀이 가장 강한 종목을 찾습니다.

**RS Rating이란?**
전체 종목 대비 최근 12개월 주가 수익률의 백분위 순위입니다.
- **RS 90+** = 전체 상위 10% 초강세
- **RS 80+** = IBD 기준 매수 고려 구간
- 산식: 최근 3개월 ×40% + 3~6개월 ×20% + 6~9개월 ×20% + 9~12개월 ×20%

**주요 기능**
- 섹터 / 시총 구간 / 최소 RS Rating 3중 필터
- RS Rating 분포 히스토그램
- RS 90+ 초강세 종목 칩 하이라이트 🚀
- 1개월 / 3개월 / 12개월 수익률 테이블
- 6시간 캐시 (재실행 시 즉시 응답)

**사용법**
""")
        st.markdown('<div class="step-block">① 섹터·시총 필터 설정 (Large Cap 기본)<br>② 실행 버튼 클릭 (첫 실행은 30~60초 소요)<br>③ 최소 RS 슬라이더로 기준 조정<br>④ RS 90+ 칩에서 초강세 종목 빠르게 파악</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 섹터 필터 없이 전체(503종목) 실행 시 1~2분 소요됩니다. Large Cap으로 좁히면 훨씬 빠릅니다.</div>', unsafe_allow_html=True)

    with st.expander("🔀 Compare — 종목 비교"):
        st.markdown("""
**한 줄 요약**: 최대 5개 종목의 주가 추이와 핵심 지표를 나란히 비교합니다.

**주요 기능**
- 종목 2~5개 동시 비교 (기본: AAPL / MSFT / NVDA / GOOGL)
- 정규화 오버레이 차트 (시작일=100 기준 상대 수익률)
- 기간 선택: 1M / 3M / 6M / 1Y / 2Y / 5Y
- 종목별 주요 지표 카드 (현재가, 등락률, 시가총액, P/E 등)

**사용법**
""")
        st.markdown('<div class="step-block">① 텍스트 입력란에 티커를 콤마로 구분해 입력 (예: NVDA, AMD, INTC)<br>② 기간 선택 후 차트에서 상대 성과 비교<br>③ 아래 지표 카드로 밸류에이션 비교</div>', unsafe_allow_html=True)

    with st.expander("🧠 Sentiment — 시장 심리 분석"):
        st.markdown("""
**한 줄 요약**: Fear & Greed Index, VIX, 섹터 수익률, 뉴스 감성 분석 등으로 시장 전체 심리를 진단합니다.

**주요 기능**
- Fear & Greed Index 현재 수치 + 히스토리 차트
- VIX(공포지수) 추이
- 11개 섹터 수익률 비교
- 시장 폭 지표 (상승/하락 종목 비율)
- 뉴스 헤드라인 워드클라우드 (NLP)
- AI 감성 태깅 뉴스 피드
- 센티먼트 리포트 다운로드

**사용법**
""")
        st.markdown('<div class="step-block">① Fear & Greed 수치 확인: 0~25 극단적 공포, 75~100 극단적 탐욕<br>② VIX 30 이상 = 높은 변동성 주의<br>③ 워드클라우드에서 시장의 관심 키워드 파악</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 Fear & Greed가 극단적 공포(20 이하)일 때 역발상 매수 기회로 보는 투자자가 많습니다.</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: My Investing
# ════════════════════════════════════════════════════════════════════════════
with tab_inv:
    st.markdown('<span class="menu-tag tag-invest">My Investing</span> 로그인 후 사용하는 개인 투자 관리 및 퀀트 분석 도구 모음입니다.', unsafe_allow_html=True)
    st.markdown('<span class="menu-tag tag-login">로그인 필요</span> Portfolio · Watchlist · AI Quant Lab · Factor Lab은 Google 로그인 후 이용 가능합니다.', unsafe_allow_html=True)
    st.markdown("")

    with st.expander("💼 Portfolio — 포트폴리오 관리", expanded=True):
        st.markdown("""
**한 줄 요약**: 보유 종목과 매매 내역을 기록하고 수익률·세금 정보를 추적합니다.

**주요 기능**
- 다중 포트폴리오 생성/삭제
- 매매 내역 입력 (매수/매도, 날짜, 수량, 가격)
- 보유 비중 파이 차트
- 수익률 추적 (당일 손익 / YTD / 전체 수익률)
- 배당 수익 및 일정
- 세금 요약 (자본이득 정리)

**사용법**
""")
        st.markdown('<div class="step-block">① 포트폴리오 생성 버튼으로 새 포트폴리오 만들기<br>② 종목 추가 → 티커, 수량, 매수가, 매수일 입력<br>③ 보유 현황 탭에서 실시간 평가손익 확인<br>④ 성과 탭에서 기간별 수익률 차트 확인</div>', unsafe_allow_html=True)

    with st.expander("⭐ Watchlist — 관심 종목 & 알림"):
        st.markdown("""
**한 줄 요약**: 관심 종목을 등록하고 특정 가격 조건 도달 시 알림을 받습니다.

**주요 기능**
- 종목 추가/삭제 (메모 기능)
- 알림 설정: 가격 상한/하한, 등락률 임계값
- 페이지 접속 시 알림 조건 자동 체크 (토스트 알림)
- 알림 관리 (삭제, 재활성화)
- 현재가 및 등락률 실시간 표시

**사용법**
""")
        st.markdown('<div class="step-block">① 티커 입력 → 관심 종목에 추가<br>② 알림 추가 버튼 → 가격 조건 설정<br>③ 앱 접속할 때마다 자동으로 알림 조건 체크됨</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 실적 발표 전 목표가 알림을 설정해두면 편리합니다.</div>', unsafe_allow_html=True)

    with st.expander("🤖 AI Quant Lab — AI 기반 퀀트 백테스트"):
        st.markdown("""
**한 줄 요약**: 머신러닝(Random Forest · XGBoost · LightGBM)으로 S&P 500 IT 대형주의 모멘텀 전략을 백테스트하고 오늘의 추천 종목을 제시합니다.

**주요 기능**
- ML 모델 3종 비교 (RF / XGB / LGBM)
- Purged Cross-Validation (21일 엠바고로 데이터 누수 방지)
- 생존 편향 보정 (S&P 500 구성 변경 이력 반영)
- 인버스 볼 가중 (변동성 낮은 종목에 더 많은 비중)
- HMM 레짐 감지 (Bull/Bear/Sideways 현금 전략)
- **오늘의 추천 종목** (당일 스냅샷 기준 실시간 예측)
- 프리셋 로드: 사전 계산된 3개 전략 즉시 확인 가능

**주요 설정 설명**
| 설정 | 설명 |
|---|---|
| 롤링 윈도우 | ML 학습에 사용할 과거 데이터 기간 |
| 리밸런싱 주기 | 포트폴리오 교체 빈도 (월별/분기) |
| 현금 전략 | 레짐에 따라 일부 현금 보유 여부 |
| 앙상블 | 3개 모델 평균으로 예측 정확도 향상 |

**사용법**
""")
        st.markdown('<div class="step-block">① Load Saved Preset → 사전 계산된 결과 즉시 확인 (빠름)<br>② 또는 설정 조정 후 백테스트 실행 (수분 소요)<br>③ 요약 탭: 누적 수익률·샤프 지수 확인<br>④ AI 추천 탭: 오늘 날짜 기준 추천 종목 및 비중 확인<br>⑤ 리밸런싱 내역 탭: 월별 종목 교체 이력 확인</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 매월 1일 오전 11시 자동 업데이트됩니다. 텔레그램으로 월간 리밸런싱 알림도 발송됩니다.</div>', unsafe_allow_html=True)

    with st.expander("🧪 Factor Lab — 룰 기반 퀀트 백테스터"):
        st.markdown("""
**한 줄 요약**: AI 없이 명확한 규칙(저PER, 고ROE, 모멘텀 등)으로 팩터 전략을 백테스트합니다.

**주요 기능**
- 10개+ 팩터 전략 (저PER, 저PBR, 고ROE, 고배당, 모멘텀, 로우볼, Magic Formula 등)
- 단일 전략 백테스트 + 최대 5개 전략 동시 비교
- S&P 500 유니버스, 생존 편향 보정, PIT 펀더멘털 (90일 보고 지연 반영)
- 섹터 / 시가총액 필터
- 벤치마크: SPY / QQQ
- **백테스트 종료일 기준 현재 선정 종목** 표시

**주요 전략 소개**
| 전략 | 선정 기준 |
|---|---|
| 저PER | P/E가 가장 낮은 N개 종목 |
| 고ROE 저PBR | ROE 높고 PBR 낮은 종목 (가치+퀄리티) |
| 모멘텀 12M | 12개월 수익률 상위 종목 |
| Magic Formula | Greenblatt의 이익수익률 + 자본수익률 조합 |
| 로우볼 | 30일 변동성이 가장 낮은 종목 |

**사용법**
""")
        st.markdown('<div class="step-block">① 단일 전략 탭 → 전략 선택 + 기간 + 종목 수 설정<br>② 백테스트 실행 → 누적 수익률 차트 확인<br>③ SPY/QQQ 벤치마크 대비 초과 수익률 확인<br>④ 리밸런싱 내역 → 각 시점별 선정 종목 확인<br>⑤ 전략 비교 탭 → 여러 전략을 같은 조건으로 동시 비교</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 팩터 전략은 AI Quant Lab과 달리 모델 훈련이 없어 빠르게 실행됩니다. 전략의 논리를 직접 이해하고 싶을 때 활용하세요.</div>', unsafe_allow_html=True)

    with st.expander("🔬 Stock Lab — AI 종목 리포트"):
        st.markdown("""
**한 줄 요약**: 개별 종목에 대한 AI 생성 심층 분석 리포트를 확인합니다.

**주요 기능**
- 외부 AI 분석 도구 연동 (aiquantlab-stocklab.pages.dev)
- 사업 개요, 재무 분석, 리스크 요인, 투자 포인트 등 포함
- 새 탭에서 열기

**사용법**
""")
        st.markdown('<div class="step-block">① Stock Lab 메뉴 클릭<br>② 링크 버튼 클릭 → 새 탭에서 리포트 페이지 열기<br>③ 원하는 종목 검색 후 AI 리포트 확인</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4: Research
# ════════════════════════════════════════════════════════════════════════════
with tab_res:
    st.markdown('<span class="menu-tag tag-research">Research</span> 거시경제 지표와 유동성 흐름을 분석하는 페이지입니다.', unsafe_allow_html=True)
    st.markdown("")

    with st.expander("📉 Macro — 거시경제 지표 대시보드", expanded=True):
        st.markdown("""
**한 줄 요약**: Fed 금리, 인플레이션, 통화량, 원자재 가격 등 거시경제 핵심 지표를 차트로 확인합니다.

**주요 지표**
| 카테고리 | 지표 |
|---|---|
| 금리 | 기준금리 / 2년물 / 10년물 국채 금리 |
| 인플레이션 | CPI / Core PCE |
| 유동성 | M1 / M2 통화량 / Fed 자산 규모 |
| 환율 | 달러인덱스 (DXY) |
| 원자재 | 금 / WTI 원유 |

**사용법**
""")
        st.markdown('<div class="step-block">① 각 지표 차트에서 추세 확인<br>② 금리와 주식 시장의 역관계 파악<br>③ M2 통화량 증가 → 유동성 확대 신호</div>', unsafe_allow_html=True)
        st.markdown('<div class="tip-block">💡 10년물 금리가 급등하면 성장주(기술주)에 부정적입니다. Macro 탭에서 미리 추세를 파악하세요.</div>', unsafe_allow_html=True)

    st.divider()

    # 빠른 참고 카드
    st.markdown("#### 📌 빠른 참고")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
**자주 묻는 질문**

**Q. 데이터는 얼마나 자주 업데이트되나요?**
시세 데이터는 15분 간격, 펀더멘털은 하루 1회 자동 업데이트됩니다.

**Q. AI Quant Lab과 Factor Lab의 차이는?**
AI Quant Lab은 ML 모델로 수익률을 예측하고, Factor Lab은 명확한 규칙(저PER 등)으로 종목을 선정합니다.

**Q. RS Rating은 어디서 활용하면 좋나요?**
강세장에서 RS 80+ 종목 위주로 스크리닝하면 상대적으로 강한 종목을 찾는 데 도움이 됩니다.
""")

    with col2:
        st.markdown("""
**투자 워크플로우 추천**

**아침 루틴 (5분)**
1. Home → 지수 등락 확인
2. Dashboard → 섹터 히트맵 스캔
3. Calendar → 오늘 주요 이벤트 확인

**종목 발굴**
1. RS Screener → RS 80+ 강세 종목 필터
2. Screener → 펀더멘털 조건 추가 필터
3. Stock Detail → 개별 종목 상세 분석

**포트폴리오 점검 (월 1회)**
1. AI Quant Lab 프리셋 로드
2. Factor Lab 현재 선정 종목 확인
3. Portfolio → 비중 리밸런싱
""")
