"""Authentication service using Streamlit's native OIDC (Google).

Streamlit 1.42+ provides st.login() / st.logout() / st.user.
This module wraps user storage in SQLite and provides helpers.
"""

import logging
from datetime import datetime

import streamlit as st

from database import get_connection

logger = logging.getLogger(__name__)


def is_logged_in() -> bool:
    """Check if user is logged in via Streamlit OIDC."""
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def get_or_create_user() -> dict | None:
    """Get current user from SQLite, creating record on first login.

    Returns:
        User dict {id, email, name, picture, google_sub} or None if not logged in.
    """
    if not is_logged_in():
        return None

    try:
        google_sub = getattr(st.user, "sub", None)
        email = getattr(st.user, "email", None)
        name = getattr(st.user, "name", email)
        picture = getattr(st.user, "picture", None)
    except Exception:
        return None

    if not email:
        return None

    conn = get_connection()
    # Try by google_sub first, then email
    row = None
    if google_sub:
        row = conn.execute(
            "SELECT id, google_sub, email, name, picture FROM users WHERE google_sub = ?",
            (google_sub,),
        ).fetchone()

    if not row:
        row = conn.execute(
            "SELECT id, google_sub, email, name, picture FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    now = datetime.now().isoformat()

    if row:
        # Update last_login + sync profile
        user_id = row[0]
        conn.execute(
            """UPDATE users SET last_login = ?, name = ?, picture = ?, google_sub = ?
               WHERE id = ?""",
            (now, name, picture, google_sub, user_id),
        )
        conn.commit()
        return {
            "id": user_id,
            "google_sub": google_sub,
            "email": email,
            "name": name,
            "picture": picture,
        }

    # Create new user
    cur = conn.execute(
        """INSERT INTO users (google_sub, email, name, picture, last_login)
           VALUES (?, ?, ?, ?, ?)""",
        (google_sub, email, name, picture, now),
    )
    conn.commit()
    new_id = cur.lastrowid
    logger.info("Created new user: id=%d email=%s", new_id, email)
    return {
        "id": new_id,
        "google_sub": google_sub,
        "email": email,
        "name": name,
        "picture": picture,
    }


def require_auth() -> dict:
    """Page guard: stop rendering if not logged in, otherwise return user dict.

    Usage at top of every protected page:
        user = require_auth()
        # rest of page uses user["id"]
    """
    if not is_logged_in():
        st.title("🔒 Sign in required")
        st.markdown("Please sign in with Google to access this page.")
        if st.button("Sign in with Google", type="primary"):
            st.login("google")
        st.stop()

    user = get_or_create_user()
    if not user:
        st.error("Could not load user profile. Please try logging out and back in.")
        if st.button("Logout"):
            st.logout()
        st.stop()
    return user


def claim_legacy_data(user_id: int) -> dict:
    """Claim portfolios/watchlist/alerts that have NULL user_id (legacy data).

    Returns counts of claimed records.
    """
    conn = get_connection()
    counts = {"portfolios": 0, "watchlist": 0, "alerts": 0}
    for table in counts:
        cur = conn.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
            (user_id,),
        )
        counts[table] = cur.rowcount
    conn.commit()
    return counts


def render_user_sidebar() -> None:
    """Render user info + compact logout button in sidebar."""
    if not is_logged_in():
        return

    user = get_or_create_user()
    if not user:
        return

    # Compact logout icon button (SVG-style logout/exit icon)
    st.sidebar.markdown("""
    <style>
    .st-key-logout_btn button {
        padding: 0 !important;
        min-height: 0 !important;
        height: 56px !important;
        width: 100% !important;
        background: rgba(239,68,68,0.10) !important;
        border: 1px solid rgba(239,68,68,0.3) !important;
        color: #EF4444 !important;
        border-radius: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.15s !important;
    }
    .st-key-logout_btn button:hover {
        background: rgba(239,68,68,0.25) !important;
        border-color: rgba(239,68,68,0.7) !important;
        transform: none !important;
    }
    .st-key-logout_btn button p {
        margin: 0 !important;
        font-size: 22px !important;
        line-height: 1 !important;
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("### Account")

    pic = user.get("picture") or ""
    name = user.get("name") or "User"
    email = user.get("email") or ""

    col_profile, col_logout = st.sidebar.columns([4, 1])
    with col_profile:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; padding:8px;
                    background:rgba(30,41,59,0.5); border-radius:8px;">
            <img src="{pic}" style="width:36px;height:36px;border-radius:50%;
                 object-fit:cover;" onerror="this.style.display='none'"/>
            <div style="overflow:hidden;min-width:0;">
                <div style="font-weight:600;color:#F8FAFC;font-size:12px;
                     overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{name}</div>
                <div style="font-size:10px;color:#94A3B8;
                     overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{email}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_logout:
        # Unicode "exit" icon (rectangle with arrow leaving)
        if st.button("⇥", key="logout_btn", help="Logout"):
            st.logout()
