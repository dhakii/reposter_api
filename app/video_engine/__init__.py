# app/video_engine/__init__.py
"""
Video Engine for Art Auction Reels / Shorts / Clips generation.
Includes:
- Editorial Symmetrical Layouts (4A Red Pill, 4B Framed Badge, 4C Sotheby's)
- Ambient Glow Layout (Variant 2)
- Branded White Outro
"""

from .overlays import (
    make_semi_transparent_blurred_background,
    create_adaptive_ambient_background,
    make_editorial_typography_overlay,
    make_static_typography_overlay,
    render_brand_white_outro,
)
from .music_manager import MusicManager
from .builder import VideoBatchBuilder
from .scraper import fetch_channel_lots

__all__ = [
    "make_semi_transparent_blurred_background",
    "create_adaptive_ambient_background",
    "make_editorial_typography_overlay",
    "make_static_typography_overlay",
    "render_brand_white_outro",
    "MusicManager",
    "VideoBatchBuilder",
    "fetch_channel_lots",
]
