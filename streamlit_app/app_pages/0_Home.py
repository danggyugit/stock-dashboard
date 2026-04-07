"""Home page — landing screen with hero, welcome, and quick action cards."""

from datetime import datetime, timedelta, timezone

import streamlit as st

from services.auth_service import (
    is_logged_in, get_or_create_user, claim_legacy_data,
)
from services.market_service import get_indices

# ═══════════════════════════════════════════════════════════
# CSS — hero, cards, gradients
# ═══════════════════════════════════════════════════════════
st.markdown("""
<style>
/* Hero */
.hero {
    background: radial-gradient(ellipse at top left,
                rgba(59,130,246,0.15) 0%,
                rgba(15,23,42,0) 60%),
                radial-gradient(ellipse at bottom right,
                rgba(168,85,247,0.12) 0%,
                rgba(15,23,42,0) 60%);
    border: 1px solid rgba(59,130,246,0.18);
    border-radius: 16px;
    padding: 36px 32px;
    margin-bottom: 24px;
}
.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, #60A5FA 0%, #A855F7 50%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 8px 0;
    line-height: 1.1;
}
.hero-subtitle {
    font-size: 1.05rem;
    color: #CBD5E1;
    margin: 0 0 4px 0;
}
.hero-meta {
    font-size: 0.85rem;
    color: #94A3B8;
    margin-top: 16px;
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
}
.hero-meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
}
.hero-meta-item .dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* Welcome banner (logged in) */
.welcome-banner {
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(59,130,246,0.10));
    border: 1px solid rgba(16,185,129,0.3);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 14px;
}
.welcome-avatar {
    width: 48px; height: 48px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(16,185,129,0.5);
}
.welcome-text {
    flex: 1;
}
.welcome-greet {
    font-size: 1.1rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 0;
}
.welcome-sub {
    font-size: 0.85rem;
    color: #94A3B8;
    margin: 2px 0 0 0;
}

/* Quick action cards */
.qa-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
}
.qa-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5));
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px;
    padding: 18px;
    text-decoration: none !important;
    color: inherit !important;
    transition: all 0.2s ease;
    display: block;
    cursor: pointer;
}
.qa-card:hover {
    border-color: rgba(59,130,246,0.6);
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(59,130,246,0.18);
}
.qa-icon {
    font-size: 26px;
    margin-bottom: 8px;
    display: block;
}
.qa-title {
    font-size: 1rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 0 0 4px 0;
}
.qa-desc {
    font-size: 0.78rem;
    color: #94A3B8;
    margin: 0;
    line-height: 1.4;
}

/* Section header */
.section-h {
    font-size: 1.1rem;
    font-weight: 700;
    color: #F8FAFC;
    margin: 24px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg, #3B82F6, transparent) 1;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# Time & status helpers
# ═══════════════════════════════════════════════════════════
def _get_market_state() -> tuple[str, str, str]:
    """Return (label, color, dot_color) for current US market state."""
    ny = datetime.now(timezone.utc) + timedelta(hours=-4)
    weekday = ny.weekday()
    minutes = ny.hour * 60 + ny.minute

    if weekday >= 5:
        return "Market Closed (Weekend)", "#94A3B8", "#94A3B8"
    if 570 <= minutes < 960:  # 9:30 - 16:00 ET
        return "Market Open", "#10B981", "#10B981"
    if minutes < 570:
        return "Pre-Market", "#F59E0B", "#F59E0B"
    return "After Hours", "#A855F7", "#A855F7"


# ═══════════════════════════════════════════════════════════
# HERO SECTION
# ═══════════════════════════════════════════════════════════
now_kst = datetime.now()
ny_now = datetime.now(timezone.utc) + timedelta(hours=-4)
market_label, market_color, dot_color = _get_market_state()

hero_html = f"""
<div class="hero">
    <h1 class="hero-title">AI Quant Lab Dashboard</h1>
    <p class="hero-subtitle">Track stocks, run AI backtests, and manage your portfolio — all in one place.</p>
    <div class="hero-meta">
        <div class="hero-meta-item">
            <span class="dot" style="background:{dot_color};"></span>
            <span style="color:{market_color}; font-weight:600;">{market_label}</span>
        </div>
        <div class="hero-meta-item">
            🇰🇷 KST {now_kst.strftime('%H:%M')}
        </div>
        <div class="hero-meta-item">
            🗽 NY {ny_now.strftime('%H:%M')}
        </div>
        <div class="hero-meta-item">
            📅 {now_kst.strftime('%Y-%m-%d (%a)')}
        </div>
    </div>
</div>
"""
st.markdown(hero_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# LOGIN / WELCOME
# ═══════════════════════════════════════════════════════════
if not is_logged_in():
    # Big Google Sign-in button styling
    st.markdown("""
    <style>
    .st-key-google_signin button {
        background: linear-gradient(135deg, #4285F4 0%, #1A73E8 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        font-family: "Google Sans", Roboto, Arial, sans-serif !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        height: 180px !important;
        width: 100% !important;
        box-shadow: 0 6px 24px rgba(66,133,244,0.4) !important;
        transition: all 0.2s ease !important;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><circle cx='24' cy='24' r='22' fill='white'/><path fill='%23EA4335' d='M24 11.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 4.38 30.47 2 24 2 14.62 2 6.51 7.38 2.56 15.22l7.98 6.19C12.43 15.72 17.74 11.5 24 11.5z' transform='scale(0.7) translate(10 10)'/><path fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z' transform='scale(0.7) translate(10 10)'/><path fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z' transform='scale(0.7) translate(10 10)'/><path fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z' transform='scale(0.7) translate(10 10)'/></svg>") !important;
        background-repeat: no-repeat !important;
        background-position: center 32px !important;
        background-size: 56px 56px !important;
        padding: 100px 16px 16px 16px !important;
        text-align: center !important;
        cursor: pointer !important;
        white-space: nowrap !important;
    }
    .st-key-google_signin button:hover {
        background: linear-gradient(135deg, #1A73E8 0%, #1557B0 100%) !important;
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><circle cx='24' cy='24' r='22' fill='white'/><path fill='%23EA4335' d='M24 11.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 4.38 30.47 2 24 2 14.62 2 6.51 7.38 2.56 15.22l7.98 6.19C12.43 15.72 17.74 11.5 24 11.5z' transform='scale(0.7) translate(10 10)'/><path fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z' transform='scale(0.7) translate(10 10)'/><path fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z' transform='scale(0.7) translate(10 10)'/><path fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z' transform='scale(0.7) translate(10 10)'/></svg>") !important;
        background-repeat: no-repeat !important;
        background-position: center 32px !important;
        background-size: 56px 56px !important;
        box-shadow: 0 8px 28px rgba(66,133,244,0.55) !important;
        transform: translateY(-2px) !important;
    }
    .st-key-google_signin button:active {
        transform: translateY(0) !important;
    }
    .st-key-google_signin button p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 18px !important;
        margin: 0 !important;
    }

    /* Features comparison table */
    .features-table {
        margin-top: 16px;
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid rgba(59,130,246,0.18);
    }
    .features-table th {
        background: rgba(30,41,59,0.7);
        color: #F8FAFC;
        font-size: 13px;
        font-weight: 700;
        padding: 10px 14px;
        text-align: left;
        border-bottom: 1px solid rgba(59,130,246,0.18);
    }
    .features-table th.public { color: #94A3B8; }
    .features-table th.personal { color: #60A5FA; }
    .features-table td {
        padding: 8px 14px;
        font-size: 12px;
        color: #CBD5E1;
        border-bottom: 1px solid rgba(148,163,184,0.08);
    }
    .features-table tr:last-child td { border-bottom: none; }
    .features-table td.icon { width: 28px; text-align: center; font-size: 14px; }
    .features-table .lock { color: #F59E0B; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.markdown("### 🔒 Sign in to unlock your personal workspace")
        st.markdown(
            "Track holdings, get price alerts, run AI-powered backtests, "
            "and manage multiple portfolios — all synced to your Google account."
        )
        # Features comparison table
        features_html = """
        <table class="features-table">
            <thead>
                <tr>
                    <th></th>
                    <th class="public">Public (no sign-in)</th>
                    <th class="personal">Personal (sign-in required)</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="icon">📊</td>
                    <td>Heatmap, Stock Detail</td>
                    <td>📁 Portfolio (holdings, P&amp;L, taxes)</td>
                </tr>
                <tr>
                    <td class="icon">🧭</td>
                    <td>Sentiment, Calendar</td>
                    <td>⭐ Watchlist + 🔔 Price alerts</td>
                </tr>
                <tr>
                    <td class="icon">🔍</td>
                    <td>Screener, Compare</td>
                    <td>🧠 AI Quant Lab (ML backtest)</td>
                </tr>
            </tbody>
        </table>
        """
        st.markdown(features_html, unsafe_allow_html=True)

    with col2:
        if st.button("Sign in with Google", key="google_signin"):
            st.login("google")

else:
    user = get_or_create_user()
    if user:
        pic = user.get("picture") or ""
        name = user.get("name") or "User"
        email = user.get("email") or ""

        welcome_html = f"""
        <div class="welcome-banner">
            <img src="{pic}" class="welcome-avatar" onerror="this.style.display='none'"/>
            <div class="welcome-text">
                <p class="welcome-greet">Welcome back, {name} 👋</p>
                <p class="welcome-sub">{email} · Logged in</p>
            </div>
        </div>
        """
        st.markdown(welcome_html, unsafe_allow_html=True)

        # Legacy data claim
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


# ═══════════════════════════════════════════════════════════
# MARKET INDICES
# ═══════════════════════════════════════════════════════════
st.markdown('<div class="section-h">📊 Market Indices</div>', unsafe_allow_html=True)

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


# ═══════════════════════════════════════════════════════════
# QUICK ACTIONS
# ═══════════════════════════════════════════════════════════
st.markdown('<div class="section-h">⚡ Quick Actions</div>', unsafe_allow_html=True)

# Define quick actions: (path, icon, title, description)
if is_logged_in():
    actions = [
        ("app_pages/5_Portfolio.py",    "💼", "My Portfolio",   "Track holdings, performance & taxes"),
        ("app_pages/10_Watchlist.py",   "⭐", "Watchlist",      "Get notified on price moves"),
        ("app_pages/2_AI_Quant_Lab.py", "🧠", "AI Quant Lab",   "Run ML-based backtests"),
        ("app_pages/3_Heatmap.py",      "🗺️", "Market Heatmap", "S&P 1500 sector view"),
        ("app_pages/4_Stock_Detail.py", "📈", "Stock Search",   "Charts + fundamentals"),
        ("app_pages/8_Screener.py",     "🔍", "Screener",       "Filter by valuation, momentum"),
        ("app_pages/9_Compare.py",      "⚖️", "Compare",        "Side-by-side comparison"),
        ("app_pages/6_Sentiment.py",    "🧭", "Sentiment",      "Fear & Greed + news"),
    ]
else:
    actions = [
        ("app_pages/3_Heatmap.py",      "🗺️", "Heatmap",       "S&P 1500 sector treemap"),
        ("app_pages/4_Stock_Detail.py", "📈", "Stock Search",   "Charts + fundamentals"),
        ("app_pages/8_Screener.py",     "🔍", "Screener",       "Filter stocks"),
        ("app_pages/9_Compare.py",      "⚖️", "Compare",        "Compare 2-5 stocks"),
        ("app_pages/6_Sentiment.py",    "🧭", "Sentiment",      "Fear & Greed + news"),
        ("app_pages/7_Calendar.py",     "📅", "Calendar",       "Earnings & economic events"),
    ]

# Render as button grid
n_cols = 4
for row_start in range(0, len(actions), n_cols):
    cols = st.columns(n_cols)
    for i, action in enumerate(actions[row_start:row_start + n_cols]):
        page_path, icon, title, desc = action
        with cols[i]:
            if st.button(
                f"{icon}  {title}\n\n{desc}",
                key=f"qa_{page_path}",
                use_container_width=True,
            ):
                st.switch_page(page_path)

# Quick actions card styling
st.markdown("""
<style>
/* Make Quick Action buttons look like cards */
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button {
    background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5)) !important;
    border: 1px solid rgba(59,130,246,0.2) !important;
    border-radius: 12px !important;
    padding: 18px !important;
    height: 110px !important;
    text-align: left !important;
    transition: all 0.2s ease !important;
    color: #F8FAFC !important;
    white-space: pre-wrap !important;
    line-height: 1.4 !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button:hover {
    border-color: rgba(59,130,246,0.6) !important;
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 24px rgba(59,130,246,0.18) !important;
}
[data-testid="stHorizontalBlock"] [data-testid="stButton"] button p {
    color: #F8FAFC !important;
    font-size: 14px !important;
    margin: 0 !important;
}
</style>
""", unsafe_allow_html=True)
