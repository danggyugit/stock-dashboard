"""Calendar page — Economic indicators + earnings calendar."""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar as cal_mod

from services.calendar_service import get_economic_events, get_earnings_events
from services.auth_service import render_user_sidebar
from components.ui import inject_css, page_header, render_sidebar_info

page_header("page.calendar.title", "page.calendar.subtitle")

# --- Date Range ---
col1, col2 = st.columns(2)
today = date.today()

with col1:
    year = st.selectbox("Year", [today.year - 1, today.year, today.year + 1], index=1)
with col2:
    month = st.selectbox("Month", list(range(1, 13)), index=today.month - 1,
                         format_func=lambda x: cal_mod.month_name[x])

first_day = date(year, month, 1)
last_day = date(year, month, cal_mod.monthrange(year, month)[1])
from_str = first_day.isoformat()
to_str = last_day.isoformat()

# --- Load Data ---
tab_calendar, tab_economic, tab_earnings = st.tabs(["Monthly View", "Economic Events", "Earnings"])

with tab_economic:
    events = get_economic_events(from_str, to_str)
    if events:
        df = pd.DataFrame(events)

        # Importance filter
        importance = st.multiselect(
            "Importance", ["high", "medium", "low"],
            default=["high", "medium"],
        )
        df = df[df["importance"].isin(importance)]

        # Color-code importance
        def _imp_badge(imp: str) -> str:
            return {"high": "🔴", "medium": "🟠", "low": "⚪"}.get(imp, "⚪")

        df["badge"] = df["importance"].apply(_imp_badge)
        display_cols = ["badge", "event_date", "event_name", "actual", "forecast", "previous", "importance"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("No economic events for this period.")

with tab_earnings:
    earnings = get_earnings_events(from_str, to_str)
    if earnings:
        df = pd.DataFrame(earnings)
        st.caption(f"{len(earnings)} earnings reports")

        # Search filter
        search = st.text_input("Filter by ticker", key="earn_search")
        if search:
            df = df[df["ticker"].str.contains(search.upper())]

        display_cols = ["earnings_date", "ticker", "eps_estimate", "eps_actual",
                       "revenue_estimate", "revenue_actual"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("No earnings data for this period.")

with tab_calendar:
    st.subheader(f"{cal_mod.month_name[month]} {year}")

    events = get_economic_events(from_str, to_str)
    earnings = get_earnings_events(from_str, to_str)

    # Build events by date
    events_by_date: dict[int, list[dict]] = {}
    for ev in events:
        d = ev.get("event_date", "")
        try:
            day = int(d.split("-")[2])
            if day not in events_by_date:
                events_by_date[day] = []
            events_by_date[day].append({
                "type": "economic",
                "name": ev["event_name"],
                "importance": ev.get("importance", "medium"),
            })
        except (IndexError, ValueError):
            pass

    for ev in earnings:
        d = ev.get("earnings_date", "")
        try:
            day = int(d.split("-")[2])
            if day not in events_by_date:
                events_by_date[day] = []
            events_by_date[day].append({
                "type": "earnings",
                "name": ev.get("ticker", ""),
                "importance": "earnings",
            })
        except (IndexError, ValueError):
            pass

    # Render calendar grid
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for i, name in enumerate(weekday_names):
        header_cols[i].markdown(f"**{name}**")

    # Calendar weeks
    month_cal = cal_mod.monthcalendar(year, month)
    for week in month_cal:
        week_cols = st.columns(7)
        for i, day in enumerate(week):
            with week_cols[i]:
                if day == 0:
                    st.write("")
                    continue

                is_today = (day == today.day and month == today.month and year == today.year)
                day_label = f"**:blue[{day}]**" if is_today else f"**{day}**"
                st.markdown(day_label)

                day_events = events_by_date.get(day, [])
                for ev in day_events[:3]:
                    if ev["type"] == "economic":
                        badge = {"high": "🔴", "medium": "🟠", "low": "⚪"}.get(
                            ev["importance"], "⚪"
                        )
                        short_name = ev["name"][:20]
                        st.caption(f"{badge} {short_name}")
                    else:
                        st.caption(f"📊 {ev['name']}")

                if len(day_events) > 3:
                    st.caption(f"+{len(day_events) - 3} more")
