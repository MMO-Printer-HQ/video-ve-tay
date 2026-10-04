# Whiteboard Animation Video Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python tool and CLI that converts SVG vector drawings into hand-drawn whiteboard animation videos with realistic pen motion and zero-config demo execution.

**Architecture:** Parse SVG vector paths into polylines sampled evenly by arc-length. For each frame, incrementally render drawn lines onto a canvas and alpha-composite a hand image anchored at the pen tip. Encode resulting frames into an MP4 video file.

**Tech Stack:** Python 3.12, Pillow, OpenCV (`cv2`), NumPy, `svgpathtools`, Pytest.

## Global Constraints
- Must run out-of-the-box without required arguments (`python main.py` renders `output_handdrawn.mp4`).
- Pen tip coordinates must strictly coincide with the active drawing stroke tip.
- Transitions between disjoint strokes must glide naturally (pen-up).
- All files must reside in the project directory `/mnt/Shares/tmp/ve-tay`.

---

### Task 1: Project Setup and Default Assets Generation

**Files:**
- Create: `requirements.txt`
- Create: `assets/demo_sketch.svg`
- Create: `assets/default_hand.png` (synthesized/generated clean RGBA graphic of a hand holding a marker)
- Test: `tests/test_assets.py`

**Interfaces:**
- Produces:
  - `assets/demo_sketch.svg`: Valid SVG file containing path elements representing an idea lightbulb or sketch.
  - `assets/default_hand.png`: RGBA PNG with alpha channel, dimensions approx 300x500 to 500x700.
  - Anchor point metadata: `tip_x = 24, tip_y = 12` (or relative coordinates 0.0 to 1.0).

- [ ] **Step 1: Write tests for assets presence and validity**
```python
# tests/test_assets.py
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

def test_demo_svg_has_paths():
    with open("assets/demo_sketch.svg", "r") as f:
        content = f.read()
    assert "<svg" in content
    assert "<path" in content or "<line" in content
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_assets.py`
Expected: FAIL (files do not exist yet)

- [ ] **Step 3: Create requirements.txt and generate demo assets**
Create `requirements.txt`:
```
pillow>=10.0.0
opencv-python-headless>=4.8.0
numpy>=1.24.0
svgpathtools>=1.6.0
pytest>=8.0.0
```
Generate an aesthetic SVG vector sketch (`assets/demo_sketch.svg`) containing clean stroke paths.
Generate/create a clean, stylized hand holding a pen with transparent background (`assets/default_hand.png`).

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_assets.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add requirements.txt assets/ tests/test_assets.py
git commit -m "feat: add project requirements and default demo assets"
```

---

### Task 2: SVG Parser and Arc-Length Path Sampler

**Files:**
- Create: `whiteboard/__init__.py`
- Create: `whiteboard/svg_parser.py`
- Test: `tests/test_svg_parser.py`

**Interfaces:**
- Consumes: SVG file path, viewport dimensions `(target_width, target_height)`, margin padding.
- Produces:
  ```python
  @dataclass
  class Stroke:
      points: np.ndarray       # shape (N, 2), float coordinates in viewport space
      color: tuple[int, int, int, int] = (30, 30, 30, 255)
      width: float = 4.0
      length: float = 0.0

  def parse_svg(svg_path: str, canvas_width: int = 1920, canvas_height: int = 1080, margin: float = 0.15) -> list[Stroke]:
      ...
  ```

- [ ] **Step 1: Write the failing tests for SVG parsing**
```python
# tests/test_svg_parser.py
import pytest
import numpy as np
from whiteboard.svg_parser import parse_svg, Stroke

def test_parse_simple_svg(tmp_path):
    svg_file = tmp_path / "simple.svg"
    svg_file.write_text(
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M 10 10 L 90 90" stroke="#000000" stroke-width="2"/>'
        '</svg>'
    )
    strokes = parse_svg(str(svg_file), canvas_width=800, canvas_height=600)
    assert len(strokes) >= 1
    s = strokes[0]
    assert isinstance(s, Stroke)
    assert len(s.points) > 10
    assert s.length > 0
    # Coordinates must fit within canvas
    assert np.all(s.points[:, 0] >= 0) and np.all(s.points[:, 0] <= 800)
    assert np.all(s.points[:, 1] >= 0) and np.all(s.points[:, 1] <= 600)

def test_parse_demo_svg():
    strokes = parse_svg("assets/demo_sketch.svg", canvas_width=1920, canvas_height=1080)
    assert len(strokes) > 0
    for s in strokes:
        assert len(s.points) >= 2
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_svg_parser.py`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SVG parser in `whiteboard/svg_parser.py`**
Implement SVG reading using `svgpathtools`, convert bezier curves (`CubicBezier`, `QuadraticBezier`, `Line`, `Arc`) into sampled polylines with uniform arc-length step (e.g. 1-2 pixels), compute bounding box, center and scale into target canvas dimensions.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_svg_parser.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add whiteboard/__init__.py whiteboard/svg_parser.py tests/test_svg_parser.py
git commit -m "feat: implement SVG path parser and arc-length sampler"
```

---

### Task 3: Hand Renderer and Pen-Tip Compositor

**Files:**
- Create: `whiteboard/hand_renderer.py`
- Test: `tests/test_hand_renderer.py`

**Interfaces:**
- Consumes: Hand PNG image path, pen tip coordinates `(tip_x, tip_y)`.
- Produces:
  ```python
  class HandRenderer:
      def __init__(self, hand_img_path: str, tip_offset: tuple[int, int] | None = None, scale: float = 1.0):
          ...
      def overlay_hand(self, canvas: np.ndarray, pen_position: tuple[float, float], shadow: bool = True) -> np.ndarray:
          ...
  ```

- [ ] **Step 1: Write failing test for HandRenderer**
```python
# tests/test_hand_renderer.py
import numpy as np
from whiteboard.hand_renderer import HandRenderer

def test_hand_overlay():
    canvas = np.full((600, 800, 3), 255, dtype=np.uint8)
    renderer = HandRenderer("assets/default_hand.png", scale=0.5)
    rendered = renderer.overlay_hand(canvas, pen_position=(400, 300))
    assert rendered.shape == (600, 800, 3)
    # The canvas should no longer be pure white where the hand is drawn
    assert not np.all(rendered == 255)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_hand_renderer.py`
Expected: FAIL (HandRenderer not defined)

- [ ] **Step 3: Implement `whiteboard/hand_renderer.py`**
Implement `HandRenderer`:
- Load RGBA hand image.
- Calibrate or automatically locate/accept the tip anchor.
- Optional subtle soft drop-shadow offset (+10px right, +15px down with 30% alpha).
- Fast vectorized alpha blending with boundary clipping onto a BGR/RGB canvas.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_hand_renderer.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add whiteboard/hand_renderer.py tests/test_hand_renderer.py
git commit -m "feat: implement hand renderer with pen-tip anchoring and alpha compositing"
```

---

### Task 4: Video Generator and Motion Orchestrator

**Files:**
- Create: `whiteboard/video_generator.py`
- Test: `tests/test_video_generator.py`

**Interfaces:**
- Consumes: List of `Stroke`, `HandRenderer`, output path, resolution, fps, duration.
- Produces:
  ```python
  class WhiteboardVideoGenerator:
      def __init__(self, strokes: list[Stroke], hand_renderer: HandRenderer, width: int = 1920, height: int = 1080, fps: int = 30):
          ...
      def generate(self, output_path: str, draw_duration: float = 5.0, hold_duration: float = 1.0) -> str:
          ...
  ```

- [ ] **Step 1: Write failing test for video generation**
```python
# tests/test_video_generator.py
import os
import cv2
from whiteboard.svg_parser import parse_svg
from whiteboard.hand_renderer import HandRenderer
from whiteboard.video_generator import WhiteboardVideoGenerator

def test_generate_short_video(tmp_path):
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
    cap.release()
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_video_generator.py`
Expected: FAIL (WhiteboardVideoGenerator not found)

- [ ] **Step 3: Implement `whiteboard/video_generator.py`**
Implement the animation loop:
- Allocate frame budget based on stroke lengths.
- In-between stroke pen-up easing transition.
- Progressive line drawing using antialiased OpenCV / Pillow lines onto a static persistent drawing layer.
- Composite drawing layer + hand layer on each frame.
- Hand exit transition (gliding off-screen to bottom right).
- Hold completed image for `hold_duration`.
- Stream frames to `cv2.VideoWriter`.

- [ ] **Step 4: Run test to verify it passes**
Run: `.venv/bin/pytest tests/test_video_generator.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add whiteboard/video_generator.py tests/test_video_generator.py
git commit -m "feat: implement whiteboard video generator animation orchestrator"
```

---

### Task 5: Main Entrypoint (CLI), Zero-Config Demo, and End-to-End Verification

**Files:**
- Create: `main.py`
- Create: `README.md`
- Test: `tests/test_main_cli.py`

**Interfaces:**
- CLI with `argparse`, default values pointing to `assets/demo_sketch.svg`, `assets/default_hand.png`, generating `output_handdrawn.mp4`.

- [ ] **Step 1: Write CLI end-to-end test**
```python
# tests/test_main_cli.py
import subprocess
import os

def test_cli_default_run():
    # Run main.py with small test parameters to verify zero-config behavior quickly
    cmd = [
        ".venv/bin/python", "main.py",
        "--duration", "1.0",
        "--hold", "0.5",
        "--fps", "15",
        "--width", "480",
        "--height", "270",
        "--output", "test_cli_output.mp4"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert os.path.exists("test_cli_output.mp4")
    assert os.path.getsize("test_cli_output.mp4") > 1000
    if os.path.exists("test_cli_output.mp4"):
        os.remove("test_cli_output.mp4")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv/bin/pytest tests/test_main_cli.py`
Expected: FAIL (`main.py` not found)

- [ ] **Step 3: Implement `main.py` and documentation `README.md`**
Implement argument parser, default values, user-friendly progress reporting (percentage and ETA), and documentation in `README.md`.

- [ ] **Step 4: Run all test suites and full demo render**
Run: `.venv/bin/pytest`
Run: `.venv/bin/python main.py`
Verify `output_handdrawn.mp4` is rendered successfully.

- [ ] **Step 5: Commit**
```bash
git add main.py README.md tests/test_main_cli.py
git commit -m "feat: add CLI entrypoint and complete zero-config demo"
```
