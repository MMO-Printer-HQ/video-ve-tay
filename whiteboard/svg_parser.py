"""SVG Parser and Arc-Length Path Sampler."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import numpy as np
from PIL import ImageColor
from svgpathtools import Document, Line, svg2paths


@dataclass
class Stroke:
    """Represents a continuous stroke drawn by the pen."""
    points: np.ndarray       # shape (N, 2), float coordinates in viewport space
    color: tuple[int, int, int, int] = (30, 30, 30, 255)
    width: float = 4.0
    length: float = 0.0


def _parse_color(color_str: str | None, opacity: float = 1.0) -> tuple[int, int, int, int] | None:
    """Parse color string into RGBA tuple (0-255)."""
    if not color_str:
        return None
    color_str = color_str.strip().lower()
    if color_str in ("none", "transparent", ""):
        return None

    try:
        # Check rgba(r, g, b, a)
        rgba_match = re.match(
            r"rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d\.]+)\s*\)",
            color_str
        )
        if rgba_match:
            r, g, b, a_float = rgba_match.groups()
            alpha = int(round(float(a_float) * opacity * 255))
            return (int(r), int(g), int(b), max(0, min(255, alpha)))

        # Check rgb(r, g, b)
        rgb_match = re.match(
            r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
            color_str
        )
        if rgb_match:
            r, g, b = rgb_match.groups()
            alpha = int(round(opacity * 255))
            return (int(r), int(g), int(b), max(0, min(255, alpha)))

        # Handle hex and named colors via PIL ImageColor
        rgba = ImageColor.getcolor(color_str, "RGBA")
        alpha = int(round((rgba[3] / 255.0) * opacity * 255))
        return (rgba[0], rgba[1], rgba[2], max(0, min(255, alpha)))
    except Exception:
        return None


def _parse_stroke_width(width_str: str | None) -> float | None:
    """Extract numeric stroke width from string (e.g., '4px', '2.5')."""
    if not width_str:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", width_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _parse_attr_dict(attr: dict) -> dict[str, str]:
    """Parse raw SVG attributes dictionary, unpacking any inline CSS style."""
    combined: dict[str, str] = {}
    if not attr:
        return combined
    # 1. Direct XML presentation attributes first
    for k, v in attr.items():
        if k.lower() != "style":
            combined[k.split("}")[-1].lower()] = v
    # 2. Inline style rules on top (higher precedence in SVG/CSS)
    if "style" in attr:
        for item in attr["style"].split(";"):
            if ":" in item:
                k, v = item.split(":", 1)
                combined[k.strip().lower()] = v.strip()
    return combined


def _extract_element_style(element: Any, parent_map: dict) -> dict[str, str]:
    """Extract combined CSS and XML attributes for an element respecting tree hierarchy."""
    # Build ancestor chain from root to element
    chain = []
    curr = element
    while curr is not None:
        chain.append(curr)
        curr = parent_map.get(curr)
    chain.reverse()

    combined: dict[str, str] = {}
    for node in chain:
        if hasattr(node, "attrib"):
            # 1. Direct XML presentation attributes first
            for k, v in node.attrib.items():
                attr_name = k.split("}")[-1].lower()
                if attr_name != "style":
                    combined[attr_name] = v
            # 2. Inline style rules on top (higher precedence in SVG/CSS)
            if "style" in node.attrib:
                for item in node.attrib["style"].split(";"):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        combined[k.strip().lower()] = v.strip()

    return combined


def parse_svg(
    svg_path: str,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    margin: float = 0.15,
    step: float = 1.5,
) -> list[Stroke]:
    """Parse SVG into discretized strokes, scaled and centered within target viewport.

    Args:
        svg_path: Path to the SVG file.
        canvas_width: Target canvas width in pixels.
        canvas_height: Target canvas height in pixels.
        margin: Fractional margin padding (e.g. 0.15 for 15% margin).
        step: Desired arc-length sampling step in canvas pixels.

    Returns:
        List of Stroke objects.
    """
    if canvas_width <= 0 or canvas_height <= 0:
        raise ValueError("Canvas dimensions must be positive integers.")

    path_obj = Path(svg_path)
    if not path_obj.is_file():
        raise FileNotFoundError(f"SVG file not found: {svg_path}")

    if path_obj.stat().st_size == 0:
        raise ValueError(f"No drawable paths found in SVG: {svg_path}")

    # Load SVG paths and associated attributes
    path_items: list[tuple[Any, dict[str, str]]] = []
    try:
        doc = Document(str(path_obj))
        parent_map: dict = {}
        if hasattr(doc, "tree") and doc.tree is not None:
            parent_map = {child: parent for parent in doc.tree.iter() for child in parent}
        for p in doc.paths():
            elem = getattr(p, "element", None)
            attr = _extract_element_style(elem, parent_map) if elem is not None else {}
            path_items.append((p, attr))
    except Exception:
        try:
            raw_paths, raw_attrs = svg2paths(str(path_obj))
            for p, a in zip(raw_paths, raw_attrs):
                attr = _parse_attr_dict(a)
                path_items.append((p, attr))
        except Exception as e:
            raise ValueError(f"Failed to parse SVG file '{svg_path}': {e}") from e

    # Extract continuous subpaths and their dense sample points in SVG coordinate space
    subpaths_data: list[tuple[np.ndarray, dict[str, str]]] = []

    for path, attr_dict in path_items:
        if len(path) == 0:
            continue

        # Skip completely invisible paths (explicit stroke="none" and fill="none")
        stroke_val = attr_dict.get("stroke", "").strip().lower()
        fill_val = attr_dict.get("fill", "").strip().lower()
        if stroke_val in ("none", "transparent") and fill_val in ("none", "transparent"):
            continue

        # Skip elements with zero opacity
        opacity_str = attr_dict.get("opacity")
        try:
            if opacity_str is not None and float(opacity_str) <= 0:
                continue
        except (ValueError, TypeError):
            pass

        # Split into continuous subpaths
        try:
            subpaths = path.continuous_subpaths()
        except Exception:
            subpaths = [path]

        for sp in subpaths:
            if len(sp) == 0:
                continue

            dense_coords: list[tuple[float, float]] = []
            for seg in sp:
                if isinstance(seg, Line):
                    ts = np.array([0.0, 1.0])
                else:
                    seg_len = float(seg.length())
                    n_eval = max(30, min(200, int(np.ceil(seg_len * 2.0))))
                    ts = np.linspace(0.0, 1.0, n_eval)

                seg_pts = [(seg.point(t).real, seg.point(t).imag) for t in ts]
                if dense_coords:
                    if (
                        np.isclose(seg_pts[0][0], dense_coords[-1][0], atol=1e-5)
                        and np.isclose(seg_pts[0][1], dense_coords[-1][1], atol=1e-5)
                    ):
                        dense_coords.extend(seg_pts[1:])
                    else:
                        dense_coords.extend(seg_pts)
                else:
                    dense_coords.extend(seg_pts)

            coords_arr = np.array(dense_coords, dtype=np.float64)
            if len(coords_arr) >= 2:
                # Check segment has non-zero length
                diffs = np.diff(coords_arr, axis=0)
                length_svg = float(np.sum(np.hypot(diffs[:, 0], diffs[:, 1])))
                if length_svg > 1e-4:
                    subpaths_data.append((coords_arr, attr_dict))

    if not subpaths_data:
        raise ValueError(f"No drawable paths found in SVG: {svg_path}")

    # Compute bounding box of all paths in SVG space
    all_points = np.vstack([data[0] for data in subpaths_data])
    min_x = float(np.min(all_points[:, 0]))
    max_x = float(np.max(all_points[:, 0]))
    min_y = float(np.min(all_points[:, 1]))
    max_y = float(np.max(all_points[:, 1]))

    bbox_w = max_x - min_x
    bbox_h = max_y - min_y

    # Calculate scale and centering offset
    effective_margin = max(0.0, min(float(margin), 0.49))
    target_w = float(canvas_width) * (1.0 - 2.0 * effective_margin)
    target_h = float(canvas_height) * (1.0 - 2.0 * effective_margin)

    if bbox_w <= 1e-6 and bbox_h <= 1e-6:
        scale = 1.0
    elif bbox_w <= 1e-6:
        scale = target_h / bbox_h
    elif bbox_h <= 1e-6:
        scale = target_w / bbox_w
    else:
        scale = min(target_w / bbox_w, target_h / bbox_h)

    scaled_w = bbox_w * scale
    scaled_h = bbox_h * scale

    offset_x = (float(canvas_width) - scaled_w) / 2.0 - min_x * scale
    offset_y = (float(canvas_height) - scaled_h) / 2.0 - min_y * scale

    # Discretize each subpath with uniform arc-length parameterization
    strokes: list[Stroke] = []

    for coords_arr, attr_dict in subpaths_data:
        canvas_x = coords_arr[:, 0] * scale + offset_x
        canvas_y = coords_arr[:, 1] * scale + offset_y
        canvas_pts = np.column_stack([canvas_x, canvas_y])

        diffs = np.diff(canvas_pts, axis=0)
        seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
        cum_lens = np.concatenate([[0.0], np.cumsum(seg_lens)])
        stroke_length = float(cum_lens[-1])

        if stroke_length < 1e-4:
            continue

        num_samples = max(2, int(np.ceil(stroke_length / step)) + 1)
        s_targets = np.linspace(0.0, stroke_length, num_samples)
        sampled_x = np.interp(s_targets, cum_lens, canvas_pts[:, 0])
        sampled_y = np.interp(s_targets, cum_lens, canvas_pts[:, 1])
        sampled_pts = np.column_stack([sampled_x, sampled_y])

        # Resolve color
        stroke_val = attr_dict.get("stroke")
        fill_val = attr_dict.get("fill")
        try:
            opacity_val = float(attr_dict.get("opacity", 1.0))
        except (ValueError, TypeError):
            opacity_val = 1.0
        try:
            stroke_opacity = float(attr_dict.get("stroke-opacity", opacity_val))
        except (ValueError, TypeError):
            stroke_opacity = opacity_val

        color = None
        if stroke_val and stroke_val.strip().lower() != "none":
            color = _parse_color(stroke_val, stroke_opacity)
        elif fill_val and fill_val.strip().lower() != "none":
            try:
                fill_opacity = float(attr_dict.get("fill-opacity", opacity_val))
            except (ValueError, TypeError):
                fill_opacity = opacity_val
            color = _parse_color(fill_val, fill_opacity)

        if color is None:
            color = (30, 30, 30, 255)

        # Resolve stroke width
        sw_val = attr_dict.get("stroke-width")
        if sw_val:
            parsed_w = _parse_stroke_width(sw_val)
            if parsed_w is not None and parsed_w > 0:
                stroke_width = max(1.0, float(parsed_w) * scale)
            else:
                stroke_width = 4.0
        else:
            stroke_width = 4.0

        strokes.append(
            Stroke(
                points=sampled_pts,
                color=color,
                width=stroke_width,
                length=stroke_length,
            )
        )

    if not strokes:
        raise ValueError(f"No drawable paths found in SVG: {svg_path}")

    return strokes
