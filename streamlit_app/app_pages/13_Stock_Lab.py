"""Stock Lab — launcher page for external stock analysis tool."""

import streamlit as st
from components.ui import inject_css

inject_css()

TARGET_URL = "https://aiquantlab-stocklab.netlify.app/"

st.markdown(f"""
<div style="display:flex;flex-direction:column;align-items:center;
            justify-content:center;padding:100px 20px;text-align:center;">
  <div style="font-size:3rem;margin-bottom:20px;">🔬</div>
  <h2 style="color:#F8FAFC;margin:0 0 10px 0;font-size:1.8rem;">Stock Lab</h2>
  <p style="color:#94A3B8;margin:0 0 36px 0;font-size:1rem;">
    AI 기반 종목 분석 리포트 도구입니다.<br>새 탭에서 열립니다.
  </p>
</div>
""", unsafe_allow_html=True)

st.link_button(
    "🔬 Stock Lab 열기",
    TARGET_URL,
    use_container_width=False,
)
