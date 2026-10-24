# app/video_engine/__init__.py
"""
Video Engine for Art Auction Reels / Shorts / Clips generation.
Compliant with DESIGN_SYSTEM.md specification.
"""

from .liquid_glass import (
    render_liquid_glass_card,
    render_floating_artwork,
    get_supersampled_logo,
)
from .overlays import (
    make_background_layer,
    render_upper_pill_component,
    render_bottom_card_component,
    render_intro_slide,
    render_outro_slide,
)
from .music_manager import MusicManager
from .builder import VideoBatchBuilder

__all__ = [
    "render_liquid_glass_card",
    "render_floating_artwork",
    "get_supersampled_logo",
    "make_background_layer",
    "render_upper_pill_component",
    "render_bottom_card_component",
    "render_intro_slide",
    "render_outro_slide",
    "MusicManager",
    "VideoBatchBuilder",
]
