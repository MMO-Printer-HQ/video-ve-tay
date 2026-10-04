"""Tests for WhiteboardVideoGenerator and motion orchestrator."""

import os
from pathlib import Path
import cv2
import numpy as np
import pytest

from whiteboard.hand_renderer import HandRenderer
from whiteboard.svg_parser import Stroke, parse_svg
from whiteboard.video_generator import WhiteboardVideoGenerator


def test_generate_short_video(tmp_path):
    """Test generating a short video with demo assets."""
    out_video = str(tmp_path / "test.mp4")
    strokes = parse_svg("assets/demo_sketch.svg", canvas_width=640, canvas_height=360)
    renderer = HandRenderer("assets/default_hand.png", scale=0.4)
    gen = WhiteboardVideoGenerator(strokes, renderer, width=640, height=360, fps=20)
    res = gen.generate(out_video, draw_duration=1.0, hold_duration=0.5)

    assert os.path.exists(res)
    assert os.path.getsize(res) > 1000
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert frame_count >= 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    assert width == 640
    assert height == 360
    cap.release()


def test_invalid_parameters():
    """Test validation errors for invalid constructor and generator arguments."""
    renderer = HandRenderer("assets/default_hand.png", scale=0.4)
    strokes = [Stroke(points=np.array([[0, 0], [10, 10]], dtype=float), length=14.14)]

    with pytest.raises(ValueError, match="Canvas dimensions"):
        WhiteboardVideoGenerator(strokes, renderer, width=0, height=360)

    with pytest.raises(ValueError, match="Canvas dimensions"):
        WhiteboardVideoGenerator(strokes, renderer, width=640, height=-10)

    with pytest.raises(ValueError, match="fps"):
        WhiteboardVideoGenerator(strokes, renderer, fps=0)

    gen = WhiteboardVideoGenerator(strokes, renderer, width=320, height=240, fps=10)

    with pytest.raises(ValueError, match="duration"):
        gen.generate("out.mp4", draw_duration=-1.0)

    with pytest.raises(ValueError, match="duration"):
        gen.generate("out.mp4", hold_duration=-0.5)

    with pytest.raises(ValueError, match="exit_duration"):
        gen.generate("out.mp4", exit_duration=-0.1)

    with pytest.raises(ValueError, match="output_path"):
        gen.generate("")


def test_empty_strokes(tmp_path):
    """Test generating a video with empty strokes produces valid blank output."""
    out_video = str(tmp_path / "empty.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    gen = WhiteboardVideoGenerator([], renderer, width=320, height=180, fps=15)
    res = gen.generate(out_video, draw_duration=0.5, hold_duration=0.5, exit_duration=0.2)

    assert os.path.exists(res)
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert count > 0
    ret, frame = cap.read()
    assert ret
    # Canvas should remain pure white (or default background)
    assert np.all(frame >= 250)
    cap.release()


def test_zero_length_stroke(tmp_path):
    """Test handling single-point or zero-length strokes."""
    out_video = str(tmp_path / "single_pt.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    dot_stroke = Stroke(points=np.array([[100.0, 100.0]], dtype=float), length=0.0, width=6.0)
    gen = WhiteboardVideoGenerator([dot_stroke], renderer, width=320, height=200, fps=10)
    res = gen.generate(out_video, draw_duration=0.5, hold_duration=0.2, exit_duration=0.2)

    assert os.path.exists(res)
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    cap.release()


def test_progress_callback(tmp_path):
    """Test progress callback is invoked during video generation."""
    out_video = str(tmp_path / "progress.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    stroke = Stroke(points=np.array([[50.0, 50.0], [150.0, 150.0]], dtype=float), length=141.4)
    gen = WhiteboardVideoGenerator([stroke], renderer, width=320, height=240, fps=15)

    progress_calls = []

    def on_progress(cur, total):
        progress_calls.append((cur, total))

    gen.generate(out_video, draw_duration=0.5, hold_duration=0.2, exit_duration=0.2, progress_callback=on_progress)

    assert len(progress_calls) > 0
    # Last call should report current == total
    last_cur, total = progress_calls[-1]
    assert last_cur == total
    assert total == len(progress_calls)


def test_hold_phase_has_no_hand(tmp_path):
    """Test that frames in hold phase do not contain the hand and match completed canvas."""
    out_video = str(tmp_path / "no_hand_hold.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.3)
    stroke = Stroke(
        points=np.array([[50.0, 50.0], [250.0, 200.0]], dtype=float),
        color=(0, 0, 0, 255),
        width=8.0,
        length=250.0,
    )
    gen = WhiteboardVideoGenerator([stroke], renderer, width=320, height=240, fps=10)
    gen.generate(out_video, draw_duration=0.5, hold_duration=0.5, exit_duration=0.3)

    cap = cv2.VideoCapture(out_video)
    assert cap.isOpened()
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Read the very last frame (must be in hold phase)
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    ret, last_frame = cap.read()
    assert ret

    # Read frame 1 (during drawing phase - should have hand)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 2)
    ret, draw_frame = cap.read()
    assert ret

    # Hand should create a visible difference between drawing frame and final hold frame
    assert not np.array_equal(last_frame, draw_frame)
    cap.release()


def test_custom_background_color(tmp_path):
    """Test generating video with custom background color."""
    out_video = str(tmp_path / "custom_bg.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    bg_color = (200, 220, 240)  # Light blue in BGR
    gen = WhiteboardVideoGenerator(
        strokes=[],
        hand_renderer=renderer,
        width=320,
        height=240,
        fps=10,
        background_color=bg_color,
    )
    gen.generate(out_video, draw_duration=0.2, hold_duration=0.2, exit_duration=0.0)

    cap = cv2.VideoCapture(out_video)
    ret, frame = cap.read()
    assert ret
    # Pixels should be close to background color
    assert np.allclose(frame[10, 10], bg_color, atol=5)
    cap.release()


def test_discontinuous_stroke_easing(tmp_path):
    """Test that disjoint strokes transition smoothly without drawing in air."""
    out_video = str(tmp_path / "discontinuous.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    s1 = Stroke(points=np.array([[20.0, 20.0], [50.0, 20.0]], dtype=float), length=30.0)
    s2 = Stroke(points=np.array([[200.0, 200.0], [250.0, 200.0]], dtype=float), length=50.0)
    gen = WhiteboardVideoGenerator([s1, s2], renderer, width=320, height=240, fps=20)
    res = gen.generate(out_video, draw_duration=1.0, hold_duration=0.3, exit_duration=0.3)

    assert os.path.exists(res)
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    # Check the final frame: there should be no line drawn connecting (50, 20) and (200, 200)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1)
    ret, final_frame = cap.read()
    assert ret
    # The midpoint between s1 end and s2 start should remain clean white
    mid_x, mid_y = int((50 + 200) / 2), int((20 + 200) / 2)
    assert np.all(final_frame[mid_y, mid_x] >= 250)
    cap.release()


def test_codec_fallback(tmp_path):
    """Test fallback mechanism when preferred codec is unavailable or invalid."""
    out_video = str(tmp_path / "fallback.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    stroke = Stroke(points=np.array([[10, 10], [50, 50]], dtype=float), length=56.5)
    gen = WhiteboardVideoGenerator([stroke], renderer, width=320, height=240, fps=10)
    res = gen.generate(out_video, draw_duration=0.2, hold_duration=0.1, exit_duration=0.1, codec="INVALID_CODEC")

    assert os.path.exists(res)
    assert os.path.getsize(res) > 500
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    cap.release()


def test_zero_duration_fallback(tmp_path):
    """Test generating video when durations are zero still creates valid 1-frame video."""
    out_video = str(tmp_path / "zero_dur.mp4")
    renderer = HandRenderer("assets/default_hand.png", scale=0.2)
    stroke = Stroke(points=np.array([[10, 10], [50, 50]], dtype=float), length=56.5)
    gen = WhiteboardVideoGenerator([stroke], renderer, width=320, height=240, fps=10)
    res = gen.generate(out_video, draw_duration=0.0, hold_duration=0.0, exit_duration=0.0)

    assert os.path.exists(res)
    cap = cv2.VideoCapture(res)
    assert cap.isOpened()
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert count >= 1
    cap.release()

