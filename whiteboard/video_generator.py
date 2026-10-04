"""Whiteboard video generator and motion orchestrator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Sequence
import cv2
import numpy as np

from whiteboard.hand_renderer import HandRenderer
from whiteboard.svg_parser import Stroke


def _stroke_color_to_bgr(
    color: tuple[int, int, int, int] | tuple[int, int, int],
    bg_bgr: tuple[int, int, int] = (255, 255, 255),
) -> tuple[int, int, int]:
    """Convert RGBA stroke color tuple to composite BGR for OpenCV canvas."""
    if len(color) == 4:
        r, g, b, a = color
        if a >= 255:
            return (int(b), int(g), int(r))
        alpha = max(0.0, min(1.0, a / 255.0))
        b_out = int(round(b * alpha + bg_bgr[0] * (1.0 - alpha)))
        g_out = int(round(g * alpha + bg_bgr[1] * (1.0 - alpha)))
        r_out = int(round(r * alpha + bg_bgr[2] * (1.0 - alpha)))
        return (max(0, min(255, b_out)), max(0, min(255, g_out)), max(0, min(255, r_out)))
    else:
        r, g, b = color[:3]
        return (int(b), int(g), int(r))


def _point_at_arc_length(
    points: np.ndarray,
    cum_lens: np.ndarray,
    s: float,
) -> tuple[float, float]:
    """Interpolate coordinates on polyline at given cumulative arc-length s."""
    total_l = cum_lens[-1]
    if total_l <= 0.0 or s <= 0.0:
        return float(points[0, 0]), float(points[0, 1])
    if s >= total_l:
        return float(points[-1, 0]), float(points[-1, 1])

    idx = int(np.searchsorted(cum_lens, s))
    if idx == 0:
        return float(points[0, 0]), float(points[0, 1])

    s0 = cum_lens[idx - 1]
    s1 = cum_lens[idx]
    ds = s1 - s0
    if ds <= 1e-9:
        return float(points[idx, 0]), float(points[idx, 1])

    alpha = (s - s0) / ds
    x = (1.0 - alpha) * points[idx - 1, 0] + alpha * points[idx, 0]
    y = (1.0 - alpha) * points[idx - 1, 1] + alpha * points[idx, 1]
    return float(x), float(y)


def _get_subpath(
    points: np.ndarray,
    cum_lens: np.ndarray,
    s_start: float,
    s_end: float,
) -> list[tuple[float, float]]:
    """Extract intermediate polyline coordinates between arc-lengths s_start and s_end."""
    if s_end <= s_start:
        return []

    p_start = _point_at_arc_length(points, cum_lens, s_start)
    p_end = _point_at_arc_length(points, cum_lens, s_end)

    i_start = int(np.searchsorted(cum_lens, s_start, side="right"))
    i_end = int(np.searchsorted(cum_lens, s_end, side="left"))

    subpts = [p_start]
    for k in range(i_start, i_end):
        subpts.append((float(points[k, 0]), float(points[k, 1])))
    subpts.append(p_end)
    return subpts


def _draw_polyline(
    canvas: np.ndarray,
    pts: list[tuple[float, float]],
    bgr_color: tuple[int, int, int],
    thickness: int,
) -> None:
    """Draw antialiased connected segments and rounded joints onto canvas."""
    if not pts:
        return
    radius = max(1, thickness // 2)
    p1 = (int(round(pts[0][0])), int(round(pts[0][1])))
    cv2.circle(canvas, p1, radius, bgr_color, -1, lineType=cv2.LINE_AA)
    if len(pts) == 1:
        return

    for pt in pts[1:]:
        p2 = (int(round(pt[0])), int(round(pt[1])))
        cv2.line(canvas, p1, p2, bgr_color, thickness, lineType=cv2.LINE_AA)
        cv2.circle(canvas, p2, radius, bgr_color, -1, lineType=cv2.LINE_AA)
        p1 = p2


class WhiteboardVideoGenerator:
    """Orchestrates whiteboard animation motion and compiles to MP4 video."""

    def __init__(
        self,
        strokes: Sequence[Stroke],
        hand_renderer: HandRenderer,
        width: int = 1920,
        height: int = 1080,
        fps: int = 30,
        background_color: tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        """Initialize video generator.

        Args:
            strokes: Sequence of parsed vector Stroke objects.
            hand_renderer: HandRenderer instance configured with hand asset.
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            fps: Video frames per second.
            background_color: Canvas background color in BGR (default: white (255, 255, 255)).
        """
        if width <= 0 or height <= 0:
            raise ValueError(f"Canvas dimensions must be positive integers, got {width}x{height}")
        if fps <= 0:
            raise ValueError(f"fps must be positive, got {fps}")

        self.strokes = list(strokes)
        self.hand_renderer = hand_renderer
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.background_color = (
            int(background_color[0]),
            int(background_color[1]),
            int(background_color[2]),
        )

    def _open_video_writer(
        self,
        output_path: str | Path,
        preferred_codec: str | None = None,
    ) -> cv2.VideoWriter:
        """Create and open cv2.VideoWriter with codec fallback mechanism."""
        out_str = str(output_path)
        candidate_codecs = ["mp4v", "avc1", "H264", "XVID"]
        if preferred_codec:
            codecs_to_try = [preferred_codec] + [c for c in candidate_codecs if c != preferred_codec]
        else:
            codecs_to_try = candidate_codecs

        writer = None
        for c in codecs_to_try:
            try:
                fourcc_str = str(c)[:4]
                if len(fourcc_str) < 4:
                    fourcc_str = fourcc_str.ljust(4)
                fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
                w = cv2.VideoWriter(out_str, fourcc, float(self.fps), (self.width, self.height))
                if w.isOpened():
                    writer = w
                    break
                w.release()
            except Exception:
                continue

        if writer is None or not writer.isOpened():
            raise RuntimeError(
                f"Failed to initialize cv2.VideoWriter for output '{out_str}' with any supported codec: {codecs_to_try}"
            )

        return writer

    def generate(
        self,
        output_path: str | Path,
        draw_duration: float = 5.0,
        hold_duration: float = 1.0,
        exit_duration: float = 0.5,
        progress_callback: Callable[[int, int], None] | None = None,
        codec: str | None = None,
    ) -> str:
        """Generate whiteboard animation video.

        Args:
            output_path: Destination path for the MP4 video.
            draw_duration: Total duration for drawing strokes in seconds.
            hold_duration: Static hold duration for completed artwork in seconds.
            exit_duration: Hand off-screen glide duration in seconds.
            progress_callback: Optional callback func(current_frame, total_frames).
            codec: Optional preferred FourCC codec string (e.g. "mp4v" or "avc1").

        Returns:
            str: Resolved output file path.
        """
        if not output_path or str(output_path).strip() == "":
            raise ValueError("output_path cannot be empty")
        if draw_duration < 0 or hold_duration < 0:
            raise ValueError(f"duration must be non-negative, got draw={draw_duration}, hold={hold_duration}")
        if exit_duration < 0:
            raise ValueError(f"exit_duration must be non-negative, got {exit_duration}")

        out_path_obj = Path(output_path)
        out_path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Initialize persistent drawing canvas (BGR)
        canvas = np.empty((self.height, self.width, 3), dtype=np.uint8)
        canvas[:] = self.background_color

        # Frame budgets
        draw_frames = max(0, int(round(draw_duration * self.fps)))
        hold_frames = max(0, int(round(hold_duration * self.fps)))
        has_strokes = len(self.strokes) > 0
        exit_frames = max(0, int(round(exit_duration * self.fps))) if has_strokes else 0

        total_frames = draw_frames + exit_frames + hold_frames
        if total_frames == 0:
            total_frames = 1
            hold_frames = 1

        writer = self._open_video_writer(out_path_obj, preferred_codec=codec)
        frames_written = 0

        try:
            if not has_strokes:
                # No strokes to draw: write blank canvas
                for _ in range(total_frames):
                    writer.write(canvas)
                    frames_written += 1
                    if progress_callback:
                        progress_callback(frames_written, total_frames)
                return str(out_path_obj)

            # Preprocess stroke data
            stroke_data = []
            for stroke in self.strokes:
                pts = np.asarray(stroke.points, dtype=np.float64)
                if len(pts) == 0:
                    pts = np.zeros((1, 2), dtype=np.float64)
                    cum_lens = np.array([0.0])
                    s_len = 0.0
                elif len(pts) == 1:
                    cum_lens = np.array([0.0])
                    s_len = 0.0
                else:
                    diffs = np.diff(pts, axis=0)
                    seg_lens = np.hypot(diffs[:, 0], diffs[:, 1])
                    cum_lens = np.concatenate([[0.0], np.cumsum(seg_lens)])
                    s_len = float(cum_lens[-1])

                bgr_color = _stroke_color_to_bgr(stroke.color, self.background_color)
                thickness = max(1, int(round(stroke.width)))

                stroke_data.append({
                    "points": pts,
                    "cum_lens": cum_lens,
                    "length": s_len,
                    "color": bgr_color,
                    "thickness": thickness,
                    "drawn_length": 0.0,
                })

            # Build motion timeline with strokes and in-between transitions
            timeline_items = []
            curr_w = 0.0
            num_strokes = len(stroke_data)

            for i in range(num_strokes):
                s_info = stroke_data[i]
                s_weight = max(s_info["length"], 1.0)
                timeline_items.append({
                    "type": "stroke",
                    "stroke_idx": i,
                    "w_start": curr_w,
                    "w_end": curr_w + s_weight,
                    "weight": s_weight,
                })
                curr_w += s_weight

                if i < num_strokes - 1:
                    next_s_info = stroke_data[i + 1]
                    p_end = s_info["points"][-1]
                    p_start = next_s_info["points"][0]
                    trans_dist = float(np.hypot(p_start[0] - p_end[0], p_start[1] - p_end[1]))

                    if trans_dist >= 2.0:
                        # Effective weight for pen-up movement (~2.5x drawing speed, capped)
                        t_weight = min(trans_dist / 2.5, 120.0)
                        timeline_items.append({
                            "type": "transition",
                            "from_idx": i,
                            "to_idx": i + 1,
                            "p_end": (float(p_end[0]), float(p_end[1])),
                            "p_start": (float(p_start[0]), float(p_start[1])),
                            "w_start": curr_w,
                            "w_end": curr_w + t_weight,
                            "weight": t_weight,
                        })
                        curr_w += t_weight

            total_timeline_weight = curr_w if curr_w > 0 else 1.0
            last_hand_pos = (
                float(stroke_data[0]["points"][0, 0]),
                float(stroke_data[0]["points"][0, 1]),
            )

            # Phase 1: Progressive Drawing
            if draw_frames > 0:
                for f in range(draw_frames):
                    w_curr = ((f + 1) / draw_frames) * total_timeline_weight

                    # Incrementally draw any stroke segments up to w_curr
                    for item in timeline_items:
                        if item["type"] == "stroke":
                            s_idx = item["stroke_idx"]
                            s_info = stroke_data[s_idx]
                            s_len = s_info["length"]

                            if w_curr >= item["w_end"]:
                                target_s = s_len
                            elif w_curr <= item["w_start"]:
                                target_s = 0.0
                            else:
                                alpha = (w_curr - item["w_start"]) / item["weight"]
                                target_s = alpha * s_len

                            if target_s > s_info["drawn_length"] or (s_len == 0.0 and s_info["drawn_length"] == 0.0):
                                if s_len == 0.0 or len(s_info["points"]) <= 1:
                                    pt0 = (
                                        float(s_info["points"][0, 0]),
                                        float(s_info["points"][0, 1]),
                                    )
                                    _draw_polyline(canvas, [pt0], s_info["color"], s_info["thickness"])
                                    s_info["drawn_length"] = 1.0
                                else:
                                    subpts = _get_subpath(
                                        s_info["points"],
                                        s_info["cum_lens"],
                                        s_info["drawn_length"],
                                        target_s,
                                    )
                                    _draw_polyline(canvas, subpts, s_info["color"], s_info["thickness"])
                                    s_info["drawn_length"] = target_s

                    # Locate hand position at w_curr
                    active_item = timeline_items[-1]
                    for item in timeline_items:
                        if item["w_start"] <= w_curr <= item["w_end"]:
                            active_item = item
                            break

                    if active_item["type"] == "stroke":
                        s_idx = active_item["stroke_idx"]
                        s_info = stroke_data[s_idx]
                        if s_info["length"] == 0.0 or len(s_info["points"]) <= 1:
                            hand_pos = (
                                float(s_info["points"][0, 0]),
                                float(s_info["points"][0, 1]),
                            )
                        else:
                            alpha = (w_curr - active_item["w_start"]) / active_item["weight"]
                            alpha = max(0.0, min(1.0, alpha))
                            current_s = alpha * s_info["length"]
                            hand_pos = _point_at_arc_length(
                                s_info["points"],
                                s_info["cum_lens"],
                                current_s,
                            )
                    else:  # transition
                        alpha = (w_curr - active_item["w_start"]) / active_item["weight"]
                        alpha = max(0.0, min(1.0, alpha))
                        # Cosine easing for smooth pen-up glide
                        alpha_eased = 0.5 * (1.0 - math.cos(math.pi * alpha))
                        p_e = active_item["p_end"]
                        p_s = active_item["p_start"]
                        hand_pos = (
                            (1.0 - alpha_eased) * p_e[0] + alpha_eased * p_s[0],
                            (1.0 - alpha_eased) * p_e[1] + alpha_eased * p_s[1],
                        )

                    last_hand_pos = hand_pos

                    # Composite hand on copy of current drawing canvas
                    frame = self.hand_renderer.overlay_hand(canvas, hand_pos, copy=True)
                    writer.write(frame)
                    frames_written += 1
                    if progress_callback:
                        progress_callback(frames_written, total_frames)

            # Ensure all strokes are 100% drawn on canvas
            for s_info in stroke_data:
                s_len = s_info["length"]
                if s_info["drawn_length"] < s_len:
                    subpts = _get_subpath(
                        s_info["points"],
                        s_info["cum_lens"],
                        s_info["drawn_length"],
                        s_len,
                    )
                    _draw_polyline(canvas, subpts, s_info["color"], s_info["thickness"])
                    s_info["drawn_length"] = s_len
                elif s_len == 0.0 and s_info["drawn_length"] == 0.0:
                    pt0 = (float(s_info["points"][0, 0]), float(s_info["points"][0, 1]))
                    _draw_polyline(canvas, [pt0], s_info["color"], s_info["thickness"])
                    s_info["drawn_length"] = 1.0

            # Phase 2: Exit Animation (glide off-screen bottom-right)
            if exit_frames > 0:
                p_start = last_hand_pos
                p_target = (
                    float(self.width + self.hand_renderer.scaled_tip_offset[0] + 50.0),
                    float(self.height + self.hand_renderer.scaled_tip_offset[1] + 50.0),
                )
                for e in range(exit_frames):
                    u = (e + 1) / exit_frames
                    # Ease-in: accelerates off-screen
                    u_eased = u * u
                    pos = (
                        (1.0 - u_eased) * p_start[0] + u_eased * p_target[0],
                        (1.0 - u_eased) * p_start[1] + u_eased * p_target[1],
                    )
                    frame = self.hand_renderer.overlay_hand(canvas, pos, copy=True)
                    writer.write(frame)
                    frames_written += 1
                    if progress_callback:
                        progress_callback(frames_written, total_frames)

            # Phase 3: Hold Freeze (static completed artwork without hand)
            for _ in range(hold_frames):
                writer.write(canvas)
                frames_written += 1
                if progress_callback:
                    progress_callback(frames_written, total_frames)

        finally:
            writer.release()

        return str(out_path_obj)
