"""Dashboard page — Market overview + heatmap + portfolio summary."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from services.market_service import get_indices, get_chart_data, get_heatmap_data
from services.portfolio_service import get_portfolios, get_holdings
from services.sentiment_service import get_stock_news
from services.auth_service import is_logged_in, get_or_create_user, render_user_sidebar
from components.ui import inject_css, page_header, render_sidebar_info

page_header("Dashboard", "Real-time market overview and portfolio summary")

# User context (Dashboard works without login but portfolio requires it)
_user = get_or_create_user() if is_logged_in() else None
USER_ID = _user["id"] if _user else None

# --- Market Indices ---
st.subheader("Market Indices")
indices = get_indices()

if indices:
    cols = st.columns(len(indices))
    for i, idx in enumerate(indices):
        with cols[i]:
            price = idx.get("price")
            change = idx.get("change_pct")
            st.metric(
                label=idx["name"],
                value=f"{price:,.2f}" if price else "N/A",
                delta=f"{change:+.2f}%" if change is not None else None,
            )

# --- Mini Index Charts ---
st.subheader("Index Charts")
index_tickers = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^VIX": "VIX"}
chart_cols = st.columns(4)

# For x-axis range: extract actual trading date from data
from datetime import datetime as _dt, timedelta as _td

for i, (ticker, name) in enumerate(index_tickers.items()):
    with chart_cols[i]:
        is_vix = ticker == "^VIX"
        if is_vix:
            data = get_chart_data(ticker, period="1mo", interval="1d")
            label = f"{name} (1M)"
        else:
            data = get_chart_data(ticker, period="1d", interval="5m")
            label = f"{name} (1D)"
            # Need at least 5 points for a meaningful chart, otherwise fallback
            if not data or len(data) < 5:
                data = get_chart_data(ticker, period="5d", interval="5m")
                label = f"{name} (5D)"

        if not data:
            st.caption(f"{name}: No data")
            continue

        dates = [d["date"] for d in data]
        closes = [d["close"] for d in data]
        valid = [c for c in closes if c is not None]
        if not valid:
            st.caption(f"{name}: No data")
            continue

        # Color from Market Indices change_pct (accurate)
        idx_match = next((idx for idx in indices if idx["ticker"] == ticker), None)
        change_pct = idx_match.get("change_pct", 0) if idx_match else 0
        today_up = (change_pct or 0) >= 0
        color = "#10B981" if today_up else "#EF4444"
        fill_color = "rgba(16,185,129,0.15)" if today_up else "rgba(239,68,68,0.15)"

        y_min = min(valid)
        y_max = max(valid)
        y_pad = (y_max - y_min) * 0.1 if y_max != y_min else 1

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=[y_min] * len(dates), mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=closes, mode="lines",
            line=dict(color=color, width=2),
            fill="tonexty", fillcolor=fill_color,
            name=name,
        ))

        # x-axis: intraday = time labels, VIX = date labels
        x_range = None
        if not is_vix and "1D" in label and dates:
            trading_date = dates[0][:10]
            x_range = [f"{trading_date} 09:30:00", f"{trading_date} 16:00:00"]

        fig.update_layout(
            title=dict(text=label, font=dict(size=14)),
            height=200, margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(
                showgrid=False, showticklabels=True,
                range=x_range,
                tickformat="%H:%M" if not is_vix else "%m/%d",
                nticks=5,
                tickfont=dict(size=9),
            ),
            yaxis=dict(showgrid=False, showticklabels=True,
                       range=[y_min - y_pad, y_max + y_pad]),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

# --- Auto-refresh: re-fetch intraday charts every 5 min during market hours ---
_now = _dt.now()
_ny_offset = -4  # EDT
_ny_hour = (_now.hour + _ny_offset) % 24 if _now.hour + _ny_offset >= 0 else _now.hour + _ny_offset + 24
_weekday = _now.weekday()
_market_is_open = _weekday < 5 and 9 <= _ny_hour < 16

if _market_is_open:
    # Clear intraday chart cache so next rerun gets fresh data
    from services.market_service import _get_chart_data_cached
    _get_chart_data_cached.clear()
    # Use Streamlit's built-in auto-rerun via HTML meta refresh (5 min = 300s)
    st.markdown(
        '<meta http-equiv="refresh" content="300">',
        unsafe_allow_html=True,
    )
    st.caption("Auto-refreshing every 5 minutes (market open)")

# --- Market Heatmap ---
st.markdown("---")
st.subheader("S&P 500 Heatmap")
heatmap_period = st.selectbox("Period", ["1d", "1w", "1m"], index=0, key="dash_heatmap_period")

hm_data = get_heatmap_data(heatmap_period)

sectors = hm_data.get("sectors", [])
if sectors:
    rows = []
    for sector in sectors:
        for stock in sector["stocks"]:
            change = stock.get("change_pct")
            rows.append({
                "sector": sector["name"],
                "ticker": stock["ticker"],
                "name": stock.get("name", stock["ticker"]),
                "market_cap": stock.get("market_cap") or 1_000_000_000,
                "change_pct": round(change, 2) if change is not None else 0.0,
            })

    df = pd.DataFrame(rows)
    df["change_pct"] = df["change_pct"].round(2)
    df["change_label"] = df["change_pct"].apply(lambda x: f"{x:+.2f}%")
    fig = px.treemap(
        df, path=["sector", "ticker"], values="market_cap",
        color="change_pct",
        color_continuous_scale=["#DC2626", "#991B1B", "#1E293B", "#166534", "#16A34A"],
        color_continuous_midpoint=0,
        custom_data=["name", "change_label"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]}",
        textfont=dict(size=22, family="sans-serif"),
    )
    fig.update_layout(
        height=500, margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_colorbar=dict(title="Change %", tickformat="+.2f"),
        uniformtext=dict(minsize=10, mode="hide"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No heatmap data cached. Go to Heatmap page and click 'Refresh Data'.")

# --- Portfolio Summary ---
st.markdown("---")
st.subheader("Portfolio Summary")

if not USER_ID:
    st.info("🔒 Sign in to see your portfolio summary.")
    portfolios = []
else:
    portfolios = get_portfolios(user_id=USER_ID)

if not portfolios and USER_ID:
    st.info("No portfolios yet. Go to the Portfolio page to create one.")
else:
    portfolio_options = {p["id"]: p["name"] for p in portfolios}
    selected_ids = st.multiselect(
        "Select Portfolios",
        options=list(portfolio_options.keys()),
        default=list(portfolio_options.keys()),
        format_func=lambda x: portfolio_options[x],
    )

    if not selected_ids:
        st.caption("Select at least one portfolio above to see summary and news.")
    else:
        all_holdings = []
        total_value = 0.0
        total_cost = 0.0

        for pid in selected_ids:
            data = get_holdings(pid)
            if data and data.get("holdings"):
                all_holdings.extend(data["holdings"])
                total_value += data["total_value"]
                total_cost += data["total_cost"]

        if all_holdings:
            gain = total_value - total_cost
            gain_pct = (gain / total_cost * 100) if total_cost else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Value", f"${total_value:,.2f}")
            m2.metric("Total Cost", f"${total_cost:,.2f}")
            m3.metric("Unrealized P&L", f"${gain:,.2f}", delta=f"{gain_pct:+.2f}%")

            # Allocation: By Stock + By Sector
            colors = [
                "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
                "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
            ]

            alloc_col1, alloc_col2 = st.columns(2)

            with alloc_col1:
                labels = [h["ticker"] for h in all_holdings]
                values = [h.get("market_value") or h["total_cost"] for h in all_holdings]
                fig = px.pie(names=labels, values=values, hole=0.5, title="By Stock")
                fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=40))
                st.plotly_chart(fig, use_container_width=True)

            with alloc_col2:
                sector_totals: dict[str, float] = {}
                for h in all_holdings:
                    sector = h.get("sector") or "Unknown"
                    value = h.get("market_value") or h["total_cost"]
                    sector_totals[sector] = sector_totals.get(sector, 0) + value
                if sector_totals:
                    fig = px.pie(
                        names=list(sector_totals.keys()),
                        values=list(sector_totals.values()),
                        hole=0.5, title="By Sector",
                    )
                    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=40))
                    st.plotly_chart(fig, use_container_width=True)

        # Holdings news — fetch for all holdings, group by ticker
        st.subheader("Holdings News")
        # Sort tickers by market value desc so largest positions appear first
        tickers_sorted = [
            h["ticker"] for h in sorted(
                all_holdings,
                key=lambda x: x.get("market_value") or x.get("total_cost") or 0,
                reverse=True,
            )
        ]
        # Dedupe while preserving order
        seen_t: set[str] = set()
        tickers = [t for t in tickers_sorted if not (t in seen_t or seen_t.add(t))]

        if not tickers:
            st.caption("No holdings to show news for.")
        else:
            articles_per_ticker = 2  # show 2 articles per ticker
            news_by_ticker: dict[str, list[dict]] = {}
            for t in tickers:
                try:
                    articles = get_stock_news(t)
                    if articles:
                        news_by_ticker[t] = articles[:articles_per_ticker]
                except Exception:
                    pass

            if news_by_ticker:
                for t in tickers:
                    if t not in news_by_ticker:
                        continue
                    for article in news_by_ticker[t]:
                        sentiment = article.get("sentiment_label", "Neutral")
                        badge = {"Bullish": "🟢", "Bearish": "🔴"}.get(sentiment, "⚪")
                        url = article.get("url", "")
                        headline = article.get("headline", "")
                        source = article.get("source", "")
                        if url:
                            st.markdown(f"{badge} **[{t}]** [{headline}]({url}) — _{source}_")
                        else:
                            st.markdown(f"{badge} **[{t}]** {headline} — _{source}_")
            else:
                st.caption("No recent news found for your holdings.")
