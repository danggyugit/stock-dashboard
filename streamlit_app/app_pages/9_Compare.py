"""Stock Comparison page — Compare 2-5 stocks side by side."""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from services.market_service import get_stock_detail, get_chart_data
from services.auth_service import render_user_sidebar
from components.ui import inject_css, page_header, stock_logo_url, render_sidebar_info

page_header("Stock Comparison", "Compare 2-5 stocks side by side")

# --- Ticker Input ---
default_tickers = "AAPL, MSFT, NVDA, GOOGL"
ticker_input = st.text_input(
    "Enter 2-5 tickers (comma-separated)",
    value=default_tickers,
    key="compare_input",
)

# Period
period_label = st.selectbox(
    "Period",
    ["1M", "3M", "6M", "1Y", "2Y", "5Y"],
    index=3,
    key="compare_period",
)
period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo",
              "1Y": "1y", "2Y": "2y", "5Y": "5y"}
period = period_map[period_label]

if not ticker_input:
    st.info("Enter ticker symbols above to compare.")
    st.stop()

tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()][:5]
if len(tickers) < 2:
    st.warning("Enter at least 2 tickers.")
    st.stop()

# --- Fetch all data ---
infos: dict[str, dict] = {}
chart_data: dict[str, list] = {}

with st.spinner(f"Loading {len(tickers)} stocks..."):
    for t in tickers:
        info = get_stock_detail(t)
        if info:
            infos[t] = info
        data = get_chart_data(t, period=period, interval="1d")
        if data:
            chart_data[t] = data

if not infos:
    st.error("Could not load any stock data.")
    st.stop()

# --- Header cards ---
st.subheader("Overview")

card_css = """
<style>
.compare-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5));
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px;
    padding: 14px;
    text-align: center;
    transition: all 0.2s;
}
.compare-card:hover {
    border-color: rgba(59,130,246,0.6);
    transform: translateY(-2px);
}
.compare-logo {
    width: 44px; height: 44px;
    border-radius: 8px;
    background: white;
    padding: 4px;
    object-fit: contain;
    margin-bottom: 8px;
}
.compare-ticker { font-size: 16px; font-weight: 700; color: #F8FAFC; }
.compare-name {
    font-size: 11px;
    color: #94A3B8;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.compare-price { font-size: 18px; font-weight: 700; color: #F8FAFC; margin-top: 6px; }
.compare-change { font-size: 13px; font-weight: 600; padding: 2px 8px; border-radius: 999px; margin-top: 4px; display: inline-block; }
.cc-up { background: rgba(16,185,129,0.15); color: #10B981; }
.cc-down { background: rgba(239,68,68,0.15); color: #EF4444; }
</style>
"""
st.markdown(card_css, unsafe_allow_html=True)

cols = st.columns(len(tickers))
for col, t in zip(cols, tickers):
    info = infos.get(t, {})
    price = info.get("price")
    change = info.get("change_pct") or 0
    is_up = change >= 0
    arrow = "▲" if is_up else "▼"
    chg_class = "cc-up" if is_up else "cc-down"
    name = (info.get("name") or t)[:20]
    logo = stock_logo_url(t)

    with col:
        st.markdown(f"""
        <div class="compare-card">
            <img src="{logo}" class="compare-logo" onerror="this.style.display='none'"/>
            <div class="compare-ticker">{t}</div>
            <div class="compare-name">{name}</div>
            <div class="compare-price">${price:,.2f}</div>
            <div class="compare-change {chg_class}">{arrow} {change:+.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

# --- Normalized Performance Chart ---
st.subheader("Normalized Performance (rebased to 100)")

colors = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6"]
fig = go.Figure()

for i, t in enumerate(tickers):
    data = chart_data.get(t, [])
    if not data:
        continue
    dates = [d["date"] for d in data]
    closes = [d["close"] for d in data]
    if not closes or not closes[0]:
        continue
    base = closes[0]
    normalized = [(c / base) * 100 if c else None for c in closes]

    fig.add_trace(go.Scatter(
        x=dates, y=normalized, mode="lines",
        name=t,
        line=dict(color=colors[i % len(colors)], width=2),
        hovertemplate=f"<b>{t}</b><br>%{{x}}<br>%{{y:.2f}}<extra></extra>",
    ))

fig.add_hline(y=100, line_dash="dot", line_color="rgba(148,163,184,0.4)")
fig.update_layout(
    height=450,
    yaxis_title="Indexed Value (start = 100)",
    margin=dict(l=50, r=20, t=20, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
)
fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
fig.update_xaxes(showgrid=False)
st.plotly_chart(fig, use_container_width=True)

# --- Returns Bar Chart ---
st.subheader(f"{period_label} Return Comparison")
returns = []
for t in tickers:
    data = chart_data.get(t, [])
    if data and len(data) >= 2 and data[0]["close"] and data[-1]["close"]:
        ret = ((data[-1]["close"] - data[0]["close"]) / data[0]["close"]) * 100
        returns.append({"ticker": t, "return": round(ret, 2)})

if returns:
    rdf = pd.DataFrame(returns).sort_values("return", ascending=True)
    bar_colors = ["#10B981" if r >= 0 else "#EF4444" for r in rdf["return"]]
    bar_fig = go.Figure(go.Bar(
        x=rdf["return"], y=rdf["ticker"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{r:+.2f}%" for r in rdf["return"]],
        textposition="outside",
    ))
    bar_fig.update_layout(
        height=max(200, len(returns) * 50),
        margin=dict(l=20, r=20, t=10, b=20),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Return (%)",
    )
    bar_fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.1)")
    bar_fig.update_yaxes(showgrid=False)
    st.plotly_chart(bar_fig, use_container_width=True)

# --- Fundamentals Comparison Table ---
st.subheader("Fundamentals Comparison")

metrics_rows = []
for t in tickers:
    info = infos.get(t, {})
    metrics_rows.append({
        "Ticker": t,
        "Name": (info.get("name") or t)[:25],
        "Price": f"${info.get('price'):,.2f}" if info.get("price") else "N/A",
        "Market Cap": f"${info.get('market_cap', 0) / 1e9:.1f}B" if info.get("market_cap") else "N/A",
        "P/E": f"{info.get('pe_ratio'):.1f}" if info.get("pe_ratio") else "N/A",
        "P/B": f"{info.get('pb_ratio'):.1f}" if info.get("pb_ratio") else "N/A",
        "EPS": f"{info.get('eps'):.2f}" if info.get("eps") else "N/A",
        "ROE": f"{info.get('roe') * 100:.1f}%" if info.get("roe") else "N/A",
        "Div Yield": f"{info.get('dividend_yield') * 100:.2f}%" if info.get("dividend_yield") else "N/A",
        "Beta": f"{info.get('beta'):.2f}" if info.get("beta") else "N/A",
        "52W High": f"${info.get('fifty_two_week_high'):,.2f}" if info.get("fifty_two_week_high") else "N/A",
        "52W Low": f"${info.get('fifty_two_week_low'):,.2f}" if info.get("fifty_two_week_low") else "N/A",
    })

st.dataframe(pd.DataFrame(metrics_rows), use_container_width=True, hide_index=True)

# --- Radar Chart for visual comparison ---
st.subheader("Visual Profile (normalized)")

# Pick numeric metrics
radar_metrics = ["pe_ratio", "pb_ratio", "roe", "dividend_yield", "beta"]
radar_labels = ["P/E", "P/B", "ROE", "Div Yield", "Beta"]

# Collect raw values
raw_data: dict[str, list[float]] = {}
for t in tickers:
    info = infos.get(t, {})
    raw_data[t] = [info.get(m) or 0 for m in radar_metrics]

# Normalize each metric to 0-1 across tickers (so radar is comparable)
norm_data: dict[str, list[float]] = {t: [] for t in tickers}
for i in range(len(radar_metrics)):
    vals = [raw_data[t][i] for t in tickers]
    v_max = max(vals) if vals else 0
    v_min = min(vals) if vals else 0
    v_range = v_max - v_min if v_max != v_min else 1
    for t in tickers:
        normalized = (raw_data[t][i] - v_min) / v_range if v_range else 0
        norm_data[t].append(normalized)

radar_fig = go.Figure()
for i, t in enumerate(tickers):
    radar_fig.add_trace(go.Scatterpolar(
        r=norm_data[t] + [norm_data[t][0]],  # close the loop
        theta=radar_labels + [radar_labels[0]],
        fill="toself",
        name=t,
        line=dict(color=colors[i % len(colors)]),
        opacity=0.6,
    ))

radar_fig.update_layout(
    polar=dict(
        radialaxis=dict(visible=True, range=[0, 1], showticklabels=False),
        bgcolor="rgba(15,23,42,0.3)",
    ),
    height=450,
    margin=dict(l=20, r=20, t=20, b=20),
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=-0.1),
)
st.plotly_chart(radar_fig, use_container_width=True)
st.caption("Each metric is normalized 0-1 across the selected tickers. Larger area = stronger relative profile.")
