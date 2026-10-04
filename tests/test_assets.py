import os
from PIL import Image

def test_assets_exist():
    assert os.path.exists("assets/demo_sketch.svg")
    assert os.path.exists("assets/default_hand.png")

def test_hand_image_is_rgba():
    img = Image.open("assets/default_hand.png")
    assert img.mode == "RGBA"
    assert img.width > 100
    assert img.height > 100
    # Verify image has transparent pixels (alpha < 255) and opaque pixels (alpha > 0)
    alpha = img.getchannel("A")
    extrema = alpha.getextrema()
    assert extrema[0] < 255, "Hand image must have transparent areas"
    assert extrema[1] > 0, "Hand image must have visible non-transparent pixels"

def test_hand_image_tip_location():
    img = Image.open("assets/default_hand.png")
    # Tip at (24, 12) is opaque
    r, g, b, a = img.getpixel((24, 12))
    assert a > 200, "Pen tip at (24, 12) should be opaque"
    # Pixels outside the hand near top-left should be transparent
    _, _, _, a_outside = img.getpixel((0, 0))
    assert a_outside == 0, "Top-left boundary (0, 0) should be transparent"

def test_demo_svg_has_paths():
    with open("assets/demo_sketch.svg", "r") as f:
        content = f.read()
    assert "<svg" in content
    assert "<path" in content or "<line" in content

