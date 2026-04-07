"""Watchlist & Alerts page."""

import streamlit as st
import pandas as pd

from services.watchlist_service import (
    add_to_watchlist, remove_from_watchlist, get_watchlist,
    create_alert, delete_alert, get_alerts, check_alerts, reactivate_alert,
)
from services.auth_service import require_auth, render_user_sidebar
from components.ui import inject_css, page_header, stock_logo_url, render_sidebar_info

st.set_page_config(page_title="Watchlist", page_icon="⭐", layout="wide")
inject_css()
render_sidebar_info()
render_user_sidebar()
page_header("Watchlist & Alerts", "Track stocks and get notified on price moves")

# Auth guard
current_user = require_auth()
USER_ID = current_user["id"]

# --- Check alerts on every page load ---
newly_triggered = check_alerts(user_id=USER_ID)
if newly_triggered:
    for alert in newly_triggered:
        cond_label = {
            "above": "rose above",
            "below": "fell below",
            "change_above": "daily change exceeded",
            "change_below": "daily change fell below",
        }.get(alert["condition"], alert["condition"])
        st.toast(
            f"🔔 {alert['ticker']} {cond_label} {alert['threshold']} (now ${alert['current']:.2f})",
            icon="🔔",
        )

tab_watchlist, tab_alerts = st.tabs(["⭐ Watchlist", "🔔 Alerts"])

# ===== WATCHLIST TAB =====
with tab_watchlist:
    # --- Add ticker form ---
    with st.expander("➕ Add to Watchlist", expanded=False):
        with st.form("add_watchlist", clear_on_submit=True):
            wcol1, wcol2 = st.columns([1, 2])
            with wcol1:
                new_ticker = st.text_input("Ticker", placeholder="AAPL")
            with wcol2:
                new_note = st.text_input("Note (optional)", placeholder="Why are you watching?")
            if st.form_submit_button("Add"):
                if new_ticker:
                    if add_to_watchlist(new_ticker, new_note or None, user_id=USER_ID):
                        st.success(f"Added {new_ticker.upper()}")
                        st.rerun()
                    else:
                        st.warning(f"{new_ticker.upper()} is already in your watchlist.")

    # --- Watchlist display ---
    items = get_watchlist(user_id=USER_ID)
    if not items:
        st.info("Your watchlist is empty. Add stocks above to start tracking.")
    else:
        st.markdown("""
        <style>
        .wl-card {
            background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5));
            border: 1px solid rgba(59,130,246,0.2);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 12px;
            transition: all 0.2s;
        }
        .wl-card:hover {
            border-color: rgba(59,130,246,0.6);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59,130,246,0.15);
        }
        .wl-header { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
        .wl-logo {
            width: 40px; height: 40px;
            border-radius: 8px;
            background: white;
            padding: 4px;
            object-fit: contain;
        }
        .wl-ticker { font-size: 18px; font-weight: 700; color: #F8FAFC; }
        .wl-note { font-size: 11px; color: #94A3B8; }
        .wl-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 12px; }
        .wl-label { color: #94A3B8; }
        .wl-value { color: #F8FAFC; font-weight: 600; text-align: right; }
        .wl-up { color: #10B981; font-weight: 700; }
        .wl-down { color: #EF4444; font-weight: 700; }
        </style>
        """, unsafe_allow_html=True)

        cols_per_row = 3
        for row_start in range(0, len(items), cols_per_row):
            row_items = items[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, item in zip(cols, row_items):
                ticker = item["ticker"]
                current = item.get("current_price")
                added_price = item.get("added_price")
                day_change = item.get("change_pct") or 0
                since_added = item.get("change_since_added")
                logo = stock_logo_url(ticker)

                day_class = "wl-up" if day_change >= 0 else "wl-down"
                day_arrow = "▲" if day_change >= 0 else "▼"

                since_html = ""
                if since_added is not None:
                    since_class = "wl-up" if since_added >= 0 else "wl-down"
                    since_arrow = "▲" if since_added >= 0 else "▼"
                    since_html = f'<span class="{since_class}">{since_arrow} {since_added:+.2f}%</span>'
                else:
                    since_html = '<span class="wl-value">N/A</span>'

                current_str = f"${current:,.2f}" if current else "N/A"
                added_str = f"${added_price:,.2f}" if added_price else "N/A"
                note_str = (item.get("note") or "")[:40]

                with col:
                    st.markdown(f"""
                    <div class="wl-card">
                        <div class="wl-header">
                            <img src="{logo}" class="wl-logo" onerror="this.style.display='none'"/>
                            <div>
                                <div class="wl-ticker">{ticker}</div>
                                <div class="wl-note">{note_str}</div>
                            </div>
                        </div>
                        <div class="wl-stats">
                            <span class="wl-label">Current</span>
                            <span class="wl-value">{current_str}</span>
                            <span class="wl-label">Day</span>
                            <span class="{day_class}">{day_arrow} {day_change:+.2f}%</span>
                            <span class="wl-label">Added @</span>
                            <span class="wl-value">{added_str}</span>
                            <span class="wl-label">Since</span>
                            {since_html}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button(f"Remove {ticker}", key=f"rm_wl_{ticker}", use_container_width=True):
                        remove_from_watchlist(ticker, user_id=USER_ID)
                        st.rerun()

# ===== ALERTS TAB =====
with tab_alerts:
    # --- Create alert form ---
    with st.expander("➕ Create Alert", expanded=False):
        with st.form("create_alert", clear_on_submit=True):
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                a_ticker = st.text_input("Ticker", placeholder="AAPL")
            with ac2:
                a_condition = st.selectbox(
                    "Condition",
                    ["above", "below", "change_above", "change_below"],
                    format_func=lambda x: {
                        "above": "Price above",
                        "below": "Price below",
                        "change_above": "Daily change above (%)",
                        "change_below": "Daily change below (%)",
                    }[x],
                )
            with ac3:
                a_threshold = st.number_input("Threshold", value=0.0, step=0.01, format="%.2f")
            a_note = st.text_input("Note (optional)")

            if st.form_submit_button("Create Alert"):
                if a_ticker and a_threshold != 0:
                    create_alert(a_ticker, a_condition, a_threshold, a_note or None, user_id=USER_ID)
                    st.success(f"Alert created for {a_ticker.upper()}")
                    st.rerun()

    # --- Alerts display ---
    alerts = get_alerts(user_id=USER_ID)
    if not alerts:
        st.info("No alerts yet. Create one above.")
    else:
        active_alerts = [a for a in alerts if a["active"] and not a["triggered"]]
        triggered_alerts = [a for a in alerts if a["triggered"]]

        st.markdown(f"**Active: {len(active_alerts)}** | **Triggered: {len(triggered_alerts)}**")

        # --- Active alerts ---
        if active_alerts:
            st.markdown("### 🟢 Active Alerts")
            for a in active_alerts:
                cond_label = {
                    "above": "≥",
                    "below": "≤",
                    "change_above": "Δ ≥",
                    "change_below": "Δ ≤",
                }.get(a["condition"], a["condition"])
                unit = "%" if "change" in a["condition"] else ""

                col_info, col_btn = st.columns([5, 1])
                with col_info:
                    st.markdown(
                        f"**{a['ticker']}** {cond_label} **{a['threshold']:.2f}{unit}**"
                        + (f" — _{a['note']}_" if a.get("note") else "")
                    )
                with col_btn:
                    if st.button("Delete", key=f"del_alert_{a['id']}"):
                        delete_alert(a["id"], user_id=USER_ID)
                        st.rerun()

        # --- Triggered alerts ---
        if triggered_alerts:
            st.markdown("### 🔴 Triggered Alerts")
            for a in triggered_alerts:
                cond_label = {
                    "above": "rose above",
                    "below": "fell below",
                    "change_above": "daily change exceeded",
                    "change_below": "daily change fell below",
                }.get(a["condition"], a["condition"])
                unit = "%" if "change" in a["condition"] else ""

                col_info, col_react, col_del = st.columns([4, 1, 1])
                with col_info:
                    st.markdown(
                        f"~~**{a['ticker']}** {cond_label} **{a['threshold']:.2f}{unit}**~~"
                        + (f" — _triggered at {a['triggered_at'][:16] if a['triggered_at'] else ''}_")
                    )
                with col_react:
                    if st.button("Reactivate", key=f"react_{a['id']}"):
                        reactivate_alert(a["id"], user_id=USER_ID)
                        st.rerun()
                with col_del:
                    if st.button("Delete", key=f"del_t_{a['id']}"):
                        delete_alert(a["id"], user_id=USER_ID)
                        st.rerun()
