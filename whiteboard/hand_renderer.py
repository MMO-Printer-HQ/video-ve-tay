"""Hand renderer and pen-tip compositor for whiteboard animations."""

from pathlib import Path
from typing import Sequence
import cv2
import numpy as np
from PIL import Image

DEFAULT_TIP_OFFSET: tuple[int, int] = (24, 12)


class HandRenderer:
    """Renders and composites a hand holding a marker onto video frame canvases."""

    def __init__(
        self,
        hand_img_path: str | Path = "assets/default_hand.png",
        tip_offset: tuple[int, int] | None = None,
        scale: float = 1.0,
        shadow: bool = True,
        shadow_offset: tuple[int, int] = (10, 12),
        shadow_alpha: float = 0.3,
        color_format: str = "bgr",
    ) -> None:
        """Initialize the hand renderer with asset path, scaling, and anchor offset.

        Args:
            hand_img_path: Path to the RGBA hand graphic.
            tip_offset: Optional (x, y) coordinates of marker tip in the original image.
                        Defaults to (24, 12) for default_hand.png or auto-detects nearest opaque pixel.
            scale: Positive scaling factor for the hand image.
            shadow: Default flag whether to render drop shadow.
            shadow_offset: (dx, dy) offset for the drop shadow in base pixels.
            shadow_alpha: Maximum opacity for the drop shadow (0.0 to 1.0).
            color_format: Target canvas color format, either "bgr" or "rgb".
        """
        path_obj = Path(hand_img_path)
        if not path_obj.is_file():
            raise FileNotFoundError(f"Hand image file not found: {hand_img_path}")

        if scale <= 0:
            raise ValueError(f"scale must be positive, got {scale}")

        color_fmt = color_format.lower()
        if color_fmt not in ("bgr", "rgb"):
            raise ValueError(f"color_format must be 'bgr' or 'rgb', got {color_format}")

        self.hand_img_path = str(path_obj)
        self.scale = float(scale)
        self.default_shadow = bool(shadow)
        self.color_format = color_fmt

        # Load image and ensure RGBA
        raw_img = Image.open(path_obj).convert("RGBA")
        self.orig_size = raw_img.size  # (width, height)

        # Calibrate tip offset
        if tip_offset is not None:
            if not (isinstance(tip_offset, (tuple, list, Sequence)) and len(tip_offset) == 2):
                raise ValueError(f"tip_offset must be a tuple of (x, y), got {tip_offset}")
            self.tip_offset = (int(tip_offset[0]), int(tip_offset[1]))
        elif "default_hand" in path_obj.name:
            self.tip_offset = DEFAULT_TIP_OFFSET
        else:
            # Auto-detect tip as closest opaque pixel to top-left origin (0, 0)
            alpha_raw = np.array(raw_img.getchannel("A"))
            ys, xs = np.where(alpha_raw > 128)
            if len(xs) > 0:
                dists = xs**2 + ys**2
                min_idx = np.argmin(dists)
                self.tip_offset = (int(xs[min_idx]), int(ys[min_idx]))
            else:
                self.tip_offset = (0, 0)

        # Apply scaling
        orig_w, orig_h = self.orig_size
        self.width = max(1, int(round(orig_w * self.scale)))
        self.height = max(1, int(round(orig_h * self.scale)))
        self.size = (self.width, self.height)

        if self.scale != 1.0:
            scaled_img = raw_img.resize((self.width, self.height), Image.Resampling.LANCZOS)
        else:
            scaled_img = raw_img

        self.scaled_tip_offset = (
            int(round(self.tip_offset[0] * self.scale)),
            int(round(self.tip_offset[1] * self.scale)),
        )

        scaled_hand_rgba = np.array(scaled_img, dtype=np.uint8)
        self._alpha = (scaled_hand_rgba[:, :, 3].astype(np.float32) / 255.0)[:, :, None]

        # Precompute RGB and BGR representation for fast frame blitting
        rgb = scaled_hand_rgba[:, :, :3].astype(np.float32)
        self._hand_rgb = rgb
        self._hand_bgr = rgb[:, :, ::-1]

        # Precompute soft drop shadow mask
        self.scaled_shadow_offset = (
            int(round(shadow_offset[0] * self.scale)),
            int(round(shadow_offset[1] * self.scale)),
        )
        self.shadow_alpha = float(np.clip(shadow_alpha, 0.0, 1.0))

        # Blur kernel size proportional to scale, minimum 3x3 odd integer
        k = max(3, int(round(15 * self.scale)) | 1)
        if k % 2 == 0:
            k += 1
        sigma = max(1.0, 4.0 * self.scale)
        blurred_alpha = cv2.GaussianBlur(self._alpha[:, :, 0], (k, k), sigma)
        self._shadow_mask = (blurred_alpha * self.shadow_alpha)[:, :, None]

    def overlay_hand(
        self,
        canvas: np.ndarray,
        pen_position: tuple[float, float],
        shadow: bool | None = None,
        copy: bool = True,
        color_format: str | None = None,
    ) -> np.ndarray:
        """Composite the hand holding a marker onto the canvas at pen_position.

        The hand graphic is positioned so that `tip_offset` in the hand image
        coincides exactly with `pen_position` on the canvas. Boundary clipping
        is applied cleanly when the hand is partially outside canvas bounds.

        Args:
            canvas: uint8 numpy array with shape (H, W, 3) or (H, W, 4).
            pen_position: (x, y) coordinates on canvas where marker tip touches.
            shadow: Whether to render drop shadow beneath hand (defaults to self.default_shadow).
            copy: If True, returns a copy of canvas; if False, modifies canvas in-place.
            color_format: Optional override for color format ("bgr" or "rgb").

        Returns:
            np.ndarray: Canvas with hand composited.
        """
        if not isinstance(canvas, np.ndarray) or canvas.dtype != np.uint8 or canvas.ndim != 3 or canvas.shape[2] not in (3, 4):
            raise ValueError("canvas must be a uint8 numpy array with 3 or 4 channels")

        fmt = (color_format or self.color_format).lower()
        if fmt not in ("bgr", "rgb"):
            raise ValueError(f"color_format must be 'bgr' or 'rgb', got {fmt}")

        out = canvas.copy() if copy else canvas
        use_shadow = self.default_shadow if shadow is None else bool(shadow)

        pen_x = float(pen_position[0])
        pen_y = float(pen_position[1])

        hand_x = int(round(pen_x - self.scaled_tip_offset[0]))
        hand_y = int(round(pen_y - self.scaled_tip_offset[1]))

        # Step 1: Render soft drop shadow beneath hand if enabled
        if use_shadow:
            shadow_x = hand_x + self.scaled_shadow_offset[0]
            shadow_y = hand_y + self.scaled_shadow_offset[1]
            self._composite_layer(
                canvas=out,
                overlay_src=None,
                alpha_src=self._shadow_mask,
                origin_x=shadow_x,
                origin_y=shadow_y,
            )

        # Step 2: Render hand graphic on top
        hand_src = self._hand_bgr if fmt == "bgr" else self._hand_rgb
        self._composite_layer(
            canvas=out,
            overlay_src=hand_src,
            alpha_src=self._alpha,
            origin_x=hand_x,
            origin_y=hand_y,
        )

        return out

    def _composite_layer(
        self,
        canvas: np.ndarray,
        overlay_src: np.ndarray | None,
        alpha_src: np.ndarray,
        origin_x: int,
        origin_y: int,
    ) -> None:
        """Blend an overlay and alpha mask onto canvas with boundary clipping."""
        canvas_h, canvas_w, channels = canvas.shape
        img_h, img_w = alpha_src.shape[:2]

        dst_x1 = max(0, origin_x)
        dst_y1 = max(0, origin_y)
        dst_x2 = min(canvas_w, origin_x + img_w)
        dst_y2 = min(canvas_h, origin_y + img_h)

        if dst_x1 >= dst_x2 or dst_y1 >= dst_y2:
            return  # Completely out of bounds

        src_x1 = dst_x1 - origin_x
        src_y1 = dst_y1 - origin_y
        src_x2 = src_x1 + (dst_x2 - dst_x1)
        src_y2 = src_y1 + (dst_y2 - dst_y1)

        c_crop = canvas[dst_y1:dst_y2, dst_x1:dst_x2].astype(np.float32)
        a_crop = alpha_src[src_y1:src_y2, src_x1:src_x2]

        if overlay_src is None:
            # Drop shadow: pure darkening of background
            if channels == 4:
                c_crop[:, :, :3] = c_crop[:, :, :3] * (1.0 - a_crop)
            else:
                c_crop = c_crop * (1.0 - a_crop)
            canvas[dst_y1:dst_y2, dst_x1:dst_x2] = np.clip(c_crop + 0.5, 0, 255).astype(np.uint8)
        else:
            # Image overlay
            src_crop = overlay_src[src_y1:src_y2, src_x1:src_x2]
            if channels == 3:
                blended = src_crop * a_crop + c_crop * (1.0 - a_crop)
                canvas[dst_y1:dst_y2, dst_x1:dst_x2] = np.clip(blended + 0.5, 0, 255).astype(np.uint8)
            else:
                # 4-channel canvas (RGBA / BGRA)
                src_rgb = src_crop[:, :, :3]
                blended_rgb = src_rgb * a_crop + c_crop[:, :, :3] * (1.0 - a_crop)
                c_alpha = c_crop[:, :, 3:4] / 255.0
                out_alpha = a_crop + c_alpha * (1.0 - a_crop)
                canvas[dst_y1:dst_y2, dst_x1:dst_x2, :3] = np.clip(blended_rgb + 0.5, 0, 255).astype(np.uint8)
                canvas[dst_y1:dst_y2, dst_x1:dst_x2, 3:4] = np.clip(out_alpha * 255.0 + 0.5, 0, 255).astype(np.uint8)
