"""Stock Lab — redirect to external stock analysis tool."""

import streamlit as st
from components.ui import inject_css
from services.i18n import t as tr

inject_css()

TARGET_URL = "https://aiquantlab-stockreport.netlify.app/"

# Auto-redirect via meta refresh
st.markdown(
    f'<meta http-equiv="refresh" content="0; url={TARGET_URL}">',
    unsafe_allow_html=True,
)

st.markdown(f"""
<div style="text-align:center;padding:80px 20px;">
  <div style="font-size:2.5rem;margin-bottom:16px;">🔬</div>
  <h2 style="color:#F8FAFC;margin-bottom:8px;">Stock Lab</h2>
  <p style="color:#94A3B8;margin-bottom:32px;">외부 페이지로 이동 중...</p>
  <a href="{TARGET_URL}" target="_blank"
     style="display:inline-block;padding:12px 28px;background:#3B82F6;color:#fff;
            border-radius:8px;text-decoration:none;font-weight:600;">
    Stock Lab 열기 →
  </a>
</div>
""", unsafe_allow_html=True)
