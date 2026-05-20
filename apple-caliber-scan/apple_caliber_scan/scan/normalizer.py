"""Normalize point cloud to top-down view.

For Polycam Raw ARKit exports the coordinate system is fixed:
  - Column 1 (Y-world) = vertical / gravity direction (ARKit Y-up, preserved by
    the alignment transform in mesh_info.json which only rotates in the XZ plane).
  - Column 0 (X-world) and Column 2 (Z-world) = horizontal plane.

Output column convention (matches preview.py and classify_orientations()):
  - col 0: X_norm in [0, 1]   → horizontal in the rendered image
  - col 1: Z_norm in [0, 1]   → vertical in the rendered image (1-y mapping)
  - col 2: Y_norm in [0, 1]   → height above ground (used by orientation classifier)
"""

from __future__ import annotations

import numpy as np


def normalize_top_down(
    points: np.ndarray,
    top_percentile: float = 0.20,
) -> np.ndarray:
    """
    Project Polycam Raw point cloud to a top-down view and normalise to [0, 1].

    Accepts (N, 3) or (N, 6) XYZ[+RGB] — colour columns are preserved in output.

    Steps:
      1. Y-sign guard: verify column 1 (Y) increases upward.
         If the top-percentile crop of Y is nearly empty (<0.5% of all points),
         the Y axis is inverted — flip it.
      2. Crop to top `top_percentile` of Y range (apple top surfaces).
      3. Remap: X → out_col_0, Z → out_col_1, Y → out_col_2.
      4. Normalise out_col_0 and out_col_1 (horizontal plane) to [0,1] with a
         single uniform scale (preserves circles as circles).
      5. Centre content in the square canvas.
      6. Normalise out_col_2 (height) to [0, 1] using the full scan Y range so
         that top-layer points land near 1.0.
    """
    if len(points) < 3:
        return points.astype(np.float32)

    has_color = points.shape[1] >= 6
    xyz = points[:, :3].astype(np.float64)
    colors = points[:, 3:6] if has_color else None

    # Column indices (fixed for Polycam Raw ARKit exports)
    VERT = 1   # Y-world = vertical (gravity)
    H0   = 0   # X-world = horizontal
    H1   = 2   # Z-world = horizontal

    # --- 1. Y-sign guard ---
    # ARKit Y increases upward. The top-percentile crop of Y should give a
    # non-trivial fraction of all points (the apple tops). If it does not,
    # the Y axis is inverted — flip it before proceeding.
    y = xyz[:, VERT]
    y_range = float(y.max() - y.min())
    if y_range > 1e-9:
        probe_threshold = float(y.max()) - top_percentile * y_range
        top_count = int((y >= probe_threshold).sum())
        if top_count < max(10, int(0.005 * len(y))):
            xyz[:, VERT] = -y
            y = xyz[:, VERT]
            y_range = float(y.max() - y.min())

    # --- 2. Crop to top layer ---
    if y_range < 1e-9:
        threshold = float(y.min())
    else:
        threshold = float(y.max()) - top_percentile * y_range

    mask = y >= threshold
    if mask.sum() < 10:
        mask = np.ones(len(xyz), dtype=bool)

    top_pts = xyz[mask]

    # --- 3. Remap columns: [X, Z, Y] ---
    # out_col_0 = X (horizontal, appears left-right in image)
    # out_col_1 = Z (horizontal, appears top-bottom in image via 1-y mapping)
    # out_col_2 = Y (height above ground, used by orientation classifier)
    h0 = top_pts[:, H0]
    h1 = top_pts[:, H1]
    ht = top_pts[:, VERT]

    # --- 4. Normalise horizontal axes with a single scale (aspect-ratio safe) ---
    h0_min, h0_max = float(h0.min()), float(h0.max())
    h1_min, h1_max = float(h1.min()), float(h1.max())
    h0_range = max(h0_max - h0_min, 1e-9)
    h1_range = max(h1_max - h1_min, 1e-9)

    max_range = max(h0_range, h1_range)   # uniform scale → circles stay circular

    out_h0 = (h0 - h0_min) / max_range
    out_h1 = (h1 - h1_min) / max_range

    # --- 5. Centre content so neither axis hugs the canvas wall ---
    offset_h0 = (1.0 - h0_range / max_range) / 2.0
    offset_h1 = (1.0 - h1_range / max_range) / 2.0
    out_h0 += offset_h0
    out_h1 += offset_h1

    # --- 6. Normalise height (Y) to [0, 1] using the full scan Y range ---
    # Using the full range (not just the top crop's range) means top-layer points
    # land near 1.0, which the orientation classifier relies on.
    out_ht = (
        np.zeros_like(ht) if y_range < 1e-9
        else (ht - float(y.min())) / y_range
    )

    result = np.column_stack([out_h0, out_h1, out_ht]).astype(np.float32)

    if has_color and colors is not None:
        return np.column_stack([result, colors[mask]])

    return result
