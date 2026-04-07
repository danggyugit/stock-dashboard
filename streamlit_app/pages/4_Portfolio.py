"""Portfolio page — Portfolio management, trades, performance, dividends, tax."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

from services.portfolio_service import (
    create_portfolio, get_portfolios, delete_portfolio,
    add_trade, delete_trade, get_trades,
    get_holdings, get_allocation, get_performance,
    get_dividends, get_tax_summary,
)
from services.market_service import get_chart_data
from services.auth_service import require_auth, render_user_sidebar
from components.ui import inject_css, page_header, stock_logo_url, render_sidebar_info

st.set_page_config(page_title="Portfolio", page_icon="💼", layout="wide")
inject_css()
render_sidebar_info()
render_user_sidebar()
page_header("Portfolio", "Track holdings, performance, dividends, and taxes")

# Auth guard
current_user = require_auth()
USER_ID = current_user["id"]

# --- Portfolio Management (main area) ---
portfolios = get_portfolios(user_id=USER_ID)

mgmt_col1, mgmt_col2 = st.columns(2)

with mgmt_col1:
    with st.expander("➕ Create New Portfolio", expanded=not portfolios):
        with st.form("create_portfolio_form", clear_on_submit=True):
            new_name = st.text_input("Portfolio Name", key="new_pf_name")
            new_desc = st.text_input("Description (optional)", key="new_pf_desc")
            if st.form_submit_button("Create", type="primary"):
                if new_name:
                    create_portfolio(new_name, new_desc or None, user_id=USER_ID)
                    st.rerun()
                else:
                    st.warning("Enter a portfolio name.")

with mgmt_col2:
    if portfolios:
        with st.expander("🗑️ Delete Portfolio"):
            all_ids_tmp = [p["id"] for p in portfolios]
            pf_options_tmp = {p["id"]: p["name"] for p in portfolios}
            del_id = st.selectbox(
                "Portfolio to delete", all_ids_tmp,
                format_func=lambda x: pf_options_tmp[x], key="del_pf",
            )
            if st.button("Delete", type="secondary", key="del_pf_btn"):
                delete_portfolio(del_id, user_id=USER_ID)
                st.rerun()

if not portfolios:
    st.info("Create your first portfolio above to get started.")
    st.stop()

pf_options = {p["id"]: p["name"] for p in portfolios}
all_ids = list(pf_options.keys())

st.markdown("---")

# --- Tabs ---
tab_holdings, tab_trades, tab_performance, tab_dividends, tab_tax = st.tabs(
    ["Holdings", "Trades", "Performance", "Dividends", "Tax"]
)


def _portfolio_selector(key_prefix: str) -> list[int]:
    """Render portfolio dropdown: All / individual."""
    options = ["All"] + [pf_options[pid] for pid in all_ids]
    choice = st.selectbox("Portfolio", options, key=f"{key_prefix}_pf_select")
    if choice == "All":
        return all_ids
    return [pid for pid, name in pf_options.items() if name == choice]


def _merge_holdings(selected_ids: list[int]) -> tuple[list[dict], float, float]:
    """Merge holdings across selected portfolios."""
    merged = []
    total_value = total_cost = 0.0
    for pid in selected_ids:
        data = get_holdings(pid)
        if data and data.get("holdings"):
            merged.extend(data["holdings"])
            total_value += data["total_value"]
            total_cost += data["total_cost"]
    return merged, total_value, total_cost


def _build_allocation(holdings: list[dict], total_value: float) -> dict:
    """Build allocation data from merged holdings."""
    if not holdings or total_value == 0:
        return {"by_stock": [], "by_sector": []}

    colors = [
        "#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6",
        "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#6366F1",
    ]
    by_stock = []
    sector_totals: dict[str, float] = {}

    for i, h in enumerate(holdings):
        value = h.get("market_value") or h["total_cost"]
        pct = (value / total_value) * 100 if total_value > 0 else 0
        by_stock.append({
            "label": h["ticker"], "value": round(value, 2),
            "percentage": round(pct, 2), "color": colors[i % len(colors)],
        })
        sector = h.get("sector") or "Unknown"
        sector_totals[sector] = sector_totals.get(sector, 0) + value

    by_sector = [
        {"label": s, "value": round(v, 2),
         "percentage": round((v / total_value) * 100, 2), "color": colors[i % len(colors)]}
        for i, (s, v) in enumerate(sorted(sector_totals.items(), key=lambda x: x[1], reverse=True))
    ]

    return {"by_stock": by_stock, "by_sector": by_sector}


# ===== HOLDINGS TAB =====
with tab_holdings:
    selected_ids = _portfolio_selector("holdings")
    merged_holdings, total_value, total_cost = _merge_holdings(selected_ids)

    if merged_holdings:
        gain = total_value - total_cost
        gain_pct = (gain / total_cost * 100) if total_cost else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Value", f"${total_value:,.2f}")
        m2.metric("Total Cost", f"${total_cost:,.2f}")
        m3.metric("Unrealized P&L", f"${gain:,.2f}", delta=f"{gain_pct:+.2f}%")

        # Allocation charts (top)
        alloc = _build_allocation(merged_holdings, total_value)
        if alloc.get("by_stock"):
            col1, col2 = st.columns(2)
            with col1:
                fig = px.pie(
                    names=[s["label"] for s in alloc["by_stock"]],
                    values=[s["value"] for s in alloc["by_stock"]],
                    hole=0.5, title="By Stock",
                )
                fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=40))
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                if alloc.get("by_sector"):
                    fig = px.pie(
                        names=[s["label"] for s in alloc["by_sector"]],
                        values=[s["value"] for s in alloc["by_sector"]],
                        hole=0.5, title="By Sector",
                    )
                    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=40))
                    st.plotly_chart(fig, use_container_width=True)

        # --- Portfolio Treemap (sector → stock, sized by value, colored by P&L) ---
        treemap_rows = []
        for h in merged_holdings:
            value = h.get("market_value") or h.get("total_cost") or 0
            pnl_pct = h.get("unrealized_gain_pct") or 0
            if value > 0:
                treemap_rows.append({
                    "sector": h.get("sector") or "Unknown",
                    "ticker": h["ticker"],
                    "name": h.get("name") or h["ticker"],
                    "value": value,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_label": f"{pnl_pct:+.2f}%",
                })

        if treemap_rows:
            tdf = pd.DataFrame(treemap_rows)
            tm_fig = px.treemap(
                tdf, path=["sector", "ticker"], values="value",
                color="pnl_pct",
                color_continuous_scale=["#DC2626", "#991B1B", "#1E293B", "#166534", "#16A34A"],
                color_continuous_midpoint=0,
                custom_data=["name", "pnl_label", "value"],
                title="Portfolio Treemap (size = market value, color = P&L %)",
            )
            tm_fig.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[1]}",
                textfont=dict(size=18),
                hovertemplate="<b>%{customdata[0]}</b><br>"
                              "Ticker: %{label}<br>"
                              "Value: $%{customdata[2]:,.2f}<br>"
                              "P&L: %{customdata[1]}<extra></extra>",
            )
            tm_fig.update_layout(
                height=500, margin=dict(l=0, r=0, t=50, b=0),
                coloraxis_colorbar=dict(title="P&L %", tickformat="+.2f"),
                uniformtext=dict(minsize=10, mode="hide"),
            )
            st.plotly_chart(tm_fig, use_container_width=True)

        st.markdown("---")
        st.subheader("Holdings Detail")

        # View toggle: Card Grid / Table
        view_mode = st.radio(
            "View", ["Card Grid", "Table"],
            horizontal=True, key="holdings_view",
        )

        if view_mode == "Table":
            df = pd.DataFrame(merged_holdings)
            display_cols = ["ticker", "name", "quantity", "avg_cost", "current_price",
                           "market_value", "unrealized_gain", "unrealized_gain_pct"]
            available = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available], use_container_width=True, hide_index=True)
        else:
            # --- Card Grid with logo + sparkline ---
            st.markdown("""
            <style>
            .holding-card {
                background: linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.6));
                border: 1px solid rgba(59,130,246,0.2);
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 12px;
                transition: all 0.2s;
                backdrop-filter: blur(8px);
            }
            .holding-card:hover {
                border-color: rgba(59,130,246,0.6);
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(59,130,246,0.15);
            }
            .holding-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }
            .holding-logo {
                width: 40px; height: 40px;
                border-radius: 8px;
                background: white;
                padding: 4px;
                object-fit: contain;
            }
            .holding-ticker {
                font-size: 18px;
                font-weight: 700;
                color: #F8FAFC;
            }
            .holding-name {
                font-size: 11px;
                color: #94A3B8;
            }
            .holding-stats {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 6px;
                font-size: 12px;
                margin-top: 8px;
            }
            .stat-label { color: #94A3B8; }
            .stat-value { color: #F8FAFC; font-weight: 600; text-align: right; }
            .gain-up { color: #10B981; }
            .gain-down { color: #EF4444; }
            .holding-pnl {
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-top: 6px;
                padding-top: 8px;
                border-top: 1px solid rgba(148,163,184,0.15);
            }
            .pnl-amount { font-size: 16px; font-weight: 700; }
            .pnl-pct {
                font-size: 13px; font-weight: 600;
                padding: 2px 8px;
                border-radius: 999px;
            }
            .pnl-up-bg { background: rgba(16,185,129,0.15); color: #10B981; }
            .pnl-down-bg { background: rgba(239,68,68,0.15); color: #EF4444; }
            </style>
            """, unsafe_allow_html=True)

            # Sort holdings by market value desc
            sorted_holdings = sorted(
                merged_holdings,
                key=lambda h: h.get("market_value") or h.get("total_cost") or 0,
                reverse=True,
            )

            cols_per_row = 3
            for row_start in range(0, len(sorted_holdings), cols_per_row):
                row = sorted_holdings[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for col, h in zip(cols, row):
                    ticker = h["ticker"]
                    name = h.get("name") or ticker
                    qty = h.get("quantity") or 0
                    avg_cost = h.get("avg_cost") or 0
                    current = h.get("current_price")
                    mv = h.get("market_value") or 0
                    pnl = h.get("unrealized_gain") or 0
                    pnl_pct = h.get("unrealized_gain_pct") or 0
                    is_up = pnl >= 0
                    pnl_class = "gain-up" if is_up else "gain-down"
                    pnl_bg = "pnl-up-bg" if is_up else "pnl-down-bg"
                    arrow = "▲" if is_up else "▼"
                    logo_url = stock_logo_url(ticker)

                    # Pre-format values to handle None safely
                    qty_str = f"{qty:,.4g}" if qty else "0"
                    avg_cost_str = f"${avg_cost:,.2f}" if avg_cost else "N/A"
                    current_str = f"${current:,.2f}" if current else "N/A"
                    mv_str = f"${mv:,.2f}" if mv else "N/A"
                    pnl_str = f"${pnl:+,.2f}" if pnl else "$0.00"
                    pnl_pct_str = f"{pnl_pct:+.2f}%" if pnl_pct else "0.00%"

                    with col:
                        # Render card header info
                        st.markdown(f"""
                        <div class="holding-card">
                            <div class="holding-header">
                                <img src="{logo_url}" class="holding-logo"
                                     onerror="this.style.display='none'"/>
                                <div>
                                    <div class="holding-ticker">{ticker}</div>
                                    <div class="holding-name">{name[:30]}</div>
                                </div>
                            </div>
                            <div class="holding-stats">
                                <span class="stat-label">Qty</span>
                                <span class="stat-value">{qty_str}</span>
                                <span class="stat-label">Avg Cost</span>
                                <span class="stat-value">{avg_cost_str}</span>
                                <span class="stat-label">Current</span>
                                <span class="stat-value">{current_str}</span>
                                <span class="stat-label">Value</span>
                                <span class="stat-value">{mv_str}</span>
                            </div>
                            <div class="holding-pnl">
                                <span class="pnl-amount {pnl_class}">{pnl_str}</span>
                                <span class="pnl-pct {pnl_bg}">{arrow} {pnl_pct_str}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Mini sparkline (1M)
                        try:
                            spark_data = get_chart_data(ticker, period="1mo", interval="1d")
                            if spark_data and len(spark_data) >= 2:
                                spark_dates = [d["date"] for d in spark_data]
                                spark_closes = [d["close"] for d in spark_data]
                                spark_color = "#10B981" if spark_closes[-1] >= spark_closes[0] else "#EF4444"

                                spark_fig = go.Figure()
                                spark_fig.add_trace(go.Scatter(
                                    x=spark_dates, y=spark_closes,
                                    mode="lines",
                                    line=dict(color=spark_color, width=1.5),
                                    fill="tozeroy",
                                    fillcolor=spark_color.replace("#10B981", "rgba(16,185,129,0.15)").replace("#EF4444", "rgba(239,68,68,0.15)"),
                                    hoverinfo="skip",
                                ))
                                y_min = min(spark_closes)
                                y_max = max(spark_closes)
                                y_pad = (y_max - y_min) * 0.1 if y_max != y_min else 1
                                spark_fig.update_layout(
                                    height=60,
                                    margin=dict(l=0, r=0, t=0, b=0),
                                    xaxis=dict(visible=False),
                                    yaxis=dict(visible=False, range=[y_min - y_pad, y_max + y_pad]),
                                    showlegend=False,
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                )
                                st.plotly_chart(spark_fig, use_container_width=True,
                                                key=f"spark_{ticker}_{row_start}")
                        except Exception:
                            pass
    else:
        st.info("No holdings. Add trades to see your portfolio.")

# ===== TRADES TAB =====
with tab_trades:
    st.subheader("Add Trade")
    active_pf = st.selectbox(
        "Target Portfolio", all_ids,
        format_func=lambda x: pf_options[x], key="trade_target",
    )

    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        trade_type = st.selectbox("Type", ["BUY", "SELL"], key="trade_type_sel")
    with t_col2:
        ticker_input = st.text_input("Ticker", placeholder="AAPL", key="trade_ticker").upper().strip()
    with t_col3:
        trade_date_input = st.date_input("Date", value=date.today(), key="trade_date")

    auto_price = 0.0
    if ticker_input and trade_date_input:
        try:
            start = trade_date_input
            end = trade_date_input + timedelta(days=5)
            hist = yf.Ticker(ticker_input).history(start=str(start), end=str(end))
            if not hist.empty:
                auto_price = round(float(hist["Close"].iloc[0]), 2)
        except Exception:
            pass

    with st.form("add_trade"):
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            price = st.number_input("Price ($)", min_value=0.0, value=auto_price, step=0.01, format="%.2f")
        with p_col2:
            quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
        with p_col3:
            commission = st.number_input("Commission ($)", min_value=0.0, value=0.0, step=0.01)

        note = st.text_input("Note (optional)")
        submitted = st.form_submit_button("Add Trade")

        if submitted and ticker_input and quantity > 0 and price > 0:
            add_trade(active_pf, {
                "ticker": ticker_input, "trade_type": trade_type,
                "quantity": quantity, "price": price,
                "commission": commission,
                "trade_date": str(trade_date_input), "note": note or None,
            })
            st.success(f"Added {trade_type} {quantity} {ticker_input} @ ${price:.2f}")
            st.rerun()
        elif submitted:
            if not ticker_input:
                st.warning("Enter a ticker.")
            elif quantity <= 0:
                st.warning("Enter quantity.")
            elif price <= 0:
                st.warning("Price must be > 0.")

    st.subheader("Trade History")
    for pid in all_ids:
        pf_name = pf_options.get(pid, f"Portfolio {pid}")
        trades = get_trades(pid)
        if trades:
            st.caption(f"**{pf_name}**")
            trade_df = pd.DataFrame(trades)
            display = ["ticker", "trade_type", "quantity", "price", "commission", "trade_date", "note"]
            available = [c for c in display if c in trade_df.columns]
            st.dataframe(trade_df[available], use_container_width=True, hide_index=True)

            trade_ids = {t["id"]: f"{t['ticker']} {t['trade_type']} {t['quantity']}@{t['price']} ({t['trade_date']})"
                        for t in trades}
            with st.expander(f"Delete trade from {pf_name}"):
                del_tid = st.selectbox("Trade", list(trade_ids.keys()),
                                       format_func=lambda x: trade_ids[x], key=f"del_trade_{pid}")
                if st.button("Delete Trade", key=f"del_trade_btn_{pid}"):
                    delete_trade(pid, del_tid)
                    st.rerun()

# ===== PERFORMANCE TAB =====
with tab_performance:
    perf_selected = _portfolio_selector("perf")
    perf_period = st.selectbox("Period", ["1m", "3m", "6m", "1y", "ytd"], key="perf_period")

    # Merge performance across selected portfolios
    all_points: dict[str, dict] = {}  # date -> merged point
    for pid in perf_selected:
        perf = get_performance(pid, perf_period)
        if not perf.get("points"):
            continue
        for p in perf["points"]:
            d = p["date"]
            if d not in all_points:
                all_points[d] = {"date": d, "portfolio_value": 0.0, "total_cost": 0.0,
                                 "spy_pct": p.get("spy_pct"), "qqq_pct": p.get("qqq_pct")}
            all_points[d]["portfolio_value"] += p.get("portfolio_value", 0)
            all_points[d]["total_cost"] += p.get("total_cost", 0)
            # Keep benchmark from first portfolio that has it
            if all_points[d]["spy_pct"] is None:
                all_points[d]["spy_pct"] = p.get("spy_pct")
            if all_points[d]["qqq_pct"] is None:
                all_points[d]["qqq_pct"] = p.get("qqq_pct")

    if all_points:
        sorted_points = sorted(all_points.values(), key=lambda x: x["date"])
        for p in sorted_points:
            cost = p["total_cost"]
            p["gain_pct"] = round(((p["portfolio_value"] - cost) / cost) * 100, 2) if cost > 0 else 0

        total_return = sorted_points[-1]["gain_pct"] if sorted_points else 0
        spy_return = sorted_points[-1].get("spy_pct") if sorted_points else None
        qqq_return = sorted_points[-1].get("qqq_pct") if sorted_points else None

        r1, r2, r3 = st.columns(3)
        r1.metric("Portfolio Return", f"{total_return:+.2f}%")
        r2.metric("SPY", f"{spy_return:+.2f}%" if spy_return is not None else "N/A")
        r3.metric("QQQ", f"{qqq_return:+.2f}%" if qqq_return is not None else "N/A")

        fig = go.Figure()
        dates = [p["date"] for p in sorted_points]
        fig.add_trace(go.Scatter(
            x=dates, y=[p["gain_pct"] for p in sorted_points],
            name="Portfolio", line=dict(color="#3B82F6", width=2),
        ))
        if any(p.get("spy_pct") is not None for p in sorted_points):
            fig.add_trace(go.Scatter(
                x=dates, y=[p.get("spy_pct") for p in sorted_points],
                name="SPY", line=dict(color="#F59E0B", width=1, dash="dash"),
            ))
        if any(p.get("qqq_pct") is not None for p in sorted_points):
            fig.add_trace(go.Scatter(
                x=dates, y=[p.get("qqq_pct") for p in sorted_points],
                name="QQQ", line=dict(color="#10B981", width=1, dash="dash"),
            ))
        fig.update_layout(
            height=400, yaxis_title="Return (%)",
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
        st.plotly_chart(fig, use_container_width=True)

        # --- Drawdown chart ---
        st.markdown("**Drawdown** (peak-to-trough decline from running maximum)")
        values = [p["portfolio_value"] for p in sorted_points]
        if len(values) >= 2:
            running_max = []
            cur_max = values[0]
            for v in values:
                cur_max = max(cur_max, v)
                running_max.append(cur_max)
            drawdowns = [
                ((v - rm) / rm * 100) if rm > 0 else 0
                for v, rm in zip(values, running_max)
            ]
            max_dd = min(drawdowns) if drawdowns else 0

            dd_fig = go.Figure()
            dd_fig.add_trace(go.Scatter(
                x=dates, y=drawdowns, mode="lines",
                line=dict(color="#EF4444", width=1.5),
                fill="tozeroy", fillcolor="rgba(239,68,68,0.2)",
                name="Drawdown",
                hovertemplate="%{x}<br>Drawdown: %{y:.2f}%<extra></extra>",
            ))
            dd_fig.update_layout(
                height=250, yaxis_title="Drawdown (%)",
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            )
            dd_fig.update_yaxes(gridcolor="rgba(255,255,255,0.1)")
            st.plotly_chart(dd_fig, use_container_width=True)

            # Risk metrics: Max DD, Volatility, Sharpe (simple)
            import numpy as _np
            returns = []
            for i in range(1, len(values)):
                if values[i - 1] > 0:
                    returns.append((values[i] - values[i - 1]) / values[i - 1])
            if returns:
                vol = _np.std(returns) * _np.sqrt(252) * 100  # annualized
                avg_ret = _np.mean(returns) * 252 * 100
                sharpe = (avg_ret / vol) if vol > 0 else 0
            else:
                vol = avg_ret = sharpe = 0

            rm1, rm2, rm3 = st.columns(3)
            rm1.metric("Max Drawdown", f"{max_dd:.2f}%")
            rm2.metric("Volatility (annualized)", f"{vol:.2f}%")
            rm3.metric("Sharpe Ratio", f"{sharpe:.2f}")
    else:
        st.caption("No performance data.")

    # --- Correlation Matrix of holdings ---
    st.markdown("---")
    st.subheader("Holdings Correlation Matrix")
    st.caption("Daily return correlation between portfolio holdings (last 6 months)")

    # Get unique tickers from selected portfolios' holdings
    corr_tickers: list[str] = []
    for pid in perf_selected:
        h_data = get_holdings(pid)
        if h_data and h_data.get("holdings"):
            for h in h_data["holdings"]:
                if h["ticker"] not in corr_tickers:
                    corr_tickers.append(h["ticker"])

    if len(corr_tickers) < 2:
        st.caption("Need at least 2 holdings to compute correlation.")
    else:
        # Fetch 6 month daily prices for each
        price_series: dict[str, pd.Series] = {}
        for t in corr_tickers:
            chart = get_chart_data(t, period="6mo", interval="1d")
            if chart:
                s = pd.Series(
                    [d["close"] for d in chart],
                    index=[d["date"] for d in chart],
                )
                price_series[t] = s

        if len(price_series) >= 2:
            price_df = pd.DataFrame(price_series).dropna()
            returns_df = price_df.pct_change().dropna()
            corr = returns_df.corr().round(2)

            corr_fig = go.Figure(data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale=[
                    [0.0, "#DC2626"],
                    [0.5, "#1E293B"],
                    [1.0, "#16A34A"],
                ],
                zmid=0, zmin=-1, zmax=1,
                text=corr.values,
                texttemplate="%{text:.2f}",
                textfont=dict(size=12, color="#F8FAFC"),
                hovertemplate="<b>%{y}</b> ↔ <b>%{x}</b><br>Correlation: %{z:.2f}<extra></extra>",
                colorbar=dict(title="Correlation"),
            ))
            corr_fig.update_layout(
                height=max(400, len(corr_tickers) * 35),
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            corr_fig.update_xaxes(side="bottom")
            st.plotly_chart(corr_fig, use_container_width=True)
            st.caption("1.0 = perfectly correlated, 0 = uncorrelated, -1 = inversely correlated. Lower correlation = better diversification.")
        else:
            st.caption("Insufficient price data.")

# ===== DIVIDENDS TAB =====
with tab_dividends:
    div_selected = _portfolio_selector("div")
    div_year = st.number_input("Year", min_value=2020, max_value=2030,
                                value=date.today().year, key="div_year")

    # Merge dividends
    all_events: list[dict] = []
    all_monthly: dict[str, float] = {}
    total_annual = 0.0

    for pid in div_selected:
        div_data = get_dividends(pid, int(div_year))
        all_events.extend(div_data.get("events", []))
        total_annual += div_data.get("total_annual", 0)
        for k, v in div_data.get("monthly_breakdown", {}).items():
            all_monthly[k] = all_monthly.get(k, 0) + v

    st.metric("Total Annual Dividends", f"${total_annual:,.2f}")

    if all_events:
        st.dataframe(pd.DataFrame(all_events), use_container_width=True, hide_index=True)

        if all_monthly:
            fig = px.bar(
                x=sorted(all_monthly.keys()), y=[all_monthly[k] for k in sorted(all_monthly.keys())],
                labels={"x": "Month", "y": "Dividends ($)"},
                title="Monthly Dividends",
            )
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No dividend events this year.")

# ===== TAX TAB =====
with tab_tax:
    tax_selected = _portfolio_selector("tax")
    tax_year = st.number_input("Tax Year", min_value=2020, max_value=2030,
                                value=date.today().year, key="tax_year")

    # Merge tax
    merged_tax = {
        "realized_gains": 0.0, "realized_losses": 0.0, "net_gain": 0.0,
        "short_term_gain": 0.0, "long_term_gain": 0.0,
        "short_term_loss": 0.0, "long_term_loss": 0.0,
    }
    all_tax_trades: list[dict] = []

    for pid in tax_selected:
        tax = get_tax_summary(pid, int(tax_year))
        for key in merged_tax:
            merged_tax[key] += tax.get(key, 0)
        all_tax_trades.extend(tax.get("trades", []))

    c1, c2, c3 = st.columns(3)
    c1.metric("Net Gain/Loss", f"${merged_tax['net_gain']:,.2f}")
    c2.metric("Realized Gains", f"${merged_tax['realized_gains']:,.2f}")
    c3.metric("Realized Losses", f"-${merged_tax['realized_losses']:,.2f}")

    c4, c5, c6, c7 = st.columns(4)
    c4.metric("Short-Term Gain", f"${merged_tax['short_term_gain']:,.2f}")
    c5.metric("Long-Term Gain", f"${merged_tax['long_term_gain']:,.2f}")
    c6.metric("Short-Term Loss", f"-${merged_tax['short_term_loss']:,.2f}")
    c7.metric("Long-Term Loss", f"-${merged_tax['long_term_loss']:,.2f}")

    if all_tax_trades:
        st.dataframe(pd.DataFrame(all_tax_trades), use_container_width=True, hide_index=True)
