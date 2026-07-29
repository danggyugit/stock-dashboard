"""Breakout Screener — monthly-bar long-term trend-channel upper breakouts.

Fits a log-price linear regression channel over a user-chosen look-back window
and screens for stocks whose current month broke above the channel's upper
(trend-resistance) band. Close-based (monthly close) — the monthly cache stores
close only, and a month-end close break is less noisy than an intramonth wick.
"""

from __future__ import annotations

import logging
import math

import pandas as pd
import streamlit as st

from components.ui import inject_css, render_sidebar_info
from services.auth_service import render_user_sidebar
from services.cache_loader import get_cached_stocks
from services.price_history_service import load_monthly_prices, prefetch
from services.breakout_service import compute_breakouts, MIN_MONTHS

logger = logging.getLogger(__name__)
inject_css()

st.markdown("""
<style>
.bo-hero { background: linear-gradient(135deg,#0a0e27 0%,#101d33 60%,#0a1628 100%);
  border:1px solid rgba(46,134,171,0.25); border-radius:14px; padding:28px 32px 22px; margin-bottom:22px; }
.bo-hero h2 { font-size:1.7rem; font-weight:700; color:#F8FAFC; margin:0 0 6px; }
.bo-hero p { font-size:0.9rem; color:#94A3B8; margin:0; line-height:1.6; }
.bo-badge { display:inline-block; background:rgba(46,134,171,0.15); border:1px solid rgba(46,134,171,0.4);
  color:#7EC8E3; font-size:0.72rem; font-weight:600; padding:3px 11px; border-radius:20px; margin:8px 3px 0 0; }
</style>
<div class="bo-hero">
  <h2>📈 장기 추세채널 돌파 스크리너</h2>
  <p>월봉 로그가격에 선형회귀 <b>추세채널(상단/하단)</b>을 그려, <b>이번 달에 추세 상단을 돌파</b>한 종목을 찾습니다.
     조회 기간·채널 폭을 직접 조절하세요. 상장 5년 미만 종목은 상장 후 데이터로 계산됩니다.</p>
  <span class="bo-badge">S&P 500</span><span class="bo-badge">월봉 · 회귀채널</span>
  <span class="bo-badge">종가 기준</span>
</div>
""", unsafe_allow_html=True)

render_user_sidebar()

# ── Universe (cached stocks) ─────────────────────────────────────────────────
_stocks = get_cached_stocks() or []
_meta = {s["ticker"]: s for s in _stocks if s.get("ticker")}
_universe = sorted(_meta.keys())


def _cap_tier(mc: float | None) -> str:
    if not mc:
        return "-"
    if mc >= 10e9:
        return "대형"
    if mc >= 2e9:
        return "중형"
    return "소형"


# ── Compute controls (require Run) ───────────────────────────────────────────
st.markdown("#### 채널 설정")
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    lookback = st.slider("조회 기간 (개월)", min_value=12, max_value=60, value=60, step=6,
                         help="추세채널을 적합할 월봉 개수. 60 = 최근 5년")
with c2:
    k = st.slider("채널 폭 (표준편차 배수)", min_value=1.0, max_value=3.0, value=2.0, step=0.25,
                  help="상단/하단 = 회귀선 ± k×잔차표준편차. 작을수록 돌파가 자주, 클수록 강한 돌파만")
with c3:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    run = st.button("🔎 스캔 실행", use_container_width=True, type="primary")

if run:
    if not _universe:
        st.error("종목 유니버스를 불러오지 못했습니다 (stocks 캐시 없음).")
    else:
        years_needed = max(6, math.ceil(lookback / 12) + 1)
        prog = st.progress(0.0, text="월봉 데이터 준비 중...")

        def _cb(done: int, total: int, msg: str) -> None:
            prog.progress(min(done / total, 1.0) if total else 1.0, text=f"데이터 수집: {msg}")

        try:
            prefetch(_universe, years=years_needed, progress_callback=_cb)
            prog.progress(0.9, text="추세채널 계산 중...")
            mw = load_monthly_prices(_universe, f"{pd.Timestamp.today().year - years_needed}-01-01",
                                     pd.Timestamp.today().strftime("%Y-%m-%d"))
            res = compute_breakouts(mw, lookback=lookback, k=k)
            prog.progress(1.0, text="완료")
            st.session_state["_bo_result"] = res
            st.session_state["_bo_params"] = {"lookback": lookback, "k": k,
                                              "asof": (mw.index[-1].strftime("%Y-%m") if not mw.empty else "?")}
        except Exception as e:
            logger.exception("Breakout scan failed")
            st.error(f"스캔 실패: {e}")
        prog.empty()

# ── Results + display filters (instant, no recompute) ────────────────────────
res: pd.DataFrame = st.session_state.get("_bo_result", pd.DataFrame())
params = st.session_state.get("_bo_params", {})

if res.empty:
    st.info("채널 설정을 정하고 **🔎 스캔 실행**을 눌러주세요. (전체 S&P 500 월봉 수집 → 최초 1회는 다소 시간이 걸립니다)")
    st.stop()

st.divider()
st.markdown("#### 필터")
f1, f2, f3, f4 = st.columns(4)
with f1:
    fresh_only = st.toggle("이번 달 신규 돌파만", value=True,
                           help="지난달엔 상단 아래였다가 이번 달 처음 돌파한 종목만")
with f2:
    direction = st.selectbox("추세 방향", ["전체", "상승 추세만", "하락 추세만"],
                             help="채널 기울기 부호. 상승채널 돌파 = 추세 가속, 하락채널 돌파 = 반전 후보")
with f3:
    min_r2 = st.slider("최소 추세 적합도 R²", 0.0, 0.95, 0.50, 0.05,
                       help="채널이 얼마나 '추세다운가'. 낮으면 횡보·노이즈까지 잡힘")
with f4:
    sectors = sorted({(_meta.get(t, {}).get("sector") or "-") for t in res.index})
    sector_pick = st.selectbox("섹터", ["전체"] + [s for s in sectors if s != "-"])

f5, f6 = st.columns([1, 3])
with f5:
    cap_pick = st.selectbox("시총", ["전체", "대형", "중형", "소형"])

# apply filters
df = res.copy()
if fresh_only:
    df = df[df["fresh"]]
else:
    df = df[df["breakout"]]
if direction == "상승 추세만":
    df = df[df["slope_ann_pct"] > 0]
elif direction == "하락 추세만":
    df = df[df["slope_ann_pct"] < 0]
df = df[df["r2"] >= min_r2]

# enrich with name / sector / cap
df = df.copy()
df["name"] = [(_meta.get(t, {}).get("name") or t) for t in df.index]
df["sector"] = [(_meta.get(t, {}).get("sector") or "-") for t in df.index]
df["cap"] = [_cap_tier(_meta.get(t, {}).get("market_cap")) for t in df.index]
if sector_pick != "전체":
    df = df[df["sector"] == sector_pick]
if cap_pick != "전체":
    df = df[df["cap"] == cap_pick]

df = df.sort_values("pct_above", ascending=False)

asof = params.get("asof", "?")
st.caption(f"기준월: **{asof}** · 조회 {params.get('lookback')}개월 · 채널폭 {params.get('k')}σ · "
           f"돌파 {len(df)}종목")
if asof != pd.Timestamp.today().strftime("%Y-%m"):
    st.caption("ℹ️ 현재 월봉은 월말에 확정됩니다 — 진행 중인 달은 마지막 종가 기준(잠정)입니다.")

if df.empty:
    st.warning("조건에 맞는 종목이 없습니다. R²를 낮추거나 채널 폭(k)을 줄여보세요.")
    st.stop()

table = pd.DataFrame({
    "티커": df.index,
    "종목": df["name"].str.slice(0, 24).values,
    "섹터": df["sector"].values,
    "시총": df["cap"].values,
    "현재가": df["close"].map(lambda x: f"${x:,.2f}").values,
    "상단밴드": df["upper"].map(lambda x: f"${x:,.2f}").values,
    "상단대비": df["pct_above"].map(lambda x: f"+{x:.1f}%").values,
    "연 추세기울기": df["slope_ann_pct"].map(lambda x: f"{x:+.0f}%/년").values,
    "R²": df["r2"].values,
    "월봉수": df["n_months"].values,
})
table.insert(0, "#", range(1, len(table) + 1))
st.dataframe(table, use_container_width=True, hide_index=True, height=520)

with st.expander("ℹ️ 계산 방식 / 해석 주의"):
    st.markdown(f"""
- **채널**: 각 종목의 월봉 **로그 종가**에 선형회귀선을 긋고, 상단/하단 = 회귀선 ± **{params.get('k')}σ**(잔차 표준편차).
- **돌파 판정**: 채널은 *현재월 직전까지*의 데이터로 적합해 최신 바가 추세선을 끌어올리지 않게 하고, 그 상단을 현재월로 투영해 **현재 종가가 상단 위**면 돌파.
- **이번 달 신규 돌파**: 지난달엔 상단 아래였는데 이번 달 처음 위로 올라온 경우.
- **R²**: 채널이 얼마나 직선 추세에 가까운가(0~1). 낮으면 횡보/노이즈라 '돌파'의 의미가 약합니다 — 0.5 이상 권장.
- **연 추세기울기**: 채널의 연환산 상승률. 양(+)=상승채널 가속, 음(−)=하락채널 반전 후보.
- **한계**: 월봉 캐시가 **종가만** 저장하므로 고가(wick) 기반 돌파는 반영하지 않습니다. 최소 {MIN_MONTHS}개월 이력이 있어야 계산됩니다. 투자 참고용이며 권유가 아닙니다.
""")
