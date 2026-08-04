"""Image loading helpers for the Streamlit app.

Two access patterns are used throughout the app:
  * ``abs_path`` for plain ``st.image(...)`` calls (Streamlit serves the file
    itself, so we just need a real filesystem path).
  * ``data_uri`` for images that must live *inside* hand-written HTML/CSS
    (e.g. the hero crossfade background), since Streamlit doesn't expose an
    HTTP route for arbitrary local files.
"""
from __future__ import annotations

import base64
import mimetypes
from functools import lru_cache

from common.paths import IMAGES_DIR


def abs_path(local_path: str | None) -> str | None:
    if not local_path:
        return None
    path = IMAGES_DIR / local_path
    return str(path) if path.exists() else None


@lru_cache(maxsize=64)
def data_uri(local_path: str | None) -> str | None:
    if not local_path:
        return None
    path = IMAGES_DIR / local_path
    if not path.exists():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
