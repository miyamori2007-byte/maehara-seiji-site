from __future__ import annotations

import base64
import html
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.images import abs_path, data_uri
from app.theme import fact_strip, section_header
from common import db

profile = db.get_profile_basic() or {}
hero_slides = db.get_hero_slides()
photo_news = db.get_news("photo_log")
topics_news = db.get_news("topics")


def is_old_site_link(url: str | None) -> bool:
    """True if the link points back at the old official site (maehara21.com)
    rather than a genuinely external destination — this new site stands on
    its own, so those links are dropped rather than followed."""
    if not url:
        return True
    host = urlparse(url).netloc.lower()
    return host in ("", "maehara21.com", "www.maehara21.com")


# ---------------------------------------------------------------------------
# Hero — asymmetric split: big display name / duotone photo bleed
# ---------------------------------------------------------------------------

portrait = db.get_images("site", "portrait")
hero_img = data_uri(portrait[0].local_path) if portrait else None
if not hero_img and hero_slides:
    hero_img = data_uri(hero_slides[0]["local_path"])

tagline = profile.get("dream") or ""
roles = [r for r in (profile.get("current_roles") or "").split("\n") if r]
eyebrow = roles[0] if roles else "衆議院議員（京都２区）"

photo_html = f'<img src="{hero_img}" alt="">' if hero_img else ""

st.markdown(
    f"""
    <div class="hero">
      <div class="hero-grid">
        <div class="hero-text">
          <div class="idx">{html.escape(eyebrow)}</div>
          <h1 class="disp hero-name">前原<span class="accent">誠司</span></h1>
          <p class="hero-tagline">{html.escape(tagline)}</p>
        </div>
        <div class="hero-photo">
          {photo_html}
          <div class="frame-num">MAEHARA / 01</div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(key="hero-actions"):
    c1, c2, _ = st.columns([1.1, 1.1, 3])
    with c1:
        with st.container(key="cta-primary-profile"):
            st.page_link("views/profile.py", label="プロフィールを見る")
    with c2:
        with st.container(key="cta-light-policy"):
            st.page_link("views/policy.py", label="政策を見る")

# ---------------------------------------------------------------------------
# Fact strip — original stat band (not a copy of any reference site's ticker)
# ---------------------------------------------------------------------------

career = db.get_career_history()
n_terms = 0
for c in career:
    m = re.search(r"(\d+)期目", c["event_text"] or "")
    if m:
        n_terms = max(n_terms, int(m.group(1)))
first_election_year = None
for c in career:
    if "衆議院議員総選挙において初当選" in (c["event_text"] or ""):
        first_election_year = c["date_text"]
        break

fact_strip(
    [
        (f'<span class="accent">{n_terms}</span>期' if n_terms else "—", "当選回数"),
        (first_election_year or "平成5年", "衆議院 初当選"),
        ("京都 2区", "選挙区"),
        (roles[0] if roles else "衆議院議員", "現職"),
    ]
)

# ---------------------------------------------------------------------------
# News: 活動写真館 / 新着情報 — editorial list rows
# ---------------------------------------------------------------------------

with st.container(key="sec-home-news"):
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2, gap="large")

    with col_a:
        section_header("PHOTO LOG", "活動写真館")
        rows_html = ""
        for i, n in enumerate(photo_news, start=1):
            rows_html += (
                '<div class="erow">'
                f'<div class="n">{i:02d}</div>'
                f'<div class="news-date">{html.escape(n["date_text"] or "")}</div>'
                f'<div class="erow-title">{html.escape(n["title"])}</div>'
                '<div></div>'
                "</div>"
            )
        st.markdown(rows_html or '<p style="color:var(--ink-soft);">最新情報はありません。</p>', unsafe_allow_html=True)

    with col_b:
        section_header("TOPICS", "新着情報")
        for i, n in enumerate(topics_news, start=1):
            external = not is_old_site_link(n.get("link_url"))
            row_html = (
                '<div class="erow">'
                f'<div class="n">{i:02d}</div>'
                f'<div class="news-date">{html.escape(n["date_text"] or "")}</div>'
                f'<div class="erow-title">{html.escape(n["title"])}</div>'
                f'<div class="news-catwrap"><span class="news-cat">{html.escape(n["category"] or "")}</span></div>'
                "</div>"
            )
            st.markdown(row_html, unsafe_allow_html=True)
            if n.get("body_text"):
                with st.expander("続きを読む"):
                    st.markdown(n["body_text"].replace("\n", "\n\n"))
                    if n.get("image_id"):
                        img = db.get_image_by_id(n["image_id"])
                        if img and img.local_path:
                            path = abs_path(img.local_path)
                            if path:
                                st.image(path)
                    if external:
                        with st.container(key=f"cta-light-news-{i}"):
                            st.link_button("詳しく見る", n["link_url"])
    st.markdown("<div style='height:56px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 素顔 — a personal-side callout: hobbies + a nod to his Kyoto roots
# ---------------------------------------------------------------------------

with st.container(key="sec-home-profile-teaser"):
    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
    col_text, col_photo = st.columns([1, 1], gap="large")
    with col_text:
        section_header("OFF DUTY", "素顔")
        hobby = profile.get("hobby") or ""
        motto = profile.get("motto") or ""
        st.markdown(
            f"""
            <div class="stat-row" style="border-top:1px solid var(--ink);">
              <div class="k">趣味</div><div class="v">{html.escape(hobby)}</div>
            </div>
            <div class="stat-row">
              <div class="k">座右の銘</div><div class="v">{html.escape(motto)}</div>
            </div>
            <p style="margin-top:22px;color:var(--ink-soft);">
            趣味は鉄道・SLの写真撮影。生まれ育った京都市左京区・修学院の街を今も走り抜けるのが、
            地元の足として親しまれる叡山電鉄だ。
            </p>
            """,
            unsafe_allow_html=True,
        )
        with st.container(key="cta-light-profile2"):
            st.page_link("views/profile.py", label="プロフィールをもっと見る")
    with col_photo:
        eizan_path = Path(__file__).resolve().parent.parent / "assets" / "eizan-maple-tunnel.jpg"
        eizan_b64 = base64.b64encode(eizan_path.read_bytes()).decode()
        st.markdown(
            f"""
            <div class="hobby-card">
              <img src="data:image/jpeg;base64,{eizan_b64}">
              <div class="cap">
                <h4>叡山電鉄 鞍馬線（京都市左京区）</h4>
                <p>二ノ瀬〜市原間、通称「もみじのトンネル」を行く叡山電車。</p>
                <span class="credit">Photo: Nkensei ／ <a href="https://commons.wikimedia.org/wiki/File:Eiden_Kirara_passing_the_maple_tree_tunnel.jpg" target="_blank">CC BY-SA 3.0, Wikimedia Commons</a></span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
