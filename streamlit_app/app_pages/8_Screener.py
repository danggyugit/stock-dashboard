"""Screener page — Finviz-style stock screener with SQLite-cached fundamentals."""

import streamlit as st
import pandas as pd
import plotly.express as px

from services.market_service import (
    get_stock_list, get_screener_from_cache,
    get_fundamentals_cache_status, refresh_fundamentals_cache,
)
from services.auth_service import render_user_sidebar
from services.i18n import t as tr
from components.ui import inject_css, page_header, render_sidebar_info

page_header("page.screener.title", "page.screener.subtitle")

# --- Cache Status & Refresh ---
cache_status = get_fundamentals_cache_status()
cached_count = cache_status["count"]

if cached_count > 0:
    st.caption(tr(
        "scr.cached_status",
        n=cached_count,
        ts=cache_status['newest'][:16] if cache_status['newest'] else "N/A",
    ))
else:
    st.warning(tr("scr.cache_warning"))

if st.button(tr("common.refresh"), help=tr("scr.refresh_help")):
    progress_bar = st.progress(0, text=tr("scr.starting"))

    def _update_progress(current: int, total: int) -> None:
        pct = current / total
        progress_bar.progress(pct, text=tr("scr.fetching_progress", cur=current, total=total))

    try:
        with st.spinner(tr("scr.refreshing")):
            count = refresh_fundamentals_cache(progress_callback=_update_progress)
        progress_bar.progress(1.0, text=tr("scr.done", n=count))
        st.success(tr("scr.refresh_done", n=count))
        st.rerun()
    except Exception as e:
        st.error(tr("scr.refresh_failed", e=e))

# --- Load Data ---
if cached_count > 0:
    df = get_screener_from_cache()
else:
    df = get_stock_list()

if df.empty:
    st.warning(tr("scr.no_data"))
    st.stop()

# --- Filters ---
st.subheader(tr("scr.filters"))

has_fundamentals = "pe_ratio" in df.columns and cached_count > 0

# Defaults stored in session_state so the table reflects whatever was
# last applied — no rerun until the user clicks "Apply Filters".
_DEFAULTS = {
    "scr_sector":   "All",
    "scr_industry": "All",
    "scr_search":   "",
    "scr_pe":       "Any",
    "scr_pb":       "Any",
    "scr_ps":       "Any",
    "scr_div":      "Any",
    "scr_roe":      "Any",
    "scr_de":       "Any",
    "scr_eps":      "Any",
    "scr_beta":     "Any",
    "scr_cap":      "Any",
    "scr_vol":      "Any",
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

# All filter widgets live INSIDE a single st.form so changing them
# does not trigger a full page rerun. The filtered table is rebuilt
# only when "Apply Filters" or "Reset" is clicked.
with st.form("screener_filters"):
    # Row 1: Sector / Industry / Search
    f1, f2, f3 = st.columns(3)
    with f1:
        sectors = ["All"] + sorted(df["sector"].dropna().unique().tolist())
        selected_sector = st.selectbox(
            tr("scr.sector"), sectors,
            index=sectors.index(st.session_state["scr_sector"])
                  if st.session_state["scr_sector"] in sectors else 0,
            key="scr_sector_widget",
        )
    with f2:
        if "industry" in df.columns:
            # Industry list depends on sector — recompute from the
            # form's CURRENT selectbox value (not session_state, which
            # reflects the last applied state)
            base = df if selected_sector == "All" else df[df["sector"] == selected_sector]
            industries = ["All"] + sorted(base["industry"].dropna().unique().tolist())
            selected_industry = st.selectbox(
                tr("scr.industry"), industries,
                index=industries.index(st.session_state["scr_industry"])
                      if st.session_state["scr_industry"] in industries else 0,
                key="scr_industry_widget",
            )
        else:
            selected_industry = "All"
    with f3:
        search = st.text_input(
            tr("common.search"),
            value=st.session_state["scr_search"],
            placeholder=tr("scr.search_placeholder"),
            key="scr_search_widget",
        )

    # Row 2: Valuation filters
    if has_fundamentals:
        st.markdown(f"**{tr('scr.valuation')}**")
        v1, v2, v3, v4 = st.columns(4)
        _pe_opts = ["Any", "Under 5", "Under 10", "Under 15",
                    "Under 20", "Under 30", "Under 50", "Over 50"]
        _pb_opts = ["Any", "Under 1", "Under 2", "Under 3", "Under 5", "Over 5"]
        _ps_opts = ["Any", "Under 1", "Under 2", "Under 5", "Under 10", "Over 10"]
        _div_opts = ["Any", "Over 0%", "Over 1%", "Over 2%",
                     "Over 3%", "Over 5%", "Over 7%"]
        with v1:
            pe_filter = st.selectbox("P/E", _pe_opts,
                index=_pe_opts.index(st.session_state["scr_pe"])
                      if st.session_state["scr_pe"] in _pe_opts else 0)
        with v2:
            pb_filter = st.selectbox("P/B", _pb_opts,
                index=_pb_opts.index(st.session_state["scr_pb"])
                      if st.session_state["scr_pb"] in _pb_opts else 0)
        with v3:
            ps_filter = st.selectbox("P/S", _ps_opts,
                index=_ps_opts.index(st.session_state["scr_ps"])
                      if st.session_state["scr_ps"] in _ps_opts else 0)
        with v4:
            div_filter = st.selectbox(tr("scr.dividend_yield"), _div_opts,
                index=_div_opts.index(st.session_state["scr_div"])
                      if st.session_state["scr_div"] in _div_opts else 0)

        st.markdown(f"**{tr('scr.fundamentals')}**")
        f4, f5, f6, f7 = st.columns(4)
        _roe_opts = ["Any", "Positive (>0%)", "Over 5%", "Over 10%",
                     "Over 15%", "Over 20%", "Over 30%"]
        _de_opts  = ["Any", "Under 0.5", "Under 1", "Under 2", "Over 2"]
        _eps_opts = ["Any", "Positive", "Negative", "Over 1", "Over 5", "Over 10"]
        _beta_opts= ["Any", "Under 0.5", "Under 1", "1 to 1.5", "1.5 to 2", "Over 2"]
        with f4:
            roe_filter = st.selectbox("ROE", _roe_opts,
                index=_roe_opts.index(st.session_state["scr_roe"])
                      if st.session_state["scr_roe"] in _roe_opts else 0)
        with f5:
            de_filter = st.selectbox("Debt/Equity", _de_opts,
                index=_de_opts.index(st.session_state["scr_de"])
                      if st.session_state["scr_de"] in _de_opts else 0)
        with f6:
            eps_filter = st.selectbox("EPS", _eps_opts,
                index=_eps_opts.index(st.session_state["scr_eps"])
                      if st.session_state["scr_eps"] in _eps_opts else 0)
        with f7:
            beta_filter = st.selectbox("Beta", _beta_opts,
                index=_beta_opts.index(st.session_state["scr_beta"])
                      if st.session_state["scr_beta"] in _beta_opts else 0)

        st.markdown(f"**{tr('scr.market_cap_volume')}**")
        m1, m2 = st.columns(2)
        _cap_opts = ["Any", "Mega (>200B)", "Large (10B-200B)",
                     "Mid (2B-10B)", "Small (300M-2B)", "Micro (<300M)"]
        _vol_opts = ["Any", "Over 100K", "Over 500K", "Over 1M", "Over 5M"]
        with m1:
            cap_filter = st.selectbox(tr("scr.market_cap"), _cap_opts,
                index=_cap_opts.index(st.session_state["scr_cap"])
                      if st.session_state["scr_cap"] in _cap_opts else 0)
        with m2:
            vol_filter = st.selectbox(tr("scr.avg_volume"), _vol_opts,
                index=_vol_opts.index(st.session_state["scr_vol"])
                      if st.session_state["scr_vol"] in _vol_opts else 0)
    else:
        pe_filter = pb_filter = ps_filter = div_filter = "Any"
        roe_filter = de_filter = eps_filter = beta_filter = "Any"
        cap_filter = vol_filter = "Any"

    # Apply / Reset buttons
    btn_col1, btn_col2, _ = st.columns([1, 1, 4])
    with btn_col1:
        apply_clicked = st.form_submit_button(
            "🔍 Apply Filters", type="primary", use_container_width=True,
        )
    with btn_col2:
        reset_clicked = st.form_submit_button(
            "↺ Reset", use_container_width=True,
        )

# Persist whatever the user just submitted (or reset to defaults)
if apply_clicked:
    st.session_state["scr_sector"]   = selected_sector
    st.session_state["scr_industry"] = selected_industry
    st.session_state["scr_search"]   = search
    st.session_state["scr_pe"]       = pe_filter
    st.session_state["scr_pb"]       = pb_filter
    st.session_state["scr_ps"]       = ps_filter
    st.session_state["scr_div"]      = div_filter
    st.session_state["scr_roe"]      = roe_filter
    st.session_state["scr_de"]       = de_filter
    st.session_state["scr_eps"]      = eps_filter
    st.session_state["scr_beta"]     = beta_filter
    st.session_state["scr_cap"]      = cap_filter
    st.session_state["scr_vol"]      = vol_filter
elif reset_clicked:
    for _k, _v in _DEFAULTS.items():
        st.session_state[_k] = _v
    st.rerun()

# Read the applied (committed) filter values for table rendering
selected_sector   = st.session_state["scr_sector"]
selected_industry = st.session_state["scr_industry"]
search            = st.session_state["scr_search"]
pe_filter         = st.session_state["scr_pe"]
pb_filter         = st.session_state["scr_pb"]
ps_filter         = st.session_state["scr_ps"]
div_filter        = st.session_state["scr_div"]
roe_filter        = st.session_state["scr_roe"]
de_filter         = st.session_state["scr_de"]
eps_filter        = st.session_state["scr_eps"]
beta_filter       = st.session_state["scr_beta"]
cap_filter        = st.session_state["scr_cap"]
vol_filter        = st.session_state["scr_vol"]

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
    sort_by = st.selectbox(tr("scr.sort_by"), list(available_sorts.keys()))
with sc2:
    desc_label = tr("scr.descending")
    asc_label = tr("scr.ascending")
    sort_order = st.selectbox(tr("scr.order"), [desc_label, asc_label])

sort_field = available_sorts.get(sort_by, "ticker")
if sort_field in filtered.columns:
    filtered = filtered.sort_values(sort_field, ascending=(sort_order == asc_label), na_position="last")
filtered = filtered.reset_index(drop=True)

# --- Results ---
st.markdown("---")
st.caption(tr("scr.found", n=len(filtered)))

# Build display columns
base_cols = ["ticker", "name", "sector"]
fund_cols = ["current_price", "market_cap", "pe_ratio", "pb_ratio", "dividend_yield",
             "eps", "roe", "beta", "debt_to_equity", "avg_volume"]
display_cols = base_cols + [c for c in fund_cols if c in filtered.columns]

display_df = filtered[display_cols].copy()

# Format display values
fmt_map = {
    "current_price": lambda x: f"${x:,.2f}" if pd.notna(x) else "",
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
st.subheader(tr("scr.sector_dist"))
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
    st.caption(tr("scr.no_dist_data"))
