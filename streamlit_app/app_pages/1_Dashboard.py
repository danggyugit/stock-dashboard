"""Dashboard page — Market overview + heatmap + portfolio summary."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from services.market_service import get_indices, get_chart_data, get_heatmap_data
from services.portfolio_service import get_portfolios, get_holdings
from services.sentiment_service import get_stock_news
from services.auth_service import is_logged_in, get_or_create_user, render_user_sidebar
from services.i18n import t as tr
from components.ui import inject_css, page_header, render_sidebar_info

page_header("page.dashboard.title", "page.dashboard.subtitle")

# User context (Dashboard works without login but portfolio requires it)
_user = get_or_create_user() if is_logged_in() else None
USER_ID = _user["id"] if _user else None

# --- Market Indices ---
st.subheader(tr("dash.market_indices"))
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
st.subheader(tr("dash.index_charts"))
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
    st.caption(tr("dash.auto_refresh"))

# --- Market Heatmap ---
st.markdown("---")
st.subheader(tr("dash.heatmap_title"))
heatmap_period = st.selectbox(tr("common.period"), ["1d", "1w", "1m"], index=0, key="dash_heatmap_period")

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
    st.info(tr("dash.no_heatmap"))

# --- Portfolio Summary ---
st.markdown("---")
st.subheader(tr("dash.portfolio_summary"))

if not USER_ID:
    st.info(tr("dash.signin_portfolio"))
    portfolios = []
else:
    portfolios = get_portfolios(user_id=USER_ID)

if not portfolios and USER_ID:
    st.info(tr("dash.no_portfolio"))
else:
    portfolio_options = {p["id"]: p["name"] for p in portfolios}
    selected_ids = st.multiselect(
        tr("dash.select_portfolios"),
        options=list(portfolio_options.keys()),
        default=list(portfolio_options.keys()),
        format_func=lambda x: portfolio_options[x],
    )

    if not selected_ids:
        st.caption(tr("dash.select_help"))
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

            # Force equal height across the three summary metric cards
            st.markdown("""
            <style>
            div.st-key-port_summary_metrics [data-testid="stMetric"] {
                height: 130px !important;
                box-sizing: border-box !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
            }
            </style>
            """, unsafe_allow_html=True)

            with st.container(key="port_summary_metrics"):
                m1, m2, m3 = st.columns(3)
                m1.metric(tr("dash.total_value"), f"${total_value:,.2f}")
                m2.metric(tr("dash.total_cost"), f"${total_cost:,.2f}")
                m3.metric(tr("dash.unrealized_pnl"), f"${gain:,.2f}", delta=f"{gain_pct:+.2f}%")

            # Allocation: By Stock + By Sector
            colors = [
                "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
                "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
            ]

            alloc_col1, alloc_col2 = st.columns(2)

            with alloc_col1:
                labels = [h["ticker"] for h in all_holdings]
                values = [h.get("market_value") or h["total_cost"] for h in all_holdings]
                fig = px.pie(names=labels, values=values, hole=0.5, title=tr("dash.by_stock"))
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
                        hole=0.5, title=tr("dash.by_sector"),
                    )
                    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=40))
                    st.plotly_chart(fig, use_container_width=True)

        # Holdings news — one section per holding (logo + ticker + name header)
        st.markdown("---")
        st.subheader(tr("dash.holdings_news"))

        # Sort holdings by market value desc, dedupe by ticker
        holdings_sorted = sorted(
            all_holdings,
            key=lambda x: x.get("market_value") or x.get("total_cost") or 0,
            reverse=True,
        )
        seen_t: set[str] = set()
        unique_holdings: list[dict] = []
        for h in holdings_sorted:
            t = h.get("ticker")
            if t and t not in seen_t:
                seen_t.add(t)
                unique_holdings.append(h)

        if not unique_holdings:
            st.caption("No holdings to show news for.")
        else:
            # Inject section card styles once
            st.markdown("""
            <style>
            .news-section {
                background: linear-gradient(135deg, rgba(30,41,59,0.55), rgba(15,23,42,0.35));
                border: 1px solid rgba(59,130,246,0.18);
                border-radius: 12px;
                padding: 14px 18px;
                margin-bottom: 14px;
            }
            .news-head {
                display: flex;
                align-items: center;
                gap: 12px;
                padding-bottom: 10px;
                margin-bottom: 10px;
                border-bottom: 1px solid rgba(148,163,184,0.18);
            }
            .news-logo {
                width: 38px; height: 38px;
                border-radius: 8px;
                background: white;
                padding: 4px;
                object-fit: contain;
                flex-shrink: 0;
            }
            .news-title-stack {
                display: flex;
                flex-direction: column;
                line-height: 1.25;
                min-width: 0;
            }
            .news-ticker {
                font-size: 16px;
                font-weight: 700;
                color: #F8FAFC;
                letter-spacing: 0.3px;
            }
            .news-company {
                font-size: 12px;
                color: #94A3B8;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .news-pnl {
                margin-left: auto;
                font-size: 13px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 999px;
            }
            .news-pnl-pos { color: #34D399; background: rgba(16,185,129,0.12); }
            .news-pnl-neg { color: #F87171; background: rgba(239,68,68,0.12); }
            .news-pnl-flat { color: #94A3B8; background: rgba(148,163,184,0.12); }
            .news-list { display: flex; flex-direction: column; gap: 8px; }
            .news-item {
                display: flex;
                gap: 10px;
                align-items: flex-start;
                padding: 8px 10px;
                background: rgba(15,23,42,0.45);
                border-left: 3px solid #475569;
                border-radius: 6px;
                transition: background 0.15s ease;
            }
            .news-item:hover { background: rgba(15,23,42,0.7); }
            .news-item.bull { border-left-color: #10B981; }
            .news-item.bear { border-left-color: #EF4444; }
            .news-dot {
                font-size: 9px;
                margin-top: 5px;
                flex-shrink: 0;
            }
            .news-body { flex: 1; min-width: 0; }
            .news-headline {
                font-size: 13px;
                color: #E2E8F0;
                text-decoration: none;
                font-weight: 500;
                display: block;
                line-height: 1.4;
            }
            .news-headline:hover { color: #60A5FA; text-decoration: underline; }
            .news-source {
                font-size: 11px;
                color: #64748B;
                margin-top: 2px;
                display: block;
            }
            .news-empty {
                font-size: 12px;
                color: #64748B;
                font-style: italic;
            }
            </style>
            """, unsafe_allow_html=True)

            articles_per_ticker = 3
            for h in unique_holdings:
                t = h["ticker"]
                name = h.get("name") or t
                pnl_pct = h.get("unrealized_gain_pct")

                # Build P&L pill
                if pnl_pct is None:
                    pnl_html = ""
                else:
                    if pnl_pct > 0:
                        pnl_cls = "news-pnl-pos"
                    elif pnl_pct < 0:
                        pnl_cls = "news-pnl-neg"
                    else:
                        pnl_cls = "news-pnl-flat"
                    pnl_html = f'<span class="news-pnl {pnl_cls}">{pnl_pct:+.2f}%</span>'

                # Fetch news for this ticker
                try:
                    raw_articles = get_stock_news(t) or []
                except Exception:
                    raw_articles = []
                articles = raw_articles[:articles_per_ticker]

                # Build articles HTML
                if articles:
                    items_html = '<div class="news-list">'
                    for article in articles:
                        sentiment = article.get("sentiment_label", "Neutral")
                        sent_cls = {"Bullish": "bull", "Bearish": "bear"}.get(sentiment, "")
                        sent_dot = {"Bullish": "🟢", "Bearish": "🔴"}.get(sentiment, "⚪")
                        url = article.get("url", "")
                        headline = (article.get("headline", "") or "").replace("<", "&lt;").replace(">", "&gt;")
                        source = (article.get("source", "") or "").replace("<", "&lt;").replace(">", "&gt;")
                        if url:
                            headline_html = f'<a href="{url}" target="_blank" class="news-headline">{headline}</a>'
                        else:
                            headline_html = f'<span class="news-headline">{headline}</span>'
                        items_html += (
                            f'<div class="news-item {sent_cls}">'
                            f'<span class="news-dot">{sent_dot}</span>'
                            f'<div class="news-body">'
                            f'{headline_html}'
                            f'<span class="news-source">{source}</span>'
                            f'</div>'
                            f'</div>'
                        )
                    items_html += '</div>'
                else:
                    items_html = '<div class="news-empty">No recent news.</div>'

                logo_url = f"https://assets.parqet.com/logos/symbol/{t}?format=png"
                section_html = (
                    '<div class="news-section">'
                    '<div class="news-head">'
                    f'<img src="{logo_url}" class="news-logo" '
                    f"onerror=\"this.style.background='#1e293b';this.src='';\"/>"
                    '<div class="news-title-stack">'
                    f'<span class="news-ticker">{t}</span>'
                    f'<span class="news-company">{name}</span>'
                    '</div>'
                    f'{pnl_html}'
                    '</div>'
                    f'{items_html}'
                    '</div>'
                )
                st.markdown(section_html, unsafe_allow_html=True)
