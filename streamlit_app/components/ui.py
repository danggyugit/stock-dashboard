"""Reusable UI components for visual polish."""

import logging
import traceback
from datetime import datetime, timezone, timedelta

import streamlit as st

# Configure logging once
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# --- Custom CSS (injected once per page) ---
CUSTOM_CSS = """
<style>
/* Hide Streamlit Cloud toolbar (Share, Star, GitHub, menu) */
[data-testid="stToolbar"] {
    visibility: hidden !important;
    height: 0 !important;
    position: fixed !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
.stDeployButton { display: none !important; }

/* Metric card hover + glow effect */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.4));
    border: 1px solid rgba(59, 130, 246, 0.15);
    border-radius: 12px;
    padding: 16px 20px;
    transition: all 0.25s ease;
    backdrop-filter: blur(8px);
}
[data-testid="stMetric"]:hover {
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
    transform: translateY(-2px);
}

/* Tab style */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: rgba(30, 41, 59, 0.5);
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    transition: background 0.2s;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(59, 130, 246, 0.2);
}
.stTabs [aria-selected="true"] {
    background: rgba(59, 130, 246, 0.3) !important;
    border-bottom: 2px solid #3B82F6 !important;
}

/* Subheader gradient underline */
h2, h3 {
    border-bottom: 2px solid;
    border-image: linear-gradient(90deg, #3B82F6, transparent) 1;
    padding-bottom: 6px;
}

/* DataFrame border + shadow */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

/* Plotly chart container — minimal styling, no overlay */
[data-testid="stPlotlyChart"] {
    border-radius: 12px;
}

/* Selectbox + input polish */
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    border-radius: 8px !important;
}

/* Market status badge */
.market-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: 12px;
}
.market-badge-open {
    background: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border: 1px solid rgba(16, 185, 129, 0.4);
}
.market-badge-closed {
    background: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    border: 1px solid rgba(239, 68, 68, 0.4);
}
.market-badge-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}
</style>
"""


def inject_css() -> None:
    """Inject custom CSS once. Call at top of each page."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def market_status() -> tuple[bool, str]:
    """Return (is_open, status_text). NY market hours: 9:30-16:00 ET, Mon-Fri."""
    # NY is UTC-5 (EST) or UTC-4 (EDT). Use simple offset (-4 for EDT).
    ny = datetime.now(timezone.utc) + timedelta(hours=-4)
    weekday = ny.weekday()
    minutes = ny.hour * 60 + ny.minute

    if weekday >= 5:
        return False, "Market Closed (Weekend)"
    if 570 <= minutes < 960:  # 9:30 - 16:00
        return True, "Market Open"
    if minutes < 570:
        return False, "Pre-Market"
    return False, "After Hours"


def page_header(title: str, subtitle: str | None = None) -> None:
    """Render page header with market status badge."""
    is_open, status = market_status()
    badge_class = "market-badge-open" if is_open else "market-badge-closed"

    html = f"""
    <div style="display: flex; align-items: center; margin-bottom: 8px;">
        <h1 style="margin: 0; padding: 0; border: none;">{title}</h1>
        <span class="market-badge {badge_class}">
            <span class="market-badge-pulse"></span>
            {status}
        </span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def stock_logo_url(ticker: str) -> str:
    """Return company logo URL from parqet."""
    return f"https://assets.parqet.com/logos/symbol/{ticker}?format=png"


# --- Global Sidebar Info Panel ---

def render_sidebar_info() -> None:
    """Render global info panel in sidebar (cache age, market status)."""
    from database import get_connection

    is_open, status = market_status()
    badge_color = "#10B981" if is_open else "#EF4444"

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Status")

    # Market status
    st.sidebar.markdown(
        f'<div style="padding:6px 0;">'
        f'<span style="color:{badge_color};">●</span> '
        f'<span style="font-weight:600;">{status}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Cache info
    try:
        conn = get_connection()
        # Heatmap cache
        hm_age = conn.execute(
            "SELECT updated_at FROM cache_meta WHERE key = 'heatmap'"
        ).fetchone()
        # Stock count
        sc = conn.execute("SELECT COUNT(*) FROM stocks").fetchone()
        stock_count = sc[0] if sc else 0
        # Fundamentals count
        fc = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()
        fund_count = fc[0] if fc else 0
        # Portfolio count
        pc = conn.execute("SELECT COUNT(*) FROM portfolios").fetchone()
        portfolio_count = pc[0] if pc else 0

        def _age_label(iso_str: str | None) -> str:
            if not iso_str:
                return "never"
            try:
                last = datetime.fromisoformat(iso_str)
                age_h = (datetime.now() - last).total_seconds() / 3600
                if age_h < 1:
                    return f"{int(age_h * 60)}m ago"
                if age_h < 24:
                    return f"{age_h:.1f}h ago"
                return f"{int(age_h / 24)}d ago"
            except Exception:
                return "?"

        hm_label = _age_label(hm_age[0] if hm_age else None)

        st.sidebar.caption(f"Stocks: **{stock_count}**")
        st.sidebar.caption(f"Fundamentals: **{fund_count}**")
        st.sidebar.caption(f"Portfolios: **{portfolio_count}**")
        st.sidebar.caption(f"Heatmap cache: {hm_label}")
    except Exception:
        st.sidebar.caption("Status unavailable.")

    st.sidebar.markdown("---")
    st.sidebar.caption("Stock Dashboard v1.0")
    st.sidebar.caption("Powered by yfinance, Finnhub")


# --- Error boundary helper ---

def safe_render(label: str = "section"):
    """Decorator/context manager-like helper for safe rendering.

    Usage:
        with safe_render("Holdings table"):
            st.dataframe(df)
    """
    return _SafeRenderContext(label)


class _SafeRenderContext:
    def __init__(self, label: str) -> None:
        self.label = label

    def __enter__(self) -> "_SafeRenderContext":
        return self

    def __exit__(self, exc_type, exc_value, tb) -> bool:
        if exc_type is None:
            return False
        # Log and show friendly message
        logger.exception("Error in %s", self.label)
        st.error(f"Could not load {self.label}.")
        with st.expander("Show error details"):
            st.code("".join(traceback.format_exception(exc_type, exc_value, tb)))
        return True  # suppress exception so other sections still render
