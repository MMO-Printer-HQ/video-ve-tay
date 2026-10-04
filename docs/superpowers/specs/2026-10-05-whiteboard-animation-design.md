# Design Spec: Whiteboard Animation Video Generator (Video Vẽ Tay)

## 1. Overview
A standalone Python library and CLI tool that converts SVG vector graphics into whiteboard animation videos (hand-drawn style). A realistic hand holding a pen moves smoothly across the screen, drawing each stroke incrementally in sync with the hand motion. The tool provides ready-to-run default assets (sample hand image and sample sketch SVG), allowing users to execute `python main.py` with zero configuration to produce an instant high-quality MP4 demo video.

## 2. Goals & Non-Goals

### Goals
- **Zero-config demo**: Running `python main.py` immediately renders a complete demo video (`output_handdrawn.mp4`) using bundled assets.
- **Accurate pen-to-stroke sync**: The hand's pen tip matches the exact coordinates of the stroke tip at every video frame.
- **Natural hand motion**:
  - Smooth arc-length parameterization for drawing lines.
  - Pen-lift and reposition motion when transitioning between discontinuous strokes.
  - Exit animation at the end: The hand moves smoothly off-screen, revealing the final artwork for a configurable pause duration.
- **Customizable CLI**: Supports custom SVG files, hand images, output resolution, FPS, total drawing duration, stroke color, stroke width, and background color.
- **Pure Python with minimal standard dependencies**: Requires only `pillow`, `opencv-python`, `numpy`, and `svgpathtools` (or pure vector parser).

### Non-Goals
- Real-time live browser editing (UI is out of scope for this CLI/library version).
- Text-to-speech audio alignment (can be extended in the future).
- Complex raster-to-vector tracing (input should be vector SVG or default SVG).

## 3. Architecture & Project Layout

```
ve-tay/
├── assets/
│   ├── default_hand.png      # Hand holding a marker/pen with transparent background (RGBA)
│   └── demo_sketch.svg       # Sample SVG vector illustration (lightbulb/idea sketch)
├── whiteboard/
│   ├── __init__.py           # Package exports
│   ├── svg_parser.py         # Parse SVG curves/lines into discretized polyline strokes
│   ├── hand_renderer.py      # Manages hand image, tip anchor, drop shadow, and alpha compositing
│   └── video_generator.py    # Main animation orchestrator: timing, interpolation, frame rendering, MP4 export
├── main.py                   # CLI entrypoint with default arguments for instant demo
├── requirements.txt          # Python dependencies
└── docs/
    └── superpowers/specs/2026-10-05-whiteboard-animation-design.md
```

## 4. Detailed Component Design

### 4.1 SVG Parser (`whiteboard/svg_parser.py`)
- **Input**: SVG file path or XML string.
- **Supported Elements**: `<path>`, `<line>`, `<rect>`, `<circle>`, `<ellipse>`, `<polyline>`, `<polygon>`.
- **Processing**:
  - Extract path commands (M, L, C, S, Q, T, A, Z).
  - Normalize coordinates and scale to fit the target video viewport (e.g. 1920x1080 with margin padding).
  - Discretize each continuous curve into fine-grained point sequences based on arc length, preserving stroke curvature.
  - Return a list of `Stroke` objects:
    ```python
    @dataclass
    class Stroke:
        points: np.ndarray      # Shape (N, 2) of float (x, y) coordinates
        color: tuple[int, int, int, int]  # RGBA
        width: float
        length: float
    ```

### 4.2 Hand Renderer (`whiteboard/hand_renderer.py`)
- **Hand Asset**:
  - High-resolution RGBA PNG of a hand holding a pen.
  - Anchored at `tip_x, tip_y` (the point where the pen nib touches the paper, e.g., top-left corner of the pen tip).
- **Features**:
  - Optional subtle drop-shadow beneath the hand for depth and realistic whiteboard aesthetic.
  - Smooth scale adjustment matching resolution.
  - Fast alpha blending on canvas using NumPy slicing and PIL Image blending.

### 4.3 Animation & Video Generator (`whiteboard/video_generator.py`)
- **Timeline Computation**:
  - Total drawing length $L_{total} = \sum length(stroke_i)$.
  - Given `duration` (e.g., 6.0s) and `fps` (30 fps), calculate total drawing frames: $N_{draw} = duration \times fps$.
  - Assign frames to each stroke proportional to its length.
  - Add transition frames for "pen-up" repositioning between disjoint strokes (easing motion).
  - Add exit frames: Hand smoothly glides off-screen (e.g., bottom-right).
  - Add freeze/hold frames: 1.0s static display of the completed drawing.
- **Rendering Loop**:
  - Base canvas: Whiteboard background (solid white or subtle off-white/canvas texture).
  - Accumulation layer: Progressively draws line segments `(p_{k-1}, p_k)` with anti-aliasing.
  - Composite layer: Overlay hand at the current $(x, y)$ tip position.
  - Write frame to video stream using `cv2.VideoWriter` (mp4v/avc1 codec) or piped to `ffmpeg`.

### 4.4 Default Assets
- `assets/demo_sketch.svg`: An aesthetically pleasing vector drawing containing multiple strokes (e.g., an idea lightbulb with rays and a hand-written cursive "Idea").
- `assets/default_hand.png`: A clean hand holding a drawing pen, rendered with high alpha fidelity, with calibrated pen-tip offset coordinates.

### 4.5 CLI & Programmatic Usage (`main.py`)
- CLI command:
  ```bash
  # Zero config (default demo):
  python main.py

  # Custom config:
  python main.py --svg my_drawing.svg --output my_video.mp4 --duration 8 --fps 30 --width 1920 --height 1080
  ```
- Command-line Arguments:
  - `--svg`: Path to SVG file (default: `assets/demo_sketch.svg`).
  - `--hand`: Path to hand PNG (default: `assets/default_hand.png`).
  - `--output`: Output video path (default: `output_handdrawn.mp4`).
  - `--duration`: Total drawing time in seconds (default: 6.0).
  - `--fps`: Frame rate (default: 30).
  - `--width`: Video width (default: 1920).
  - `--height`: Video height (default: 1080).
  - `--tip-x`: Relative or absolute X offset of pen tip in hand image (optional override).
  - `--tip-y`: Relative or absolute Y offset of pen tip in hand image (optional override).

## 5. Error Handling & Edge Cases
- **Missing or empty SVG**: Validate SVG contains drawable elements; raise clear error message if no strokes found.
- **Bounding Box Scaling**: Auto-scale and center the SVG within canvas margins (e.g. 15% margin) so drawings never clip off-screen.
- **Discontinuous paths**: Smoothly interpolate hand position during `pen-up` jumps to avoid sudden hand flickering or teleportation.
- **Codec compatibility**: Try `mp4v` and fallback/detect available codecs or use ffmpeg CLI if available on the system.

## 6. Verification Plan
- Unit tests for SVG path extraction and point discretization.
- Integration test rendering the default demo SVG without errors.
- Validate that output MP4 video has valid duration, resolution, and non-zero byte size.
- Visually verify pen tip alignment with stroke ends.
