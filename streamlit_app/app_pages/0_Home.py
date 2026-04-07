"""Home page — landing screen with hero, welcome, and quick action cards."""

from datetime import datetime, timedelta, timezone

import streamlit as st

from services.auth_service import (
    is_logged_in, get_or_create_user, claim_legacy_data,
)
from services.market_service import get_indices, get_heatmap_data
from services.portfolio_service import get_portfolios, get_holdings
from services.sentiment_service import get_fear_greed
from services.calendar_service import get_earnings_events

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
    # ═══════════════════════════════════════════════════════
    # 🎨 GOOGLE SIGN-IN BUTTON — adjust these values freely
    # ═══════════════════════════════════════════════════════
    BTN_HEIGHT      = 320   # button height in px (match table height)
    BTN_RADIUS      = 16    # corner radius
    BTN_OFFSET_TOP  = 15     # move button up (negative) or down (positive) px
    LOGO_SIZE       = 100   # Google logo size (px)
    LOGO_TOP        = 80    # logo distance from top (px)
    TEXT_SIZE       = 25    # "Sign in with Google" font size (px)
    TEXT_BOTTOM     = 25    # text distance from bottom (px)
    # ═══════════════════════════════════════════════════════

    google_svg = (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'>"
        "<circle cx='24' cy='24' r='23' fill='white'/>"
        "<g transform='translate(8 8) scale(0.667)'>"
        "<path fill='%23EA4335' d='M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z'/>"
        "<path fill='%234285F4' d='M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z'/>"
        "<path fill='%23FBBC05' d='M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z'/>"
        "<path fill='%2334A853' d='M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z'/>"
        "</g></svg>"
    )

    st.markdown(f"""
    <style>
    /* Force button container to match table height */
    div.st-key-google_signin {{
        position: relative !important;
        width: 100% !important;
        height: {BTN_HEIGHT}px !important;
        margin-top: {BTN_OFFSET_TOP}px !important;
    }}
    div.st-key-google_signin > div,
    div.st-key-google_signin [data-testid="stButton"],
    div.st-key-google_signin [data-testid="stButton"] > div {{
        position: relative !important;
        width: 100% !important;
        height: {BTN_HEIGHT}px !important;
    }}

    .st-key-google_signin button {{
        background: linear-gradient(135deg, #4285F4 0%, #1A73E8 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: {BTN_RADIUS}px !important;
        font-family: "Google Sans", Roboto, Arial, sans-serif !important;
        font-weight: 700 !important;
        height: {BTN_HEIGHT}px !important;
        min-height: {BTN_HEIGHT}px !important;
        width: 100% !important;
        min-width: 100% !important;
        box-shadow: 0 10px 40px rgba(66,133,244,0.45) !important;
        transition: all 0.2s ease !important;
        padding: 0 !important;
        text-align: center !important;
        cursor: pointer !important;
        position: relative !important;
        overflow: hidden !important;
    }}
    .st-key-google_signin button:hover {{
        background: linear-gradient(135deg, #1A73E8 0%, #1557B0 100%) !important;
        box-shadow: 0 14px 48px rgba(66,133,244,0.65) !important;
        transform: translateY(-3px) !important;
    }}
    .st-key-google_signin button:active {{
        transform: translateY(0) !important;
    }}
    /* Google logo — always visible pseudo-element */
    .st-key-google_signin button::before {{
        content: "" !important;
        position: absolute !important;
        top: {LOGO_TOP}px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: {LOGO_SIZE}px !important;
        height: {LOGO_SIZE}px !important;
        background-image: url("{google_svg}") !important;
        background-size: contain !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        pointer-events: none !important;
    }}
    /* Button text — target ALL descendants to override Streamlit defaults */
    div.st-key-google_signin button,
    div.st-key-google_signin button *,
    div.st-key-google_signin button p,
    div.st-key-google_signin button span,
    div.st-key-google_signin button div,
    div.st-key-google_signin button div p,
    div.st-key-google_signin button div span,
    div.st-key-google_signin button > div > p,
    div.st-key-google_signin button [data-testid="stMarkdownContainer"],
    div.st-key-google_signin button [data-testid="stMarkdownContainer"] p,
    div.st-key-google_signin button [data-testid="stMarkdownContainer"] span {{
        color: #60A5FA !important;
        font-weight: 700 !important;
        font-size: {TEXT_SIZE}px !important;
        line-height: 1 !important;
    }}
    /* Position the text at bottom of the button */
    div.st-key-google_signin button > div,
    div.st-key-google_signin button [data-testid="stMarkdownContainer"] {{
        position: absolute !important;
        bottom: {TEXT_BOTTOM}px !important;
        left: 0 !important;
        right: 0 !important;
        text-align: center !important;
    }}
    div.st-key-google_signin button p {{
        margin: 0 !important;
    }}

    /* Plan comparison table */
    .plan-table {{
        margin-top: 16px;
        border-collapse: separate;
        border-spacing: 0;
        width: 100%;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid rgba(59,130,246,0.2);
    }}
    .plan-table th {{
        font-size: 13px;
        font-weight: 700;
        padding: 12px 14px;
        text-align: left;
        background: rgba(30,41,59,0.8);
        border-bottom: 1px solid rgba(59,130,246,0.25);
    }}
    .plan-table th.feature-col {{ color: #F8FAFC; width: 50%; }}
    .plan-table th.public-col {{
        color: #94A3B8;
        text-align: center;
        width: 25%;
    }}
    .plan-table th.personal-col {{
        color: #60A5FA;
        text-align: center;
        width: 25%;
        background: rgba(59,130,246,0.15);
    }}
    .plan-table td {{
        padding: 9px 14px;
        font-size: 13px;
        color: #CBD5E1;
        border-bottom: 1px solid rgba(148,163,184,0.08);
    }}
    .plan-table td.feature {{
        font-weight: 500;
    }}
    .plan-table td.check {{
        text-align: center;
        font-size: 16px;
    }}
    .plan-table td.check.yes {{ color: #10B981; }}
    .plan-table td.check.no {{ color: #475569; }}
    .plan-table td.personal-cell {{
        background: rgba(59,130,246,0.06);
    }}
    .plan-table tr:last-child td {{ border-bottom: none; }}
    </style>
    """, unsafe_allow_html=True)

    # Header text spans full width above the table+button row
    st.markdown("### 🔒 Sign in to unlock your personal workspace")
    st.markdown(
        "Track holdings, get price alerts, run AI-powered backtests, "
        "and manage multiple portfolios — all synced to your Google account."
    )

    # Now table (col1) and button (col2) start at same vertical position
    col1, col2 = st.columns([3, 2], gap="medium", vertical_alignment="top")
    with col1:
        # Plan comparison table — uses Material Symbols (same as sidebar)
        # Inline SVG icons matching sidebar :material/...:
        ic_grid    = '<span class="mi mi-grid">grid_view</span>'
        ic_chart   = '<span class="mi mi-chart">show_chart</span>'
        ic_brain   = '<span class="mi mi-brain">psychology</span>'
        ic_cal     = '<span class="mi mi-cal">calendar_month</span>'
        ic_filter  = '<span class="mi mi-filter">filter_alt</span>'
        ic_compare = '<span class="mi mi-compare">compare_arrows</span>'
        ic_folder  = '<span class="mi mi-folder">folder</span>'
        ic_star    = '<span class="mi mi-star">star</span>'
        ic_lab     = '<span class="mi mi-lab">science</span>'

        features_html = f"""
        <link href="https://fonts.googleapis.com/icon?family=Material+Symbols+Outlined" rel="stylesheet"/>
        <style>
        .mi {{
            font-family: 'Material Symbols Outlined';
            font-weight: normal;
            font-style: normal;
            font-size: 18px;
            line-height: 1;
            vertical-align: middle;
            color: #60A5FA;
            margin-right: 4px;
            font-feature-settings: 'liga';
        }}
        </style>
        <table class="plan-table">
            <thead>
                <tr>
                    <th class="feature-col">Feature</th>
                    <th class="public-col">Public</th>
                    <th class="personal-col">Personal</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td class="feature">{ic_grid} Heatmap &nbsp;·&nbsp; {ic_chart} Stock Detail</td>
                    <td class="check yes">✓</td>
                    <td class="check yes personal-cell">✓</td>
                </tr>
                <tr>
                    <td class="feature">{ic_brain} Sentiment &nbsp;·&nbsp; {ic_cal} Calendar</td>
                    <td class="check yes">✓</td>
                    <td class="check yes personal-cell">✓</td>
                </tr>
                <tr>
                    <td class="feature">{ic_filter} Screener &nbsp;·&nbsp; {ic_compare} Compare</td>
                    <td class="check yes">✓</td>
                    <td class="check yes personal-cell">✓</td>
                </tr>
                <tr>
                    <td class="feature">{ic_folder} Portfolio (holdings, P&amp;L, taxes)</td>
                    <td class="check no">—</td>
                    <td class="check yes personal-cell">✓</td>
                </tr>
                <tr>
                    <td class="feature">{ic_star} Watchlist + price alerts</td>
                    <td class="check no">—</td>
                    <td class="check yes personal-cell">✓</td>
                </tr>
                <tr>
                    <td class="feature">{ic_lab} AI Quant Lab (ML backtest)</td>
                    <td class="check no">—</td>
                    <td class="check yes personal-cell">✓</td>
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

        # ═══════════════════════════════════════════════════
        # MY PORTFOLIO SUMMARY (logged in users only)
        # ═══════════════════════════════════════════════════
        try:
            portfolios = get_portfolios(user_id=user["id"])
        except Exception:
            portfolios = []

        if portfolios:
            st.markdown(
                '<div class="section-h">💼 My Portfolio</div>',
                unsafe_allow_html=True,
            )

            # Force all metric cards on this page to same height
            st.markdown("""
            <style>
            [data-testid="stMetric"] {
                height: 130px !important;
                box-sizing: border-box !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
            }
            </style>
            """, unsafe_allow_html=True)

            # Aggregate across all user's portfolios
            total_value = 0.0
            total_cost = 0.0
            all_holdings: list[dict] = []
            for p in portfolios:
                try:
                    h_data = get_holdings(p["id"])
                except Exception:
                    continue
                if h_data and h_data.get("holdings"):
                    all_holdings.extend(h_data["holdings"])
                    total_value += h_data.get("total_value", 0)
                    total_cost += h_data.get("total_cost", 0)

            gain = total_value - total_cost
            gain_pct = (gain / total_cost * 100) if total_cost else 0
            num_positions = len(all_holdings)
            num_portfolios = len(portfolios)

            # Find top gainer & loser within holdings
            top_gainer = None
            top_loser = None
            for h in all_holdings:
                pct = h.get("unrealized_gain_pct")
                if pct is None:
                    continue
                if top_gainer is None or pct > top_gainer["unrealized_gain_pct"]:
                    top_gainer = h
                if top_loser is None or pct < top_loser["unrealized_gain_pct"]:
                    top_loser = h

            # 4 metric cards
            mc1, mc2, mc3, mc4 = st.columns(4)
            with mc1:
                st.metric(
                    "Total Value",
                    f"${total_value:,.0f}" if total_value else "$0",
                )
            with mc2:
                st.metric(
                    "Unrealized P&L",
                    f"${gain:+,.0f}" if gain else "$0",
                    delta=f"{gain_pct:+.2f}%" if gain_pct else None,
                )
            with mc3:
                st.metric(
                    "Positions",
                    f"{num_positions}",
                    help=f"{num_portfolios} portfolio(s)",
                )
            with mc4:
                if top_gainer:
                    st.metric(
                        f"Top: {top_gainer['ticker']}",
                        f"${top_gainer.get('current_price', 0):,.2f}",
                        delta=f"{top_gainer.get('unrealized_gain_pct', 0):+.2f}%",
                    )
                else:
                    st.metric("Top Position", "—")

            # Quick link to full portfolio page
            if st.button(
                "→ Open full Portfolio page",
                key="goto_portfolio",
                use_container_width=True,
            ):
                st.switch_page("app_pages/5_Portfolio.py")
        else:
            # No portfolios yet — encourage them to create one
            st.info(
                "📁 You don't have any portfolios yet. "
                "[Create your first portfolio →](javascript:void(0))",
                icon="💡",
            )


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
# TOP MOVERS (S&P 1500) — from cached heatmap data
# ═══════════════════════════════════════════════════════════
try:
    hm_data = get_heatmap_data("1d")
    all_stocks = []
    for sector in hm_data.get("sectors", []):
        for stock in sector.get("stocks", []):
            if stock.get("change_pct") is not None and stock.get("price"):
                all_stocks.append(stock)
except Exception:
    all_stocks = []

if all_stocks:
    all_stocks.sort(key=lambda x: x["change_pct"], reverse=True)
    top_gainers = all_stocks[:5]
    top_losers = all_stocks[-5:][::-1]

    st.markdown(
        '<div class="section-h">🔥 Top Movers (Today)</div>',
        unsafe_allow_html=True,
    )

    # Top movers card styling
    st.markdown("""
    <style>
    .mover-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.7), rgba(15,23,42,0.5));
        border-left: 4px solid;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 10px;
        transition: all 0.15s;
    }
    .mover-card:hover {
        transform: translateX(3px);
        box-shadow: 0 4px 14px rgba(0,0,0,0.3);
    }
    .mover-up   { border-left-color: #10B981; }
    .mover-down { border-left-color: #EF4444; }
    .mover-logo {
        width: 32px; height: 32px;
        border-radius: 6px;
        background: white;
        padding: 3px;
        object-fit: contain;
        flex-shrink: 0;
    }
    .mover-info { flex: 1; min-width: 0; }
    .mover-ticker { font-size: 14px; font-weight: 700; color: #F8FAFC; }
    .mover-name {
        font-size: 11px;
        color: #94A3B8;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .mover-stats { text-align: right; flex-shrink: 0; }
    .mover-price { font-size: 12px; color: #CBD5E1; }
    .mover-change { font-size: 13px; font-weight: 700; }
    .mover-change-up   { color: #10B981; }
    .mover-change-down { color: #EF4444; }
    .mover-section-title {
        font-size: 14px;
        font-weight: 700;
        color: #CBD5E1;
        margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    def _render_mover(stock: dict, is_up: bool) -> str:
        ticker = stock["ticker"]
        name = (stock.get("name") or ticker)[:24]
        change = stock.get("change_pct") or 0
        price = stock.get("price")
        arrow = "▲" if is_up else "▼"
        card_cls = "mover-up" if is_up else "mover-down"
        chg_cls = "mover-change-up" if is_up else "mover-change-down"
        logo_url = f"https://assets.parqet.com/logos/symbol/{ticker}?format=png"
        price_str = f"${price:,.2f}" if price else ""
        return f"""
        <div class="mover-card {card_cls}">
            <img src="{logo_url}" class="mover-logo" onerror="this.style.display='none'"/>
            <div class="mover-info">
                <div class="mover-ticker">{ticker}</div>
                <div class="mover-name">{name}</div>
            </div>
            <div class="mover-stats">
                <div class="mover-price">{price_str}</div>
                <div class="mover-change {chg_cls}">{arrow} {change:+.2f}%</div>
            </div>
        </div>
        """

    col_g, col_l = st.columns(2)
    with col_g:
        st.markdown(
            '<div class="mover-section-title">📈 Top 5 Gainers</div>',
            unsafe_allow_html=True,
        )
        gainers_html = "".join(_render_mover(s, True) for s in top_gainers)
        st.markdown(gainers_html, unsafe_allow_html=True)
    with col_l:
        st.markdown(
            '<div class="mover-section-title">📉 Top 5 Losers</div>',
            unsafe_allow_html=True,
        )
        losers_html = "".join(_render_mover(s, False) for s in top_losers)
        st.markdown(losers_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# MARKET PULSE — Mini Heatmap + Fear & Greed + Earnings Today
# ═══════════════════════════════════════════════════════════
st.markdown('<div class="section-h">🌡️ Market Pulse</div>', unsafe_allow_html=True)

import plotly.express as _px
import plotly.graph_objects as _go
import pandas as _pd
from datetime import date as _date, timedelta as _td

pulse_col1, pulse_col2, pulse_col3 = st.columns([2, 1, 1.3])

# --- Mini Heatmap (sector-level only) ---
with pulse_col1:
    st.markdown(
        '<div style="font-size:13px; font-weight:600; color:#94A3B8; '
        'margin-bottom:6px;">SECTOR HEATMAP</div>',
        unsafe_allow_html=True,
    )
    try:
        sectors = (hm_data or {}).get("sectors", [])
    except NameError:
        sectors = []

    if sectors:
        sector_rows = []
        for s in sectors:
            avg = s.get("avg_change_pct")
            cap = s.get("total_market_cap") or 1
            if avg is not None:
                avg_r = round(float(avg), 2)
                sector_rows.append({
                    "sector": s["name"],
                    "market_cap": cap,
                    "change_pct": avg_r,
                    "display": f"<b>{s['name']}</b><br>{avg_r:+.2f}%",
                    "hover": f"{s['name']}: {avg_r:+.2f}%",
                })
        if sector_rows:
            _df_sec = _pd.DataFrame(sector_rows)
            mini_fig = _px.treemap(
                _df_sec,
                path=["sector"],
                values="market_cap",
                color="change_pct",
                color_continuous_scale=[
                    "#DC2626", "#991B1B", "#1E293B", "#166534", "#16A34A",
                ],
                color_continuous_midpoint=0,
                custom_data=["display", "hover"],
            )
            mini_fig.update_traces(
                texttemplate="%{customdata[0]}",
                textfont=dict(size=14),
                hovertemplate="%{customdata[1]}<extra></extra>",
            )
            mini_fig.update_layout(
                height=260,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
            )
            st.plotly_chart(mini_fig, use_container_width=True)
        else:
            st.caption("No heatmap data.")
    else:
        st.caption("Heatmap cache empty. Visit Heatmap page to refresh.")

# --- Fear & Greed gauge ---
with pulse_col2:
    st.markdown(
        '<div style="font-size:13px; font-weight:600; color:#94A3B8; '
        'margin-bottom:6px;">FEAR &amp; GREED</div>',
        unsafe_allow_html=True,
    )
    try:
        fg = get_fear_greed()
        score = fg.get("score", 50)
        label = fg.get("label", "Neutral")
    except Exception:
        score = 50
        label = "Unavailable"

    gauge_fig = _go.Figure(_go.Indicator(
        mode="gauge+number",
        value=score,
        number={"font": {"size": 36, "color": "#F8FAFC"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#94A3B8"},
            "bar": {"color": "#3B82F6", "thickness": 0.25},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 20],   "color": "#DC2626"},
                {"range": [20, 40],  "color": "#F97316"},
                {"range": [40, 60],  "color": "#EAB308"},
                {"range": [60, 80],  "color": "#84CC16"},
                {"range": [80, 100], "color": "#22C55E"},
            ],
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))
    gauge_fig.update_layout(
        height=200,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F8FAFC"),
    )
    st.plotly_chart(gauge_fig, use_container_width=True)
    label_color = (
        "#22C55E" if score >= 60 else
        "#DC2626" if score <= 40 else "#EAB308"
    )
    st.markdown(
        f'<div style="text-align:center; font-size:14px; font-weight:700; '
        f'color:{label_color}; margin-top:-10px;">{label}</div>',
        unsafe_allow_html=True,
    )

# --- Earnings: Today & Tomorrow (top by market cap) ---
with pulse_col3:
    st.markdown(
        '<div style="font-size:13px; font-weight:600; color:#94A3B8; '
        'margin-bottom:6px;">EARNINGS</div>',
        unsafe_allow_html=True,
    )
    try:
        today = _date.today()
        tomorrow = today + _td(days=1)
        earnings = get_earnings_events(today.isoformat(), tomorrow.isoformat())
    except Exception:
        earnings = []

    # Build ticker -> market_cap map from cached heatmap (S&P 1500)
    cap_map: dict[str, float] = {}
    try:
        for sector in (hm_data or {}).get("sectors", []):
            for stk in sector.get("stocks", []):
                t = stk.get("ticker")
                mc = stk.get("market_cap") or 0
                if t:
                    cap_map[t] = mc
    except Exception:
        pass

    def _top_n_for_date(target: _date, n: int = 7) -> list[dict]:
        target_iso = target.isoformat()
        rows = [
            ev for ev in earnings
            if (ev.get("earnings_date") or "")[:10] == target_iso
            and ev.get("ticker") in cap_map
        ]
        rows.sort(key=lambda x: cap_map.get(x["ticker"], 0), reverse=True)
        return rows[:n]

    today_top = _top_n_for_date(today)
    tomorrow_top = _top_n_for_date(tomorrow)

    st.markdown("""
    <style>
    .earn-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 5px 10px;
        background: rgba(30,41,59,0.5);
        border-left: 3px solid #60A5FA;
        border-radius: 6px;
        margin-bottom: 4px;
        font-size: 12px;
    }
    .earn-logo {
        width: 20px; height: 20px;
        border-radius: 4px;
        background: white;
        padding: 2px;
        object-fit: contain;
        flex-shrink: 0;
    }
    .earn-ticker {
        font-weight: 700;
        color: #F8FAFC;
        min-width: 50px;
    }
    .earn-cap {
        color: #94A3B8;
        font-size: 11px;
        margin-left: auto;
    }
    .earn-day-label {
        font-size: 11px;
        font-weight: 700;
        color: #60A5FA;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 6px 0 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    def _fmt_cap(mc: float) -> str:
        if mc >= 1e12:
            return f"${mc / 1e12:.1f}T"
        if mc >= 1e9:
            return f"${mc / 1e9:.0f}B"
        if mc >= 1e6:
            return f"${mc / 1e6:.0f}M"
        return "—"

    def _render_group(label: str, rows: list[dict]) -> None:
        st.markdown(f'<div class="earn-day-label">{label}</div>', unsafe_allow_html=True)
        if not rows:
            st.caption("No major earnings.")
            return
        items_html = ""
        for ev in rows:
            ticker = ev.get("ticker", "")
            cap_str = _fmt_cap(cap_map.get(ticker, 0))
            logo = f"https://assets.parqet.com/logos/symbol/{ticker}?format=png"
            items_html += f"""
            <div class="earn-item">
                <img src="{logo}" class="earn-logo" onerror="this.style.display='none'"/>
                <span class="earn-ticker">{ticker}</span>
                <span class="earn-cap">{cap_str}</span>
            </div>
            """
        st.markdown(items_html, unsafe_allow_html=True)

    _render_group(f"Today · {today.strftime('%a %m/%d')}", today_top)
    _render_group(f"Tomorrow · {tomorrow.strftime('%a %m/%d')}", tomorrow_top)


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
