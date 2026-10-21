"""Project-local scenic assets with a non-blocking image fallback."""
from base64 import b64encode
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
ASSET_FILES = {
    "liuhuixie": "assets/user/scenery/liuhuixie.webp",
    "memorial": "assets/user/scenery/sun_yat_sen_memorial.webp",
    "linggu": "assets/user/scenery/linggu.webp",
    "sports": "assets/user/scenery/sports_park.webp",
    "meiling": "assets/user/scenery/meiling_palace.webp",
    "observatory": "assets/user/scenery/observatory.webp",
    "routes": "assets/user/maps/sightseeing_routes.jpg",
    "portal": "assets/brand/liuhuixie.jpg",
    "admin_login": "assets/brand/forest_road.jpg",
}


def asset_path(asset_key: str) -> Path:
    """Resolve from the project location, never from the process directory."""
    return ROOT / ASSET_FILES[asset_key]


def asset_download(asset_key: str) -> bytes | None:
    """Return a verified image, or None for an absent/invalid optional asset."""
    try:
        content = asset_path(asset_key).read_bytes()
        with Image.open(BytesIO(content)) as image:
            image.verify()
        return content
    except (KeyError, OSError, ValueError, UnidentifiedImageError):
        return None


@lru_cache(maxsize=4)
def asset_data_uri(asset_key: str) -> str | None:
    """Embed a verified local photo in page CSS without external requests."""
    content = asset_download(asset_key)
    if content is None:
        return None
    suffix = asset_path(asset_key).suffix.lower()
    mime = "image/webp" if suffix == ".webp" else "image/jpeg"
    return f"data:{mime};base64,{b64encode(content).decode('ascii')}"


def render_image(asset_key: str, caption: str | None = None) -> bool:
    """Display an optional image without stopping data or query rendering."""
    import streamlit as st

    content = asset_download(asset_key)
    if content is None:
        st.caption(f"{caption or '景区图片'}暂不可用，线路查询和仿真功能仍可使用。")
        return False
    try:
        st.image(content, caption=caption, use_container_width=True)
        return True
    except (OSError, ValueError, RuntimeError):
        st.caption(f"{caption or '景区图片'}暂无法显示，线路查询和仿真功能仍可使用。")
        return False
