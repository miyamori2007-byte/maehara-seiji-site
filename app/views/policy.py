from __future__ import annotations

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.images import abs_path
from app.theme import page_hero, section_header
from common import db

nippon = db.get_policy_sections("日本のために")
kyoto = db.get_policy_sections("京都への思い")
illustration = db.get_images("policy", "illustration")

by_heading: dict[str, list[dict]] = {}
for row in nippon:
    by_heading.setdefault(row["heading"], []).append(row)

page_hero("POLICY / 02", "政策", "自らの国に誇りを持って、他国からも尊敬される国家に。")

# ---------------------------------------------------------------------------
# 目指す方針
# ---------------------------------------------------------------------------

with st.container(key="sec-policy-hoshin"):
    st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)
    section_header("日本のために", "目指す方針", num="01")
    rows_html = '<div class="policy-row">'
    for row in by_heading.get("目指す方針", []):
        rows_html += (
            '<div class="policy-cell">'
            f'<h4>{html.escape(row["subheading"] or "")}</h4>'
            f'<p>{html.escape(row["body_text"] or "")}</p>'
            "</div>"
        )
    rows_html += "</div>"
    st.markdown(rows_html, unsafe_allow_html=True)
    st.markdown("<div style='height:80px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 目指す政治家像：坂本龍馬 (quote, on dark)
# ---------------------------------------------------------------------------

ryoma = by_heading.get("目指す政治家像：坂本龍馬", [])
if ryoma:
    body = ryoma[0]["body_text"] or ""
    lines = body.split("\n")
    cite = ""
    if lines and lines[-1].startswith("引用"):
        cite = lines[-1]
        lines = lines[:-1]
    quote_text = "\n".join(lines)
    with st.container(key="dark-policy-ryoma"):
        st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
        section_header("日本のために", "目指す政治家像：坂本龍馬", num="02")
        st.markdown(
            f"""
            <div class="quote-block" style="max-width:900px;">
              <div class="mark">&ldquo;</div>
              <p>{html.escape(quote_text)}</p>
              <div class="cite">{html.escape(cite)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 目指す国家像：尊厳ある国家 (3 pillars, hairline columns)
# ---------------------------------------------------------------------------

pillars = by_heading.get("目指す国家像：尊厳ある国家", [])
if pillars:
    with st.container(key="sec-policy-pillars"):
        st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
        section_header("日本のために", "目指す国家像：尊厳ある国家", "自らの国に誇りを持って、他国からも尊敬される国家に。", num="03")
        cols_html = '<div class="pillar-row">'
        for row in pillars:
            cols_html += (
                '<div class="pillar">'
                f'<div class="label">{html.escape(row["label"] or "")}</div>'
                f'<h4 class="serif">{html.escape(row["subheading"] or "")}</h4>'
                f'<p>{html.escape(row["body_text"] or "")}</p>'
                "</div>"
            )
        cols_html += "</div>"
        st.markdown(cols_html, unsafe_allow_html=True)
        st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 京都への思い
# ---------------------------------------------------------------------------

with st.container(key="dark-policy-kyoto"):
    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
    section_header("KYOTO", "京都への思い", "京都を大切にします。", num="04")
    rows_html = '<div class="policy-row">'
    for row in kyoto:
        rows_html += (
            '<div class="policy-cell">'
            f'<h4>{html.escape(row["subheading"] or "")}</h4>'
            f'<p>{html.escape(row["body_text"] or "")}</p>'
            "</div>"
        )
    rows_html += "</div>"
    st.markdown(rows_html, unsafe_allow_html=True)

    if illustration:
        img = abs_path(illustration[0].local_path)
        if img:
            st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
            st.image(img, use_container_width=True)

    st.markdown("<div style='height:96px;'></div>", unsafe_allow_html=True)
