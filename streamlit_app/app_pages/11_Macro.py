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
_section("💧 Liquidity — Money Supply & Fed Balance Sheet")

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
