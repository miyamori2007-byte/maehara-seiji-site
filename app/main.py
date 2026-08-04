"""Entry point: `streamlit run app/main.py`.

Defines the three pages, renders the shared top nav + footer around
whichever page is active, and hands off to Streamlit's navigation runner.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.theme import footer, inject_base_css, top_nav
from common.db import db_exists

st.set_page_config(
    page_title="前原誠司 公式サイト",
    page_icon="🎌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_base_css()

# Optional access gate: set SITE_PASSWORD to require it before the site
# renders. Meant for sharing a work-in-progress preview link, not real auth.
_site_password = os.environ.get("SITE_PASSWORD")
if _site_password and not st.session_state.get("authed"):
    st.markdown("<div style='height:18vh;'></div>", unsafe_allow_html=True)
    col = st.columns([1, 1, 1])[1]
    with col:
        st.markdown(
            "<div class='idx' style='justify-content:center;'>PREVIEW</div>"
            "<h2 class='serif' style='text-align:center;'>前原誠司 サイトプレビュー</h2>",
            unsafe_allow_html=True,
        )
        with st.form("gate"):
            pw = st.text_input("パスワード", type="password", label_visibility="collapsed", placeholder="パスワード")
            submitted = st.form_submit_button("入室する", use_container_width=True)
        if submitted:
            if pw == _site_password:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("パスワードが違います。")
    st.stop()

if not db_exists():
    st.error(
        "データベースが見つかりません。先にスクレイパーを実行してください：\n\n"
        "`python -m scraper.scrape`"
    )
    st.stop()

home_page = st.Page("views/home.py", title="ホーム", url_path="home", default=True)
profile_page = st.Page("views/profile.py", title="プロフィール", url_path="profile")
policy_page = st.Page("views/policy.py", title="政策", url_path="policy")

pg = st.navigation([home_page, profile_page, policy_page], position="hidden")

top_nav(home_page, profile_page, policy_page, pg.url_path or "home")
pg.run()
footer()
