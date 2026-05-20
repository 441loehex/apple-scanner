"""Generate top-down PNG preview from normalized point cloud."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def render_preview(
    points: np.ndarray,
    output_path: Path,
    width: int = 1024,
    height: int = 1024,
) -> Path:
    """
    Project normalized point cloud to a top-down PNG.

    If the points array has 6 columns (XYZ + RGB from a coloured PLY export),
    the actual scan colours are rendered — apples appear red/green, the blue
    calibration ring appears blue, and the ground is its natural colour.

    If only XYZ is available, falls back to a height-based green-tinted render
    with gamma correction so the image is bright enough to annotate.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(points) == 0:
        Image.new("RGB", (width, height), (50, 60, 50)).save(str(output_path))
        return output_path

    has_color = points.shape[1] >= 6

    if has_color:
        _render_colored(points, output_path, width, height)
    else:
        _render_height(points, output_path, width, height)

    return output_path


# ---------------------------------------------------------------------------
# Coloured render — uses actual RGB from Polycam PLY
# ---------------------------------------------------------------------------

def _render_colored(
    points: np.ndarray,
    output_path: Path,
    width: int,
    height: int,
) -> None:
    xs = np.clip(points[:, 0], 0.0, 1.0)
    ys = np.clip(points[:, 1], 0.0, 1.0)
    rs = np.clip(points[:, 3], 0, 255).astype(np.uint8)
    gs = np.clip(points[:, 4], 0, 255).astype(np.uint8)
    bs = np.clip(points[:, 5], 0, 255).astype(np.uint8)

    # Sort ascending by col 2 (height) so highest points (apple tops) are drawn
    # last and win per pixel when multiple points map to the same canvas position.
    if points.shape[1] >= 3:
        sort_idx = np.argsort(points[:, 2])
        xs = xs[sort_idx]
        ys = ys[sort_idx]
        rs = rs[sort_idx]
        gs = gs[sort_idx]
        bs = bs[sort_idx]

    px = (xs * (width - 1)).astype(np.int32)
    py = ((1.0 - ys) * (height - 1)).astype(np.int32)

    # Dark background so apple colours and the blue ring stand out clearly.
    BG = 40
    canvas_r = np.full((height, width), BG, dtype=np.uint8)
    canvas_g = np.full((height, width), BG, dtype=np.uint8)
    canvas_b = np.full((height, width), BG, dtype=np.uint8)
    painted = np.zeros((height, width), dtype=bool)

    canvas_r[py, px] = rs
    canvas_g[py, px] = gs
    canvas_b[py, px] = bs
    painted[py, px] = True

    # Fill only actual holes (unpainted pixels) — dense scans need no blur at all.
    if not painted.all():
        mask = (~painted).astype(np.uint8) * 255
        for canvas in (canvas_r, canvas_g, canvas_b):
            blurred = cv2.GaussianBlur(canvas, (5, 5), 1)
            canvas[mask > 0] = blurred[mask > 0]

    rgb = np.stack([canvas_r, canvas_g, canvas_b], axis=-1)
    Image.fromarray(rgb, mode="RGB").save(str(output_path))


# ---------------------------------------------------------------------------
# Height-based render — fallback when no colour data is available
# ---------------------------------------------------------------------------

def _render_height(
    points: np.ndarray,
    output_path: Path,
    width: int,
    height: int,
) -> None:
    xs = np.clip(points[:, 0], 0.0, 1.0)
    ys = np.clip(points[:, 1], 0.0, 1.0)
    zs = np.clip(points[:, 2], 0.0, 1.0)

    px = (xs * (width - 1)).astype(np.int32)
    py = ((1.0 - ys) * (height - 1)).astype(np.int32)

    # Height map: tallest Z wins per pixel
    hmap = np.zeros((height, width), dtype=np.float32)
    np.maximum.at(hmap, (py, px), zs)

    # Splat: fill gaps between sparse sample points
    hmap = np.asarray(cv2.GaussianBlur(hmap, (31, 31), 8), dtype=np.float32)

    # Percentile contrast stretch
    flat = hmap.ravel()
    nonzero = flat[flat > 1e-6]
    if len(nonzero) > 100:
        lo = float(np.percentile(nonzero, 2))
        hi = float(np.percentile(nonzero, 98))
    else:
        lo = 0.0
        hi = float(hmap.max()) if hmap.max() > 1e-9 else 1.0
    hi = max(hi, lo + 1e-9)

    stretched = np.clip((hmap - lo) / (hi - lo), 0.0, 1.0)

    # Gamma 0.4 lifts dark mid-tones aggressively (50 % input → 76 % output)
    brightened = np.power(stretched, 0.4)
    gray = (brightened * 255).astype(np.uint8)

    # Brightness floor: background is dark grey, not pure black
    gray = np.clip(gray.astype(np.int16) + 60, 0, 255).astype(np.uint8)

    r_ch = (gray * 0.20).astype(np.uint8)
    g_ch = gray
    b_ch = (gray * 0.08).astype(np.uint8)
    rgb = np.stack([r_ch, g_ch, b_ch], axis=-1)
    Image.fromarray(rgb, mode="RGB").save(str(output_path))
