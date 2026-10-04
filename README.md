# Whiteboard Animation Video Generator (Vẽ tay) ✍️🎥

> Công cụ tạo video hiệu ứng vẽ tay (Whiteboard Animation) từ đồ họa vector SVG bằng Python, mô phỏng chuyển động tay cầm bút vẽ nét mượt mà, chân thực theo chuẩn video bảng trắng.

[English summary below](#english-summary)

---

## 🌟 Tính năng nổi bật (Features)

- **Zero-Config Demo**: Chạy ngay lập tức với `python main.py` mà không cần cấu hình, tự động xuất video demo 1080p sắc nét (`output_handdrawn.mp4`).
- **Khớp nét vẽ chính xác (Pen-to-Stroke Sync)**: Đầu ngòi bút luôn bám sát tọa độ thực tế của từng nét vẽ trong từng khung hình.
- **Chuyển động tay tự nhiên (Natural Motion)**:
  - Tham số hóa theo độ dài cung (arc-length parameterization) giúp nét vẽ đều đặn, không bị giật.
  - Hiệu ứng nhấc bút (pen-up) và di chuyển mượt mà (easing) khi chuyển giữa các nét rời rạc.
  - Hiệu ứng lướt tay ra ngoài màn hình (hand exit glide) khi hoàn thành.
  - Giữ khung hình tĩnh (hold freeze) hiển thị trọn vẹn tác phẩm cuối video.
- **Bóng đổ mềm mại (Realistic Drop Shadow)**: Tạo chiều sâu 3D trên nền bảng trắng.
- **Tùy biến linh hoạt**: Tùy chỉnh kích thước video, FPS, thời lượng, tỷ lệ bàn tay, tọa độ ngòi bút, lề khung hình.
- **Đầy đủ CLI & Python API**: Sử dụng dễ dàng từ dòng lệnh hoặc tích hợp trực tiếp vào dự án Python.

---

## 📦 Cài đặt & Sử dụng siêu tốc với `uv` (Khuyên dùng) ⚡

Dự án đã cấu hình sẵn [`pyproject.toml`](pyproject.toml) tương thích hoàn toàn với **`uv`**. Không cần mất thời gian cài pip hay tạo venv thủ công:

```bash
# Chạy ngay lập tức với uv (tự động đồng bộ và render trong 2 giây):
uv run main.py
```

### Cách cài đặt truyền thống qua `pip` (Alternative)

```bash
# Tạo và kích hoạt môi trường ảo
python3 -m venv .venv
source .venv/bin/activate  # Trên Linux/macOS

# Cài đặt qua pip hoặc uv pip
uv pip install -r requirements.txt
# hoặc: pip install -r requirements.txt
```

---

## 🚀 Sử dụng nhanh (Quick Start)

### 1. Chạy bản demo mặc định (Zero-config)

Chỉ cần gõ:
```bash
uv run main.py
# hoặc: python main.py (khi đã active .venv)
```
Hệ thống sẽ tải file vector `assets/demo_sketch.svg` và hình ảnh bàn tay `assets/default_hand.png`, xuất ra video `output_handdrawn.mp4` độ phân giải 1080p (1920x1080) với thanh tiến trình trực quan trên terminal.

---

## ⚙️ Các tham số dòng lệnh (CLI Flags)

```bash
python main.py [TÙY CHỌN]
```

| Tham số | Kiểu dữ liệu | Mặc định | Mô tả |
|---|---|---|---|
| `--svg` | `str` | `assets/demo_sketch.svg` | Đường dẫn đến file vector SVG đầu vào |
| `--hand` | `str` | `assets/default_hand.png` | Đường dẫn đến ảnh bàn tay cầm bút (PNG trong suốt RGBA) |
| `--output` | `str` | `output_handdrawn.mp4` | Đường dẫn file video MP4 kết quả |
| `--duration` | `float` | `6.0` | Thời lượng vẽ hoạt ảnh (giây) |
| `--hold` | `float` | `1.0` | Thời gian dừng hiển thị tác phẩm sau khi vẽ xong (giây) |
| `--exit` | `float` | `0.5` | Thời gian bàn tay lướt ra ngoài màn hình (giây) |
| `--fps` | `int` | `30` | Tốc độ khung hình (khung hình / giây) |
| `--width` | `int` | `1920` | Chiều rộng khung hình video (pixel) |
| `--height` | `int` | `1080` | Chiều cao khung hình video (pixel) |
| `--scale-hand`| `float` | `0.5` | Tỉ lệ phóng to/thu nhỏ hình ảnh bàn tay |
| `--tip-x` | `int` | `None` | Tọa độ X ngòi bút trên ảnh gốc bàn tay (tùy chọn ghi đè) |
| `--tip-y` | `int` | `None` | Tọa độ Y ngòi bút trên ảnh gốc bàn tay (tùy chọn ghi đè) |
| `--margin` | `float` | `0.15` | Tỷ lệ khoảng đệm lề cho hình vẽ (0.15 = 15% viền) |

### Ví dụ nâng cao:
```bash
# Tạo video 4K tốc độ 60fps vẽ trong 10 giây
python main.py \
  --svg my_artwork.svg \
  --output my_artwork_4k.mp4 \
  --width 3840 \
  --height 2160 \
  --fps 60 \
  --duration 10.0 \
  --scale-hand 0.8

# Tạo video dọc ngắn (Shorts / Reels / TikTok) 1080x1920
python main.py \
  --svg logo.svg \
  --output vertical_short.mp4 \
  --width 1080 \
  --height 1920 \
  --scale-hand 0.4 \
  --duration 4.0
```

---

## 🐍 Sử dụng qua Python API (Library Usage)

Bạn có thể import trực tiếp các module vào code Python:

```python
from whiteboard import parse_svg, HandRenderer, WhiteboardVideoGenerator

# 1. Phân tích SVG thành chuỗi các nét vẽ (Strokes)
strokes = parse_svg(
    svg_path="assets/demo_sketch.svg",
    canvas_width=1920,
    canvas_height=1080,
    margin=0.15,
)

# 2. Khởi tạo HandRenderer với ảnh tay và độ co giãn
hand = HandRenderer(
    hand_img_path="assets/default_hand.png",
    scale=0.5,
    shadow=True,
)

# 3. Khởi tạo bộ tạo video
generator = WhiteboardVideoGenerator(
    strokes=strokes,
    hand_renderer=hand,
    width=1920,
    height=1080,
    fps=30,
    background_color=(255, 255, 255),  # Trắng BGR
)

# 4. Xuất video MP4
def on_progress(current_frame, total_frames):
    percent = (current_frame / total_frames) * 100
    print(f"Tiến độ: {current_frame}/{total_frames} ({percent:.1f}%)")

generator.generate(
    output_path="my_video.mp4",
    draw_duration=6.0,
    hold_duration=1.0,
    exit_duration=0.5,
    progress_callback=on_progress,
)
```

---

## 🧪 Kiểm thử (Testing)

Dự án áp dụng phương pháp kiểm thử Test-Driven Development (TDD). Chạy toàn bộ test suite bằng `pytest`:

```bash
.venv/bin/pytest
```

Chạy kiểm thử với báo cáo chi tiết:
```bash
.venv/bin/pytest -v
```

---

## 📁 Cấu trúc dự án (Project Structure)

```text
ve-tay/
├── assets/
│   ├── default_hand.png          # Ảnh bàn tay cầm bút (RGBA PNG với alpha channel)
│   └── demo_sketch.svg           # File mẫu SVG vector (bóng đèn ý tưởng)
├── whiteboard/
│   ├── __init__.py               # Exports thư viện
│   ├── svg_parser.py             # Bộ phân tích và lấy mẫu đường cong SVG
│   ├── hand_renderer.py          # Bộ render tay cầm bút, bóng đổ và ghép layer
│   └── video_generator.py        # Bộ điều phối chuyển động và xuất file MP4
├── tests/
│   ├── test_assets.py            # Kiểm tra tài nguyên mẫu
│   ├── test_svg_parser.py        # Kiểm tra parser SVG
│   ├── test_hand_renderer.py     # Kiểm tra ghép hình bàn tay và anchor ngòi bút
│   ├── test_video_generator.py   # Kiểm tra sinh video và đồng bộ thời gian
│   └── test_main_cli.py          # Kiểm thử dòng lệnh CLI và tham số
├── main.py                       # CLI entrypoint
├── pytest.ini                    # Cấu hình pytest
├── requirements.txt              # Danh sách thư viện Python
└── README.md                     # Tài liệu hướng dẫn sử dụng
```

---

<a id="english-summary"></a>
## 🌐 English Summary

### Overview
**Whiteboard Animation Video Generator** is a Python CLI and library that transforms vector SVG graphics into realistic hand-drawn whiteboard animation videos. It precisely tracks the pen tip with stroke coordinates, renders realistic hand drop-shadows, smoothly interpolates pen lift/motion, and glides off-screen before holding on the completed illustration.

### Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Render out-of-the-box 1080p demo
python main.py

# Custom render
python main.py --svg drawing.svg --output video.mp4 --duration 8.0 --fps 30 --scale-hand 0.5
```

### Key CLI Options
- `--svg`: Input SVG vector file (default: `assets/demo_sketch.svg`)
- `--hand`: Hand graphic holding a pen (default: `assets/default_hand.png`)
- `--output`: Output MP4 file path (default: `output_handdrawn.mp4`)
- `--duration`: Drawing duration in seconds (default: `6.0`)
- `--hold`: Hold duration after completion in seconds (default: `1.0`)
- `--exit`: Off-screen hand exit glide duration in seconds (default: `0.5`)
- `--fps`: Frame rate (default: `30`)
- `--width`, `--height`: Canvas resolution (default: `1920x1080`)
- `--scale-hand`: Scale factor for hand graphic (default: `0.5`)
- `--tip-x`, `--tip-y`: Optional pen tip offset override on original hand image
- `--margin`: Viewport margin padding fraction (default: `0.15`)

### Python API Example
```python
from whiteboard import parse_svg, HandRenderer, WhiteboardVideoGenerator

strokes = parse_svg("assets/demo_sketch.svg", canvas_width=1920, canvas_height=1080)
hand = HandRenderer("assets/default_hand.png", scale=0.5)
generator = WhiteboardVideoGenerator(strokes, hand, width=1920, height=1080, fps=30)
generator.generate("output.mp4", draw_duration=6.0, hold_duration=1.0)
```
