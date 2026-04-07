"""Stock Dashboard — Streamlit App

Main entry point with st.navigation for full sidebar control.
Layout: Account (top) -> page menu -> Status (bottom).
"""

import streamlit as st

from database import init_db
from components.ui import inject_css, render_sidebar_info
from services.auth_service import render_user_sidebar

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

# --- Page navigation ---
PAGES = [
    st.Page("app_pages/0_Home.py", title="app", icon=":material/home:"),
    st.Page("app_pages/1_Dashboard.py", title="Dashboard", icon=":material/dashboard:"),
    st.Page("app_pages/2_AI_Quant_Lab.py", title="AI Quant Lab", icon=":material/science:"),
    st.Page("app_pages/3_Heatmap.py", title="Heatmap", icon=":material/grid_view:"),
    st.Page("app_pages/4_Stock_Detail.py", title="Stock Detail", icon=":material/show_chart:"),
    st.Page("app_pages/5_Portfolio.py", title="Portfolio", icon=":material/folder:"),
    st.Page("app_pages/6_Sentiment.py", title="Sentiment", icon=":material/psychology:"),
    st.Page("app_pages/7_Calendar.py", title="Calendar", icon=":material/calendar_month:"),
    st.Page("app_pages/8_Screener.py", title="Screener", icon=":material/filter_alt:"),
    st.Page("app_pages/9_Compare.py", title="Compare", icon=":material/compare_arrows:"),
    st.Page("app_pages/10_Watchlist.py", title="Watchlist", icon=":material/star:"),
]
pg = st.navigation(PAGES, position="sidebar")

# --- Sidebar: Status (BOTTOM) ---
render_sidebar_info()

# --- Run selected page ---
pg.run()
