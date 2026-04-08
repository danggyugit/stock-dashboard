"""Heatmap page — S&P 500 sector treemap with SQLite cache."""

import streamlit as st
import plotly.express as px
import pandas as pd

from services.market_service import (
    get_heatmap_data, get_heatmap_cache_status, refresh_heatmap_cache,
    heatmap_cache_age_hours,
)
from services.auth_service import render_user_sidebar
from components.ui import inject_css, page_header, stock_logo_url, render_sidebar_info

page_header("page.heatmap.title", "page.heatmap.subtitle")

# Cache status & refresh
cache_status = get_heatmap_cache_status()
age_hours = heatmap_cache_age_hours()

col_info, col_btn = st.columns([3, 1])
with col_info:
    if cache_status["count"] > 0:
        age_label = ""
        if age_hours is not None:
            if age_hours < 1:
                age_label = f" • Updated {int(age_hours * 60)}m ago"
            elif age_hours < 24:
                age_label = f" • Updated {age_hours:.1f}h ago"
                if age_hours > 12:
                    age_label += " ⚠️ stale"
            else:
                age_label = f" • Updated {int(age_hours / 24)}d ago ⚠️ stale"
        st.caption(f"Cached: {cache_status['count']} stocks | Last: {cache_status['last_date']}{age_label}")
    else:
        st.warning("No cached data. Click Refresh to load.")
with col_btn:
    if st.button("Refresh Data", key="heatmap_refresh"):
        progress = st.progress(0, text="Starting...")

        def _cb(step: int, total: int, msg: str = "") -> None:
            progress.progress(step / total, text=msg)

        try:
            with st.spinner("Refreshing heatmap data..."):
                count = refresh_heatmap_cache(progress_callback=_cb)
            progress.progress(1.0, text=f"Done! {count} stocks updated.")
            st.rerun()
        except Exception as e:
            st.error(f"Refresh failed: {e}")

# Period + view mode selector
ctrl_col1, ctrl_col2 = st.columns([1, 1])
with ctrl_col1:
    period = st.selectbox("Period", ["1d", "1w", "1m", "3m", "ytd", "1y"], index=0)
with ctrl_col2:
    view_mode = st.radio(
        "View", ["Treemap", "Card Grid (with logos)"],
        horizontal=True, key="heatmap_view",
    )

data = get_heatmap_data(period)

sectors = data.get("sectors", [])
if not sectors:
    st.info("No heatmap data. Click 'Refresh Data' to load.")
    st.stop()

# Build treemap
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


def _change_color(pct: float) -> tuple[str, str]:
    """Return (background, border) color for a change percent."""
    if pct >= 3:
        return "rgba(22, 163, 74, 0.55)", "#16A34A"
    if pct >= 1:
        return "rgba(22, 163, 74, 0.35)", "#16A34A"
    if pct > 0:
        return "rgba(22, 101, 52, 0.30)", "#166534"
    if pct == 0:
        return "rgba(71, 85, 105, 0.30)", "#475569"
    if pct > -1:
        return "rgba(153, 27, 27, 0.30)", "#991B1B"
    if pct > -3:
        return "rgba(220, 38, 38, 0.40)", "#DC2626"
    return "rgba(220, 38, 38, 0.60)", "#DC2626"


if view_mode == "Treemap":
    fig = px.treemap(
        df, path=["sector", "ticker"], values="market_cap",
        color="change_pct",
        color_continuous_scale=["#DC2626", "#991B1B", "#1E293B", "#166534", "#16A34A"],
        color_continuous_midpoint=0,
        custom_data=["name", "change_label", "market_cap", "change_pct"],
        title=f"S&P 500 Heatmap — {period.upper()} Change",
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>%{customdata[1]}",
        textfont=dict(size=24, family="sans-serif"),
        hovertemplate="<b>%{customdata[0]}</b><br>"
                      "Ticker: %{label}<br>"
                      "Change: %{customdata[1]}<br>"
                      "Market Cap: $%{customdata[2]:,.0f}<extra></extra>",
    )
    fig.update_layout(
        height=800, margin=dict(l=0, r=0, t=40, b=0),
        coloraxis_colorbar=dict(title="Change %", tickformat="+.2f"),
        uniformtext=dict(minsize=10, mode="hide"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    # --- Card Grid View with logos ---
    st.markdown("""
    <style>
    .heatmap-card {
        border-radius: 10px;
        padding: 12px 10px;
        text-align: center;
        margin-bottom: 8px;
        border: 1px solid;
        transition: transform 0.15s, box-shadow 0.15s;
        height: 130px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
    }
    .heatmap-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }
    .heatmap-card img {
        width: 36px;
        height: 36px;
        border-radius: 6px;
        background: white;
        padding: 3px;
        object-fit: contain;
    }
    .heatmap-card .ticker {
        font-size: 14px;
        font-weight: 700;
        color: #F8FAFC;
    }
    .heatmap-card .change {
        font-size: 13px;
        font-weight: 600;
    }
    .heatmap-card .change-up { color: #10B981; }
    .heatmap-card .change-down { color: #EF4444; }
    </style>
    """, unsafe_allow_html=True)

    # Sort sectors by market cap, render each
    for sector in sectors:
        # Sort stocks by market cap desc, take top 24
        sector_stocks = sorted(
            sector["stocks"],
            key=lambda x: x.get("market_cap") or 0,
            reverse=True,
        )[:24]

        if not sector_stocks:
            continue

        st.markdown(f"### {sector['name']}")
        cols_per_row = 8

        for row_start in range(0, len(sector_stocks), cols_per_row):
            row_stocks = sector_stocks[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, stock in zip(cols, row_stocks):
                ticker = stock["ticker"]
                change = stock.get("change_pct") or 0
                bg, border = _change_color(change)
                change_class = "change-up" if change >= 0 else "change-down"
                arrow = "▲" if change >= 0 else "▼"
                logo_url = stock_logo_url(ticker)

                with col:
                    st.markdown(f"""
                    <div class="heatmap-card" style="background:{bg}; border-color:{border};">
                        <img src="{logo_url}" onerror="this.style.display='none'"/>
                        <div class="ticker">{ticker}</div>
                        <div class="change {change_class}">{arrow} {change:+.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

# Sector summary
st.subheader("Sector Summary")
sector_rows = []
for s in sectors:
    sector_rows.append({
        "Sector": s["name"],
        "Stocks": len(s["stocks"]),
        "Avg Change (%)": s.get("avg_change_pct"),
        "Total Market Cap": f"${s.get('total_market_cap', 0) / 1e12:.2f}T",
    })
st.dataframe(pd.DataFrame(sector_rows), use_container_width=True, hide_index=True)

# --- Top Gainers / Losers (Card Grid) ---
st.subheader("Top Movers")

st.markdown("""
<style>
.mover-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5));
    border-left: 4px solid;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 12px;
    transition: all 0.2s;
}
.mover-card:hover {
    transform: translateX(4px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.mover-up { border-left-color: #10B981; }
.mover-down { border-left-color: #EF4444; }
.mover-logo {
    width: 38px; height: 38px;
    border-radius: 6px;
    background: white;
    padding: 3px;
    object-fit: contain;
    flex-shrink: 0;
}
.mover-info { flex: 1; min-width: 0; }
.mover-ticker { font-size: 15px; font-weight: 700; color: #F8FAFC; }
.mover-name {
    font-size: 11px;
    color: #94A3B8;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.mover-stats { text-align: right; flex-shrink: 0; }
.mover-price { font-size: 13px; color: #CBD5E1; }
.mover-change { font-size: 14px; font-weight: 700; }
.mover-change-up { color: #10B981; }
.mover-change-down { color: #EF4444; }
</style>
""", unsafe_allow_html=True)

all_stocks = []
for sector in sectors:
    for stock in sector["stocks"]:
        if stock.get("change_pct") is not None:
            all_stocks.append(stock)

all_stocks.sort(key=lambda x: x["change_pct"], reverse=True)


def _render_mover_card(stock: dict, is_up: bool) -> str:
    """Render a single top mover card as HTML."""
    ticker = stock["ticker"]
    name = (stock.get("name") or ticker)[:28]
    change = stock.get("change_pct") or 0
    price = stock.get("price")
    arrow = "▲" if is_up else "▼"
    card_class = "mover-up" if is_up else "mover-down"
    chg_class = "mover-change-up" if is_up else "mover-change-down"
    logo_url = stock_logo_url(ticker)
    price_str = f"${price:,.2f}" if price else ""

    return f"""
    <div class="mover-card {card_class}">
        <img src="{logo_url}" class="mover-logo" onerror="this.style.display='none'"/>
        <div class="mover-info">
            <div class="mover-ticker">{ticker}</div>
            <div class="mover-name">{name}</div>
        </div>
        <div class="mover-stats">
            <div class="mover-price">{price_str}</div>
            <div class="mover-change {chg_class}">{arrow} {change:+.2f}%</div>
        </div>
    </div>
    """


col_gain, col_lose = st.columns(2)
with col_gain:
    st.markdown("**📈 Top 10 Gainers**")
    gainers = all_stocks[:10]
    cards_html = "".join(_render_mover_card(s, True) for s in gainers)
    st.markdown(cards_html, unsafe_allow_html=True)

with col_lose:
    st.markdown("**📉 Top 10 Losers**")
    losers = all_stocks[-10:][::-1]
    cards_html = "".join(_render_mover_card(s, False) for s in losers)
    st.markdown(cards_html, unsafe_allow_html=True)

if data.get("updated_at"):
    st.caption(f"Updated: {data['updated_at']}")
