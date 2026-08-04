"""SQLite schema + access layer shared by the scraper and the Streamlit app.

The scraper (scraper/scrape.py) is the only writer. The Streamlit app only
reads. Keeping both sides of the boundary in this one module means the
table/column names can never drift out of sync between them.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from common.paths import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    slug        TEXT PRIMARY KEY,   -- 'home' | 'profile' | 'policy'
    title       TEXT,
    source_url  TEXT,
    scraped_at  TEXT
);

CREATE TABLE IF NOT EXISTS images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    page_slug    TEXT NOT NULL,
    category     TEXT NOT NULL,     -- hero / menu / news / profile / policy / sns / logo ...
    original_url TEXT NOT NULL,
    local_path   TEXT,              -- path relative to data/images, NULL if download failed
    alt          TEXT,
    sort_order   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hero_slides (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id   INTEGER NOT NULL REFERENCES images(id),
    link_url   TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS news_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    section    TEXT NOT NULL,       -- '活動写真館' | '新着情報'
    date_text  TEXT,
    category   TEXT,
    title      TEXT,
    body_text  TEXT,                -- plain text, paragraphs separated by \n\n
    link_url   TEXT,
    image_id   INTEGER REFERENCES images(id),
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS site_info (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS quick_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_slug  TEXT NOT NULL,
    group_name TEXT NOT NULL,        -- 'menu' | 'small_menu' | 'sns'
    label      TEXT,
    url        TEXT,
    image_id   INTEGER REFERENCES images(id),
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profile_basic (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    name_ja          TEXT,
    name_kana        TEXT,
    birth_date       TEXT,
    gender           TEXT,
    current_roles    TEXT,          -- newline-separated
    dream            TEXT,
    focus_areas      TEXT,
    motto            TEXT,
    hobby            TEXT,
    favorite_food    TEXT,
    charm_point      TEXT,
    fun_fact         TEXT,
    photo_image_id   INTEGER REFERENCES images(id),
    name_image_id    INTEGER REFERENCES images(id)
);

CREATE TABLE IF NOT EXISTS career_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date_text  TEXT,
    event_text TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    category     TEXT NOT NULL,     -- 政府 / 国会 / 衆議院 / 政党
    title_text   TEXT,
    period_text  TEXT,
    sort_order   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS policy_sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name  TEXT NOT NULL,      -- '日本のために' | '京都への思い'
    heading     TEXT,               -- e.g. '目指す方針', '目指す政治家像：坂本龍馬'
    subheading  TEXT,               -- card-level title, may be empty
    label       TEXT,               -- small eyebrow label e.g. '外交・安全保障'
    body_text   TEXT,
    sort_order  INTEGER DEFAULT 0
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(reset: bool = False) -> None:
    """Create tables. If reset=True, drop all known tables first (used by the
    scraper so re-running it always produces a clean, consistent dataset)."""
    with connect() as conn:
        if reset:
            tables = [
                "hero_slides", "news_items", "quick_links", "career_history",
                "positions", "policy_sections", "profile_basic", "site_info",
                "images", "pages",
            ]
            for t in tables:
                conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA)


# ---------------------------------------------------------------------------
# Write helpers (scraper side)
# ---------------------------------------------------------------------------

def upsert_page(conn: sqlite3.Connection, slug: str, title: str, source_url: str, scraped_at: str) -> None:
    conn.execute(
        "INSERT INTO pages (slug, title, source_url, scraped_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT(slug) DO UPDATE SET title=excluded.title, source_url=excluded.source_url, scraped_at=excluded.scraped_at",
        (slug, title, source_url, scraped_at),
    )


def set_site_info(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO site_info (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def insert_image(conn: sqlite3.Connection, page_slug: str, category: str, original_url: str,
                  local_path: Optional[str], alt: str = "", sort_order: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO images (page_slug, category, original_url, local_path, alt, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
        (page_slug, category, original_url, local_path, alt, sort_order),
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Read helpers (Streamlit app side)
# ---------------------------------------------------------------------------

@dataclass
class Image:
    id: int
    category: str
    original_url: str
    local_path: Optional[str]
    alt: str
    sort_order: int


def _row_to_image(row: Optional[sqlite3.Row]) -> Optional[Image]:
    if row is None:
        return None
    return Image(row["id"], row["category"], row["original_url"], row["local_path"], row["alt"] or "", row["sort_order"])


def get_page_meta(slug: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM pages WHERE slug=?", (slug,)).fetchone()


def get_images(page_slug: str, category: str) -> list[Image]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM images WHERE page_slug=? AND category=? ORDER BY sort_order",
            (page_slug, category),
        ).fetchall()
        return [_row_to_image(r) for r in rows]


def get_image_by_id(image_id: Optional[int]) -> Optional[Image]:
    if image_id is None:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
        return _row_to_image(row)


def get_hero_slides() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT h.link_url, i.* FROM hero_slides h
               JOIN images i ON i.id = h.image_id
               ORDER BY h.sort_order"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_news(section: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM news_items WHERE section=? ORDER BY sort_order",
            (section,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_quick_links(page_slug: str, group_name: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT q.label, q.url, i.local_path, i.original_url, i.alt FROM quick_links q
               LEFT JOIN images i ON i.id = q.image_id
               WHERE q.page_slug=? AND q.group_name=? ORDER BY q.sort_order""",
            (page_slug, group_name),
        ).fetchall()
        return [dict(r) for r in rows]


def get_profile_basic() -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profile_basic WHERE id=1").fetchone()
        return dict(row) if row else None


def get_career_history() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM career_history ORDER BY sort_order").fetchall()
        return [dict(r) for r in rows]


def get_positions(category: Optional[str] = None) -> list[dict]:
    with connect() as conn:
        if category:
            rows = conn.execute(
                "SELECT * FROM positions WHERE category=? ORDER BY sort_order", (category,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM positions ORDER BY category, sort_order").fetchall()
        return [dict(r) for r in rows]


def get_position_categories() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT category FROM positions GROUP BY category ORDER BY MIN(id)"
        ).fetchall()
        return [r["category"] for r in rows]


def get_site_info() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT key, value FROM site_info").fetchall()
        return {r["key"]: r["value"] for r in rows}


def get_policy_sections(group_name: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM policy_sections WHERE group_name=? ORDER BY sort_order",
            (group_name,),
        ).fetchall()
        return [dict(r) for r in rows]


def db_exists() -> bool:
    return DB_PATH.exists()
