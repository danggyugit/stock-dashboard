"""RS Rating 스크리너 — IBD-style Relative Strength Rating (1-99).

S&P 500 전 종목 대비 12개월 모멘텀 백분위 순위.
가중 산식: 최근 3개월 ×40% + 3~6개월 ×20% + 6~9개월 ×20% + 9~12개월 ×20%
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from services.auth_service import require_auth
from components.ui import inject_css
from services.rs_service import get_rs_table
from services.cache_loader import get_cached_stocks

_user = require_auth()
inject_css()

st.markdown("""
<style>
    .rs-hero {
        background: radial-gradient(ellipse at top left,
                    rgba(139,92,246,0.15) 0%, rgba(15,23,42,0) 60%),
                    radial-gradient(ellipse at bottom right,
                    rgba(59,130,246,0.10) 0%, rgba(15,23,42,0) 60%);
        border: 1px solid rgba(139,92,246,0.22);
        border-radius: 16px; padding: 28px 30px; margin-bottom: 20px;
    }
    .rs-hero h1 {
        font-size: 2.2rem; font-weight: 800; margin: 0 0 6px 0;
        background: linear-gradient(135deg, #A78BFA 0%, #60A5FA 70%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        line-height: 1.15;
    }
    .rs-hero .sub { font-size: 0.95rem; color: #CBD5E1; margin: 0; }
    .rs-hero .meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .rs-hero .meta span {
        font-size: 0.72rem; font-weight: 600; color: #C4B5FD;
        background: rgba(139,92,246,0.12); border: 1px solid rgba(139,92,246,0.30);
        padding: 4px 10px; border-radius: 999px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="rs-hero">
  <h1>📊 RS Rating 스크리너</h1>
  <p class="sub">IBD-style 상대 강도 지수 — S&P 500 내 12개월 모멘텀 백분위 순위 (1~99)</p>
  <div class="meta">
    <span>S&P 500 유니버스</span>
    <span>캐시 6시간</span>
    <span>IBD 가중 산식</span>
    <span>RS 80+ = 강세 신호</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load stock universe ────────────────────────────────────────────────────
stocks = get_cached_stocks() or []
if not stocks:
    st.error("종목 데이터를 불러올 수 없습니다. 잠시 후 다시 시도하세요.")
    st.stop()

stock_df = pd.DataFrame(stocks)
keep = [c for c in ["ticker", "name", "sector", "cap_tier"] if c in stock_df.columns]
stock_df = stock_df[keep].dropna(subset=["ticker"])
stock_df["ticker"] = stock_df["ticker"].astype(str)

sectors = (
    ["전체"] + sorted(stock_df["sector"].dropna().unique().tolist())
    if "sector" in stock_df.columns else ["전체"]
)
cap_tiers = (
    ["전체"] + sorted(stock_df["cap_tier"].dropna().unique().tolist())
    if "cap_tier" in stock_df.columns else ["전체"]
)

# ── Filters ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
with c1:
    sel_sector = st.selectbox("섹터", sectors)
with c2:
    default_cap = cap_tiers.index("Large Cap") if "Large Cap" in cap_tiers else 0
    sel_cap = st.selectbox("시총 구간", cap_tiers, index=default_cap)
with c3:
    min_rs = st.slider("최소 RS Rating", 0, 99, 70)
with c4:
    st.markdown("&nbsp;")
    run_btn = st.button("실행", type="primary", use_container_width=True)

# Filter universe
filtered = stock_df.copy()
if sel_sector != "전체" and "sector" in filtered.columns:
    filtered = filtered[filtered["sector"] == sel_sector]
if sel_cap != "전체" and "cap_tier" in filtered.columns:
    filtered = filtered[filtered["cap_tier"] == sel_cap]

tickers_key = tuple(sorted(filtered["ticker"].tolist()))

if not tickers_key:
    st.warning("선택된 조건에 해당하는 종목이 없습니다.")
    st.stop()

if len(tickers_key) > 200:
    st.warning(
        f"⏱️ {len(tickers_key)}개 종목 — 첫 계산에 1~2분 소요됩니다. "
        "캐시 후 6시간 이내 재실행은 즉시 응답합니다."
    )

# Compute on button press or when universe changes
prev_key = st.session_state.get("rs_last_key")
if run_btn or prev_key != tickers_key:
    with st.spinner(f"{len(tickers_key)}개 종목 RS Rating 계산 중…"):
        rs_tbl = get_rs_table(tickers_key)
        st.session_state["rs_table_cache"] = rs_tbl
        st.session_state["rs_last_key"] = tickers_key

rs_tbl: pd.DataFrame = st.session_state.get("rs_table_cache", pd.DataFrame())

if rs_tbl.empty:
    st.info("실행 버튼을 클릭하면 RS Rating을 계산합니다.")
    st.stop()

# ── Merge & apply min_rs filter ────────────────────────────────────────────
merged = filtered.merge(rs_tbl, on="ticker", how="inner")
result = merged[merged["rs_rating"] >= min_rs].sort_values("rs_rating", ascending=False)

# ── Summary metrics ────────────────────────────────────────────────────────
st.divider()
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("스캔 종목", len(rs_tbl))
mc2.metric("필터 결과", len(result))
mc3.metric("RS 90+", int((result["rs_rating"] >= 90).sum()))
mc4.metric("RS 80+", int((result["rs_rating"] >= 80).sum()))
avg_rs = int(result["rs_rating"].mean()) if not result.empty else 0
mc5.metric("평균 RS", avg_rs)

# ── RS Distribution chart ──────────────────────────────────────────────────
fig = go.Figure()
fig.add_trace(go.Histogram(
    x=rs_tbl["rs_rating"].values,
    nbinsx=20,
    marker_color="rgba(139,92,246,0.65)",
    marker_line=dict(color="rgba(139,92,246,0.3)", width=1),
))
if 0 < min_rs < 99:
    fig.add_vline(
        x=min_rs, line_color="#60A5FA", line_dash="dot", line_width=2,
        annotation_text=f"  RS ≥ {min_rs}", annotation_position="top right",
        annotation_font_color="#93C5FD",
    )
fig.update_layout(
    title=dict(text="전체 RS Rating 분포", font=dict(size=13, color="#CBD5E1")),
    height=200, margin=dict(t=30, b=10, l=0, r=0),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#CBD5E1"), showlegend=False,
    xaxis=dict(range=[0, 102], title="RS Rating"),
    yaxis=dict(title="종목 수"),
)
st.plotly_chart(fig, use_container_width=True)

# ── RS 90+ highlight chips ─────────────────────────────────────────────────
top90 = result[result["rs_rating"] >= 90]
if not top90.empty:
    chips = "".join(
        f'<span style="background:rgba(139,92,246,0.15);'
        f'border:1px solid rgba(139,92,246,0.40);'
        f'border-radius:8px;padding:4px 13px;'
        f'font-size:0.88rem;font-weight:700;color:#C4B5FD;'
        f'font-family:monospace;margin:2px;display:inline-block;">'
        f'{row["ticker"]}'
        f'<span style="font-weight:400;font-size:0.75rem;color:#A78BFA;margin-left:5px;">'
        f'RS {row["rs_rating"]}</span></span>'
        for _, row in top90.iterrows()
    )
    st.markdown(
        f'<div style="margin:6px 0 4px 0;font-size:0.8rem;font-weight:700;color:#C4B5FD;">'
        f'🚀 RS 90+ 초강세 종목 ({len(top90)}개)</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px;">{chips}</div>',
        unsafe_allow_html=True,
    )

# ── Main table ─────────────────────────────────────────────────────────────
col_map = {
    "ticker": "티커",
    "rs_rating": "RS Rating",
    "ret_1m_pct": "1개월(%)",
    "ret_3m_pct": "3개월(%)",
    "ret_12m_pct": "12개월(%)",
    "sector": "섹터",
    "cap_tier": "시총",
}
if "name" in result.columns:
    col_map = {"ticker": "티커", "name": "회사명", **{k: v for k, v in col_map.items() if k != "ticker"}}

show_cols = [c for c in col_map if c in result.columns]
display_df = result[show_cols].rename(columns=col_map).reset_index(drop=True)

def _fmt_pct(v: float | None) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:+.1f}%"

fmt_cols = {c: _fmt_pct for c in ["1개월(%)", "3개월(%)", "12개월(%)"] if c in display_df.columns}

def _rs_style(v: object) -> str:
    if not isinstance(v, (int, float)):
        return ""
    if v >= 90:
        return "color:#C4B5FD;font-weight:700"
    if v >= 80:
        return "color:#4ADE80;font-weight:600"
    if v >= 70:
        return "color:#60A5FA"
    return "color:#94A3B8"

styled = (
    display_df.style
    .map(_rs_style, subset=["RS Rating"])
    .format(fmt_cols)
)

st.markdown(
    f'<div style="font-size:1rem;font-weight:700;color:#CBD5E1;margin-bottom:6px;">'
    f'RS {min_rs}+ 종목 목록 ({len(display_df)}개)</div>',
    unsafe_allow_html=True,
)
st.dataframe(styled, width="stretch", hide_index=True)

# ── Formula footnote ───────────────────────────────────────────────────────
st.caption(
    "**산식**: 가중 수익률 = 최근 3M ×40% + 3~6M ×20% + 6~9M ×20% + 9~12M ×20%  →  "
    "전체 종목 대비 백분위 점수로 1~99 변환.  "
    "IBD Investor's Business Daily 방식 (최근 모멘텀 중시)."
)
