"""Stock Detail page — Individual stock analysis with interactive candlestick chart."""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

from services.market_service import get_stock_detail, get_chart_data, search_stocks
from services.sentiment_service import get_stock_news
from services.auth_service import render_user_sidebar
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

st.set_page_config(page_title="Stock Detail", page_icon="📈", layout="wide")
inject_css()
render_user_sidebar()
render_sidebar_info()
page_header("Stock Detail", "Individual stock analysis with interactive chart")

# --- Recently viewed sidebar ---
if "recent_tickers" not in st.session_state:
    st.session_state.recent_tickers = []

with st.sidebar:
    st.subheader("Recently Viewed")
    if st.session_state.recent_tickers:
        for rt in st.session_state.recent_tickers[:8]:
            if st.button(f"📈 {rt}", key=f"recent_{rt}", use_container_width=True):
                st.session_state.recent_pick = rt
                st.rerun()
        if st.button("Clear", key="clear_recent", use_container_width=True):
            st.session_state.recent_tickers = []
            st.rerun()
    else:
        st.caption("Stocks you view will appear here.")

# --- Ticker Search ---
# Handle pick from recent
default_ticker = st.session_state.pop("recent_pick", "AAPL")

query = st.text_input("Search Ticker", placeholder="e.g. AAPL, NVDA, MSFT")

if query:
    results = search_stocks(query)
    if results:
        options = {r["ticker"]: f"{r['ticker']} — {r.get('name', '')}" for r in results}
        selected = st.selectbox("Select Stock", options.keys(), format_func=lambda x: options[x])
    else:
        selected = query.upper().strip()
        st.caption(f"No matches. Using: {selected}")
else:
    selected = st.text_input("Or enter ticker directly", value=default_ticker).upper().strip()

if not selected:
    st.stop()

# Track recently viewed (dedupe + cap at 8)
recent = st.session_state.recent_tickers
if selected in recent:
    recent.remove(selected)
recent.insert(0, selected)
st.session_state.recent_tickers = recent[:8]

# --- Stock Info ---
with st.spinner(f"Loading {selected}..."):
    info = get_stock_detail(selected)

if not info:
    st.error(f"Could not load data for {selected}")
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
c1.metric("Price", f"${price:,.2f}" if price else "N/A", delta=f"{change:+.2f}%" if change else None)
c2.metric("Market Cap", f"${info.get('market_cap', 0) / 1e9:.1f}B" if info.get("market_cap") else "N/A")
c3.metric("P/E", f"{info.get('pe_ratio'):.1f}" if info.get("pe_ratio") else "N/A")
c4.metric("52W High", f"${info.get('fifty_two_week_high'):,.2f}" if info.get("fifty_two_week_high") else "N/A")
c5.metric("52W Low", f"${info.get('fifty_two_week_low'):,.2f}" if info.get("fifty_two_week_low") else "N/A")

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

# --- Chart with mode toggle ---
st.subheader("Price Chart")

chart_mode = st.radio(
    "Chart Mode",
    ["Plotly (custom)", "TradingView (advanced)"],
    horizontal=True,
    key=f"chart_mode_{selected}",
)

if chart_mode == "TradingView (advanced)":
    # TradingView Advanced Chart Widget — full-featured live chart
    # Most US stocks use NASDAQ/NYSE prefix; let TradingView resolve automatically
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

else:
    # --- Plotly chart (custom) ---
    all_data = get_chart_data(selected, period="5y", interval="1d")

    if not all_data:
        st.caption("No chart data available.")
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
            show_bb = st.checkbox("Bollinger Bands", value=False, key=f"bb_{selected}")
        with ind_col2:
            show_ma = st.checkbox("MA (20/50)", value=False, key=f"ma_{selected}")
        with ind_col3:
            show_rsi = st.checkbox("RSI", value=False, key=f"rsi_{selected}")
        with ind_col4:
            show_macd = st.checkbox("MACD", value=False, key=f"macd_{selected}")

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

        st.caption("Drag to pan, scroll to zoom, double-click to reset.")

# --- Fundamentals ---
st.subheader("Fundamentals")
fund_cols = st.columns(4)
metrics = [
    ("P/E Ratio", info.get("pe_ratio")),
    ("P/B Ratio", info.get("pb_ratio")),
    ("EPS", info.get("eps")),
    ("ROE", f"{info.get('roe') * 100:.1f}%" if info.get("roe") else None),
    ("Beta", info.get("beta")),
    ("Dividend Yield", f"{info.get('dividend_yield') * 100:.2f}%" if info.get("dividend_yield") else None),
    ("D/E Ratio", info.get("debt_to_equity")),
    ("Avg Volume", f"{info.get('avg_volume'):,.0f}" if info.get("avg_volume") else None),
]

for i, (label, val) in enumerate(metrics):
    with fund_cols[i % 4]:
        display = f"{val:.2f}" if isinstance(val, (int, float)) else (val or "N/A")
        st.metric(label, display)

# --- Company Description ---
if info.get("description"):
    with st.expander("Company Description"):
        st.write(info["description"])

# --- News ---
st.subheader(f"Recent News — {selected}")
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
    st.caption("No recent news.")
