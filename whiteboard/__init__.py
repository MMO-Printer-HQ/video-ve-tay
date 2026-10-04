"""Whiteboard animation package."""

from whiteboard.svg_parser import Stroke, parse_svg
from whiteboard.hand_renderer import HandRenderer, DEFAULT_TIP_OFFSET
from whiteboard.video_generator import WhiteboardVideoGenerator

__all__ = [
    "Stroke",
    "parse_svg",
    "HandRenderer",
    "DEFAULT_TIP_OFFSET",
    "WhiteboardVideoGenerator",
]
