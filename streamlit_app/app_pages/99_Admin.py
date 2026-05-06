"""Admin page — user approval management (owner only)."""

import streamlit as st
from services.auth_service import (
    require_auth,
    approve_user,
    revoke_user,
    get_all_users,
    _OWNER_EMAIL,
)

user = require_auth()

if user["email"].lower() != _OWNER_EMAIL.lower():
    st.error("접근 권한이 없습니다.")
    st.stop()

st.title("👤 사용자 관리")

users = get_all_users()
pending  = [u for u in users if not u["is_approved"]]
approved = [u for u in users if u["is_approved"]]

# ── 승인 대기 ─────────────────────────────────────────────────────────
st.subheader(f"승인 대기 ({len(pending)}명)")

if not pending:
    st.caption("대기 중인 사용자가 없습니다.")
else:
    for u in pending:
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(
                f"**{u['name'] or '(이름 없음)'}** · `{u['email']}`  \n"
                f"<span style='font-size:12px;color:#94A3B8'>가입: {(u['created_at'] or '')[:10]}</span>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("✅ 승인", key=f"approve_{u['id']}", type="primary"):
                approve_user(u["id"])
                st.rerun()

st.divider()

# ── 승인된 사용자 ─────────────────────────────────────────────────────
st.subheader(f"승인된 사용자 ({len(approved)}명)")

for u in approved:
    col_info, col_btn = st.columns([5, 1])
    with col_info:
        st.markdown(
            f"**{u['name'] or '(이름 없음)'}** · `{u['email']}`  \n"
            f"<span style='font-size:12px;color:#94A3B8'>마지막 접속: {(u['last_login'] or '')[:16]}</span>",
            unsafe_allow_html=True,
        )
    with col_btn:
        is_owner = u["email"].lower() == _OWNER_EMAIL.lower()
        if not is_owner:
            if st.button("🚫 취소", key=f"revoke_{u['id']}"):
                revoke_user(u["id"])
                st.rerun()
        else:
            st.caption("(owner)")
