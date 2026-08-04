"""Shared visual language for the site: one CSS injection + a handful of
layout primitives (top nav, footer, section headers) that every page
composes from. Keeping this in one module is what makes the three pages
read as one site instead of three different Streamlit apps.

Design direction: editorial / studio — monochrome base (ink + paper) with a
single loud accent, oversized serif display type, hairline rules instead of
boxed-shadow cards, and asymmetric grids.

Implementation note: Streamlit renders every st.markdown() call as its own
isolated HTML fragment. Opening a <div> in one call and closing it many
calls later (after native widgets in between) does NOT nest them in the
real DOM — the browser silently auto-closes the div at the end of that one
fragment, and everything "inside" ends up as unstyled siblings instead.
Any section that mixes raw HTML with native widgets (columns, tabs,
expanders) is therefore built with `st.container(key=...)`, which *does*
wrap its children for real, and is styled here via the stable `st-key-*`
class Streamlit attaches to that container.
"""
from __future__ import annotations

import html as _html

import streamlit as st

from common import db

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+JP:wght@500;600;700;900&family=Noto+Sans+JP:wght@300;400;500;600;700&display=swap');

:root{
  --ink:#111110;
  --ink-soft:#5c584f;
  --paper:#f5f2ea;
  --paper-2:#eae5d7;
  --accent:#d5391f;
  --line-soft:#c9c2ac;
}

html, body, [class*="css"], .stApp { font-family:'Noto Sans JP', -apple-system, 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif; }
.stApp{ background:var(--paper); color:var(--ink); }
h1,h2,h3,h4, .serif { font-family:'Noto Serif JP','Hiragino Mincho ProN',serif; letter-spacing:.01em; }
p, li { line-height:1.9; }
::selection{ background:var(--accent); color:#fff; }

/* ---- hide default streamlit chrome so this reads as a real site ---- */
#MainMenu, header[data-testid="stHeader"], footer,
[data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
  display:none !important;
}
.block-container{ padding:0 !important; max-width:100% !important; }
div[data-testid="stAppViewBlockContainer"]{ padding-top:0 !important; }
div[data-testid="stMainBlockContainer"]{ padding-top:0 !important; padding-bottom:0 !important; }
.stApp > div:first-child{ padding-top:0 !important; }

/* ---- layout helpers (safe only inside a single self-contained markdown call) ---- */
.wrap{ max-width:1320px; margin:0 auto; padding:0 40px; }
@media (max-width:640px){ .wrap{ padding:0 20px; } }
.hr-hair{ border:none; border-top:1px solid var(--line-soft); margin:0; }

/* ---- section containers: each wraps a `st.container(key=...)` block.
   "sec-*" keys sit on paper; add an explicit background rule per key when a
   section needs paper-2 or ink. "dark-*" keys always get the ink treatment. ---- */
[class*="st-key-sec-"] > div, [class*="st-key-dark-"] > div{ max-width:1320px; margin:0 auto; padding:0 40px; }
[class*="st-key-dark-"]{ background:var(--ink); color:var(--paper); }

/* index / eyebrow labels, agency-style */
.idx{ font-size:.78rem; letter-spacing:.28em; text-transform:uppercase; color:var(--accent); font-weight:700; margin-bottom:18px; display:flex; align-items:center; gap:10px; }
.idx::before{ content:""; width:34px; height:1px; background:var(--accent); display:inline-block; }

.disp{ font-family:'Noto Serif JP',serif; font-weight:900; line-height:1.04; letter-spacing:-.01em; color:var(--ink); }
.disp .accent{ color:var(--accent); font-style:italic; }

.section-title{ font-size:clamp(1.9rem,3.4vw,2.6rem); font-weight:800; margin:0 0 6px 0; color:var(--ink); }
[class*="st-key-dark-"] .section-title{ color:var(--paper); }
.section-sub{ color:var(--ink-soft); font-size:1.02rem; margin-top:14px; max-width:640px; }
[class*="st-key-dark-"] .section-sub{ color:#c9c4b6; }
.section-head-row{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap; margin-bottom:40px; }
.section-num{ font-family:'Noto Serif JP',serif; font-size:.95rem; color:var(--ink-soft); letter-spacing:.06em; }
[class*="st-key-dark-"] .section-num{ color:#8a8577; }

/* ---- top nav ---- */
.st-key-topnav{ position:sticky; top:0; z-index:999; background:var(--paper); border-bottom:1px solid var(--ink); }
.st-key-topnav .block-container{ padding:0 !important; }
.st-key-topnav > div{ max-width:1320px; margin:0 auto; padding:2px 40px; }
.brand-mark{ display:flex; align-items:baseline; gap:10px; height:100%; padding:10px 0; }
.brand-mark .name{ font-family:'Noto Serif JP',serif; font-weight:800; font-size:1.05rem; color:var(--ink); letter-spacing:.02em; }
.brand-mark .title{ font-size:.66rem; color:var(--ink-soft); letter-spacing:.1em; }
.st-key-topnav [data-testid="stPageLink"]{ justify-content:center; }
.st-key-topnav [data-testid="stPageLink"] p{ color:var(--ink) !important; font-weight:600 !important; font-size:.82rem !important; letter-spacing:.12em !important; text-transform:uppercase; }
.st-key-topnav [data-testid="stPageLink"]:hover{ background:transparent !important; }
.st-key-topnav [data-testid="stPageLink"]:hover p{ color:var(--accent) !important; }
[class*="st-key-nav-active-"] [data-testid="stPageLink"] p{ color:var(--accent) !important; }

/* ---- fact strip (original stat band — deliberately NOT a marquee/ticker) ---- */
.st-key-fact-strip{ background:var(--ink); border-top:1px solid rgba(245,242,234,.16); border-bottom:1px solid rgba(245,242,234,.16); }
.st-key-fact-strip > div{ max-width:1320px; margin:0 auto; padding:26px 40px; }
.fact-row{ display:grid; grid-template-columns:repeat(4,1fr); }
@media (max-width:820px){ .fact-row{ grid-template-columns:repeat(2,1fr); row-gap:20px; } }
.fact{ padding:0 22px; border-left:1px solid rgba(245,242,234,.2); }
.fact:first-child{ border-left:none; padding-left:0; }
@media (max-width:820px){ .fact:nth-child(2n+1){ border-left:none; padding-left:0; } }
.fact .num{ font-family:'Noto Serif JP',serif; font-weight:800; font-size:1.9rem; color:#fff; line-height:1; }
.fact .num .accent{ color:var(--accent); }
.fact .lbl{ font-size:.72rem; letter-spacing:.1em; color:#a8a294; margin-top:8px; text-transform:uppercase; }

/* ---- buttons ---- */
.stButton>button, .stLinkButton a, .stDownloadButton>button, .stPageLink a{ border-radius:0 !important; }
.st-key-hero-actions > div{ max-width:1320px; margin:0 auto; padding:0 40px; }

[class*="st-key-cta-"] a, [class*="st-key-cta-"] button{
  border-radius:0 !important; font-weight:700 !important; letter-spacing:.04em !important;
  background:transparent !important;
}
[class*="st-key-cta-light"] a, [class*="st-key-cta-light"] button{ border:1px solid var(--ink) !important; }
[class*="st-key-cta-light"] a p, [class*="st-key-cta-light"] a div, [class*="st-key-cta-light"] button p, [class*="st-key-cta-light"] button div{ color:var(--ink) !important; }
[class*="st-key-cta-primary"] a, [class*="st-key-cta-primary"] button{ background:var(--accent) !important; border:1px solid var(--accent) !important; }
[class*="st-key-cta-primary"] a p, [class*="st-key-cta-primary"] a div, [class*="st-key-cta-primary"] button p, [class*="st-key-cta-primary"] button div{ color:#fff !important; }
[class*="st-key-cta-dark"] a, [class*="st-key-cta-dark"] button{ border:1px solid var(--paper) !important; }
[class*="st-key-cta-dark"] a p, [class*="st-key-cta-dark"] a div, [class*="st-key-cta-dark"] button p, [class*="st-key-cta-dark"] button div{ color:var(--paper) !important; }

/* ---- hero (home): asymmetric split, duotone photo bleed ---- */
.hero{ position:relative; background:var(--paper); overflow:hidden; }
.hero-grid{ display:grid; grid-template-columns:1.15fr 1fr; align-items:stretch; min-height:78vh; }
@media (max-width:900px){ .hero-grid{ grid-template-columns:1fr; min-height:auto; } }
.hero-text{ display:flex; flex-direction:column; justify-content:center; padding:64px 0 64px 40px; max-width:640px; }
@media (max-width:900px){ .hero-text{ padding:56px 20px 40px 20px; max-width:none; } }
.hero-name{ font-size:clamp(3.4rem,7.4vw,6.2rem); }
.hero-tagline{ color:var(--ink-soft); font-size:1.1rem; max-width:480px; margin-top:22px; line-height:1.9; }
.hero-photo{ position:relative; overflow:hidden; }
.hero-photo img{ width:100%; height:100%; object-fit:cover; object-position:top center; filter:grayscale(1) contrast(1.08) brightness(1.02); display:block; min-height:420px; }
@media (max-width:900px){ .hero-photo img{ min-height:320px; } }
.hero-photo .frame-num{ position:absolute; left:20px; bottom:20px; color:#fff; font-family:'Noto Serif JP',serif; font-size:.82rem; letter-spacing:.08em; mix-blend-mode:difference; }

.st-key-profile-photo [data-testid="stImage"] img{ filter:grayscale(1) contrast(1.08); }

/* ---- page header band (profile / policy) ---- */
.page-hero{ position:relative; background:var(--paper); padding:88px 0 0 0; border-bottom:1px solid var(--ink); }
.page-hero .idx{ margin-bottom:22px; }
.page-hero h1{ font-size:clamp(3rem,8vw,6.4rem); margin:0; }
.page-hero p{ color:var(--ink-soft); max-width:600px; font-size:1.04rem; margin:22px 0 0 0; }
.page-hero .foot-row{ display:flex; justify-content:space-between; align-items:center; padding:26px 0; margin-top:40px; border-top:1px solid var(--line-soft); }
.page-hero .foot-row span{ font-size:.78rem; letter-spacing:.14em; color:var(--ink-soft); text-transform:uppercase; }

/* ---- asymmetric tile grid (internal-only quick links) ---- */
.tile-grid{ display:grid; grid-template-columns:repeat(2,1fr); gap:2px; background:var(--ink); }
@media (max-width:700px){ .tile-grid{ grid-template-columns:1fr !important; } }
.tile{ position:relative; overflow:hidden; display:block; text-decoration:none; background:var(--ink); aspect-ratio:5/4; }
.tile img{ width:100%; height:100%; object-fit:cover; filter:grayscale(1) contrast(1.05); transition:filter .5s ease, transform .8s ease; transform:scale(1.01); }
.tile:hover img{ filter:grayscale(0) contrast(1.05); transform:scale(1.06); }
.tile-scrim{ position:absolute; inset:0; background:linear-gradient(180deg, rgba(17,17,16,0) 45%, rgba(17,17,16,.92) 100%); }
.tile-label{ position:absolute; left:22px; right:22px; bottom:18px; color:#fff; font-weight:700; font-size:1.15rem; font-family:'Noto Serif JP',serif; display:flex; justify-content:space-between; align-items:flex-end; }
.tile-label span{ font-family:'Noto Sans JP',sans-serif; font-weight:500; font-size:.68rem; letter-spacing:.16em; color:#cfcabc; }
.tile-label .arrow{ font-family:'Noto Sans JP',sans-serif; font-size:1.3rem; transition:transform .3s ease; }
.tile:hover .tile-label .arrow{ transform:translate(4px,-4px); }

/* ---- editorial list rows (news / positions) ---- */
.erow{ display:grid; grid-template-columns:36px 90px 1fr auto; gap:20px; align-items:baseline; padding:22px 0; border-bottom:1px solid var(--line-soft); }
.erow:first-child{ border-top:1px solid var(--ink); }
@media (max-width:700px){ .erow{ grid-template-columns:28px 1fr; row-gap:6px; } .erow .news-date{ grid-column:2; order:1; } .erow .news-catwrap{ grid-column:2; order:2; } .erow .erow-title{ grid-column:1/3; order:3; } }
.erow .n{ font-family:'Noto Serif JP',serif; color:var(--ink-soft); font-size:.85rem; }
.erow .news-date{ font-size:.85rem; color:var(--ink-soft); font-variant-numeric:tabular-nums; }
.erow .news-cat{ font-size:.68rem; font-weight:700; letter-spacing:.1em; color:var(--accent); border:1px solid var(--accent); padding:2px 10px; display:inline-block; white-space:nowrap; }
.erow .erow-title{ color:var(--ink); font-weight:600; line-height:1.6; }
.erow .erow-title a{ color:var(--ink); text-decoration:none; background-image:linear-gradient(var(--accent),var(--accent)); background-repeat:no-repeat; background-size:0% 1px; background-position:0 100%; transition:background-size .3s ease; padding-bottom:2px; }
.erow .erow-title a:hover{ background-size:100% 1px; color:var(--accent); }

/* ---- quote ---- */
.quote-block{ position:relative; padding:0; }
.quote-block .mark{ font-family:'Noto Serif JP',serif; font-size:5rem; color:var(--accent); line-height:1; margin-bottom:0; }
.quote-block p{ font-family:'Noto Serif JP',serif; font-size:clamp(1.3rem,2.6vw,1.9rem); line-height:1.9; color:var(--ink); white-space:pre-line; font-weight:600; }
[class*="st-key-dark-"] .quote-block p{ color:var(--paper); }
.quote-block .cite{ margin-top:22px; color:var(--ink-soft); font-size:.86rem; letter-spacing:.05em; }
[class*="st-key-dark-"] .quote-block .cite{ color:#a8a294; }

/* ---- policy pillar columns (hairline-divided, not boxed) ---- */
.pillar-row{ display:grid; grid-template-columns:repeat(3,1fr); }
@media (max-width:900px){ .pillar-row{ grid-template-columns:1fr; } }
.pillar{ padding:34px 34px 0 0; border-top:2px solid var(--ink); }
.pillar-row .pillar + .pillar{ border-left:1px solid var(--line-soft); padding-left:34px; }
@media (max-width:900px){ .pillar-row .pillar + .pillar{ border-left:none; border-top:1px solid var(--line-soft); padding-left:0; padding-top:34px; margin-top:34px; } }
.pillar .label{ font-size:.76rem; letter-spacing:.18em; color:var(--accent); font-weight:700; text-transform:uppercase; margin-bottom:14px; }
.pillar h4{ font-size:1.5rem; margin:0 0 14px 0; color:var(--ink); }
.pillar p{ color:var(--ink-soft); margin:0; white-space:pre-line; }

.policy-row{ display:grid; grid-template-columns:1fr 1fr; gap:0; border-top:1px solid var(--line-soft); }
@media (max-width:750px){ .policy-row{ grid-template-columns:1fr; } }
.policy-cell{ padding:30px 30px 30px 0; border-bottom:1px solid var(--line-soft); }
.policy-row .policy-cell:nth-child(2n){ padding-left:30px; border-left:1px solid var(--line-soft); }
@media (max-width:750px){ .policy-row .policy-cell:nth-child(2n){ padding-left:0; border-left:none; } }
.policy-cell h4{ font-family:'Noto Serif JP',serif; font-size:1.2rem; margin:0 0 10px 0; color:var(--ink); }
[class*="st-key-dark-"] .policy-cell h4{ color:var(--paper); }
.policy-cell p{ color:var(--ink-soft); margin:0; white-space:pre-line; }
[class*="st-key-dark-"] .policy-cell p{ color:#c9c4b6; }
[class*="st-key-dark-"] .policy-cell{ border-color:rgba(245,242,234,.22); }
[class*="st-key-dark-"] .policy-row{ border-color:rgba(245,242,234,.22); }

/* ---- badges ---- */
.badge-row{ display:flex; flex-wrap:wrap; gap:8px; }
.badge{ display:inline-block; border:1px solid var(--ink); color:var(--ink); font-size:.78rem; font-weight:600; padding:5px 14px; letter-spacing:.02em; }

/* ---- timeline (career) ---- */
.timeline{ border-top:1px solid var(--ink); }
.timeline-item{ display:grid; grid-template-columns:170px 1fr; gap:24px; padding:20px 0; border-bottom:1px solid var(--line-soft); }
@media (max-width:640px){ .timeline-item{ grid-template-columns:1fr; gap:4px; } }
.timeline-date{ font-family:'Noto Serif JP',serif; font-size:.95rem; color:var(--accent); font-weight:700; letter-spacing:.02em; }
.timeline-event{ color:var(--ink); }

/* ---- position list ---- */
.pos-item{ padding:16px 0; border-bottom:1px solid var(--line-soft); }
.pos-item:first-child{ border-top:1px solid var(--line-soft); }
.pos-title{ color:var(--ink); font-weight:600; }
.pos-period{ color:var(--ink-soft); font-size:.85rem; margin-top:2px; }
[class*="st-key-dark-"] .pos-item{ border-color:rgba(245,242,234,.2); }
[class*="st-key-dark-"] .pos-title{ color:var(--paper); }
[class*="st-key-dark-"] .pos-period{ color:#a8a294; }
[class*="st-key-dark-"] [data-baseweb="tab-list"]{ border-bottom-color:rgba(245,242,234,.2) !important; }
[class*="st-key-dark-"] [data-baseweb="tab"] p{ color:#c9c4b6 !important; font-weight:600 !important; letter-spacing:.06em; text-transform:uppercase; font-size:.78rem !important; }
[class*="st-key-dark-"] [aria-selected="true"] p{ color:var(--accent) !important; }
[data-baseweb="tab-highlight"]{ background-color:var(--accent) !important; }

/* stat list (profile "about") */
.stat-row{ display:grid; grid-template-columns:1fr 2fr; gap:24px; padding:22px 0; border-bottom:1px solid var(--line-soft); }
@media (max-width:640px){ .stat-row{ grid-template-columns:1fr; gap:6px; } }
.stat-row .k{ font-size:.76rem; letter-spacing:.14em; color:var(--accent); font-weight:700; text-transform:uppercase; }
.stat-row .v{ font-size:1rem; color:var(--ink); white-space:pre-line; line-height:1.85; }

/* ---- hobby / human-interest callout (photo + caption, hairline framed) ---- */
.hobby-card{ border:1px solid var(--ink); }
.hobby-card img{ width:100%; display:block; }
.hobby-card .cap{ padding:20px 22px; }
.hobby-card .cap h4{ font-family:'Noto Serif JP',serif; font-size:1.05rem; margin:0 0 8px 0; }
.hobby-card .cap p{ color:var(--ink-soft); font-size:.92rem; margin:0; }
.hobby-card .credit{ display:block; margin-top:10px; font-size:.72rem; color:var(--ink-soft); opacity:.8; }
.hobby-card .credit a{ color:inherit; }

/* ---- footer ---- */
.st-key-site-footer{ background:var(--ink); color:#c9c4b6; padding:72px 0 26px 0; }
.st-key-site-footer > div{ max-width:1320px; margin:0 auto; padding:0 40px; }
.st-key-site-footer h5{ color:var(--paper); font-size:.78rem; letter-spacing:.14em; text-transform:uppercase; margin-bottom:16px; }
.st-key-site-footer a{ color:#c9c4b6; text-decoration:none; }
.st-key-site-footer a:hover{ color:#fff; }
.st-key-site-footer .foot-line{ line-height:2; font-size:.92rem; }
.st-key-site-footer .foot-brand{ font-family:'Noto Serif JP',serif; color:var(--paper); font-size:2.2rem; font-weight:800; }
.st-key-site-footer hr{ border-color:rgba(245,242,234,.16); margin:44px 0 20px 0; }
.st-key-site-footer .copyright{ color:#83806f; font-size:.78rem; text-align:center; letter-spacing:.03em; }
.st-key-site-footer .sns-row{ display:flex; gap:10px; margin-top:18px; }
.st-key-site-footer .sns-row img{ width:88px; filter:grayscale(1); opacity:.85; transition:opacity .2s, filter .2s; }
.st-key-site-footer .sns-row img:hover{ opacity:1; filter:grayscale(0); }

.stApp [data-testid="stImage"] img{ border-radius:0; }
.stApp [data-testid="stHeaderActionElements"]{ display:none !important; }

/* ---- responsive: keep nav labels from clipping at tablet widths ---- */
@media (max-width:1100px){
  .brand-mark .title{ display:none; }
  .st-key-topnav [data-testid="stPageLink"] p{ font-size:.72rem !important; letter-spacing:.04em !important; }
}
@media (max-width:560px){
  .st-key-topnav > div{ padding-left:20px; padding-right:20px; }
  .st-key-topnav [data-testid="stPageLink"] p{ font-size:.62rem !important; letter-spacing:0 !important; }
  .brand-mark .name{ font-size:.9rem; }
}
</style>
"""


def inject_base_css() -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Nav + footer + shared bits
# ---------------------------------------------------------------------------

def top_nav(home_page, profile_page, policy_page, active_url_path: str) -> None:
    with st.container(key="topnav"):
        c_brand, c_gap, c1, c2, c3 = st.columns([2.5, 1, 1, 1, 1], vertical_alignment="center")
        with c_brand:
            st.markdown(
                '<div class="brand-mark">'
                '<span class="name">前原誠司</span>'
                '<span class="title">SEIJI MAEHARA</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        for col, page, path in ((c1, home_page, "home"), (c2, profile_page, "profile"), (c3, policy_page, "policy")):
            with col:
                key = f"nav-active-{path}" if active_url_path == path else f"nav-inactive-{path}"
                with st.container(key=key):
                    st.page_link(page, label=page.title, use_container_width=True)


def fact_strip(facts: list[tuple[str, str]]) -> None:
    """An original stat band (NOT a scrolling marquee) — big numbers, static,
    hairline-divided. Each fact is (number_html, label)."""
    with st.container(key="fact-strip"):
        cells = "".join(
            f'<div class="fact"><div class="num">{num}</div><div class="lbl">{_html.escape(lbl)}</div></div>'
            for num, lbl in facts
        )
        st.markdown(f'<div class="fact-row">{cells}</div>', unsafe_allow_html=True)


def page_hero(idx: str, title: str, subtitle: str = "", foot_right: str = "") -> None:
    sub_html = f"<p>{_html.escape(subtitle)}</p>" if subtitle else ""
    foot_html = (
        f'<div class="foot-row"><span>SCROLL</span><span>{_html.escape(foot_right)}</span></div>'
        if foot_right
        else ""
    )
    st.markdown(
        f"""
        <div class="page-hero">
          <div class="wrap">
            <div class="idx">{_html.escape(idx)}</div>
            <h1 class="disp">{_html.escape(title)}</h1>
            {sub_html}
            {foot_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(idx: str, title: str, subtitle: str = "", num: str = "") -> None:
    sub_html = f'<div class="section-sub">{_html.escape(subtitle)}</div>' if subtitle else ""
    num_html = f'<div class="section-num">{_html.escape(num)}</div>' if num else ""
    st.markdown(
        f"""
        <div class="section-head-row">
          <div>
            <div class="idx">{_html.escape(idx)}</div>
            <div class="section-title serif">{_html.escape(title)}</div>
            {sub_html}
          </div>
          {num_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    info = db.get_site_info()
    sns_links = db.get_quick_links("site", "sns")

    from app.images import data_uri

    with st.container(key="site-footer"):
        c1, c2, c3 = st.columns([1.3, 1, 1])
        with c1:
            st.markdown(
                """
                <div class="foot-brand">前原 誠司</div>
                <div class="foot-line" style="margin-top:10px;">衆議院議員 ｜ 日本維新の会</div>
                """,
                unsafe_allow_html=True,
            )
            sns_html = '<div class="sns-row">'
            for link in sns_links:
                data = data_uri(link.get("local_path"))
                if data and link.get("url"):
                    sns_html += f'<a href="{_html.escape(link["url"])}" target="_blank"><img src="{data}"></a>'
            sns_html += "</div>"
            st.markdown(sns_html, unsafe_allow_html=True)
        with c2:
            st.markdown(
                f"""
                <h5>{_html.escape(info.get('kyoto_office_name',''))}</h5>
                <div class="foot-line">{_html.escape(info.get('kyoto_office_address',''))}<br>{_html.escape(info.get('kyoto_office_tel',''))}</div>
                <h5 style="margin-top:22px;">{_html.escape(info.get('tokyo_office_name',''))}</h5>
                <div class="foot-line">{_html.escape(info.get('tokyo_office_address',''))}<br>{_html.escape(info.get('tokyo_office_tel',''))}</div>
                """,
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                """
                <h5>Sitemap</h5>
                <div class="foot-line">ホーム ／ プロフィール ／ 政策</div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown(
            f"""
            <hr>
            <div class="copyright">{_html.escape(info.get('copyright', ''))}</div>
            """,
            unsafe_allow_html=True,
        )
