"""Stock Lab — service intro + launcher page."""

import streamlit as st
from components.ui import inject_css

inject_css()

TARGET_URL = "https://aiquantlab-stocklab.pages.dev"

st.markdown("""
<style>
.sl-hero {
    background: linear-gradient(135deg, #0a0e27 0%, #0d2137 60%, #0a1628 100%);
    border: 1px solid rgba(46,134,171,0.25);
    border-radius: 16px;
    padding: 52px 40px 44px;
    text-align: center;
    margin-bottom: 36px;
    position: relative;
    overflow: hidden;
}
.sl-hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 20% 50%, rgba(46,134,171,0.12) 0%, transparent 55%),
                radial-gradient(circle at 80% 50%, rgba(247,183,49,0.06) 0%, transparent 55%);
}
.sl-hero-inner { position: relative; z-index: 1; }
.sl-hero h1 {
    font-size: 2.4rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 0 0 10px;
    letter-spacing: -0.5px;
}
.sl-hero h1 span { color: #2E86AB; }
.sl-hero .tagline {
    font-size: 1.05rem;
    color: #94A3B8;
    margin: 0 0 28px;
    line-height: 1.7;
}
.sl-badge {
    display: inline-block;
    background: rgba(46,134,171,0.15);
    border: 1px solid rgba(46,134,171,0.4);
    color: #7EC8E3;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 20px;
    letter-spacing: 0.8px;
    margin: 0 4px;
}

/* Report content cards */
.sl-section-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #475569;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-align: center;
    margin: 0 0 20px;
}
.sl-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 36px;
}
.sl-card {
    background: rgba(15,23,42,0.7);
    border: 1px solid rgba(203,213,225,0.1);
    border-radius: 12px;
    padding: 22px 18px;
    transition: border-color 0.2s, transform 0.2s;
}
.sl-card:hover {
    border-color: rgba(46,134,171,0.5);
    transform: translateY(-3px);
}
.sl-card-icon { font-size: 1.7rem; margin-bottom: 10px; }
.sl-card-title {
    font-size: 1.0rem;
    font-weight: 700;
    color: #E2E8F0;
    margin-bottom: 6px;
}
.sl-card-desc {
    font-size: 0.85rem;
    color: #64748B;
    line-height: 1.55;
}

/* How it works */
.sl-flow {
    display: flex;
    align-items: flex-start;
    gap: 0;
    margin-bottom: 36px;
    background: rgba(15,23,42,0.5);
    border: 1px solid rgba(203,213,225,0.08);
    border-radius: 12px;
    padding: 28px 24px;
}
.sl-step {
    flex: 1;
    text-align: center;
    padding: 0 12px;
}
.sl-step-num {
    width: 32px; height: 32px;
    background: rgba(46,134,171,0.2);
    border: 1px solid rgba(46,134,171,0.4);
    border-radius: 50%;
    color: #2E86AB;
    font-size: 0.85rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    margin: 0 auto 10px;
}
.sl-step-title { font-size: 0.95rem; font-weight: 700; color: #CBD5E1; margin-bottom: 4px; }
.sl-step-desc { font-size: 0.82rem; color: #64748B; line-height: 1.5; }
.sl-arrow {
    color: #334155;
    font-size: 1.2rem;
    padding-top: 14px;
    flex-shrink: 0;
}

.sl-cta-wrap { text-align: center; padding: 16px 0 32px; }
.sl-cta-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, #1a6b8a 0%, #2E86AB 50%, #1a6b8a 100%);
    background-size: 200% auto;
    color: #ffffff !important;
    text-decoration: none !important;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 16px 44px;
    border-radius: 50px;
    border: 1px solid rgba(126,200,227,0.35);
    box-shadow: 0 4px 24px rgba(46,134,171,0.35), 0 0 0 0 rgba(46,134,171,0.4);
    transition: background-position 0.4s, box-shadow 0.3s, transform 0.2s;
    cursor: pointer;
}
.sl-cta-btn:hover {
    background-position: right center;
    box-shadow: 0 8px 32px rgba(46,134,171,0.55), 0 0 0 4px rgba(46,134,171,0.15);
    transform: translateY(-2px);
    color: #ffffff !important;
    text-decoration: none !important;
}
.sl-cta-btn .btn-icon { font-size: 1.2rem; }
.sl-disclaimer {
    text-align: center;
    font-size: 0.72rem;
    color: #475569;
    margin-top: 16px;
}
</style>

<div class="sl-hero">
  <div class="sl-hero-inner">
    <h1>🔬 <span>AI</span> Stock Lab</h1>
    <p class="tagline">
      S&P 500 종목에 대한 심층 투자 분석 리포트를 제공합니다.<br>
      12개의 전문화된 AI 에이전트가 재무·밸류에이션·리스크를 종합 분석합니다.
    </p>
    <span class="sl-badge">S&P 500</span>
    <span class="sl-badge">12-Agent Pipeline</span>
    <span class="sl-badge">기관급 분석</span>
  </div>
</div>

<p class="sl-section-title">리포트에 담긴 내용</p>
<div class="sl-cards">
  <div class="sl-card">
    <div class="sl-card-icon">📊</div>
    <div class="sl-card-title">투자 의견</div>
    <div class="sl-card-desc">BUY / HOLD / SELL 판정과 확신도 레이팅. 목표 주가 및 업사이드 산출.</div>
  </div>
  <div class="sl-card">
    <div class="sl-card-icon">💰</div>
    <div class="sl-card-title">밸류에이션</div>
    <div class="sl-card-desc">PER·PBR·EV/EBITDA 등 복수 모델로 적정가 산출. 섹터 평균 대비 비교.</div>
  </div>
  <div class="sl-card">
    <div class="sl-card-icon">📈</div>
    <div class="sl-card-title">재무 분석</div>
    <div class="sl-card-desc">매출·영업이익·EPS 추이, 마진 구조, FCF 및 부채 건전성 심층 점검.</div>
  </div>
  <div class="sl-card">
    <div class="sl-card-icon">⚠️</div>
    <div class="sl-card-title">리스크 요인</div>
    <div class="sl-card-desc">거시·섹터·기업별 리스크를 불 케이스 / 베어 케이스로 구분 정리.</div>
  </div>
</div>

<p class="sl-section-title">이용 방법</p>
<div class="sl-flow">
  <div class="sl-step">
    <div class="sl-step-num">1</div>
    <div class="sl-step-title">종목 탐색</div>
    <div class="sl-step-desc">S&P 500 전체 종목을 섹터별로 탐색하거나 검색으로 바로 찾기</div>
  </div>
  <div class="sl-arrow">›</div>
  <div class="sl-step">
    <div class="sl-step-num">2</div>
    <div class="sl-step-title">리포트 열람</div>
    <div class="sl-step-desc">분석이 완료된 종목은 즉시 풀 리포트 확인 가능</div>
  </div>
  <div class="sl-arrow">›</div>
  <div class="sl-step">
    <div class="sl-step-num">3</div>
    <div class="sl-step-title">분석 요청</div>
    <div class="sl-step-desc">미분석 종목은 분석 요청 등록 — AI가 순차적으로 리포트 생성</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="sl-cta-wrap">
  <a href="{TARGET_URL}" target="_blank" class="sl-cta-btn">
    <span class="btn-icon">🔬</span> Stock Lab 바로가기
  </a>
  <p class="sl-disclaimer">분석 리포트는 투자 참고용이며 투자 권유가 아닙니다.</p>
</div>
""", unsafe_allow_html=True)
