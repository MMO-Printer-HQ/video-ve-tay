import os
import pytest
import numpy as np
from PIL import Image

from whiteboard.hand_renderer import HandRenderer, DEFAULT_TIP_OFFSET


def test_hand_overlay():
    """Verify basic hand overlay on white canvas as defined in task brief."""
    canvas = np.full((600, 800, 3), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.5)
    rendered = renderer.overlay_hand(canvas, pen_position=(400, 300))
    assert rendered.shape == (600, 800, 3)
    # The canvas should no longer be pure white where the hand is drawn
    assert not np.all(rendered == 255)
    # Original canvas should not be mutated
    assert np.all(canvas == 255)


def test_tip_offset_default_and_custom():
    """Verify default tip offset for default_hand.png and custom tip offsets."""
    assert DEFAULT_TIP_OFFSET == (24, 12)
    renderer_default = HandRenderer("assets/default_hand.png", scale=1.0)
    assert renderer_default.tip_offset == (24, 12)
    assert renderer_default.scaled_tip_offset == (24, 12)

    # With scale 0.5
    renderer_half = HandRenderer("assets/default_hand.png", scale=0.5)
    assert renderer_half.tip_offset == (24, 12)
    assert renderer_half.scaled_tip_offset == (12, 6)

    # Custom offset
    renderer_custom = HandRenderer("assets/default_hand.png", tip_offset=(100, 50), scale=0.5)
    assert renderer_custom.tip_offset == (100, 50)
    assert renderer_custom.scaled_tip_offset == (50, 25)


def test_pen_position_anchoring():
    """Verify that the hand is anchored such that tip_offset touches pen_position."""
    canvas = np.full((600, 800, 3), 255, dtype=np.uint8)
    scale = 0.5
    renderer = HandRenderer("assets/default_hand.png", scale=scale, shadow=False)

    pen_x, pen_y = 350, 250
    rendered = renderer.overlay_hand(canvas, pen_position=(pen_x, pen_y), shadow=False)

    # At pen_position, the marker tip must have altered the pure white canvas
    # The default hand image at (24, 12) has dark marker tip (alpha 255)
    tip_pixel = rendered[pen_y, pen_x]
    assert not np.all(tip_pixel == 255), "Pen tip coordinate should have marker pixels rendered"

    # Coordinates strictly before the hand's top-left corner should be untouched
    # Hand origin is at pen_x - scaled_tip_x, pen_y - scaled_tip_y
    hand_x = pen_x - renderer.scaled_tip_offset[0]
    hand_y = pen_y - renderer.scaled_tip_offset[1]
    assert np.all(rendered[hand_y - 10, hand_x - 10] == 255)


def test_shadow_effect():
    """Verify drop shadow effect creates darker pixels outside the hand body."""
    canvas_no_shadow = np.full((600, 800, 3), 255, dtype=np.uint8)
    canvas_with_shadow = np.full((600, 800, 3), 255, dtype=np.uint8)

    renderer = HandRenderer("assets/default_hand.png", scale=0.5)
    rendered_no_shadow = renderer.overlay_hand(canvas_no_shadow, pen_position=(300, 200), shadow=False)
    rendered_with_shadow = renderer.overlay_hand(canvas_with_shadow, pen_position=(300, 200), shadow=True)

    # The shadow version should have fewer pure white pixels than the no-shadow version
    white_no_shadow = np.count_nonzero(np.all(rendered_no_shadow == 255, axis=-1))
    white_with_shadow = np.count_nonzero(np.all(rendered_with_shadow == 255, axis=-1))
    assert white_with_shadow < white_no_shadow, "Shadow should darken pixels outside the hand"


def test_boundary_clipping():
    """Verify clean rendering and clipping when hand is partially or wholly off-screen."""
    canvas = np.full((400, 400, 3), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.5)

    # Partially clipped on top-left
    res_top_left = renderer.overlay_hand(canvas, pen_position=(0, 0))
    assert res_top_left.shape == (400, 400, 3)
    assert not np.all(res_top_left == 255)

    # Partially clipped on bottom-right
    res_bottom_right = renderer.overlay_hand(canvas, pen_position=(390, 390))
    assert res_bottom_right.shape == (400, 400, 3)
    assert not np.all(res_bottom_right == 255)

    # Completely off-screen (top/left)
    res_far_negative = renderer.overlay_hand(canvas, pen_position=(-1000, -1000))
    assert res_far_negative.shape == (400, 400, 3)
    assert np.all(res_far_negative == 255)

    # Completely off-screen (bottom/right)
    res_far_positive = renderer.overlay_hand(canvas, pen_position=(2000, 2000))
    assert res_far_positive.shape == (400, 400, 3)
    assert np.all(res_far_positive == 255)


def test_color_format_support():
    """Verify support for both BGR and RGB canvases."""
    canvas_bgr = np.full((300, 300, 3), 255, dtype=np.uint8)
    canvas_rgb = np.full((300, 300, 3), 255, dtype=np.uint8)

    renderer_bgr = HandRenderer("assets/default_hand.png", scale=0.3, color_format="bgr")
    renderer_rgb = HandRenderer("assets/default_hand.png", scale=0.3, color_format="rgb")

    res_bgr = renderer_bgr.overlay_hand(canvas_bgr, pen_position=(100, 100), shadow=False)
    res_rgb = renderer_rgb.overlay_hand(canvas_rgb, pen_position=(100, 100), shadow=False)

    assert res_bgr.shape == (300, 300, 3)
    assert res_rgb.shape == (300, 300, 3)
    # Both produce non-white pixels
    assert not np.all(res_bgr == 255)
    assert not np.all(res_rgb == 255)


def test_four_channel_rgba_canvas():
    """Verify compositing on 4-channel RGBA canvas."""
    canvas = np.full((400, 400, 4), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.4)
    rendered = renderer.overlay_hand(canvas, pen_position=(200, 200))
    assert rendered.shape == (400, 400, 4)
    assert not np.all(rendered == 255)


def test_input_validation(tmp_path):
    """Verify error handling on invalid inputs."""
    # Missing file
    with pytest.raises(FileNotFoundError):
        HandRenderer("non_existent_file.png")

    # Invalid scale
    with pytest.raises(ValueError, match="scale must be positive"):
        HandRenderer("assets/default_hand.png", scale=0.0)
    with pytest.raises(ValueError, match="scale must be positive"):
        HandRenderer("assets/default_hand.png", scale=-1.0)

    # Invalid canvas
    renderer = HandRenderer("assets/default_hand.png", scale=0.5)
    with pytest.raises(ValueError, match="canvas must be a uint8 numpy array"):
        renderer.overlay_hand(np.full((100, 100), 255, dtype=np.uint8), pen_position=(50, 50))
    with pytest.raises(ValueError, match="canvas must be a uint8 numpy array"):
        renderer.overlay_hand(np.full((100, 100, 3), 1.0, dtype=np.float32), pen_position=(50, 50))

    # Invalid tip_offset
    with pytest.raises(ValueError, match="tip_offset must be a tuple"):
        HandRenderer("assets/default_hand.png", tip_offset=(1,))


def test_package_export():
    """Verify HandRenderer and DEFAULT_TIP_OFFSET are exported by whiteboard package."""
    import whiteboard
    assert hasattr(whiteboard, "HandRenderer")
    assert hasattr(whiteboard, "DEFAULT_TIP_OFFSET")
    assert "HandRenderer" in whiteboard.__all__
    assert "DEFAULT_TIP_OFFSET" in whiteboard.__all__


def test_in_place_modification_when_copy_false():
    """Verify that copy=False modifies the canvas in-place."""
    canvas = np.full((300, 300, 3), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.3)
    res = renderer.overlay_hand(canvas, pen_position=(150, 150), copy=False)
    assert res is canvas
    assert not np.all(canvas == 255)


def test_subpixel_float_pen_positions():
    """Verify that fractional pen coordinates are accepted without errors."""
    canvas = np.full((300, 300, 3), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.3)
    res = renderer.overlay_hand(canvas, pen_position=(150.7, 150.2))
    assert res.shape == (300, 300, 3)
    assert not np.all(res == 255)


def test_custom_image_tip_autodetection(tmp_path):
    """Verify auto-detection of tip on a custom RGBA image when tip_offset is None."""
    # Create an image with transparent background and an opaque circle centered at (30, 40)
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    # Place an opaque pixel at (30, 40)
    img.putpixel((30, 40), (255, 0, 0, 255))
    img.putpixel((31, 40), (255, 0, 0, 255))
    img.putpixel((50, 50), (255, 0, 0, 255))

    custom_path = str(tmp_path / "custom_pen.png")
    img.save(custom_path)

    renderer = HandRenderer(custom_path, scale=1.0)
    assert renderer.tip_offset == (30, 40)


def test_invalid_color_format():
    """Verify ValueError on unsupported color formats."""
    with pytest.raises(ValueError, match="color_format must be 'bgr' or 'rgb'"):
        HandRenderer("assets/default_hand.png", color_format="cmyk")

    renderer = HandRenderer("assets/default_hand.png")
    with pytest.raises(ValueError, match="color_format must be 'bgr' or 'rgb'"):
        canvas = np.full((100, 100, 3), 255, dtype=np.uint8)
        renderer.overlay_hand(canvas, pen_position=(50, 50), color_format="invalid")

