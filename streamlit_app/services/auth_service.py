"""Authentication service using Streamlit's native OIDC (Google).

Streamlit 1.42+ provides st.login() / st.logout() / st.user.
This module wraps user storage in SQLite and provides helpers.
"""

import hashlib
import hmac as hmac_lib
import logging
import urllib.parse
import urllib.request
import json
from datetime import datetime

import streamlit as st

from database import get_connection

logger = logging.getLogger(__name__)

_OWNER_EMAIL    = "sksk28y@gmail.com"
_APPROVE_SECRET = "aiquantlab-approve-2026"
_APPROVE_BASE   = "https://aiquantlab-stocklab.netlify.app/.netlify/functions/approve-user"


def _make_approve_url(email: str) -> str:
    token = hmac_lib.new(_APPROVE_SECRET.encode(), email.lower().encode(), hashlib.sha256).hexdigest()
    return f"{_APPROVE_BASE}?email={urllib.parse.quote(email.lower())}&token={token}"


def _send_telegram(text: str) -> None:
    try:
        tg_token = st.secrets.get("telegram", {}).get("bot_token", "")
        tg_chat_id = str(st.secrets.get("telegram", {}).get("chat_id", ""))
    except Exception:
        return
    if not tg_token or not tg_chat_id:
        return
    try:
        data = json.dumps({"chat_id": tg_chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tg_token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def is_approved(email: str) -> bool:
    """Check approval via DB. Owner is always approved."""
    if email.lower() == _OWNER_EMAIL.lower():
        return True
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT is_approved FROM users WHERE email = ?", (email,)
        ).fetchone()
        return bool(row[0]) if row else False
    except Exception:
        return False


def approve_user(user_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
    conn.commit()


def revoke_user(user_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE users SET is_approved = 0 WHERE id = ?", (user_id,))
    conn.commit()


def get_all_users() -> list[dict]:
    """Return all registered users for admin management."""
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT id, email, name, is_approved, created_at, last_login FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [
            {"id": r[0], "email": r[1], "name": r[2],
             "is_approved": bool(r[3]), "created_at": r[4], "last_login": r[5]}
            for r in rows
        ]
    except Exception:
        return []


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

    def _lookup() -> tuple | None:
        # Always fetch a fresh connection — handles libsql stream expiry
        c = get_connection()
        r = None
        if google_sub:
            r = c.execute(
                "SELECT id, google_sub, email, name, picture FROM users WHERE google_sub = ?",
                (google_sub,),
            ).fetchone()
        if not r:
            r = c.execute(
                "SELECT id, google_sub, email, name, picture FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return r

    try:
        row = _lookup()
    except Exception as e:
        logger.warning("users lookup failed (%s) — resetting conn + re-running init_db()", e)
        try:
            from database import init_db as _init, reset_connection
            reset_connection()
            _init()
            row = _lookup()
        except Exception:
            logger.exception("users lookup retry also failed")
            return None

    conn = get_connection()

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

    # Create new user (owner is auto-approved)
    auto_approved = 1 if email.lower() == _OWNER_EMAIL.lower() else 0
    cur = conn.execute(
        """INSERT INTO users (google_sub, email, name, picture, last_login, is_approved)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (google_sub, email, name, picture, now, auto_approved),
    )
    conn.commit()
    new_id = cur.lastrowid
    logger.info("Created new user: id=%d email=%s", new_id, email)

    # Notify admin via Telegram for non-owner new users
    if not auto_approved:
        approve_url = _make_approve_url(email)
        msg = (
            f"🔔 <b>AI Quant Lab 접근 요청 (Streamlit)</b>\n\n"
            f"👤 이름: {name or '(없음)'}\n"
            f"📧 이메일: {email}\n\n"
            f"아래 링크를 클릭하면 즉시 승인됩니다:\n"
            f"<a href=\"{approve_url}\">✅ 승인하기</a>"
        )
        _send_telegram(msg)

    return {
        "id": new_id,
        "google_sub": google_sub,
        "email": email,
        "name": name,
        "picture": picture,
    }


def require_auth() -> dict:
    """Page guard: stop rendering if not logged in or not approved.

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

    if not is_approved(user["email"]):
        approve_url = _make_approve_url(user["email"])
        subject = urllib.parse.quote(f"AI Quant Lab 접근 요청 — {user['email']}")
        body = urllib.parse.quote(
            f"다음 사용자의 접근 요청입니다.\n\n"
            f"이메일: {user['email']}\n"
            f"이름: {user.get('name', '')}\n\n"
            f"아래 링크를 클릭하면 자동으로 승인됩니다 (Streamlit + 리포트 앱 동시 적용):\n\n"
            f"{approve_url}\n\n"
            f"승인 후 사용자에게 새로고침하라고 안내해주세요."
        )
        mailto = f"mailto:{_OWNER_EMAIL}?subject={subject}&body={body}"

        st.title("⏳ Access Pending Approval")
        st.markdown(f"**{user['email']}** 계정이 등록되었지만 아직 승인되지 않았습니다.")
        st.info("Your account has been registered but is awaiting admin approval.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 승인 받았어요 (확인)", type="primary", key="check_approval"):
                st.rerun()
        with col2:
            st.link_button("📧 관리자에게 접근 요청", mailto)

        if st.button("Logout", key="logout_pending"):
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
    """Render user info + compact logout button at top of sidebar.

    Also renders the global EN/KO language toggle right above the
    account block — this is the only place we mount it so every page
    sees the same toggle in the same location.
    """
    # Lazy import to avoid circular deps
    from services.i18n import render_lang_toggle
    render_lang_toggle(location="sidebar")

    if not is_logged_in():
        return

    # Fail-soft: never crash the whole app if the users table is
    # missing/locked or the auth lookup fails for some reason. The page
    # should still render — the user just won't see the profile card.
    try:
        user = get_or_create_user()
    except Exception:
        logger.exception("render_user_sidebar: get_or_create_user failed")
        return
    if not user:
        return

    # ─────────────────────────────────────────────────────
    # Sidebar Account — adjustable knobs (edit these numbers!)
    # ─────────────────────────────────────────────────────
    SB_PROFILE_WIDTH   = 4      # profile column ratio
    SB_LOGOUT_WIDTH    = 1      # logout column ratio
    SB_PROFILE_HEIGHT  = 52     # profile card height (px)
    SB_PROFILE_PAD     = 8      # profile card padding (px)
    SB_PROFILE_RADIUS  = 8      # profile card border radius (px)
    SB_AVATAR_SIZE     = 36     # profile avatar diameter (px)
    SB_NAME_FONT       = 14     # name font size (px)
    SB_EMAIL_FONT      = 10     # email font size (px)

    # Logout button — independent from profile because Streamlit wraps
    # the button in extra divs that add their own height
    SB_LOGOUT_HEIGHT     = 50      # logout button height (px) — tweak to match profile visually
    SB_LOGOUT_BTN_WIDTH  = "50px"  # button width: "100%" | "120%" | "60px" etc.
    SB_LOGOUT_RADIUS     = 8       # logout button border radius (px)
    SB_LOGOUT_FONT       = 16      # logout icon size (px)
    SB_LOGOUT_OFFSET_X   = 80       # horizontal shift in px (negative=left, positive=right)
    SB_LOGOUT_LABEL      = "⇥"     # button text/icon

    # Subtle gray logout button
    # NOTE: We boost selector specificity (extra [data-testid] prefixes) to
    # beat the global Quick Actions rule from 0_Home.py which targets
    # [data-testid="stHorizontalBlock"] [data-testid="stButton"] button and
    # forces height:110px on every column-based button.
    st.sidebar.markdown(f"""
    <style>
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.st-key-logout_btn button,
    [data-testid="stSidebar"] div.st-key-logout_btn button,
    div.st-key-logout_btn [data-testid="stButton"] button,
    .st-key-logout_btn button {{
        padding: 0 !important;
        min-height: 0 !important;
        height: {SB_LOGOUT_HEIGHT}px !important;
        max-height: {SB_LOGOUT_HEIGHT}px !important;
        width: {SB_LOGOUT_BTN_WIDTH} !important;
        max-width: none !important;
        margin-left: {SB_LOGOUT_OFFSET_X}px !important;
        background: rgba(148,163,184,0.10) !important;
        border: 1px solid rgba(148,163,184,0.25) !important;
        color: #94A3B8 !important;
        border-radius: {SB_LOGOUT_RADIUS}px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.15s !important;
    }}
    /* Allow the button to overflow its column when SB_LOGOUT_BTN_WIDTH > 100% */
    [data-testid="stSidebar"] div.st-key-logout_btn,
    [data-testid="stSidebar"] div.st-key-logout_btn [data-testid="stButton"] {{
        overflow: visible !important;
    }}
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.st-key-logout_btn button:hover,
    .st-key-logout_btn button:hover {{
        background: rgba(148,163,184,0.20) !important;
        border-color: rgba(148,163,184,0.5) !important;
        color: #CBD5E1 !important;
        transform: none !important;
    }}
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] div.st-key-logout_btn button p,
    .st-key-logout_btn button p {{
        margin: 0 !important;
        font-size: {SB_LOGOUT_FONT}px !important;
        line-height: 1 !important;
    }}
    /* Compact account heading */
    .sidebar-account-block h3 {{
        margin: 0 0 6px 0 !important;
        padding: 0 !important;
        font-size: 1rem !important;
        border: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("### Account")

    pic = user.get("picture") or ""
    name = user.get("name") or "User"
    email = user.get("email") or ""

    col_profile, col_logout = st.sidebar.columns(
        [SB_PROFILE_WIDTH, SB_LOGOUT_WIDTH],
        vertical_alignment="center",
    )
    with col_profile:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:10px; padding:{SB_PROFILE_PAD}px;
                    background:rgba(30,41,59,0.5); border-radius:{SB_PROFILE_RADIUS}px;
                    height:{SB_PROFILE_HEIGHT}px; box-sizing:border-box;">
            <img src="{pic}" style="width:{SB_AVATAR_SIZE}px;height:{SB_AVATAR_SIZE}px;
                 border-radius:50%; object-fit:cover;" onerror="this.style.display='none'"/>
            <div style="overflow:hidden;min-width:0;">
                <div style="font-weight:600;color:#F8FAFC;font-size:{SB_NAME_FONT}px;
                     overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{name}</div>
                <div style="font-size:{SB_EMAIL_FONT}px;color:#94A3B8;
                     overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{email}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_logout:
        if st.button(SB_LOGOUT_LABEL, key="logout_btn", help="Logout"):
            st.logout()
