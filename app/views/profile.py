from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.images import abs_path
from app.theme import page_hero, section_header
from common import db

profile = db.get_profile_basic() or {}
career = db.get_career_history()
position_categories = db.get_position_categories()

page_hero(
    "PROFILE / 01",
    "プロフィール",
    (profile.get("name_kana") or "").strip("（）"),
    foot_right="MAEHARA SEIJI — 衆議院議員",
)

# ---------------------------------------------------------------------------
# Header: photo + basics, asymmetric split
# ---------------------------------------------------------------------------

with st.container(key="sec-profile-header"):
    st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)
    col_photo, col_info = st.columns([1, 1.4], gap="large")

    with col_photo:
        with st.container(key="profile-photo"):
            portrait = db.get_images("site", "portrait")
            photo = portrait[0] if portrait else None
            if not photo:
                photo_id = profile.get("photo_image_id")
                photo = db.get_image_by_id(photo_id) if photo_id else None
            if photo and photo.local_path:
                path = abs_path(photo.local_path)
                if path:
                    st.image(path, use_container_width=True)

    with col_info:
        roles = [r for r in (profile.get("current_roles") or "").split("\n") if r]
        badges = "".join(f'<span class="badge">{html.escape(r)}</span>' for r in roles)
        st.markdown(
            f"""
            <div class="stat-row" style="border-top:1px solid var(--ink);">
              <div class="k">生年月日</div><div class="v">{html.escape(profile.get('birth_date',''))}（性別：{html.escape(profile.get('gender',''))}）</div>
            </div>
            <div class="stat-row">
              <div class="k">現在の役職</div><div class="v"><div class="badge-row">{badges}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if profile.get("dream"):
            st.markdown(
                f"""
                <div style="padding:34px 0 6px 0;">
                  <div class="quote-block"><div class="mark">&ldquo;</div>
                  <p>{html.escape(profile['dream'])}</p>
                  <div class="cite">今の夢</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# About — editorial stat rows
# ---------------------------------------------------------------------------

with st.container(key="sec-profile-about"):
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)
    section_header("ABOUT", "人となり", num="02")

    stat_fields = [
        ("注力したい分野", profile.get("focus_areas")),
        ("座右の銘", profile.get("motto")),
        ("趣味", profile.get("hobby")),
        ("好きな食べもの", profile.get("favorite_food")),
        ("チャームポイント", profile.get("charm_point")),
        ("実は私・・・", profile.get("fun_fact")),
    ]
    rows_html = ""
    for label, value in stat_fields:
        if not value:
            continue
        rows_html += (
            '<div class="stat-row">'
            f'<div class="k">{html.escape(label)}</div>'
            f'<div class="v">{html.escape(value)}</div>'
            "</div>"
        )
    st.markdown(f'<div style="border-top:1px solid var(--ink);">{rows_html}</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Career timeline
# ---------------------------------------------------------------------------

with st.container(key="sec-profile-career"):
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)
    section_header("CAREER", "経歴", num="03")
    items_html = '<div class="timeline">'
    for c in career:
        items_html += (
            '<div class="timeline-item">'
            f'<div class="timeline-date">{html.escape(c["date_text"] or "")}</div>'
            f'<div class="timeline-event">{html.escape(c["event_text"] or "")}</div>'
            "</div>"
        )
    items_html += "</div>"
    st.markdown(items_html, unsafe_allow_html=True)
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Past positions, by category
# ---------------------------------------------------------------------------

with st.container(key="dark-profile-positions"):
    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
    section_header("CAREER HIGHLIGHTS", "これまでの主な役職", num="04")
    if position_categories:
        tabs = st.tabs(position_categories)
        for tab, category in zip(tabs, position_categories):
            with tab:
                rows = db.get_positions(category)
                rows_html = ""
                for r in rows:
                    rows_html += (
                        '<div class="pos-item">'
                        f'<div class="pos-title">{html.escape(r["title_text"] or "")}</div>'
                        f'<div class="pos-period">{html.escape(r["period_text"] or "")}</div>'
                        "</div>"
                    )
                st.markdown(rows_html, unsafe_allow_html=True)
    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
