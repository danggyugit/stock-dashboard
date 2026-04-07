"""Home page — landing screen with login + market overview."""

import streamlit as st

from components.ui import page_header
from services.auth_service import (
    is_logged_in, get_or_create_user, claim_legacy_data,
)

page_header("Stock Dashboard", "Real-time market overview and personal portfolio tracker")

# Login section
if not is_logged_in():
    st.markdown("---")

    # Google Sign-in button styling — dark theme with 4-color logo
    st.markdown("""
    <style>
    .st-key-google_signin button {
        background: #131314 !important;
        color: #E3E3E3 !important;
        border: 1px solid #8E918F !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-family: "Google Sans", Roboto, Arial, sans-serif !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        height: 48px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
        transition: all 0.2s !important;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><path fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/><path fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/><path fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z'/><path fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z'/></svg>") !important;
        background-repeat: no-repeat !important;
        background-position: 14px center !important;
        background-size: 22px 22px !important;
        padding-left: 48px !important;
        text-align: center !important;
    }
    .st-key-google_signin button:hover {
        background-color: #1F1F20 !important;
        border-color: #A5A8A5 !important;
        box-shadow: 0 2px 6px rgba(255,255,255,0.08) !important;
        transform: none !important;
    }
    .st-key-google_signin button:active {
        background-color: #2A2A2B !important;
    }
    .st-key-google_signin button p {
        color: #E3E3E3 !important;
        font-weight: 500 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### 🔒 Sign in")
        st.markdown(
            "Sign in with Google to access your personal portfolio, watchlist, and alerts."
        )
        if st.button("Sign in with Google", use_container_width=True, key="google_signin"):
            st.login("google")
    with col2:
        st.markdown("### Public features")
        st.markdown("""
        These pages work without sign-in:
        - **Heatmap** — S&P 500 sector treemap
        - **Stock Detail** — Individual stock charts
        - **Sentiment** — Fear & Greed, news
        - **Calendar** — Economic & earnings
        - **Screener** — Filter S&P 500 stocks
        - **Compare** — Compare 2-5 stocks
        """)
        st.markdown("### Personal features (sign-in required)")
        st.markdown("""
        - **Portfolio** — Track holdings, performance, dividends, taxes
        - **Watchlist & Alerts** — Get notified on price moves
        """)
else:
    user = get_or_create_user()
    if user:
        st.success(f"Welcome back, **{user['name']}** 👋")

        # Check for legacy data
        from database import get_connection
        conn = get_connection()
        legacy_count = conn.execute(
            "SELECT COUNT(*) FROM portfolios WHERE user_id IS NULL"
        ).fetchone()[0]

        if legacy_count > 0:
            st.warning(
                f"Found **{legacy_count}** unassigned portfolios from before sign-in was added."
            )
            cl1, cl2 = st.columns(2)
            with cl1:
                if st.button("Claim them as mine", type="primary"):
                    counts = claim_legacy_data(user["id"])
                    st.success(
                        f"Claimed: {counts['portfolios']} portfolios, "
                        f"{counts['watchlist']} watchlist items, "
                        f"{counts['alerts']} alerts."
                    )
                    st.rerun()
            with cl2:
                if st.button("Ignore (start fresh)"):
                    st.info("You can claim them later by visiting this page again.")
        st.markdown("---")

# Quick market overview
from services.market_service import get_indices

with st.spinner("Loading market indices..."):
    indices = get_indices()

if indices:
    cols = st.columns(len(indices))
    for i, idx in enumerate(indices):
        with cols[i]:
            price = idx.get("price")
            change = idx.get("change_pct")
            delta_str = f"{change:+.2f}%" if change is not None else None
            st.metric(
                label=idx["name"],
                value=f"{price:,.2f}" if price else "N/A",
                delta=delta_str,
            )

st.markdown("---")
st.markdown("""
### Pages
- **Dashboard** — Market overview + portfolio summary
- **AI Quant Lab** — ML-based backtest & predictions
- **Heatmap** — S&P 500 sector heatmap
- **Stock Detail** — Individual stock analysis
- **Portfolio** — Portfolio management & performance
- **Sentiment** — Fear & Greed index + news
- **Calendar** — Economic & earnings calendar
- **Screener** — Stock screener with filters
- **Compare** — Compare 2-5 stocks
- **Watchlist** — Track stocks + price alerts
""")
