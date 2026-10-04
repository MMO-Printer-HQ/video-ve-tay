#!/usr/bin/env python3
"""CLI entrypoint for Whiteboard Animation Generator."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from whiteboard.hand_renderer import HandRenderer
from whiteboard.svg_parser import parse_svg
from whiteboard.video_generator import WhiteboardVideoGenerator


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser with default parameters."""
    parser = argparse.ArgumentParser(
        description="Whiteboard Animation Video Generator (Hiệu ứng vẽ tay từ file vector SVG)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--svg",
        type=str,
        default="assets/demo_sketch.svg",
        help="Path to input vector SVG file",
    )
    parser.add_argument(
        "--hand",
        type=str,
        default="assets/default_hand.png",
        help="Path to RGBA hand graphic holding pen",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output_handdrawn.mp4",
        help="Destination path for rendered MP4 video",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=6.0,
        help="Drawing duration in seconds",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=1.0,
        help="Hold duration in seconds displaying completed artwork",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Frames per second for output video",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
        help="Video frame canvas width in pixels",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="Video frame canvas height in pixels",
    )
    parser.add_argument(
        "--scale-hand",
        type=float,
        default=0.5,
        help="Scale factor for the hand graphic",
    )
    parser.add_argument(
        "--tip-x",
        type=int,
        default=None,
        help="Marker tip X coordinate on hand image (optional override)",
    )
    parser.add_argument(
        "--tip-y",
        type=int,
        default=None,
        help="Marker tip Y coordinate on hand image (optional override)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.15,
        help="Fractional canvas margin padding for SVG content",
    )
    parser.add_argument(
        "--exit",
        type=float,
        default=0.5,
        help="Hand exit transition duration in seconds",
    )
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Validate argument values and report clear error messages."""
    if (args.tip_x is not None and args.tip_y is None) or (
        args.tip_x is None and args.tip_y is not None
    ):
        parser.error("--tip-x and --tip-y must both be specified when overriding tip offset.")

    if not os.path.isfile(args.svg):
        parser.error(f"SVG file not found: {args.svg}")

    if not os.path.isfile(args.hand):
        parser.error(f"Hand image file not found: {args.hand}")

    if args.width <= 0 or args.height <= 0:
        parser.error(f"Canvas dimensions must be positive integers, got {args.width}x{args.height}.")

    if args.fps <= 0:
        parser.error(f"fps must be a positive integer, got {args.fps}.")

    if args.duration < 0:
        parser.error(f"Drawing duration must be non-negative, got {args.duration}.")

    if args.hold < 0:
        parser.error(f"Hold duration must be non-negative, got {args.hold}.")

    if args.exit < 0:
        parser.error(f"Exit duration must be non-negative, got {args.exit}.")

    if args.scale_hand <= 0:
        parser.error(f"scale-hand must be positive, got {args.scale_hand}.")


def main(argv: list[str] | None = None) -> int:
    """Main CLI execution flow."""
    parser = create_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)

    tip_offset = (args.tip_x, args.tip_y) if args.tip_x is not None else None

    print("=" * 60)
    print(" Whiteboard Animation Video Generator (Vẽ tay)")
    print("=" * 60)
    print(f" Input SVG   : {args.svg}")
    print(f" Hand asset  : {args.hand}")
    print(f" Output file : {args.output}")
    print(f" Resolution  : {args.width}x{args.height} @ {args.fps} fps")
    print(
        f" Timing      : {args.duration:.1f}s draw + {args.exit:.1f}s exit + {args.hold:.1f}s hold"
    )
    print("-" * 60)

    # Step 1: Parse SVG
    print("[1/3] Parsing SVG paths...")
    t0_parse = time.time()
    try:
        strokes = parse_svg(
            args.svg,
            canvas_width=args.width,
            canvas_height=args.height,
            margin=args.margin,
        )
    except Exception as e:
        sys.stderr.write(f"Error: Failed to parse SVG '{args.svg}': {e}\n")
        return 1

    total_len = sum(s.length for s in strokes)
    print(
        f"      Found {len(strokes)} strokes (total path length: {total_len:.1f}px) in {time.time() - t0_parse:.2f}s"
    )

    # Step 2: Initialize Hand Renderer
    print("[2/3] Initializing Hand Renderer...")
    try:
        hand_renderer = HandRenderer(
            hand_img_path=args.hand,
            tip_offset=tip_offset,
            scale=args.scale_hand,
        )
    except Exception as e:
        sys.stderr.write(f"Error: Failed to initialize hand renderer: {e}\n")
        return 1

    print(
        f"      Hand resized to: {hand_renderer.width}x{hand_renderer.height}px, tip anchor: {hand_renderer.scaled_tip_offset}"
    )

    # Step 3: Render Video
    print("[3/3] Rendering video frames...")
    generator = WhiteboardVideoGenerator(
        strokes=strokes,
        hand_renderer=hand_renderer,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )

    start_render_time: float | None = None

    def progress_callback(current: int, total: int) -> None:
        nonlocal start_render_time
        if start_render_time is None:
            start_render_time = time.time()

        elapsed = max(1e-5, time.time() - start_render_time)
        speed = current / elapsed
        pct = (current / total * 100.0) if total > 0 else 100.0
        remaining_frames = max(0, total - current)
        eta = (remaining_frames / speed) if speed > 0 else 0.0

        bar_len = 28
        filled = int(round(bar_len * current / total)) if total > 0 else bar_len
        bar = "=" * filled + "-" * (bar_len - filled)

        sys.stdout.write(
            f"\rProgress: [{bar}] {current}/{total} frames ({pct:5.1f}%) | {speed:4.1f} fps | ETA: {eta:4.1f}s"
        )
        sys.stdout.flush()

        if current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    try:
        out_path = generator.generate(
            output_path=args.output,
            draw_duration=args.duration,
            hold_duration=args.hold,
            exit_duration=args.exit,
            progress_callback=progress_callback,
        )
    except Exception as e:
        sys.stderr.write(f"\nError: Rendering failed: {e}\n")
        return 1

    total_time = (time.time() - start_render_time) if start_render_time else 0.0
    out_file = Path(out_path)
    file_size_mb = out_file.stat().st_size / (1024 * 1024) if out_file.exists() else 0.0

    print("-" * 60)
    print(f"Render completed in {total_time:.2f}s!")
    print(f"Video saved to: {out_file.resolve()} ({file_size_mb:.2f} MB)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
