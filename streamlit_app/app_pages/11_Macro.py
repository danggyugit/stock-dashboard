"""Macro / Economy page — key macro indicators for US market."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from services.macro_service import (
    get_money_supply, get_fed_balance_sheet,
    get_fed_funds_rate, get_treasury_yields,
    get_cpi, get_core_pce,
    get_dxy, get_gold, get_oil,
    get_rrp, get_tga, get_bank_reserves, get_hy_spread, get_net_liquidity,
)
from services.auth_service import require_auth
from components.ui import inject_css
from services.i18n import t as tr

_user = require_auth()
inject_css()

# ── Page title ────────────────────────────────────────────
st.markdown(
    '<div style="font-size:1.8rem;font-weight:800;margin-bottom:4px;">📊 Macro / Economy</div>'
    '<div style="color:#94a3b8;font-size:0.95rem;margin-bottom:24px;">'
    'Key US macroeconomic indicators — liquidity, rates, inflation, dollar & commodities</div>',
    unsafe_allow_html=True,
)

_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=0, r=0, t=10, b=0),
    yaxis=dict(gridcolor="rgba(100,116,139,0.2)"),
    xaxis=dict(gridcolor="rgba(100,116,139,0.1)"),
    hovermode="x unified",
)


def _section(title: str):
    st.markdown(
        f'<div style="font-size:0.8rem;font-weight:700;color:#64748b;'
        f'text-transform:uppercase;letter-spacing:0.06em;'
        f'border-bottom:2px solid #334155;padding-bottom:6px;margin:28px 0 14px;">'
        f'{title}</div>',
        unsafe_allow_html=True,
    )


def _metric_card(label: str, value: str, color: str = "#e2e8f0"):
    return (
        f'<div style="text-align:center;padding:10px 0;">'
        f'<div style="font-size:0.75rem;color:#94a3b8;">{label}</div>'
        f'<div style="font-size:1.3rem;font-weight:700;color:{color};">{value}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════
# 1. LIQUIDITY
# ═══════════════════════════════════════════════════════════
_section("💧 Liquidity — 시장 유동성 종합")

# ── 유동성 요약 배지 ──────────────────────────────────────────
_nl_df = get_net_liquidity()
_rrp_df = get_rrp()
_tga_df = get_tga()
_res_df = get_bank_reserves()
_hy_df = get_hy_spread()


def _trend_badge(df, col="value", weeks=4, invert=False):
    """최근 4주 변화 방향 배지. invert=True면 감소가 유동성에 긍정."""
    if df is None or df.empty or len(df) < 2:
        return None, None
    s = df[col].dropna()
    lookback = min(len(s) - 1, weeks)
    chg = float(s.iloc[-1] - s.iloc[-1 - lookback])
    positive_for_liq = (chg < 0) if invert else (chg > 0)
    icon = "🟢" if positive_for_liq else "🔴"
    return float(s.iloc[-1]), f"{icon} {chg:+.2f}"


if not _nl_df.empty:
    b1, b2, b3, b4, b5 = st.columns(5)
    _badges = [
        (b1, "순유동성 Net Liq", _nl_df, "net_liq", False, "T", "WALCL − RRP − TGA"),
        (b2, "역레포 RRP", _rrp_df, "value", True, "T", "감소 = 시중 방출 🟢"),
        (b3, "재무부 TGA", _tga_df, "value", True, "T", "증가 = 유동성 흡수 🔴"),
        (b4, "은행 지준금", _res_df, "value", False, "T", "은행계 실탄"),
        (b5, "HY 스프레드", _hy_df, "value", True, "%", "급등 = 신용 스트레스"),
    ]
    for col_box, label, dfx, valcol, inv, unit, tip in _badges:
        with col_box:
            val, badge = _trend_badge(dfx, valcol, invert=inv)
            if val is None:
                st.metric(label, "—")
            else:
                disp = f"${val:.2f}T" if unit == "T" else f"{val:.2f}%"
                st.metric(label, disp, badge, delta_color="off", help=tip)
    st.caption("배지 = 최근 4주 변화 · 🟢 유동성에 우호 / 🔴 유동성 흡수·스트레스 방향")

# ── 순유동성 vs S&P500 오버레이 (메인 차트) ────────────────────
if not _nl_df.empty and "spx" in _nl_df.columns:
    st.markdown("**⭐ Net Liquidity vs S&P500** — 순유동성(연준자산−역레포−재무부계정)과 주가의 동행")
    fig_nl = go.Figure()
    fig_nl.add_trace(go.Scatter(
        x=_nl_df["date"], y=_nl_df["net_liq"],
        name="Net Liquidity", line=dict(color="#22D3EE", width=2.5),
        hovertemplate="%{x|%Y-%m-%d}<br>Net Liq: $%{y:.2f}T<extra></extra>",
    ))
    fig_nl.add_trace(go.Scatter(
        x=_nl_df["date"], y=_nl_df["spx"],
        name="S&P 500", yaxis="y2",
        line=dict(color="#F59E0B", width=1.8, dash="dot"),
        hovertemplate="%{x|%Y-%m-%d}<br>S&P: %{y:,.0f}<extra></extra>",
    ))
    fig_nl.update_layout(
        **_CHART_LAYOUT, height=320,
        yaxis=dict(title="Net Liq ($T)", tickprefix="$", ticksuffix="T"),
        yaxis2=dict(title="S&P 500", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig_nl, use_container_width=True)

# ── RRP · TGA · 지준금 · HY 스프레드 ──────────────────────────
liq_r1c1, liq_r1c2 = st.columns(2)
with liq_r1c1:
    st.markdown("**역레포 (RRP)** — 연준에 잠긴 유동성")
    if not _rrp_df.empty:
        fig = go.Figure(go.Scatter(
            x=_rrp_df["date"], y=_rrp_df["value"],
            line=dict(color="#818CF8", width=2), fill="tozeroy",
            fillcolor="rgba(129,140,248,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.2f}T<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=220, showlegend=False,
                          yaxis_tickprefix="$", yaxis_ticksuffix="T")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("RRP data unavailable")
with liq_r1c2:
    st.markdown("**재무부 계정 (TGA)** — 재무부 보유 현금")
    if not _tga_df.empty:
        fig = go.Figure(go.Scatter(
            x=_tga_df["date"], y=_tga_df["value"],
            line=dict(color="#F472B6", width=2), fill="tozeroy",
            fillcolor="rgba(244,114,182,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.2f}T<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=220, showlegend=False,
                          yaxis_tickprefix="$", yaxis_ticksuffix="T")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("TGA data unavailable")

liq_r2c1, liq_r2c2 = st.columns(2)
with liq_r2c1:
    st.markdown("**은행 지준금 (Reserves)** — 은행 시스템의 실탄")
    if not _res_df.empty:
        fig = go.Figure(go.Scatter(
            x=_res_df["date"], y=_res_df["value"],
            line=dict(color="#34D399", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.2f}T<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=220, showlegend=False,
                          yaxis_tickprefix="$", yaxis_ticksuffix="T")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Reserves data unavailable")
with liq_r2c2:
    st.markdown("**하이일드 스프레드 (HY OAS)** — 신용시장 스트레스")
    if not _hy_df.empty:
        fig = go.Figure(go.Scatter(
            x=_hy_df["date"], y=_hy_df["value"],
            line=dict(color="#F87171", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>",
        ))
        fig.add_hline(y=5.0, line_color="#64748b", line_width=1, line_dash="dot",
                      annotation_text="주의 5%", annotation_font_size=10)
        fig.update_layout(**_CHART_LAYOUT, height=220, showlegend=False,
                          yaxis_ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("HY spread data unavailable")

st.markdown("---")
st.markdown("**통화량 · 연준 자산** (기존)")

liq1, liq2 = st.columns(2)

# M1 / M2
with liq1:
    st.markdown("**M1 / M2 Money Supply**")
    money_df = get_money_supply()
    if not money_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=money_df["date"], y=money_df["M2"],
            name="M2", line=dict(color="#3B82F6", width=2.5),
            hovertemplate="%{x|%Y-%m}<br>M2: $%{y:.1f}T<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=money_df["date"], y=money_df["M1"],
            name="M1", line=dict(color="#10B981", width=2),
            hovertemplate="%{x|%Y-%m}<br>M1: $%{y:.1f}T<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=280,
                          yaxis_tickprefix="$", yaxis_ticksuffix="T",
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        # MoM change mini bar
        m2_chg = money_df["M2"].diff().iloc[1:] * 1000  # → $B
        chg_colors = ["#3B82F6" if v >= 0 else "#EF4444" for v in m2_chg]
        fig_chg = go.Figure(go.Bar(
            x=money_df["date"].iloc[1:], y=m2_chg,
            marker_color=chg_colors,
            hovertemplate="%{x|%Y-%m}<br>M2 Δ: %{y:+.0f}B<extra></extra>",
        ))
        fig_chg.add_hline(y=0, line_color="#64748b", line_width=1)
        fig_chg.update_layout(**_CHART_LAYOUT, height=140,
                              yaxis_tickprefix="$", yaxis_ticksuffix="B",
                              showlegend=False)
        st.plotly_chart(fig_chg, use_container_width=True)

        if len(money_df) >= 13:
            yoy = (money_df["M2"].iloc[-1] / money_df["M2"].iloc[-13] - 1) * 100
            _c = "#22C55E" if yoy > 0 else "#EF4444"
            st.markdown(
                f'<div style="text-align:center;font-size:0.85rem;">'
                f'M2 <b>${money_df["M2"].iloc[-1]:.1f}T</b> · '
                f'YoY <span style="color:{_c};font-weight:700;">{yoy:+.1f}%</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("M1/M2 data unavailable")
        st.caption("💡 FRED API 키를 Streamlit secrets에 `FRED_API_KEY`로 추가하면 활성화됩니다.")

# Fed Balance Sheet
with liq2:
    st.markdown("**Fed Balance Sheet (Total Assets)**")
    fed_df = get_fed_balance_sheet()
    if not fed_df.empty:
        fig = go.Figure(go.Scatter(
            x=fed_df["date"], y=fed_df["value"],
            line=dict(color="#A855F7", width=2.5),
            fill="tozeroy", fillcolor="rgba(168,85,247,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.2f}T<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=280,
                          yaxis_tickprefix="$", yaxis_ticksuffix="T",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        latest = fed_df["value"].iloc[-1]
        peak = fed_df["value"].max()
        off_peak = (latest / peak - 1) * 100
        st.markdown(
            f'<div style="text-align:center;font-size:0.85rem;">'
            f'Current <b>${latest:.2f}T</b> · '
            f'Peak <b>${peak:.2f}T</b> · '
            f'<span style="color:{"#22C55E" if off_peak >= 0 else "#EF4444"};font-weight:700;">'
            f'{off_peak:+.1f}%</span> from peak</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Fed Balance Sheet data unavailable")
        st.caption("💡 FRED API 키를 Streamlit secrets에 `FRED_API_KEY`로 추가하면 활성화됩니다.")

# ═══════════════════════════════════════════════════════════
# 2. INTEREST RATES
# ═══════════════════════════════════════════════════════════
_section("📈 Interest Rates — Fed Funds & Yield Curve")

rate1, rate2 = st.columns(2)

# Fed Funds Rate
with rate1:
    st.markdown("**Federal Funds Rate**")
    ffr_df = get_fed_funds_rate()
    if not ffr_df.empty:
        fig = go.Figure(go.Scatter(
            x=ffr_df["date"], y=ffr_df["value"],
            line=dict(color="#F59E0B", width=2.5), fill="tozeroy",
            fillcolor="rgba(245,158,11,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=300,
                          yaxis_ticksuffix="%", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        latest = ffr_df["value"].iloc[-1]
        st.markdown(
            f'<div style="text-align:center;">'
            + _metric_card("Current Rate", f"{latest:.2f}%", "#F59E0B")
            + '</div>', unsafe_allow_html=True,
        )
    else:
        st.caption("Fed Funds Rate data unavailable")

# Yield Curve (10Y - 2Y)
with rate2:
    st.markdown("**Treasury Yields & Spread (10Y − 2Y)**")
    yc_df = get_treasury_yields()
    if not yc_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=yc_df["date"], y=yc_df["10Y"],
            name="10Y", line=dict(color="#3B82F6", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=yc_df["date"], y=yc_df["2Y"],
            name="2Y", line=dict(color="#10B981", width=2),
        ))
        # Spread as filled area
        spread_colors = ["rgba(34,197,94,0.3)" if s >= 0 else "rgba(239,68,68,0.3)"
                         for s in yc_df["Spread"]]
        fig.add_trace(go.Bar(
            x=yc_df["date"], y=yc_df["Spread"],
            name="Spread", marker_color=spread_colors,
            opacity=0.4, yaxis="y2",
        ))
        fig.add_hline(y=0, line_color="#64748b", line_width=1)
        _yc_layout = {**_CHART_LAYOUT}
        _yc_layout["yaxis"] = dict(gridcolor="rgba(100,116,139,0.2)", ticksuffix="%", side="left")
        fig.update_layout(
            **_yc_layout, height=300,
            yaxis2=dict(ticksuffix="%", overlaying="y", side="right",
                        showgrid=False, zeroline=False),
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)

        sp = yc_df["Spread"].iloc[-1]
        _sp_clr = "#22C55E" if sp >= 0 else "#EF4444"
        _sp_lbl = "Normal" if sp >= 0 else "⚠️ Inverted"
        mc1, mc2, mc3 = st.columns(3)
        mc1.markdown(_metric_card("10Y", f'{yc_df["10Y"].iloc[-1]:.2f}%', "#3B82F6"),
                     unsafe_allow_html=True)
        mc2.markdown(_metric_card("2Y", f'{yc_df["2Y"].iloc[-1]:.2f}%', "#10B981"),
                     unsafe_allow_html=True)
        mc3.markdown(_metric_card(f"Spread ({_sp_lbl})", f"{sp:+.2f}%", _sp_clr),
                     unsafe_allow_html=True)
    else:
        st.caption("Treasury yield data unavailable")

# ═══════════════════════════════════════════════════════════
# 3. INFLATION
# ═══════════════════════════════════════════════════════════
_section("🔥 Inflation — CPI & Core PCE")

inf1, inf2 = st.columns(2)

# CPI
with inf1:
    st.markdown("**CPI (YoY %)**")
    cpi_df = get_cpi()
    if not cpi_df.empty:
        cpi_colors = ["#EF4444" if v > 3 else ("#F59E0B" if v > 2 else "#22C55E")
                      for v in cpi_df["YoY"]]
        fig = go.Figure(go.Bar(
            x=cpi_df["date"], y=cpi_df["YoY"],
            marker_color=cpi_colors,
            hovertemplate="%{x|%Y-%m}<br>CPI YoY: %{y:.1f}%<extra></extra>",
        ))
        fig.add_hline(y=2, line_dash="dash", line_color="#64748b",
                      annotation_text="2% Target", annotation_position="bottom right",
                      annotation_font_size=10, annotation_font_color="#64748b")
        fig.update_layout(**_CHART_LAYOUT, height=300,
                          yaxis_ticksuffix="%", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        latest = cpi_df["YoY"].iloc[-1]
        _c = "#22C55E" if latest <= 2 else ("#F59E0B" if latest <= 3 else "#EF4444")
        st.markdown(_metric_card("Latest CPI YoY", f"{latest:.1f}%", _c),
                    unsafe_allow_html=True)
    else:
        st.caption("CPI data unavailable")

# Core PCE
with inf2:
    st.markdown("**Core PCE (YoY %) — Fed's preferred measure**")
    pce_df = get_core_pce()
    if not pce_df.empty:
        pce_colors = ["#EF4444" if v > 3 else ("#F59E0B" if v > 2 else "#22C55E")
                      for v in pce_df["YoY"]]
        fig = go.Figure(go.Bar(
            x=pce_df["date"], y=pce_df["YoY"],
            marker_color=pce_colors,
            hovertemplate="%{x|%Y-%m}<br>Core PCE YoY: %{y:.1f}%<extra></extra>",
        ))
        fig.add_hline(y=2, line_dash="dash", line_color="#64748b",
                      annotation_text="2% Target", annotation_position="bottom right",
                      annotation_font_size=10, annotation_font_color="#64748b")
        fig.update_layout(**_CHART_LAYOUT, height=300,
                          yaxis_ticksuffix="%", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        latest = pce_df["YoY"].iloc[-1]
        _c = "#22C55E" if latest <= 2 else ("#F59E0B" if latest <= 3 else "#EF4444")
        st.markdown(_metric_card("Latest Core PCE YoY", f"{latest:.1f}%", _c),
                    unsafe_allow_html=True)
    else:
        st.caption("Core PCE data unavailable")

# ═══════════════════════════════════════════════════════════
# 4. DOLLAR & COMMODITIES
# ═══════════════════════════════════════════════════════════
_section("💰 Dollar & Commodities — DXY, Gold, Oil")

com1, com2, com3 = st.columns(3)

# DXY
with com1:
    st.markdown("**DXY (Dollar Index)**")
    dxy_df = get_dxy()
    if not dxy_df.empty:
        dxy_df = dxy_df[dxy_df["date"] >= "2021-01-01"]
        _dxy_min = dxy_df["value"].min()
        _dxy_max = dxy_df["value"].max()
        _dxy_pad = (_dxy_max - _dxy_min) * 0.1
        fig = go.Figure(go.Scatter(
            x=dxy_df["date"], y=dxy_df["value"],
            line=dict(color="#60A5FA", width=2),
            fill="tonexty" if False else "tozeroy",
            fillcolor="rgba(96,165,250,0.06)",
            hovertemplate="%{x|%Y-%m-%d}<br>DXY: %{y:.2f}<extra></extra>",
        ))
        _dxy_layout = {**_CHART_LAYOUT}
        _dxy_layout["yaxis"] = dict(
            gridcolor="rgba(100,116,139,0.2)",
            range=[_dxy_min - _dxy_pad, _dxy_max + _dxy_pad],
        )
        fig.update_layout(**_dxy_layout, height=260, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(_metric_card("DXY", f'{dxy_df["value"].iloc[-1]:.2f}', "#60A5FA"),
                    unsafe_allow_html=True)
    else:
        st.caption("DXY data unavailable")

# Gold
with com2:
    st.markdown("**Gold (GC=F)**")
    gold_df = get_gold()
    if not gold_df.empty:
        gold_df = gold_df[gold_df["date"] >= "2021-01-01"]
        fig = go.Figure(go.Scatter(
            x=gold_df["date"], y=gold_df["value"],
            line=dict(color="#FBBF24", width=2),
            fill="tozeroy", fillcolor="rgba(251,191,36,0.06)",
            hovertemplate="%{x|%Y-%m-%d}<br>Gold: $%{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=260,
                          yaxis_tickprefix="$", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(_metric_card("Gold", f'${gold_df["value"].iloc[-1]:,.0f}', "#FBBF24"),
                    unsafe_allow_html=True)
    else:
        st.caption("Gold data unavailable")

# Oil
with com3:
    st.markdown("**WTI Crude Oil (CL=F)**")
    oil_df = get_oil()
    if not oil_df.empty:
        oil_df = oil_df[oil_df["date"] >= "2021-01-01"]
        fig = go.Figure(go.Scatter(
            x=oil_df["date"], y=oil_df["value"],
            line=dict(color="#F97316", width=2),
            fill="tozeroy", fillcolor="rgba(249,115,22,0.06)",
            hovertemplate="%{x|%Y-%m-%d}<br>Oil: $%{y:.2f}<extra></extra>",
        ))
        fig.update_layout(**_CHART_LAYOUT, height=260,
                          yaxis_tickprefix="$", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown(_metric_card("WTI", f'${oil_df["value"].iloc[-1]:.2f}', "#F97316"),
                    unsafe_allow_html=True)
    else:
        st.caption("Oil data unavailable")
