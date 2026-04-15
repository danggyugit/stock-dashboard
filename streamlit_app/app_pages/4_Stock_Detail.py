"""Stock Detail page — Individual stock analysis with interactive candlestick chart."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from services.market_service import get_stock_detail, get_chart_data, search_stocks
from services.sentiment_service import get_stock_news
from services.valuation_service import (
    get_valuation_core, get_analyst_consensus,
    build_fair_value_table, build_scenario_bands,
    get_individual_analyst_targets,
)
from services.ai_valuation_service import (
    is_available as ai_val_available,
    get_ai_scenario_analysis,
    MODEL_FLASH,
)
from services.auth_service import render_user_sidebar
from services.i18n import t as tr
from components.ui import inject_css, page_header, stock_logo_url, render_sidebar_info


def _calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """Calculate RSI (Relative Strength Index)."""
    s = pd.Series(closes)
    delta = s.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.tolist()


def _calc_macd(closes: list[float]) -> tuple[list, list, list]:
    """Calculate MACD line, Signal line, Histogram."""
    s = pd.Series(closes)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    return macd.tolist(), signal.tolist(), hist.tolist()


def _calc_bollinger(closes: list[float], period: int = 20, std_dev: float = 2.0):
    """Calculate Bollinger Bands (middle, upper, lower)."""
    s = pd.Series(closes)
    middle = s.rolling(period).mean()
    std = s.rolling(period).std()
    upper = middle + std * std_dev
    lower = middle - std * std_dev
    return middle.tolist(), upper.tolist(), lower.tolist()

page_header("page.stock_detail.title", "page.stock_detail.subtitle")

# --- Recently viewed sidebar ---
if "recent_tickers" not in st.session_state:
    st.session_state.recent_tickers = []

with st.sidebar:
    st.subheader(tr("sd.recently_viewed"))
    if st.session_state.recent_tickers:
        for rt in st.session_state.recent_tickers[:8]:
            if st.button(f"📈 {rt}", key=f"recent_{rt}", use_container_width=True):
                st.session_state.recent_pick = rt
                st.rerun()
        if st.button(tr("common.clear"), key="clear_recent", use_container_width=True):
            st.session_state.recent_tickers = []
            st.rerun()
    else:
        st.caption(tr("sd.recently_empty"))

# --- Ticker Search ---
# Handle pick from recent
default_ticker = st.session_state.pop("recent_pick", "NVDA")

query = st.text_input(tr("sd.search_ticker"), placeholder=tr("sd.search_placeholder"))

if query:
    results = search_stocks(query)
    if results:
        options = {r["ticker"]: f"{r['ticker']} — {r.get('name', '')}" for r in results}
        selected = st.selectbox(tr("sd.select_stock"), options.keys(), format_func=lambda x: options[x])
    else:
        selected = query.upper().strip()
        st.caption(tr("sd.no_match", ticker=selected))
else:
    selected = st.text_input(tr("sd.enter_directly"), value=default_ticker).upper().strip()

if not selected:
    st.stop()

# Track recently viewed (dedupe + cap at 8)
recent = st.session_state.recent_tickers
if selected in recent:
    recent.remove(selected)
recent.insert(0, selected)
st.session_state.recent_tickers = recent[:8]

# --- Stock Info ---
with st.spinner(tr("sd.loading", ticker=selected)):
    info = get_stock_detail(selected)

if not info:
    st.error(tr("sd.could_not_load", ticker=selected))
    st.stop()

# Header with company logo
logo_url = stock_logo_url(selected)
header_html = f"""
<div style="display:flex; align-items:center; gap:16px; margin: 16px 0 8px 0;">
    <img src="{logo_url}" style="width:48px; height:48px; border-radius:8px; background:white; padding:4px;"
         onerror="this.style.display='none'"/>
    <h2 style="margin:0; padding:0; border:none;">{info.get('name', selected)} ({selected})</h2>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

c1, c2, c3, c4, c5 = st.columns(5)
price = info.get("price")
change = info.get("change_pct")
c1.metric(tr("sd.price"), f"${price:,.2f}" if price else "N/A", delta=f"{change:+.2f}%" if change else None)
c2.metric(tr("sd.market_cap"), f"${info.get('market_cap', 0) / 1e9:.1f}B" if info.get("market_cap") else "N/A")
c3.metric(tr("sd.pe"), f"{info.get('pe_ratio'):.1f}" if info.get("pe_ratio") else "N/A")
c4.metric(tr("sd.fifty_two_high"), f"${info.get('fifty_two_week_high'):,.2f}" if info.get("fifty_two_week_high") else "N/A")
c5.metric(tr("sd.fifty_two_low"), f"${info.get('fifty_two_week_low'):,.2f}" if info.get("fifty_two_week_low") else "N/A")

# --- 52-Week Range Slider (visual position) ---
w52_high = info.get("fifty_two_week_high")
w52_low = info.get("fifty_two_week_low")
if price and w52_high and w52_low and w52_high > w52_low:
    pct_in_range = ((price - w52_low) / (w52_high - w52_low)) * 100
    pct_in_range = max(0, min(100, pct_in_range))

    # Color based on position: red (near low) → yellow → green (near high)
    if pct_in_range < 33:
        marker_color = "#EF4444"
    elif pct_in_range < 66:
        marker_color = "#F59E0B"
    else:
        marker_color = "#10B981"

    slider_html = f"""
    <div style="margin: 16px 0 24px 0;">
        <div style="display:flex; justify-content:space-between; font-size:12px;
                    color:#94A3B8; margin-bottom:6px;">
            <span><b style="color:#EF4444;">52W Low</b> ${w52_low:,.2f}</span>
            <span style="color:{marker_color}; font-weight:700;">
                Current ${price:,.2f} ({pct_in_range:.1f}%)
            </span>
            <span><b style="color:#10B981;">52W High</b> ${w52_high:,.2f}</span>
        </div>
        <div style="position:relative; height:14px; border-radius:7px;
                    background:linear-gradient(90deg, #EF4444 0%, #F59E0B 50%, #10B981 100%);
                    overflow:visible;">
            <div style="position:absolute; left:{pct_in_range}%; top:-4px;
                        width:4px; height:22px; background:#F8FAFC;
                        border-radius:2px; transform:translateX(-50%);
                        box-shadow:0 0 8px rgba(248,250,252,0.6);"></div>
        </div>
    </div>
    """
    st.markdown(slider_html, unsafe_allow_html=True)

# --- Chart (TradingView only; Plotly disabled) ---
st.subheader(tr("sd.price_chart"))

# TradingView Advanced Chart Widget — full-featured live chart
tv_html = f"""
<div class="tradingview-widget-container" style="height:600px;">
  <div id="tv_{selected}" style="height:600px; border-radius:12px; overflow:hidden;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "{selected}",
    "interval": "D",
    "timezone": "America/New_York",
    "theme": "dark",
    "style": "1",
    "locale": "en",
    "toolbar_bg": "#0F172A",
    "enable_publishing": false,
    "withdateranges": true,
    "hide_side_toolbar": false,
    "allow_symbol_change": true,
    "studies": [
      "Volume@tv-basicstudies",
      "MASimple@tv-basicstudies"
    ],
    "container_id": "tv_{selected}"
  }});
  </script>
</div>
"""
import streamlit.components.v1 as components
components.html(tv_html, height=620)

# ── Plotly custom chart (DISABLED — kept for reference) ──────
if False:
    # --- Plotly chart (custom) ---
    all_data = get_chart_data(selected, period="5y", interval="1d")

    if not all_data:
        st.caption(tr("sd.no_chart_data"))
    else:
        period_buttons = st.columns(7)
        periods = {"1W": 5, "1M": 22, "3M": 65, "6M": 130, "1Y": 252, "2Y": 504, "All": len(all_data)}

        range_key = f"chart_range_{selected}"
        if range_key not in st.session_state:
            st.session_state[range_key] = "1M"

        for i, (label, _) in enumerate(periods.items()):
            with period_buttons[i]:
                if st.button(label, key=f"btn_{label}_{selected}", use_container_width=True):
                    st.session_state[range_key] = label

        # Technical indicators toggle
        ind_col1, ind_col2, ind_col3, ind_col4 = st.columns([1, 1, 1, 1])
        with ind_col1:
            show_bb = st.checkbox(tr("sd.bb"), value=False, key=f"bb_{selected}")
        with ind_col2:
            show_ma = st.checkbox(tr("sd.ma"), value=False, key=f"ma_{selected}")
        with ind_col3:
            show_rsi = st.checkbox(tr("sd.rsi"), value=False, key=f"rsi_{selected}")
        with ind_col4:
            show_macd = st.checkbox(tr("sd.macd"), value=False, key=f"macd_{selected}")

        active_period = st.session_state[range_key]
        visible_bars = periods.get(active_period, 22)

        n = len(all_data)
        start_idx = max(0, n - visible_bars)

        dates = [d["date"] for d in all_data]
        opens = [d["open"] for d in all_data]
        highs = [d["high"] for d in all_data]
        lows = [d["low"] for d in all_data]
        closes = [d["close"] for d in all_data]
        volumes = [d["volume"] for d in all_data]

        x_idx = list(range(n))

        # Determine subplot rows: price + volume (always), + RSI, + MACD (optional)
        rows_config = [("price", 0.55), ("volume", 0.15)]
        if show_rsi:
            rows_config.append(("rsi", 0.15))
        if show_macd:
            rows_config.append(("macd", 0.15))

        # Normalize heights
        total = sum(h for _, h in rows_config)
        row_heights = [h / total for _, h in rows_config]
        n_rows = len(rows_config)

        fig = make_subplots(
            rows=n_rows, cols=1, shared_xaxes=True,
            row_heights=row_heights, vertical_spacing=0.03,
        )

        row_map = {name: i + 1 for i, (name, _) in enumerate(rows_config)}

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=x_idx, open=opens, high=highs, low=lows, close=closes,
            name="Price",
            increasing_line_color="#10B981", increasing_fillcolor="#10B981",
            decreasing_line_color="#EF4444", decreasing_fillcolor="#EF4444",
            text=dates,
            hovertext=[
                f"<b>{d}</b><br>O: {o}<br>H: {h}<br>L: {l}<br>C: {c}"
                for d, o, h, l, c in zip(dates, opens, highs, lows, closes)
            ],
            hoverinfo="text",
        ), row=row_map["price"], col=1)

        # Bollinger Bands
        if show_bb:
            bb_mid, bb_up, bb_low = _calc_bollinger(closes)
            fig.add_trace(go.Scatter(
                x=x_idx, y=bb_up, mode="lines", name="BB Upper",
                line=dict(color="rgba(168,85,247,0.6)", width=1),
                hoverinfo="skip",
            ), row=row_map["price"], col=1)
            fig.add_trace(go.Scatter(
                x=x_idx, y=bb_low, mode="lines", name="BB Lower",
                line=dict(color="rgba(168,85,247,0.6)", width=1),
                fill="tonexty", fillcolor="rgba(168,85,247,0.08)",
                hoverinfo="skip",
            ), row=row_map["price"], col=1)
            fig.add_trace(go.Scatter(
                x=x_idx, y=bb_mid, mode="lines", name="BB Mid",
                line=dict(color="rgba(168,85,247,0.8)", width=1, dash="dot"),
                hoverinfo="skip",
            ), row=row_map["price"], col=1)

        # Moving Averages
        if show_ma:
            ma20 = pd.Series(closes).rolling(20).mean().tolist()
            ma50 = pd.Series(closes).rolling(50).mean().tolist()
            fig.add_trace(go.Scatter(
                x=x_idx, y=ma20, mode="lines", name="MA 20",
                line=dict(color="#F59E0B", width=1.5),
                hoverinfo="skip",
            ), row=row_map["price"], col=1)
            fig.add_trace(go.Scatter(
                x=x_idx, y=ma50, mode="lines", name="MA 50",
                line=dict(color="#3B82F6", width=1.5),
                hoverinfo="skip",
            ), row=row_map["price"], col=1)

        # Volume
        vol_colors = ["#10B981" if (c or 0) >= (o or 0) else "#EF4444"
                      for o, c in zip(opens, closes)]
        fig.add_trace(go.Bar(
            x=x_idx, y=volumes, name="Volume",
            marker_color=vol_colors, opacity=0.5,
            text=dates,
            hovertemplate="<b>%{text}</b><br>Volume: %{y:,.0f}<extra></extra>",
        ), row=row_map["volume"], col=1)

        # RSI
        if show_rsi:
            rsi_vals = _calc_rsi(closes)
            fig.add_trace(go.Scatter(
                x=x_idx, y=rsi_vals, mode="lines", name="RSI",
                line=dict(color="#A855F7", width=1.5),
            ), row=row_map["rsi"], col=1)
            # 70/30 reference lines
            fig.add_hline(y=70, line_dash="dash", line_color="rgba(239,68,68,0.5)",
                          row=row_map["rsi"], col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="rgba(16,185,129,0.5)",
                          row=row_map["rsi"], col=1)
            fig.update_yaxes(range=[0, 100], row=row_map["rsi"], col=1, title_text="RSI")

        # MACD
        if show_macd:
            macd_line, signal_line, hist = _calc_macd(closes)
            hist_colors = ["#10B981" if h and h >= 0 else "#EF4444" for h in hist]
            fig.add_trace(go.Bar(
                x=x_idx, y=hist, name="MACD Hist",
                marker_color=hist_colors, opacity=0.6,
            ), row=row_map["macd"], col=1)
            fig.add_trace(go.Scatter(
                x=x_idx, y=macd_line, mode="lines", name="MACD",
                line=dict(color="#3B82F6", width=1.5),
            ), row=row_map["macd"], col=1)
            fig.add_trace(go.Scatter(
                x=x_idx, y=signal_line, mode="lines", name="Signal",
                line=dict(color="#F59E0B", width=1.5),
            ), row=row_map["macd"], col=1)
            fig.update_yaxes(title_text="MACD", row=row_map["macd"], col=1)

        tick_step = max(1, n // 12)
        tickvals = list(range(0, n, tick_step))
        ticktext = [dates[i][:10] for i in tickvals]

        # Dynamic height based on number of subplots
        base_height = 600
        extra = (n_rows - 2) * 120
        chart_height = base_height + extra

        fig.update_layout(
            height=chart_height,
            xaxis_rangeslider_visible=False,
            margin=dict(l=50, r=20, t=20, b=10),
            showlegend=show_bb or show_ma,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            dragmode="pan",
        )

        # Set x range on all subplots
        for r in range(1, n_rows + 1):
            fig.update_xaxes(
                range=[start_idx, n - 1],
                showgrid=False,
                row=r, col=1,
            )
        # Bottom subplot gets date labels
        fig.update_xaxes(
            tickvals=tickvals, ticktext=ticktext,
            tickangle=-30,
            row=n_rows, col=1,
        )
        fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")

        # Auto-scale price y-axis to visible range
        visible_lows = [l for l in lows[start_idx:] if l is not None]
        visible_highs = [h for h in highs[start_idx:] if h is not None]
        if visible_lows and visible_highs:
            y_min = min(visible_lows)
            y_max = max(visible_highs)
            # Include BB if active
            if show_bb:
                bb_mid, bb_up, bb_low = _calc_bollinger(closes)
                visible_bb_up = [v for v in bb_up[start_idx:] if v is not None and not pd.isna(v)]
                visible_bb_low = [v for v in bb_low[start_idx:] if v is not None and not pd.isna(v)]
                if visible_bb_up:
                    y_max = max(y_max, max(visible_bb_up))
                if visible_bb_low:
                    y_min = min(y_min, min(visible_bb_low))
            y_pad = (y_max - y_min) * 0.05 if y_max != y_min else 1
            fig.update_yaxes(
                range=[y_min - y_pad, y_max + y_pad],
                row=row_map["price"], col=1,
            )

        visible_vols = [v for v in volumes[start_idx:] if v is not None]
        if visible_vols:
            v_max = max(visible_vols)
            fig.update_yaxes(
                range=[0, v_max * 1.1],
                row=row_map["volume"], col=1,
            )

        st.plotly_chart(
            fig, use_container_width=True,
            config={
                "scrollZoom": True,
                "displayModeBar": True,
                "modeBarButtonsToAdd": ["drawline", "eraseshape"],
                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            },
        )

        st.caption(tr("sd.chart_hint"))

# ══════════════════════════════════════════════════════════════
# --- Valuation / Fair Value (yfinance + Finnhub + AI) ---
# ══════════════════════════════════════════════════════════════
with st.spinner("Loading valuation data…"):
    _val_core = get_valuation_core(selected)
    _consensus = get_analyst_consensus(selected)

if _val_core:
    st.markdown("---")
    st.subheader("💰 Fair Value Analysis")

    # ── Helper formatters (used across sections) ──────────────
    def _fmt_money(v):
        if v is None or pd.isna(v):
            return "N/A"
        if abs(v) >= 1e12: return f"${v/1e12:.2f}T"
        if abs(v) >= 1e9:  return f"${v/1e9:.2f}B"
        if abs(v) >= 1e6:  return f"${v/1e6:.0f}M"
        return f"${v:,.2f}"

    def _fmt_pct(v, decimals=1):
        return f"{v*100:+.{decimals}f}%" if v is not None and not pd.isna(v) else "N/A"

    _cp = _val_core.get("current_price")
    _bands = build_scenario_bands(_val_core, selected)

    # ══════════════════════════════════════════════════════════
    # SECTION 1: 🤖 AI Scenario Narrative (top — primary insight)
    # ══════════════════════════════════════════════════════════
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:#94a3b8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin:6px 0;">'
        '🤖 AI Scenario Narrative</div>',
        unsafe_allow_html=True,
    )

    if ai_val_available() and _bands:
        with st.spinner("Generating AI scenario analysis (Gemini 2.5 Flash)…"):
            _ai_dual = {
                "flash": get_ai_scenario_analysis(
                    selected, _val_core, _consensus, _bands, MODEL_FLASH,
                ),
            }
    else:
        _ai_dual = None
        if not ai_val_available():
            st.caption(
                "⚠️ Gemini API key not configured. "
                "Set `GEMINI_API_KEY` in `.streamlit/secrets.toml` "
                "(free tier at ai.google.dev)."
            )

    def _render_ai_result(_ai_result, label_prefix=""):
        if not _ai_result:
            st.info(f"{label_prefix}No result.")
            return
        if _ai_result.get("error"):
            st.error(f"{label_prefix}Failed: {_ai_result['error']}")
            return

        eps_basis = _ai_result.get("eps_basis", {}) or {}
        eps_val = eps_basis.get("value")
        eps_label = eps_basis.get("label", "EPS basis")
        eps_line = (
            f'<div style="font-size:0.82rem;color:#a5b4fc;margin-top:10px;'
            f'background:rgba(99,102,241,0.12);padding:6px 12px;border-radius:6px;'
            f'display:inline-block;">'
            f'<b>AI EPS basis:</b> ${eps_val:.2f} <span style="color:#94a3b8;">({eps_label})</span>'
            f'</div>'
        ) if eps_val else ""

        st.markdown(
            f'<div style="background:rgba(168,85,247,0.08);'
            f'border:1px solid rgba(168,85,247,0.3);'
            f'border-radius:10px;padding:14px 18px;margin:10px 0;">'
            f'<div style="font-size:0.75rem;color:#c4b5fd;font-weight:600;'
            f'text-transform:uppercase;letter-spacing:0.05em;">'
            f'Sector Classification</div>'
            f'<div style="font-size:1.05rem;font-weight:600;margin-top:4px;">'
            f'{_ai_result.get("sector_classification", "N/A")}</div>'
            f'<div style="font-size:0.85rem;color:#cbd5e1;margin-top:10px;'
            f'line-height:1.5;">{_ai_result.get("multiple_rationale", "")}</div>'
            f'{eps_line}'
            f'</div>',
            unsafe_allow_html=True,
        )

        ai_sc1, ai_sc2, ai_sc3 = st.columns(3)
        for col, key, title, bg, border in [
            (ai_sc1, "bear", "🐻 Bear",  "rgba(239,68,68,0.10)",  "#EF4444"),
            (ai_sc2, "base", "🎯 Base",  "rgba(59,130,246,0.10)", "#3B82F6"),
            (ai_sc3, "bull", "🚀 Bull",  "rgba(34,197,94,0.10)",  "#22C55E"),
        ]:
            sc = _ai_result.get(key) or {}
            lo = sc.get("low")
            hi = sc.get("high")
            m_lo = sc.get("multiple_low")
            m_hi = sc.get("multiple_high")
            narr = sc.get("narrative", "")

            price_line = f'${lo:,.0f} – ${hi:,.0f}' if lo is not None and hi is not None else "N/A"
            mult_line = (f'P/E {m_lo}x–{m_hi}x'
                         if m_lo is not None and m_hi is not None else '')

            up_line = ""
            if _cp and lo and hi:
                mid = (lo + hi) / 2
                up = (mid / _cp - 1) * 100
                _up_c = "#22C55E" if up > 0 else "#EF4444"
                up_line = (
                    f'<div style="font-size:0.75rem;color:#94a3b8;margin-top:2px;">'
                    f'Mid upside: <span style="color:{_up_c};font-weight:700;">'
                    f'{up:+.1f}%</span></div>'
                )

            col.markdown(
                f'<div style="background:{bg};border:1px solid {border};'
                f'border-radius:10px;padding:14px 18px;margin:6px 0;">'
                f'<div style="color:{border};font-size:0.85rem;font-weight:700;">{title}</div>'
                f'<div style="font-size:1.2rem;font-weight:800;margin:6px 0;">'
                f'{price_line}</div>'
                f'<div style="font-size:0.7rem;color:#94a3b8;">{mult_line}</div>'
                f'{up_line}'
                f'<div style="font-size:0.78rem;color:#cbd5e1;line-height:1.45;'
                f'margin-top:8px;padding-top:8px;border-top:1px solid rgba(148,163,184,0.15);">'
                f'{narr}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        risks = _ai_result.get("key_risks") or []
        catalysts = _ai_result.get("key_catalysts") or []
        if risks or catalysts:
            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown(
                    '<div style="color:#EF4444;font-weight:700;'
                    'margin-top:10px;font-size:0.85rem;">⚠️ Key Risks</div>',
                    unsafe_allow_html=True,
                )
                for r in risks:
                    st.markdown(f"- {r}")
            with rc2:
                st.markdown(
                    '<div style="color:#22C55E;font-weight:700;'
                    'margin-top:10px;font-size:0.85rem;">✨ Key Catalysts</div>',
                    unsafe_allow_html=True,
                )
                for c in catalysts:
                    st.markdown(f"- {c}")

    if _ai_dual:
        _render_ai_result(_ai_dual.get("flash"))
        st.caption(
            "Powered by Gemini 2.5 Flash · Cached 24h per ticker · "
            "AI output — not investment advice."
        )

    # ══════════════════════════════════════════════════════════
    # SECTION 2: 🎓 Analyst Consensus (Wall Street targets)
    # ══════════════════════════════════════════════════════════
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:#94a3b8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin:20px 0 6px;">'
        '🎓 Analyst Consensus (Wall Street Targets)</div>',
        unsafe_allow_html=True,
    )

    _tm = _consensus.get("target_mean")
    _tmed = _consensus.get("target_median")
    _th = _consensus.get("target_high")
    _tl = _consensus.get("target_low")

    if any([_tm, _tmed, _th, _tl]):
        # Horizontal bar chart
        bar_rows = []
        for lbl, val, clr in [
            ("Low",    _tl,  "#EF4444"),
            ("Mean",   _tm,  "#3B82F6"),
            ("Median", _tmed, "#8B5CF6"),
            ("High",   _th,  "#22C55E"),
        ]:
            if val is not None:
                bar_rows.append({"label": lbl, "val": val, "color": clr})

        if bar_rows:
            fig = go.Figure()
            for r in bar_rows:
                fig.add_trace(go.Bar(
                    y=[r["label"]], x=[r["val"]], orientation="h",
                    marker_color=r["color"],
                    text=[f"${r['val']:,.2f}"], textposition="outside",
                    name=r["label"], showlegend=False,
                ))
            if _cp:
                fig.add_vline(
                    x=_cp, line_color="#FBBF24", line_width=2, line_dash="dash",
                    annotation_text=f"Current ${_cp:,.2f}",
                    annotation_position="top right",
                    annotation_font_color="#FBBF24",
                )
            fig.update_layout(
                height=240, margin=dict(l=40, r=80, t=10, b=30),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="rgba(100,116,139,0.2)", tickprefix="$"),
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

        # Recommendation breakdown
        n = _consensus.get("n_analysts") or 0
        sb = _consensus.get("rec_strong_buy", 0)
        b  = _consensus.get("rec_buy", 0)
        h  = _consensus.get("rec_hold", 0)
        s  = _consensus.get("rec_sell", 0)
        ss = _consensus.get("rec_strong_sell", 0)
        rec_key = (_consensus.get("rec_key") or "").upper()

        meta_line = f"**Analysts: {n}**" if n else ""
        if sb + b + h + s + ss > 0:
            meta_line += (
                f" · Strong Buy {sb} · Buy {b} · Hold {h} · Sell {s} · Strong Sell {ss}"
            )
        if rec_key:
            _rec_clr = {"STRONG_BUY": "#22C55E", "BUY": "#22C55E",
                        "HOLD": "#EAB308", "SELL": "#EF4444",
                        "STRONG_SELL": "#EF4444"}.get(rec_key, "#94A3B8")
            meta_line += f' · <span style="color:{_rec_clr};font-weight:700;">{rec_key}</span>'
        if meta_line:
            st.markdown(meta_line, unsafe_allow_html=True)

        # Upside vs current
        if _cp and _tm:
            up = (_tm / _cp - 1) * 100
            _up_clr = "#22C55E" if up > 0 else "#EF4444"
            st.markdown(
                f'<div style="font-size:0.9rem;margin-top:6px;">'
                f'Mean target upside: '
                f'<span style="color:{_up_clr};font-weight:700;">{up:+.1f}%</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No analyst targets available from yfinance / Finnhub.")

    # ── Individual analyst targets (per-firm breakdown) ───────
    _indiv = get_individual_analyst_targets(selected, limit=20)
    if not _indiv.empty:
        st.markdown(
            '<div style="font-size:0.78rem;font-weight:600;color:#94a3b8;'
            'text-transform:uppercase;letter-spacing:0.05em;margin:18px 0 4px;">'
            '🏦 Individual Analyst Targets</div>',
            unsafe_allow_html=True,
        )

        # Color each bar by position vs current price
        colors = []
        for tgt in _indiv["target"]:
            if _cp and tgt > _cp * 1.1:
                colors.append("#22C55E")   # strong upside
            elif _cp and tgt > _cp:
                colors.append("#86EFAC")   # mild upside
            elif _cp and tgt > _cp * 0.9:
                colors.append("#FBBF24")   # near current
            else:
                colors.append("#EF4444")   # downside

        labels = [f"{r.firm} ({r.date})" if r.date else r.firm
                  for r in _indiv.itertuples()]

        height = max(260, 22 * len(_indiv))  # 개별 애널리스트 수에 비례, narrower than consensus
        fig_ind = go.Figure(go.Bar(
            y=labels, x=_indiv["target"].values,
            orientation="h",
            marker_color=colors,
            text=[f"${v:,.0f}" for v in _indiv["target"]],
            textposition="outside",
            textfont=dict(size=11),
            hovertemplate="<b>%{y}</b><br>Target: $%{x:,.2f}<extra></extra>",
            width=0.55,  # narrower than consensus bars
        ))
        if _cp:
            fig_ind.add_vline(
                x=_cp, line_color="#FBBF24", line_width=2, line_dash="dash",
                annotation_text=f"Current ${_cp:,.2f}",
                annotation_position="top right",
                annotation_font_color="#FBBF24",
            )
        fig_ind.update_layout(
            height=height, margin=dict(l=40, r=80, t=10, b=30),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="rgba(100,116,139,0.2)", tickprefix="$"),
            yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
            showlegend=False,
            bargap=0.4,
        )
        st.plotly_chart(fig_ind, use_container_width=True)
        st.caption(
            f"Showing {len(_indiv)} most recent analyst targets · "
            f"Source: yfinance upgrades_downgrades"
        )

    # ══════════════════════════════════════════════════════════
    # SECTION 4: 🎯 Multiple-Based Fair Value (data-only table)
    # ══════════════════════════════════════════════════════════
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:#94a3b8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin:20px 0 6px;">'
        '🎯 Multiple-Based Fair Value (Forward EPS × P/E)</div>',
        unsafe_allow_html=True,
    )
    _fv_df = build_fair_value_table(_val_core)
    if not _fv_df.empty:
        _disp = _fv_df.drop(columns=["_fv", "_upside"])
        st.dataframe(_disp, use_container_width=True, hide_index=True)
    else:
        st.info("Forward EPS unavailable — fair value table skipped.")

    # ══════════════════════════════════════════════════════════
    # SECTION 5: 🎲 Scenario Bands (Data-based: P/E percentiles)
    # ══════════════════════════════════════════════════════════
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:#94a3b8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin:20px 0 6px;">'
        '🎲 Scenario Bands (Data-based — Historical P/E Percentiles)</div>',
        unsafe_allow_html=True,
    )
    if _bands:
        sc1, sc2, sc3 = st.columns(3)
        for col, key, title, bg, border in [
            (sc1, "bear",  "🐻 Bear",  "rgba(239,68,68,0.10)",  "#EF4444"),
            (sc2, "base",  "🎯 Base",  "rgba(59,130,246,0.10)", "#3B82F6"),
            (sc3, "bull",  "🚀 Bull",  "rgba(34,197,94,0.10)",  "#22C55E"),
        ]:
            b = _bands[key]
            col.markdown(
                f'<div style="background:{bg};border:1px solid {border};'
                f'border-radius:10px;padding:14px 18px;">'
                f'<div style="font-size:0.85rem;font-weight:700;color:{border};">{title}</div>'
                f'<div style="font-size:1.3rem;font-weight:800;margin:6px 0;">'
                f'${b["low"]:,.0f} – ${b["high"]:,.0f}</div>'
                f'<div style="font-size:0.78rem;color:#94a3b8;">'
                f'P/E {b["mult_range"]}<br>{b["note"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if _bands.get("_source"):
            st.caption(f"Bands source: {_bands['_source']}")
    else:
        st.info("Forward EPS unavailable — scenario bands skipped.")

    # ══════════════════════════════════════════════════════════
    # SECTION 6: 📊 Core Financial Metrics (reference data)
    # ══════════════════════════════════════════════════════════
    st.markdown(
        '<div style="font-size:0.8rem;font-weight:600;color:#94a3b8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin:20px 0 6px;">'
        '📊 Core Financial Metrics</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price", _fmt_money(_val_core.get("current_price")))
    c2.metric("Market Cap", _fmt_money(_val_core.get("market_cap")))
    _tte = _val_core.get("trailing_eps")
    c3.metric("TTM EPS", f"${_tte:.2f}" if _tte else "N/A")
    _fe = _val_core.get("forward_eps")
    c4.metric("Forward EPS", f"${_fe:.2f}" if _fe else "N/A")

    c5, c6, c7, c8 = st.columns(4)
    _q_rev = _val_core.get("latest_q_revenue")
    c5.metric("Latest Q Revenue", _fmt_money(_q_rev) if _q_rev else "N/A")
    _yoy = _val_core.get("q_yoy") or _val_core.get("revenue_growth_yoy")
    _qoq = _val_core.get("q_qoq")
    c6.metric("Revenue YoY / QoQ",
              f"{_fmt_pct(_yoy)} / {_fmt_pct(_qoq)}" if _yoy or _qoq else "N/A")
    _gm = _val_core.get("gross_margin")
    c7.metric("Gross Margin (TTM)", _fmt_pct(_gm, 1) if _gm else "N/A")
    _om = _val_core.get("operating_margin")
    c8.metric("Operating Margin (TTM)", _fmt_pct(_om, 1) if _om else "N/A")

# --- Fundamentals (compact reference card grid) ---
st.markdown("---")
st.subheader(tr("sd.fundamentals"))
fund_cols = st.columns(4)
metrics = [
    (tr("sd.pe_ratio"), info.get("pe_ratio")),
    (tr("sd.pb_ratio"), info.get("pb_ratio")),
    (tr("sd.eps"), info.get("eps")),
    (tr("sd.roe"), f"{info.get('roe') * 100:.1f}%" if info.get("roe") else None),
    (tr("sd.beta"), info.get("beta")),
    (tr("sd.div_yield"), f"{info.get('dividend_yield') * 100:.2f}%" if info.get("dividend_yield") else None),
    (tr("sd.de_ratio"), info.get("debt_to_equity")),
    (tr("sd.avg_volume"), f"{info.get('avg_volume'):,.0f}" if info.get("avg_volume") else None),
]
for i, (label, val) in enumerate(metrics):
    with fund_cols[i % 4]:
        display = f"{val:.2f}" if isinstance(val, (int, float)) else (val or "N/A")
        st.metric(label, display)

# --- News ---
st.markdown("---")
st.subheader(tr("sd.recent_news", ticker=selected))
articles = get_stock_news(selected)
if articles:
    for a in articles[:10]:
        sentiment = a.get("sentiment_label", "Neutral")
        badge = {"Bullish": "🟢", "Bearish": "🔴"}.get(sentiment, "⚪")
        url = a.get("url", "")
        hl = a.get("headline", "")
        source = a.get("source", "")
        if url:
            st.markdown(f"{badge} [{hl}]({url}) — _{source}_")
        else:
            st.markdown(f"{badge} {hl} — _{source}_")
else:
    st.caption(tr("dash.no_news"))

# --- Company Description (expander, end) ---
if info.get("description"):
    with st.expander(tr("sd.company_desc")):
        st.write(info["description"])
