"""Stock Dashboard — Streamlit App

Main entry point with st.navigation for full sidebar control.
Layout: Account (top) -> page menu -> Status (bottom).
"""

import streamlit as st

from database import init_db
from components.ui import inject_css, render_sidebar_info
from services.auth_service import render_user_sidebar, is_logged_in, get_or_create_user, _OWNER_EMAIL

st.set_page_config(
    page_title="Stock Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

# Initialize database on first run
init_db()

# --- Sidebar: Account section (TOP) ---
render_user_sidebar()

# --- Page navigation (grouped by usage flow) ---
PAGES = {
    "Market Overview": [
        st.Page("app_pages/0_Home.py", title="Home", icon=":material/home:"),
        st.Page("app_pages/1_Dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("app_pages/3_Heatmap.py", title="Heatmap", icon=":material/grid_view:"),
        st.Page("app_pages/7_Calendar.py", title="Calendar", icon=":material/calendar_month:"),
    ],
    "Analysis": [
        st.Page("app_pages/4_Stock_Detail.py", title="Stock Detail", icon=":material/show_chart:"),
        st.Page("app_pages/8_Screener.py", title="Screener", icon=":material/filter_alt:"),
        st.Page("app_pages/9_Compare.py", title="Compare", icon=":material/compare_arrows:"),
        st.Page("app_pages/6_Sentiment.py", title="Sentiment", icon=":material/psychology:"),
    ],
    "My Investing": [
        st.Page("app_pages/5_Portfolio.py", title="Portfolio", icon=":material/folder:"),
        st.Page("app_pages/10_Watchlist.py", title="Watchlist", icon=":material/star:"),
        st.Page("app_pages/2_AI_Quant_Lab.py", title="AI Quant Lab", icon=":material/science:"),
        st.Page("app_pages/12_Factor_Lab.py", title="Factor Lab", icon=":material/functions:"),
        st.Page("app_pages/13_Stock_Lab.py", title="Stock Lab", icon=":material/open_in_new:"),
    ],
    "Research": [
        st.Page("app_pages/11_Macro.py", title="Macro", icon=":material/trending_up:"),
    ],
}

# Admin page — only visible to owner
if is_logged_in():
    _cur = get_or_create_user()
    if _cur and _cur.get("email", "").lower() == _OWNER_EMAIL.lower():
        PAGES["Admin"] = [
            st.Page("app_pages/99_Admin.py", title="Admin", icon=":material/admin_panel_settings:"),
        ]
pg = st.navigation(PAGES, position="sidebar")

# --- Sidebar: Status (BOTTOM) ---
render_sidebar_info()

# --- Run selected page ---
pg.run()
