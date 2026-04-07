"""Screener page — Finviz-style stock screener with SQLite-cached fundamentals."""

import streamlit as st
import pandas as pd
import plotly.express as px

from services.market_service import (
    get_stock_list, get_screener_from_cache,
    get_fundamentals_cache_status, refresh_fundamentals_cache,
)
from services.auth_service import render_user_sidebar
from components.ui import inject_css, page_header, render_sidebar_info

st.set_page_config(page_title="Screener", page_icon="🔍", layout="wide")
inject_css()
render_sidebar_info()
render_user_sidebar()
page_header("Stock Screener", "Filter S&P 500 stocks by fundamentals")

# --- Cache Status & Refresh ---
cache_status = get_fundamentals_cache_status()
cached_count = cache_status["count"]

if cached_count > 0:
    st.caption(
        f"Cached: {cached_count} stocks | Last updated: {cache_status['newest'][:16] if cache_status['newest'] else 'N/A'}"
    )
else:
    st.warning("No fundamental data cached yet. Click 'Refresh Data' to load (takes 3-5 min, one-time).")

if st.button("Refresh Data", help="Fetch latest fundamentals for all S&P 500 stocks"):
    progress_bar = st.progress(0, text="Starting...")

    def _update_progress(current: int, total: int) -> None:
        pct = current / total
        progress_bar.progress(pct, text=f"Fetching fundamentals... {current}/{total}")

    try:
        with st.spinner("Fetching fundamentals (this may take a few minutes)..."):
            count = refresh_fundamentals_cache(progress_callback=_update_progress)
        progress_bar.progress(1.0, text=f"Done! Updated {count} stocks.")
        st.success(f"Updated {count} stocks.")
        st.rerun()
    except Exception as e:
        st.error(f"Refresh failed: {e}")

# --- Load Data ---
if cached_count > 0:
    df = get_screener_from_cache()
else:
    df = get_stock_list()

if df.empty:
    st.warning("No stock data available. Please refresh.")
    st.stop()

# --- Filters ---
st.subheader("Filters")

has_fundamentals = "pe_ratio" in df.columns and cached_count > 0

# Row 1: Sector, Industry, Search
f1, f2, f3 = st.columns(3)
with f1:
    sectors = ["All"] + sorted(df["sector"].dropna().unique().tolist())
    selected_sector = st.selectbox("Sector", sectors)
with f2:
    if "industry" in df.columns:
        if selected_sector != "All":
            industries = ["All"] + sorted(
                df[df["sector"] == selected_sector]["industry"].dropna().unique().tolist()
            )
        else:
            industries = ["All"] + sorted(df["industry"].dropna().unique().tolist())
        selected_industry = st.selectbox("Industry", industries)
    else:
        selected_industry = "All"
with f3:
    search = st.text_input("Search", placeholder="AAPL, Apple...")

# Row 2: Valuation filters
if has_fundamentals:
    st.markdown("**Valuation**")
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        pe_filter = st.selectbox("P/E", ["Any", "Under 5", "Under 10", "Under 15",
                                          "Under 20", "Under 30", "Under 50", "Over 50"])
    with v2:
        pb_filter = st.selectbox("P/B", ["Any", "Under 1", "Under 2", "Under 3",
                                          "Under 5", "Over 5"])
    with v3:
        ps_filter = st.selectbox("P/S", ["Any", "Under 1", "Under 2", "Under 5",
                                          "Under 10", "Over 10"])
    with v4:
        div_filter = st.selectbox("Dividend Yield", ["Any", "Over 0%", "Over 1%", "Over 2%",
                                                      "Over 3%", "Over 5%", "Over 7%"])

    st.markdown("**Fundamentals**")
    f4, f5, f6, f7 = st.columns(4)
    with f4:
        roe_filter = st.selectbox("ROE", ["Any", "Positive (>0%)", "Over 5%", "Over 10%",
                                           "Over 15%", "Over 20%", "Over 30%"])
    with f5:
        de_filter = st.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1",
                                                   "Under 2", "Over 2"])
    with f6:
        eps_filter = st.selectbox("EPS", ["Any", "Positive", "Negative", "Over 1",
                                           "Over 5", "Over 10"])
    with f7:
        beta_filter = st.selectbox("Beta", ["Any", "Under 0.5", "Under 1",
                                             "1 to 1.5", "1.5 to 2", "Over 2"])

    st.markdown("**Market Cap & Volume**")
    m1, m2 = st.columns(2)
    with m1:
        cap_filter = st.selectbox("Market Cap", ["Any", "Mega (>200B)", "Large (10B-200B)",
                                                   "Mid (2B-10B)", "Small (300M-2B)", "Micro (<300M)"])
    with m2:
        vol_filter = st.selectbox("Avg Volume", ["Any", "Over 100K", "Over 500K",
                                                   "Over 1M", "Over 5M"])
else:
    pe_filter = pb_filter = ps_filter = div_filter = "Any"
    roe_filter = de_filter = eps_filter = beta_filter = "Any"
    cap_filter = vol_filter = "Any"

# --- Apply Filters ---
filtered = df.copy()

if selected_sector != "All":
    filtered = filtered[filtered["sector"] == selected_sector]
if selected_industry != "All" and "industry" in filtered.columns:
    filtered = filtered[filtered["industry"] == selected_industry]
if search:
    s = search.upper()
    filtered = filtered[
        filtered["ticker"].str.contains(s, na=False)
        | filtered["name"].str.upper().str.contains(s, na=False)
    ]


def _apply_num_filter(frame: pd.DataFrame, col: str, val: str) -> pd.DataFrame:
    """Apply a numeric filter like 'Under 10', 'Over 5', '1 to 1.5'."""
    if val == "Any" or col not in frame.columns:
        return frame
    if val.startswith("Under "):
        n = float(val.split(" ")[1])
        return frame[frame[col].notna() & (frame[col] < n)]
    if val.startswith("Over ") and "%" not in val:
        n = float(val.split(" ")[1])
        return frame[frame[col].notna() & (frame[col] > n)]
    if val == "Positive" or val.startswith("Positive"):
        return frame[frame[col].notna() & (frame[col] > 0)]
    if val == "Negative":
        return frame[frame[col].notna() & (frame[col] < 0)]
    if " to " in val:
        lo, hi = [float(x) for x in val.split(" to ")]
        return frame[frame[col].notna() & (frame[col] >= lo) & (frame[col] <= hi)]
    return frame


filtered = _apply_num_filter(filtered, "pe_ratio", pe_filter)
filtered = _apply_num_filter(filtered, "pb_ratio", pb_filter)
filtered = _apply_num_filter(filtered, "ps_ratio", ps_filter)
filtered = _apply_num_filter(filtered, "eps", eps_filter)
filtered = _apply_num_filter(filtered, "debt_to_equity", de_filter)
filtered = _apply_num_filter(filtered, "beta", beta_filter)

# Dividend yield (stored as 0-1 decimal)
if div_filter != "Any" and "dividend_yield" in filtered.columns:
    pct = float(div_filter.split(" ")[1].replace("%", "")) / 100
    filtered = filtered[filtered["dividend_yield"].notna() & (filtered["dividend_yield"] > pct)]

# ROE (stored as 0-1 decimal)
if roe_filter != "Any" and "roe" in filtered.columns:
    if roe_filter.startswith("Positive"):
        filtered = filtered[filtered["roe"].notna() & (filtered["roe"] > 0)]
    elif roe_filter.startswith("Over"):
        pct = float(roe_filter.split(" ")[1].replace("%", "")) / 100
        filtered = filtered[filtered["roe"].notna() & (filtered["roe"] > pct)]

# Market cap
if cap_filter != "Any" and "market_cap" in filtered.columns:
    cap_ranges = {
        "Mega (>200B)": (200e9, None), "Large (10B-200B)": (10e9, 200e9),
        "Mid (2B-10B)": (2e9, 10e9), "Small (300M-2B)": (300e6, 2e9),
        "Micro (<300M)": (None, 300e6),
    }
    lo, hi = cap_ranges.get(cap_filter, (None, None))
    if lo is not None:
        filtered = filtered[filtered["market_cap"].notna() & (filtered["market_cap"] >= lo)]
    if hi is not None:
        filtered = filtered[filtered["market_cap"].notna() & (filtered["market_cap"] <= hi)]

# Volume
if vol_filter != "Any" and "avg_volume" in filtered.columns:
    vol_map = {"Over 100K": 1e5, "Over 500K": 5e5, "Over 1M": 1e6, "Over 5M": 5e6}
    filtered = filtered[filtered["avg_volume"].notna() & (filtered["avg_volume"] >= vol_map.get(vol_filter, 0))]

# --- Sort ---
sort_options = {"Market Cap": "market_cap", "Ticker": "ticker", "Name": "name"}
if has_fundamentals:
    sort_options.update({"P/E": "pe_ratio", "Dividend Yield": "dividend_yield",
                         "Beta": "beta", "ROE": "roe", "EPS": "eps"})
available_sorts = {k: v for k, v in sort_options.items() if v in filtered.columns}

sc1, sc2 = st.columns([2, 1])
with sc1:
    sort_by = st.selectbox("Sort By", list(available_sorts.keys()))
with sc2:
    sort_order = st.selectbox("Order", ["Descending", "Ascending"])

sort_field = available_sorts.get(sort_by, "ticker")
if sort_field in filtered.columns:
    filtered = filtered.sort_values(sort_field, ascending=(sort_order == "Ascending"), na_position="last")
filtered = filtered.reset_index(drop=True)

# --- Results ---
st.markdown("---")
st.caption(f"{len(filtered)} stocks found")

# Build display columns
base_cols = ["ticker", "name", "sector"]
fund_cols = ["market_cap", "pe_ratio", "pb_ratio", "dividend_yield",
             "eps", "roe", "beta", "debt_to_equity", "avg_volume"]
display_cols = base_cols + [c for c in fund_cols if c in filtered.columns]

display_df = filtered[display_cols].copy()

# Format display values
fmt_map = {
    "market_cap": lambda x: f"${x / 1e9:.1f}B" if pd.notna(x) and x >= 1e9
                  else f"${x / 1e6:.0f}M" if pd.notna(x) else "",
    "dividend_yield": lambda x: f"{x * 100:.2f}%" if pd.notna(x) else "",
    "roe": lambda x: f"{x * 100:.1f}%" if pd.notna(x) else "",
    "avg_volume": lambda x: f"{x / 1e6:.1f}M" if pd.notna(x) and x >= 1e6
                  else f"{x / 1e3:.0f}K" if pd.notna(x) else "",
    "pe_ratio": lambda x: f"{x:.1f}" if pd.notna(x) else "",
    "pb_ratio": lambda x: f"{x:.1f}" if pd.notna(x) else "",
    "eps": lambda x: f"{x:.2f}" if pd.notna(x) else "",
    "beta": lambda x: f"{x:.2f}" if pd.notna(x) else "",
    "debt_to_equity": lambda x: f"{x:.1f}" if pd.notna(x) else "",
}
for col, fn in fmt_map.items():
    if col in display_df.columns:
        display_df[col] = display_df[col].apply(fn)

st.dataframe(display_df, use_container_width=True, hide_index=True)

# --- Sector Distribution ---
st.subheader("Sector Distribution")
sector_counts = filtered["sector"].value_counts()

if not sector_counts.empty:
    chart_df = pd.DataFrame({
        "sector": sector_counts.index.tolist(),
        "count": sector_counts.values.tolist(),
    })
    fig = px.bar(
        chart_df, x="sector", y="count",
        labels={"sector": "Sector", "count": "Count"},
        color="count",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, coloraxis_showscale=False,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("No data to display.")
