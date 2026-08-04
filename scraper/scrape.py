"""Scrapes the Home / Profile / Policy pages of the official Seiji Maehara
website (https://www.maehara21.com/) and stores structured text + locally
downloaded images into a SQLite database.

Usage:
    python -m scraper.scrape

Re-run any time to refresh the dataset the Streamlit app reads from; it
always wipes and rebuilds the tables so old and new content never mix.
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import db
from common.paths import IMAGES_DIR, SOURCE_BASE_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MaeharaSiteArchiver/1.0; "
        "+https://www.maehara21.com/)"
    )
}
TIMEOUT = 20

PAGES = {
    "home": "/",
    "profile": "/profile/",
    "policy": "/policy/",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

class Fetcher:
    """Thin wrapper around requests.Session used for both page and image
    downloads, so redirects/headers/timeouts are handled consistently."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_html(self, path: str) -> tuple[str, str]:
        url = urljoin(SOURCE_BASE_URL, path)
        resp = self.session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return url, resp.text

    def get_bytes(self, url: str) -> bytes | None:
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            print(f"  ! failed to download {url}: {exc}")
            return None


MAX_IMAGE_DIM = 1600


def _optimize_image(path: Path) -> None:
    """Downscale oversized raster images in place (WordPress uploads in
    particular can be several megapixels straight out of a phone camera)."""
    try:
        with Image.open(path) as img:
            img.load()
            fmt = img.format
            w, h = img.size
            if max(w, h) <= MAX_IMAGE_DIM or fmt not in ("JPEG", "PNG"):
                return
            scale = MAX_IMAGE_DIM / max(w, h)
            resized = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            save_kwargs = {"quality": 87, "optimize": True} if fmt == "JPEG" else {"optimize": True}
            resized.save(path, format=fmt, **save_kwargs)
    except Exception as exc:  # noqa: BLE001 - best-effort optimization only
        print(f"  ! could not optimize {path.name}: {exc}")


_used_filenames: set[str] = set()


def _safe_filename(url: str) -> str:
    name = Path(urlparse(url).path).name or "image"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if "." not in name:
        name += ".jpg"
    base, ext = name.rsplit(".", 1)
    candidate = name
    n = 1
    while candidate in _used_filenames:
        candidate = f"{base}-{n}.{ext}"
        n += 1
    _used_filenames.add(candidate)
    return candidate


def download_image(fetcher: Fetcher, page_url: str, src: str, page_slug: str, category: str) -> str | None:
    """Downloads an image (resolving relative URLs against page_url) into
    data/images/<page_slug>/<category>/ and returns the path relative to
    data/images (used to build local_path), or None on failure."""
    if not src:
        return None
    abs_url = urljoin(page_url, src)
    content = fetcher.get_bytes(abs_url)
    if content is None:
        return None
    dest_dir = IMAGES_DIR / page_slug / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(abs_url)
    dest_path = dest_dir / filename
    dest_path.write_bytes(content)
    _optimize_image(dest_path)
    return str(Path(page_slug) / category / filename)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def text_with_breaks(tag: Tag | None) -> str:
    """Render a tag's text content, treating <br> as newlines, and collapse
    surrounding whitespace on each resulting line."""
    if tag is None:
        return ""
    fragment = BeautifulSoup(str(tag), "html.parser")
    for br in fragment.find_all("br"):
        br.replace_with("\n")
    raw = fragment.get_text().replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in raw.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return re.sub(r"[ \t　]+", " ", s).strip()


# ---------------------------------------------------------------------------
# Site-wide chrome (footer contact info, SNS links, party logo) — identical
# across all three pages, so we only need to read it once (from home).
# ---------------------------------------------------------------------------

def scrape_site_chrome(fetcher: Fetcher, page_url: str, soup: BeautifulSoup, conn) -> None:
    footer = soup.select_one(".footer")
    if not footer:
        return

    cols = footer.select(".footer-link-menu .row > div")
    if cols:
        brand_col = cols[0]
        logo_img = brand_col.select_one("img")
        if logo_img and logo_img.get("src"):
            local = download_image(fetcher, page_url, logo_img["src"], "site", "logo")
            db.insert_image(conn, "site", "logo", urljoin(page_url, logo_img["src"]), local,
                             alt=logo_img.get("alt", ""))
        name_span = brand_col.select_one(".fs-22")
        if name_span:
            db.set_site_info(conn, "party_rep_name", clean_text(name_span.get_text()))

    if len(cols) > 1:
        office_lines = [clean_text(li.get_text(" ", strip=True)) for li in cols[1].select("li")]
        # office_lines pattern: [京都事務所, addr, tel, 国会事務所, addr, tel]
        if len(office_lines) >= 6:
            db.set_site_info(conn, "kyoto_office_name", office_lines[0])
            db.set_site_info(conn, "kyoto_office_address", office_lines[1])
            db.set_site_info(conn, "kyoto_office_tel", office_lines[2])
            db.set_site_info(conn, "tokyo_office_name", office_lines[3])
            db.set_site_info(conn, "tokyo_office_address", office_lines[4])
            db.set_site_info(conn, "tokyo_office_tel", office_lines[5])

    # SNS banner row (Facebook / Twitter(X) / 10MTV)
    sns_labels = ["facebook", "twitter", "10mtv"]
    sns_anchors = soup.select(".section-gray .index-5-menu a")
    for i, a in enumerate(sns_anchors[:3]):
        img = a.select_one("img")
        if not img:
            continue
        local = download_image(fetcher, page_url, img["src"], "site", "sns")
        image_id = db.insert_image(conn, "site", "sns", urljoin(page_url, img["src"]), local,
                                    alt=img.get("alt", ""), sort_order=i)
        conn.execute(
            "INSERT INTO quick_links (page_slug, group_name, label, url, image_id, sort_order) VALUES (?,?,?,?,?,?)",
            ("site", "sns", sns_labels[i], urljoin(page_url, a.get("href", "")), image_id, i),
        )

    copyright_tag = footer.select_one(".credit .copyright")
    if copyright_tag:
        db.set_site_info(conn, "copyright", clean_text(copyright_tag.get_text(" ", strip=True)))

    # og:image is a much higher-resolution headshot than the small inline
    # profile photo, and makes a far better hero / portrait image.
    og_image = soup.select_one('meta[property="og:image"]')
    if og_image and og_image.get("content"):
        local = download_image(fetcher, page_url, og_image["content"], "site", "portrait")
        db.insert_image(conn, "site", "portrait", urljoin(page_url, og_image["content"]), local,
                         alt="前原誠司")


# ---------------------------------------------------------------------------
# Home page
# ---------------------------------------------------------------------------

def scrape_home(fetcher: Fetcher, page_url: str, soup: BeautifulSoup, conn) -> None:
    title = clean_text(soup.title.get_text()) if soup.title else "ホーム"
    db.upsert_page(conn, "home", title, page_url, datetime.now(timezone.utc).isoformat())

    # Hero slider
    for i, li in enumerate(soup.select(".main-visual .flexslider .slides li")):
        img = li.select_one("img")
        a = li.select_one("a")
        if not img:
            continue
        local = download_image(fetcher, page_url, img["src"], "home", "hero")
        image_id = db.insert_image(conn, "home", "hero", urljoin(page_url, img["src"]), local,
                                    alt=img.get("alt", ""), sort_order=i)
        conn.execute(
            "INSERT INTO hero_slides (image_id, link_url, sort_order) VALUES (?,?,?)",
            (image_id, urljoin(page_url, a["href"]) if a and a.get("href") else None, i),
        )

    # Three big menu tiles (活動写真館 / プロフィール / 日々是好日)
    for i, col in enumerate(soup.select(".index-menu .row .col")):
        a = col.select_one("a")
        img = col.select_one("img")
        if not a or not img:
            continue
        local = download_image(fetcher, page_url, img["src"], "home", "menu")
        image_id = db.insert_image(conn, "home", "menu", urljoin(page_url, img["src"]), local,
                                    alt=img.get("alt", ""), sort_order=i)
        conn.execute(
            "INSERT INTO quick_links (page_slug, group_name, label, url, image_id, sort_order) VALUES (?,?,?,?,?,?)",
            ("home", "menu", img.get("alt", ""), urljoin(page_url, a["href"]), image_id, i),
        )

    # Four small menu icons (政策 / 国会議事録 / 著作物 / アーカイブ)
    small_menu = soup.select_one(".index-5-menu")
    if small_menu:
        for i, col in enumerate(small_menu.select(".row .col")):
            a = col.select_one("a")
            img = col.select_one("img")
            if not a or not img:
                continue
            local = download_image(fetcher, page_url, img["src"], "home", "small_menu")
            image_id = db.insert_image(conn, "home", "small_menu", urljoin(page_url, img["src"]), local,
                                        alt=img.get("alt", ""), sort_order=i)
            conn.execute(
                "INSERT INTO quick_links (page_slug, group_name, label, url, image_id, sort_order) VALUES (?,?,?,?,?,?)",
                ("home", "small_menu", img.get("alt", ""), urljoin(page_url, a["href"]), image_id, i),
            )

    # News sections: 活動写真館 (photo log) and 新着情報 (topics)
    containers = soup.select(".container")
    section_map = {"活動写真館": "photo_log", "新着情報": "topics"}
    for container in containers:
        h3 = container.select_one("h3.top-news")
        if not h3:
            continue
        heading = clean_text(h3.contents[0]) if h3.contents else ""
        section_key = None
        for label, key in section_map.items():
            if label in heading:
                section_key = key
                break
        if not section_key:
            continue
        for i, li in enumerate(container.select("ul.newstopics > li")):
            date_span = li.select_one("span")
            date_text = ""
            category = ""
            if date_span:
                cat_span = date_span.select_one("span")
                category = clean_text(cat_span.get_text()) if cat_span else ""
                full = date_span.get_text()
                date_text = clean_text(full.replace(category, "", 1)) if category else clean_text(full)

            a = li.find("a", recursive=False)
            div = li.find("div", recursive=False)
            title = ""
            body_text = ""
            link_url = None
            image_id = None
            if a is not None:
                title = clean_text(a.get_text())
                link_url = urljoin(page_url, a.get("href", ""))
            elif div is not None:
                paragraphs = [text_with_breaks(p) for p in div.find_all("p")]
                paragraphs = [p for p in paragraphs if p]
                body_text = "\n\n".join(paragraphs)
                title = paragraphs[0] if paragraphs else ""
                first_a = div.find("a")
                if first_a and first_a.get("href"):
                    link_url = urljoin(page_url, first_a["href"])
                first_img = div.find("img")
                if first_img and first_img.get("src"):
                    local = download_image(fetcher, page_url, first_img["src"], "home", "news")
                    image_id = db.insert_image(conn, "home", "news", urljoin(page_url, first_img["src"]), local,
                                                alt=first_img.get("alt", ""))
            conn.execute(
                """INSERT INTO news_items (section, date_text, category, title, body_text, link_url, image_id, sort_order)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (section_key, date_text, category, title, body_text, link_url, image_id, i),
            )

    scrape_site_chrome(fetcher, page_url, soup, conn)


# ---------------------------------------------------------------------------
# Profile page
# ---------------------------------------------------------------------------

LABEL_MAP = {
    "現在の主な役職": "current_roles",
    "今の夢": "dream",
    "注力したい分野": "focus_areas",
    "座右の銘": "motto",
    "趣味": "hobby",
    "好きな食べもの": "favorite_food",
    "チャームポイント": "charm_point",
    "実は私・・・": "fun_fact",
}


def scrape_profile(fetcher: Fetcher, page_url: str, soup: BeautifulSoup, conn) -> None:
    title = clean_text(soup.title.get_text()) if soup.title else "プロフィール"
    db.upsert_page(conn, "profile", title, page_url, datetime.now(timezone.utc).isoformat())

    main_col = soup.select_one(".special-box-none .col-md-9")
    fields: dict[str, str] = {}
    name_image_id = None
    name_kana = ""
    birth_date = ""
    gender = ""

    if main_col:
        name_h4 = main_col.select_one("h4.title-border-left")
        if name_h4:
            img = name_h4.select_one("img")
            if img and img.get("src"):
                local = download_image(fetcher, page_url, img["src"], "profile", "name")
                name_image_id = db.insert_image(conn, "profile", "name", urljoin(page_url, img["src"]), local,
                                                 alt=img.get("alt", ""))
            full = text_with_breaks(name_h4)
            lines = full.split("\n")
            name_kana = clean_text(lines[-1]) if lines else ""

        birth_p = main_col.select_one("p.mb-20 .bold")
        if birth_p:
            m = re.match(r"(.+?生)\s*性別[：:]\s*(\S+)", clean_text(birth_p.get_text()))
            if m:
                birth_date, gender = m.group(1), m.group(2)

        for p in main_col.select("blockquote.line > p"):
            label_span = p.select_one("span.bold")
            if not label_span:
                continue
            label = clean_text(label_span.get_text()).strip("【】")
            key = LABEL_MAP.get(label)
            if not key:
                continue
            full_text = text_with_breaks(p)
            lines = full_text.split("\n")
            value = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            fields[key] = value

    photo_image_id = None
    photo_img = soup.select_one(".special-box-none .col-md-3 img")
    if photo_img and photo_img.get("src"):
        local = download_image(fetcher, page_url, photo_img["src"], "profile", "photo")
        photo_image_id = db.insert_image(conn, "profile", "photo", urljoin(page_url, photo_img["src"]), local,
                                          alt=photo_img.get("alt", ""))

    conn.execute(
        """INSERT INTO profile_basic
           (id, name_ja, name_kana, birth_date, gender, current_roles, dream, focus_areas,
            motto, hobby, favorite_food, charm_point, fun_fact, photo_image_id, name_image_id)
           VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "前原誠司", name_kana, birth_date, gender,
            fields.get("current_roles", ""), fields.get("dream", ""), fields.get("focus_areas", ""),
            fields.get("motto", ""), fields.get("hobby", ""), fields.get("favorite_food", ""),
            fields.get("charm_point", ""), fields.get("fun_fact", ""), photo_image_id, name_image_id,
        ),
    )

    # 経歴 career history
    career_container = None
    for container in soup.select(".container"):
        h3 = container.select_one("h3.top-news")
        if h3 and "経歴" == clean_text(h3.get_text()):
            career_container = container
            break
    if career_container:
        for i, li in enumerate(career_container.select("ul.newstopics > li")):
            full = text_with_breaks(li)
            parts = full.split("\n", 1)
            date_text = parts[0] if parts else ""
            event_text = parts[1] if len(parts) > 1 else ""
            conn.execute(
                "INSERT INTO career_history (date_text, event_text, sort_order) VALUES (?,?,?)",
                (date_text, event_text, i),
            )

    # これまでの主な役職 (政府 / 国会 / 衆議院 / 政党)
    sort_counters: dict[str, int] = {}
    for block in soup.select(".special-box-none-full"):
        h4 = block.select_one("h4.title-border-left")
        if not h4:
            continue
        category = clean_text(h4.get_text())
        if category in ("経歴",):
            continue
        for li in block.select("ul.newstopics > li"):
            full = text_with_breaks(li)
            parts = full.split("\n", 1)
            title_text = parts[0] if parts else ""
            period_text = parts[1] if len(parts) > 1 else ""
            idx = sort_counters.get(category, 0)
            conn.execute(
                "INSERT INTO positions (category, title_text, period_text, sort_order) VALUES (?,?,?,?)",
                (category, title_text, period_text, idx),
            )
            sort_counters[category] = idx + 1


# ---------------------------------------------------------------------------
# Policy page
# ---------------------------------------------------------------------------

def scrape_policy(fetcher: Fetcher, page_url: str, soup: BeautifulSoup, conn) -> None:
    title = clean_text(soup.title.get_text()) if soup.title else "政策"
    db.upsert_page(conn, "policy", title, page_url, datetime.now(timezone.utc).isoformat())

    containers = [c for c in soup.select(".contents .container") if c.select_one(".special-box-none")]

    group_name = "日本のために"
    sort_order = 0

    def add_section(heading: str, subheading: str, label: str, body_text: str):
        nonlocal sort_order
        conn.execute(
            """INSERT INTO policy_sections (group_name, heading, subheading, label, body_text, sort_order)
               VALUES (?,?,?,?,?,?)""",
            (group_name, heading, subheading, label, body_text, sort_order),
        )
        sort_order += 1

    for container in containers:
        box = container.select_one(".special-box-none")
        h3 = container.select_one("h3.top-news")
        if h3:
            heading_text = clean_text(h3.get_text())
            if "京都" in heading_text:
                group_name = "京都への思い"
                sort_order = 0

        top_h4 = box.select_one(":scope > h4.title-border-left")
        top_heading = clean_text(top_h4.get_text()) if top_h4 else ""

        # Cards laid out in a bootstrap row (目指す方針 / 目指す国家像)
        row = box.select_one(":scope > .row")
        if row:
            for card in row.select(":scope > .col > blockquote.line"):
                label_span = card.select_one("p > span.bold")
                label = clean_text(label_span.get_text()) if label_span else ""
                sub_span = card.select_one("h4.subtitle .text-line")
                subheading = clean_text(sub_span.get_text()) if sub_span else ""
                body_parts = []
                for p in card.select("p"):
                    if p.select_one("span.bold"):
                        continue
                    body_parts.append(text_with_breaks(p))
                body_text = "\n".join([b for b in body_parts if b])
                add_section(top_heading, subheading, label, body_text)
            continue

        # A lone intro <p> directly under the box, if any (not present today,
        # but some future edit to the site could add one).
        intro_p = box.select_one(":scope > p")
        if intro_p and clean_text(intro_p.get_text()):
            add_section(top_heading, "", "", clean_text(intro_p.get_text()))

        # Direct-child blockquotes: either a plain quote with no <h4.subtitle>
        # (目指す政治家像：坂本龍馬) or a subheaded card (京都への思い list).
        # Both shapes reduce to the same extraction: an optional subheading
        # plus the text of the <p> tag(s) that follow it.
        for bq in box.select(":scope > blockquote.line"):
            sub_span = bq.select_one("h4.subtitle .text-line")
            subheading = clean_text(sub_span.get_text()) if sub_span else ""
            body_parts = [text_with_breaks(p) for p in bq.select("p")]
            body_text = "\n".join([b for b in body_parts if b])
            add_section(top_heading, subheading, "", body_text)

    # Closing illustration image
    illus = soup.select_one(".ma-auto img")
    if illus and illus.get("src"):
        local = download_image(fetcher, page_url, illus["src"], "policy", "illustration")
        db.insert_image(conn, "policy", "illustration", urljoin(page_url, illus["src"]), local,
                         alt=illus.get("alt", ""))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    db.init_db(reset=True)
    fetcher = Fetcher()

    with db.connect() as conn:
        for slug, path in PAGES.items():
            print(f"Fetching {slug} ({path}) ...")
            page_url, html = fetcher.get_html(path)
            soup = BeautifulSoup(html, "html.parser")
            if slug == "home":
                scrape_home(fetcher, page_url, soup, conn)
            elif slug == "profile":
                scrape_profile(fetcher, page_url, soup, conn)
            elif slug == "policy":
                scrape_policy(fetcher, page_url, soup, conn)
            time.sleep(0.5)

    print("Done. Database written to", db.DB_PATH)


if __name__ == "__main__":
    run()
