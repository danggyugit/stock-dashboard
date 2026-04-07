"""Stock Dashboard — Streamlit App

Main entry point with custom sidebar navigation for full ordering control.
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
init_db()

# --- Page registry ---
PAGES = [
    ("app_pages/0_Home.py",          "app",            ":material/home:"),
    ("app_pages/1_Dashboard.py",     "Dashboard",      ":material/dashboard:"),
    ("app_pages/2_AI_Quant_Lab.py",  "AI Quant Lab",   ":material/science:"),
    ("app_pages/3_Heatmap.py",       "Heatmap",        ":material/grid_view:"),
    ("app_pages/4_Stock_Detail.py",  "Stock Detail",   ":material/show_chart:"),
    ("app_pages/5_Portfolio.py",     "Portfolio",      ":material/folder:"),
    ("app_pages/6_Sentiment.py",     "Sentiment",      ":material/psychology:"),
    ("app_pages/7_Calendar.py",      "Calendar",       ":material/calendar_month:"),
    ("app_pages/8_Screener.py",      "Screener",       ":material/filter_alt:"),
    ("app_pages/9_Compare.py",       "Compare",        ":material/compare_arrows:"),
    ("app_pages/10_Watchlist.py",    "Watchlist",      ":material/star:"),
]
st_pages = [
    st.Page(path, title=title, icon=icon, url_path=path.split("/")[-1].replace(".py", ""))
    for path, title, icon in PAGES
]

# Build st.navigation but hide its default sidebar (we render our own buttons)
pg = st.navigation(st_pages, position="hidden")

# --- Sidebar layout: Account -> Custom Nav -> Status ---

# 1. Account (top)
render_user_sidebar()

# 2. Custom navigation
st.sidebar.markdown("""
<style>
.st-key-nav_btn button {
    background: transparent !important;
    border: none !important;
    color: #CBD5E1 !important;
    text-align: left !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    font-size: 14px !important;
    height: auto !important;
    min-height: 0 !important;
    justify-content: flex-start !important;
    width: 100% !important;
}
.st-key-nav_btn button:hover {
    background: rgba(59,130,246,0.15) !important;
    color: #F8FAFC !important;
    transform: none !important;
}
.st-key-nav_btn_active button {
    background: rgba(59,130,246,0.25) !important;
    color: #F8FAFC !important;
    font-weight: 600 !important;
}
.st-key-nav_btn_active button:hover {
    background: rgba(59,130,246,0.35) !important;
}
</style>
""", unsafe_allow_html=True)

current_page = pg.url_path if hasattr(pg, "url_path") else ""
for path, title, icon in PAGES:
    page_id = path.split("/")[-1].replace(".py", "")
    is_active = current_page == page_id
    btn_key = f"nav_btn_active_{page_id}" if is_active else f"nav_btn_{page_id}"
    if st.sidebar.button(title, key=btn_key, use_container_width=True):
        st.switch_page(path)

# 3. Status (bottom)
render_sidebar_info()

# --- Run selected page ---
pg.run()
