# Apple Caliber Scan — Sprint 4: Preview Recovery

**Working directory**: `/mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan`
**Reference ZIP**: `/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip`
**Reference image**: `/mnt/c/Users/balce/Downloads/apple scanner/WhatsApp Image 2026-05-17 at 23.48.38.jpeg`
**Target**: Scan 4, Batch 2

Read the reference image with vision before starting any work. It shows the desired output
state: ~30 individual red/pink apples clearly distinguishable from directly above, a teal-green
trash bag background between them, and a blue 75 mm calibration ring visible with its
characteristic magnifying-glass shape (circle + short handle).

---

## Root Cause Analysis — Read This Before Touching Any Code

### Root Cause 1 — PCA rotation produces oblique projection

The Sprint 3 normalizer correctly identifies axis 1 (Y-world) as vertical via the IQR
heuristic (Y IQR = 0.106m, the smallest). **But the PCA rotation matrix that follows
produces an oblique output** because the full-orbit Polycam scan of an uneven trash-bag
surface does not have a clean floor plane — PCA on the central-60%-Y-filtered subset
finds eigenvectors tilted relative to the gravity axis.

Verified with the actual scan data (`17_05_2026.zip`, 4,141,512 points):

```
Axis X: IQR=0.2087  range=0.8390
Axis Y: IQR=0.1060  range=0.4897  ← true vertical (ARKit Y-up, preserved by alignment)
Axis Z: IQR=0.1644  range=0.6429  ← horizontal depth
```

The coordinate system is locked by the Polycam alignment transform in `mesh_info.json`:
```
[[-0.9836  0.      -0.1806  -0.3698]
 [ 0.       1.       0.       0.    ]   ← Y column = identity = Y preserved as vertical
 [ 0.1806   0.      -0.9836  -0.4053]
 [ 0.       0.       0.       1.    ]]
```

The alignment transform ONLY rotates in the horizontal plane (X-Z), it leaves Y unchanged.
**Y-up is guaranteed for all Polycam Raw ARKit exports.** No axis detection or PCA needed.

Verification that Y is the correct top-crop axis:
- **Z-crop (top 20% of Z)**: R=125, G=210, B=180 — trash bag side view, ZERO blue ring pixels
- **Y-crop (top 20% of Y)**: R=111, G=155, B=141 — apple tops + bag background, 1,911 blue ring pixels

The Y-crop contains the calibration ring. The Z-crop does not. Y is vertical.

### Root Cause 2 — CLAHE amplifies green trash bag pixels

`_render_colored()` applies `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))` per channel.
The 4M-point Polycam scan has already-excellent colors. CLAHE with clipLimit=2.0 in an 8×8
tile grid (128×128 px tiles for 1024×1024 image) strongly amplifies local green variations
from the scattered trash bag fragments visible at apple height. Result: the entire image gets
a teal-green cast that washes out the red apples and confuses Hough circle detection.

**Fix**: Remove CLAHE from `_render_colored`. The raw Polycam colors are sufficient.

### Root Cause 3 — Hough max radius allows crate-boundary detection

`effective_max = min(max_radius_px, max(min(h, w) // 8, 50)) = min(200, 128) = 128 px`

Expected apple radius at the correct scale: ~75 px (9 cm apple at 1663 px/m after correct
top-down projection). A 128 px max radius allows the detector to find the entire scan boundary
as a "circle" of radius 127 px. This is exactly what is stored in the DB: 120 circles all
with radius ~127 px.

**Fix**: Change `// 8` to `// 11` → `effective_max = min(200, 93) = 93 px`. This is safely
above the expected 75 px apple radius but below the 127 px boundary artifact.

### Root Cause 4 — Blue ring threshold too strict for slightly-dark preview

After removing CLAHE, the preview is slightly darker. The current threshold `B > 80` may
miss faint ring pixels. A parameter ladder for ring Hough detection increases robustness.

---

## Verified scene geometry (for parameter tuning reference)

After correct Y-based top crop:
- X range: 0.616 m → 1024 px → **scale: 1663 px/m**
- Z range: 0.370 m → fills [205 px, 820 px] vertically in the 1024×1024 preview
- Expected apple radius: 9 cm × 1663 px/m / 2 = **~75 px**
- Expected ring radius: 75 mm × 1663 px/m / 2 = **~62 px**
- Expected inter-apple centre distance: ~163 px (30 apples in 0.616 × 0.370 m)

---

## TASK 1 — Fix `normalize_top_down()` in `normalizer.py`

**File**: `apple_caliber_scan/scan/normalizer.py`

Replace the entire file content with the implementation below.

**What changes and why**:
- Remove IQR-based axis detection (Y is always vertical for Polycam Raw ARKit exports)
- Remove PCA rotation (oblique output; the horizontal plane is already X-Z in world coords)
- Keep the Y-top-crop as the layer selection mechanism
- **Remap columns**: input [X, Y, Z, R?, G?, B?] → output [X_norm, Z_norm, Y_norm, R?, G?, B?]
  so that the preview maps X→horizontal and Z→vertical-in-image correctly
- Keep uniform `max_range` scaling (Sprint 2 aspect-ratio fix — circles stay circular)
- Keep centering offsets (content centered in canvas)
- Keep Z-sign guard adapted for the new column layout (safety net in case a future scan
  has inverted Y)

```python
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
      6. Normalise out_col_2 (height) to [0, 1].
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

    # --- 6. Normalise height (Y) to [0, 1] ---
    ht_min, ht_max = float(ht.min()), float(ht.max())
    ht_range = ht_max - ht_min
    out_ht = np.zeros_like(ht) if ht_range < 1e-9 else (ht - ht_min) / ht_range

    result = np.column_stack([out_h0, out_h1, out_ht]).astype(np.float32)

    if has_color and colors is not None:
        return np.column_stack([result, colors[mask]])

    return result
```

**Tests to rewrite** in `tests/test_normalizer.py`:

Replace the three Sprint 3 IQR+PCA tests with the following. All existing non-PCA tests
must still pass.

```python
import numpy as np
import pytest
from apple_caliber_scan.scan.normalizer import normalize_top_down


def test_aspect_ratio_preserved_uniform_scale():
    """
    A circle in the horizontal plane (X-Z) must project to a circle in the image,
    not an ellipse.  The normaliser must use a single scale for both horizontal axes.
    """
    rng = np.random.default_rng(42)
    theta = rng.uniform(0, 2 * np.pi, 500)
    # Circle in X-Z plane at Y=0.30 (apple top layer)
    # Placed in an asymmetric bounding box: X in [0, 1.2], Z in [0, 0.8]
    disc = np.column_stack([
        0.6 + 0.05 * np.cos(theta),   # X: centred at 0.6 in 1.2 m span
        np.full(500, 0.30),            # Y: all at top height
        0.4 + 0.05 * np.sin(theta),   # Z: centred at 0.4 in 0.8 m span
    ]).astype(np.float32)

    # Add floor layer (Y=0.00)
    floor = np.column_stack([
        rng.uniform(0, 1.2, 2000),
        np.zeros(2000),
        rng.uniform(0, 0.8, 2000),
    ]).astype(np.float32)

    pts = np.vstack([disc, floor])
    norm = normalize_top_down(pts, top_percentile=0.05)

    # Output col 0 = X, col 1 = Z → both should reflect the circle
    disc_norm = norm[:500, :2]
    cx = disc_norm[:, 0].mean()
    cy = disc_norm[:, 1].mean()
    dx = disc_norm[:, 0] - cx
    dy = disc_norm[:, 1] - cy
    rx = float(np.sqrt((dx ** 2).mean()))
    ry = float(np.sqrt((dy ** 2).mean()))
    aspect = max(rx, ry) / (min(rx, ry) + 1e-9)
    assert aspect < 1.10, f"Aspect ratio {aspect:.3f} — circle distorted into ellipse"


def test_y_based_top_crop_uses_vertical_axis():
    """
    The normaliser must crop by Y (column 1 = vertical), not by Z (column 2 = horizontal).
    Only the top-Y layer (Y >= threshold) should appear in the output.
    Distinctly coloured top-Y points must be present; bottom points must be absent.
    """
    rng = np.random.default_rng(7)
    # Apple tops at Y=0.30 (red)
    tops = np.zeros((300, 6), dtype=np.float32)
    tops[:, 0] = rng.uniform(0, 1.0, 300)  # X
    tops[:, 1] = 0.30                       # Y = top
    tops[:, 2] = rng.uniform(0, 0.8, 300)  # Z
    tops[:, 3] = 200; tops[:, 4] = 30; tops[:, 5] = 30  # red

    # Floor at Y=0.00 (green trash bag)
    floor = np.zeros((2000, 6), dtype=np.float32)
    floor[:, 0] = rng.uniform(0, 1.0, 2000)
    floor[:, 1] = 0.00
    floor[:, 2] = rng.uniform(0, 0.8, 2000)
    floor[:, 3] = 30; floor[:, 4] = 180; floor[:, 5] = 150  # green

    pts = np.vstack([tops, floor])
    norm = normalize_top_down(pts, top_percentile=0.15)

    # The output should contain predominantly red points (apple tops)
    if norm.shape[1] >= 6:
        r_mean = float(norm[:, 3].mean())
        g_mean = float(norm[:, 4].mean())
        assert r_mean > g_mean, (
            f"Top-crop should be red (apple tops), not green (floor). "
            f"R_mean={r_mean:.0f}, G_mean={g_mean:.0f}"
        )


def test_y_sign_guard_prevents_empty_crop():
    """
    If Y is inverted (decreases upward), the guard must flip it so the top crop
    yields at least 0.5% of all points.
    """
    rng = np.random.default_rng(77)
    # Floor layer — HIGH Y (inverted: floor appears at top)
    floor = np.column_stack([
        rng.uniform(0, 1.2, 2000),
        np.full(2000, 1.0),    # Y=1.0 = inverted floor
        rng.uniform(0, 0.8, 2000),
    ]).astype(np.float32)
    # Apple tops at LOW Y (inverted: tops appear at bottom)
    tops = np.column_stack([
        rng.uniform(0.1, 1.1, 50),
        np.full(50, 0.0),      # Y=0.0 = inverted apple top
        rng.uniform(0.1, 0.7, 50),
    ]).astype(np.float32)
    pts = np.vstack([floor, tops])
    norm = normalize_top_down(pts, top_percentile=0.20)
    assert len(norm) >= 10, f"Guard failed — crop returned only {len(norm)} pts"
    assert float(norm[:, 2].min()) >= 0.0
    assert float(norm[:, 2].max()) <= 1.0


def test_column_remapping_h0_h1_ht():
    """
    Output column 2 (height) must reflect the Y-world axis;
    output columns 0 and 1 must reflect the X-world and Z-world axes.
    """
    # Construct a flat layer at Y=0.5 (tops), Y=0.0 (floor)
    tops = np.zeros((100, 3), dtype=np.float32)
    tops[:, 0] = np.linspace(0, 1, 100)   # X varies
    tops[:, 1] = 0.5                       # Y = top
    tops[:, 2] = 0.5                       # Z fixed

    floor_pts = np.zeros((500, 3), dtype=np.float32)
    floor_pts[:, 1] = 0.0

    pts = np.vstack([tops, floor_pts])
    norm = normalize_top_down(pts, top_percentile=0.10)

    # Output col 2 (height) should be ~1.0 for all points (they're all at top layer)
    assert float(norm[:, 2].min()) >= 0.8, "Top-layer height should be near 1.0"

    # Output col 0 should span a range (reflects X variation)
    assert float(norm[:, 0].max() - norm[:, 0].min()) > 0.5, \
        "Col 0 should reflect X variation"
```

---

## TASK 2 — Remove CLAHE from `_render_colored()` in `preview.py`

**File**: `apple_caliber_scan/scan/preview.py`

The 4M-point Polycam Raw scan has excellent per-vertex colors directly from the iPhone
camera. CLAHE at clipLimit=2.0 aggressively amplifies the green trash bag fragments that
appear in the top layer, casting a teal-green tint over the entire image.

**Remove** the following block (the three CLAHE lines at the end of `_render_colored`):

```python
# REMOVE THIS BLOCK:
    # CLAHE per channel to lift any remaining flat/grey regions.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    canvas_r = clahe.apply(canvas_r)
    canvas_g = clahe.apply(canvas_g)
    canvas_b = clahe.apply(canvas_b)
```

**Add Z-sort before rendering** (highest Z wins per pixel = apple tops overwrite background):

Find this block in `_render_colored`:
```python
    px = (xs * (width - 1)).astype(np.int32)
    py = ((1.0 - ys) * (height - 1)).astype(np.int32)

    # Dark background so apple colours and the blue ring stand out clearly.
    BG = 40
```

Replace with:
```python
    # Sort ascending by col 2 (height) so highest points (apple tops) are drawn
    # last and win per pixel when multiple points map to the same canvas position.
    if points.shape[1] >= 3:
        sort_idx = np.argsort(points[:, 2])
        xs = xs[sort_idx]; ys = ys[sort_idx]
        rs = rs[sort_idx]; gs = gs[sort_idx]; bs = bs[sort_idx]

    px = (xs * (width - 1)).astype(np.int32)
    py = ((1.0 - ys) * (height - 1)).astype(np.int32)

    # Dark background so apple colours and the blue ring stand out clearly.
    BG = 40
```

The final `_render_colored` function should look exactly like the current version but with:
1. The Z-sort block added before the `px`/`py` computation
2. The three CLAHE lines at the end removed

The rest of the function (BG=40, gap-fill blur, `painted` mask) stays unchanged.

**Test** (`tests/test_preview.py` — add):

```python
def test_no_green_cast_from_clahe():
    """
    A scene with red apples and a green background must render with R > G for the
    apple region.  The CLAHE removal means green is not amplified into apple areas.
    """
    import tempfile
    from pathlib import Path
    from PIL import Image
    from apple_caliber_scan.scan.preview import render_preview

    rng = np.random.default_rng(99)
    # Red apple points (top layer, col2 = height ~1.0)
    apples = np.zeros((2000, 6), dtype=np.float32)
    apples[:, 0] = rng.uniform(0.2, 0.8, 2000)  # X
    apples[:, 1] = rng.uniform(0.2, 0.8, 2000)  # Z (horizontal in image)
    apples[:, 2] = 1.0                           # Y_norm = 1.0 (top)
    apples[:, 3] = 200; apples[:, 4] = 40; apples[:, 5] = 40   # red

    # Green background points (lower layer, col2 = 0.0)
    bg = np.zeros((2000, 6), dtype=np.float32)
    bg[:, 0] = rng.uniform(0, 1, 2000)
    bg[:, 1] = rng.uniform(0, 1, 2000)
    bg[:, 2] = 0.0
    bg[:, 3] = 30; bg[:, 4] = 170; bg[:, 5] = 130   # green

    pts = np.vstack([apples, bg])
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        img = np.array(Image.open(out))
        # Centre region should be predominantly red (apple tops)
        centre = img[350:650, 350:650]
        assert float(centre[:, :, 0].mean()) > float(centre[:, :, 2].mean()), \
            "Centre region should be red-dominant (apple tops, not green background)"
    finally:
        out.unlink(missing_ok=True)
```

---

## TASK 3 — Fix Hough max radius in `detect_circles()` in `detector.py`

**File**: `apple_caliber_scan/scan/detector.py`

The `effective_max` formula currently caps at 128 px (= `1024 // 8`). At the correct
top-down scale (1663 px/m), the expected apple radius is ~75 px and the ring radius is
~62 px. A cap of 128 px allows the detector to find the 127 px scan boundary arc as a
circle. Reducing the divisor from `8` to `11` caps at 93 px, which safely captures apples
(75 px) without finding the boundary artifact.

**Find** in `detect_circles()`:
```python
    # Cap at 1/8 of image (floor 50px) — individual apples can't span half the scene
    effective_max = min(max_radius_px, max(min(h, w) // 8, 50))
```

**Replace with**:
```python
    # Cap at 1/11 of image (floor 50px).
    # At typical scan scale (1663 px/m, 1024-px canvas), this gives ~93 px max radius,
    # which covers apple-sized circles (~75 px) without matching the full scan boundary
    # arc (~127 px) that the previous cap of // 8 = 128 px allowed.
    effective_max = min(max_radius_px, max(min(h, w) // 11, 50))
```

This change applies once — there is only one assignment of `effective_max` in the function.

**Test** (`tests/test_detector.py` — add):

```python
def test_max_radius_cap_excludes_boundary_artifacts():
    """
    A preview-sized canvas with a large boundary arc (radius ~127 px) must not be
    detected as a circle after the // 11 cap (max ~93 px).
    """
    import tempfile, cv2
    from pathlib import Path
    from apple_caliber_scan.scan.detector import detect_circles

    W, H = 1024, 1024
    img = np.full((H, W, 3), 40, dtype=np.uint8)

    # Draw a large arc near the boundary (radius 500 px) — the old code found these
    cx, cy, r_big = 512, 512, 500
    for angle in np.linspace(0, 2 * np.pi, 3000):
        x = int(cx + r_big * np.cos(angle))
        y = int(cy + r_big * np.sin(angle))
        if 0 <= x < W and 0 <= y < H:
            cv2.circle(img, (x, y), 3, (200, 200, 200), -1)

    # Draw 5 small apple-sized circles (radius 70 px)
    apple_centres = [(200, 200), (400, 200), (600, 200), (300, 400), (500, 400)]
    for acx, acy in apple_centres:
        cv2.circle(img, (acx, acy), 70, (180, 60, 60), 2)

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        out = Path(f.name)
    cv2.imwrite(str(out), img)
    try:
        circles = detect_circles(out)
        # All detected circles must have radius <= 93 px
        large = [c for c in circles if c.radius_px > 93]
        assert len(large) == 0, (
            f"{len(large)} circles with radius > 93 px detected: "
            f"{[round(c.radius_px) for c in large]}"
        )
    finally:
        out.unlink(missing_ok=True)
```

---

## TASK 4 — Improve `detect_calibration_ring()` in `detector.py`

**File**: `apple_caliber_scan/scan/detector.py`

The ring is physically a magnifying-glass shape: a 75 mm diameter blue circle with a
short handle. The current single-pass Hough detection can fail if the eroded blue mask
is fragmented. The improvements are:

1. **Lower blue threshold** from `B > 80` to `B > 60` to catch the ring when it is
   faintly visible (before CLAHE was boosting it).
2. **Erode before Hough** to remove the thin handle (the handle is narrower than the
   ring arc body; erosion with a 7×7 kernel removes it while preserving the ring arc).
3. **Parameter ladder** — try three decreasing strictness levels before falling back.
4. **Distance histogram fallback** — the fallback now estimates radius via the peak
   of a distance-from-centroid histogram instead of the RMS which the handle biases.

**Replace the entire `detect_calibration_ring()` function** with:

```python
def detect_calibration_ring(
    preview_path: Path,
    min_radius_px: int = 35,
    max_radius_px: int = 110,
) -> Circle | None:
    """
    Detect the blue 75 mm calibration ring (magnifying-glass shape) in the preview.

    Strategy:
      1. Build blue-dominant binary mask: B > 60 AND B > R*1.3 AND B > G*1.3
      2. Morphological close (15×15) to join ring arc with the handle blob.
      3. Keep largest connected component.
      4. Erode the component with a 7×7 kernel to strip the thin handle,
         leaving the thicker ring arc body.
      5. Run HoughCircles with three decreasing strictness levels on the eroded mask.
         Also try on the original (un-eroded) closed mask as a second source.
      6. Distance-histogram fallback: compute the distribution of pixel distances
         from the component centroid; the peak of that histogram = ring radius.
         The handle pixels are far from the centre and do not create a peak at the
         ring radius, so the centroid is estimated robustly via median.

    Returns None if no ring is found — the caller must not abort on None.
    """
    img = cv2.imread(str(preview_path))
    if img is None:
        return None

    b = img[:, :, 0].astype(np.int32)   # OpenCV BGR
    g = img[:, :, 1].astype(np.int32)
    r = img[:, :, 2].astype(np.int32)

    # Step 1: blue-dominant mask (lower threshold than before — ring may be faint)
    blue_mask = (
        (b > 60) &
        (b > (r * 1.30).astype(np.int32)) &
        (b > (g * 1.30).astype(np.int32))
    ).astype(np.uint8) * 255

    # Step 2: morphological close — joins ring arc + handle into one region
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    closed = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel_close)

    # Step 3: keep largest connected component
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    if n_labels < 2:
        logger.info("detect_calibration_ring: no blue region found")
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    best_label = int(np.argmax(areas)) + 1
    roi_mask = (labels == best_label).astype(np.uint8) * 255

    # Step 4: erode to strip the thin handle (handle is narrower than ring arc body)
    kernel_erode = np.ones((7, 7), np.uint8)
    eroded = cv2.erode(roi_mask, kernel_erode, iterations=2)
    if cv2.countNonZero(eroded) < 20:
        eroded = roi_mask   # fallback: erosion removed everything, use original

    # Step 5: try Hough on eroded mask, then on original closed mask
    best_circle: tuple[float, float, float, float] | None = None
    for mask_candidate in [eroded, roi_mask]:
        dilated = cv2.dilate(mask_candidate, np.ones((3, 3), np.uint8), iterations=2)
        for param2 in (0.5, 0.35, 0.2):
            try:
                raw = cv2.HoughCircles(
                    dilated,
                    cv2.HOUGH_GRADIENT_ALT,
                    dp=1,
                    minDist=min_radius_px * 2,
                    param1=50,
                    param2=param2,
                    minRadius=min_radius_px,
                    maxRadius=max_radius_px,
                )
            except cv2.error:
                continue
            if raw is None:
                continue
            circles_arr = np.round(raw[0]).astype(np.float32)
            valid = [
                (float(cx), float(cy), float(rv))
                for cx, cy, rv in circles_arr
                if min_radius_px <= rv <= max_radius_px
            ]
            if not valid:
                continue
            cx, cy, rv = max(valid, key=lambda t: t[2])
            conf = 0.9 - 0.1 * [0.5, 0.35, 0.2].index(param2)
            if best_circle is None or conf > best_circle[3]:
                best_circle = (cx, cy, rv, conf)
            break   # found something at this strictness, stop inner loop
        if best_circle is not None and best_circle[3] >= 0.8:
            break   # high-confidence detection, stop trying masks

    if best_circle is not None:
        cx, cy, rv, conf = best_circle
        logger.info(
            "detect_calibration_ring: Hough cx=%.0f cy=%.0f r=%.0f conf=%.2f",
            cx, cy, rv, conf,
        )
        return Circle(cx=cx, cy=cy, radius_px=rv, confidence=conf)

    # Step 6: distance histogram fallback
    # Median-based centroid is robust to the handle pulling the mean off-centre.
    ys_pts, xs_pts = np.where(roi_mask > 0)
    if len(xs_pts) < 30:
        return None
    cx = float(np.median(xs_pts))
    cy = float(np.median(ys_pts))
    dists = np.sqrt((xs_pts - cx) ** 2 + (ys_pts - cy) ** 2)
    hist, bin_edges = np.histogram(
        dists, bins=60, range=(float(min_radius_px), float(max_radius_px))
    )
    if hist.max() == 0:
        return None
    peak_bin = int(np.argmax(hist))
    r_est = float((bin_edges[peak_bin] + bin_edges[peak_bin + 1]) / 2.0)
    if not (min_radius_px <= r_est <= max_radius_px):
        return None
    logger.info(
        "detect_calibration_ring: histogram fallback cx=%.0f cy=%.0f r=%.0f",
        cx, cy, r_est,
    )
    return Circle(cx=cx, cy=cy, radius_px=r_est, confidence=0.5)
```

**Update the call site** in `ingest.py`: `detect_calibration_ring(preview_path)` — no
signature change needed (default params updated above cover the expected ring size).

**Test** (`tests/test_detector.py` — add alongside the existing ring test):

```python
def test_ring_detection_with_handle():
    """
    A magnifying-glass shaped blue region (circle + short handle) must produce
    a detection centred on the circular part, not pulled toward the handle.
    """
    import tempfile
    from PIL import Image
    from apple_caliber_scan.scan.detector import detect_calibration_ring

    W, H = 1024, 1024
    img = np.full((H, W, 3), 40, dtype=np.uint8)   # dark background, BGR

    TRUE_CX, TRUE_CY, TRUE_R = 400, 400, 62

    # Draw the ring arc (thick blue circle)
    for angle in np.linspace(0, 2 * np.pi, 1000):
        for dr in range(-6, 7):
            x = int(TRUE_CX + (TRUE_R + dr) * np.cos(angle))
            y = int(TRUE_CY + (TRUE_R + dr) * np.sin(angle))
            if 0 <= x < W and 0 <= y < H:
                img[y, x] = [220, 30, 10]   # BGR = strong blue

    # Draw the handle (thin blue rectangle extending downward from the ring)
    for dy in range(1, 50):
        for dx in range(-8, 9):
            hx, hy = TRUE_CX + dx, TRUE_CY + TRUE_R + dy
            if 0 <= hx < W and 0 <= hy < H:
                img[hy, hx] = [200, 25, 10]   # BGR = strong blue

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        path = Path(f.name)
    import cv2 as _cv2
    _cv2.imwrite(str(path), img)
    try:
        result = detect_calibration_ring(path, min_radius_px=30, max_radius_px=120)
        assert result is not None, "Ring with handle not detected"
        assert abs(result.cx - TRUE_CX) < TRUE_R * 0.15, \
            f"cx off by {abs(result.cx - TRUE_CX):.1f} px (expected {TRUE_CX})"
        assert abs(result.cy - TRUE_CY) < TRUE_R * 0.15, \
            f"cy off by {abs(result.cy - TRUE_CY):.1f} px (expected {TRUE_CY})"
        assert abs(result.radius_px - TRUE_R) < TRUE_R * 0.25, \
            f"radius off by {abs(result.radius_px - TRUE_R):.1f} px (expected {TRUE_R})"
    finally:
        path.unlink(missing_ok=True)
```

---

## TASK 5 — Update `classify_orientations()` to match new column layout

**File**: `apple_caliber_scan/scan/detector.py`

The normalizer now outputs `[X_norm, Z_norm, Y_norm, R?, G?, B?]`.
`classify_orientations()` converts circle pixel coords to normalised [0,1] and then reads
`points[:, 2]` as height. The preview still maps col 0 → px and col 1 → py (via 1-y), so
the pixel-to-normalised conversion is unchanged. `zs = points[:, 2]` is still height
(now Y_norm), which is what the dome-ratio computation needs. **No change required.**

Verify by checking the existing `test_upright_apple_classified_correctly` and
`test_sideways_apple_classified_correctly` tests still pass after the normalizer rewrite
(they should, as the output column convention for col 2 = height is preserved).

---

## TASK 6 — Run the full test suite

```bash
cd /mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan
make test
```

**Expected**: ≥ 89 passed (85 baseline + 4 new: 2 detector, 1 preview, 1 normalizer
[test_y_based_top_crop_uses_vertical_axis]), 0 failed.

If any existing test fails, diagnose and fix it before proceeding to Task 7.

```bash
make lint       # zero ruff errors
make typecheck  # no new mypy errors
```

---

## TASK 7 — Re-ingest Scan 4 / Batch 2

### Step 7A — Reset scan state

```python
# Run from the apple-caliber-scan directory:
from apple_caliber_scan.database.connection import db_conn

with db_conn() as conn:
    deleted = conn.execute(
        "DELETE FROM scan_circles WHERE scan_id = 4"
    ).rowcount
    conn.execute(
        "UPDATE scans SET "
        "status='uploaded', "
        "scale_factor_mm_per_px=NULL, "
        "calibration_confidence='uncalibrated', "
        "auto_ring_cx_px=NULL, "
        "auto_ring_cy_px=NULL, "
        "auto_ring_radius_px=NULL, "
        "auto_ring_confidence=NULL "
        "WHERE id=4"
    )
    print(f"Cleared {deleted} stale circles; reset scan 4 to 'uploaded'")
```

### Step 7B — Re-ingest from local ZIP

```python
import shutil, tempfile
from pathlib import Path
from apple_caliber_scan.services.ingest import ingest_from_local_file

ZIP_SRC = Path("/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip")
assert ZIP_SRC.exists(), f"ZIP not found: {ZIP_SRC}"

tmp = Path(tempfile.mktemp(suffix=".zip"))
shutil.copy(ZIP_SRC, tmp)

preview_path, circles, point_count, auto_ring = ingest_from_local_file(
    tmp, scan_id=4, batch_id=2, delete_after=True
)

print(f"Points ingested : {point_count:,}")
print(f"Circles detected: {len(circles)}")
print(f"Circle radii    : {sorted(set(round(c.radius_px) for c in circles))}")
print(f"Auto ring       : {auto_ring}")
```

### Step 7C — Automated verification assertions

```python
from PIL import Image
import numpy as np

img = np.array(Image.open(preview_path))
print(f"Preview shape   : {img.shape}")

r_mean = float(img[:, :, 0].mean())
g_mean = float(img[:, :, 1].mean())
b_mean = float(img[:, :, 2].mean())
print(f"R/G/B means     : {r_mean:.0f}/{g_mean:.0f}/{b_mean:.0f}")

# 1. Circle count: must be 15–45 (not 120 giant overlapping circles)
assert 15 <= len(circles) <= 45, (
    f"Expected 15–45 circles, got {len(circles)}. "
    "If count is still 120, max-radius cap (Task 3) may not have been saved."
)

# 2. Circle sizes: no circle should have radius > 95 px
large_circles = [c for c in circles if c.radius_px > 95]
assert len(large_circles) == 0, (
    f"{len(large_circles)} circles have radius > 95 px: "
    f"{[round(c.radius_px) for c in large_circles]}"
)

# 3. Blue ring visible in the preview PNG
blue_dom = (
    (img[:, :, 2].astype(int) > 60) &
    (img[:, :, 2].astype(int) > img[:, :, 0].astype(int) * 1.3) &
    (img[:, :, 2].astype(int) > img[:, :, 1].astype(int) * 1.3)
)
assert blue_dom.sum() > 300, (
    f"Blue ring should be visible (> 300 blue-dominant pixels), "
    f"got {blue_dom.sum()}. Check CLAHE removal (Task 2) and ring detection (Task 4)."
)

# 4. Auto-ring detected with reasonable confidence
if auto_ring is not None:
    assert auto_ring.confidence >= 0.4, (
        f"Auto-ring confidence too low: {auto_ring.confidence:.2f}. "
        "Check detect_calibration_ring improvements (Task 4)."
    )
    print(f"Auto ring OK    : cx={auto_ring.cx:.0f} cy={auto_ring.cy:.0f} "
          f"r={auto_ring.radius_px:.0f} conf={auto_ring.confidence:.2f}")
else:
    print("Auto ring       : not detected (operator must set manually)")

# 5. Preview is not predominantly green (no CLAHE green-cast)
# Note: the scene has a green trash bag background, so G > R is possible globally.
# The key check is that we don't have an extreme green cast (G > R by > 60 units).
assert g_mean < r_mean + 60, (
    f"Preview has excessive green cast: G_mean={g_mean:.0f} >> R_mean={r_mean:.0f}. "
    "CLAHE (Task 2) may not have been removed."
)

print()
print("✓ All automated assertions passed.")
print("Next: open http://localhost:8000, navigate to Batch 2 → Scan 4 and visually verify:")
print("  - Individual apples visible and countable (~30)")
print("  - Teal-green trash bag background visible between apple clusters")
print("  - Blue ring visible with correct circular shape")
print("  - Circle overlays positioned on individual apples (not as huge rings)")
```

### Step 7D — Visual verification (required)

Start the web server and open the annotation page:

```bash
cd /mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan
make run-web
# Navigate to http://localhost:8000 → log in → Batch 2 → Scan 4 → Adnotacja
```

The preview in the annotation page must match the WhatsApp reference image:
1. **~30 individual apple circles** visible from directly above, clearly distinguishable
2. **Teal-green trash bag background** visible in gaps between the apple clusters
3. **Blue calibration ring** visible somewhere in the scan (faint is OK)
4. **Circle overlays** (~15–45 of them, all approximately apple-sized, not huge)
5. **No left/right cuts** — content fills the canvas without dramatic dark borders
6. **No teal-green cast** — the image should look similar to the WhatsApp reference

If the preview still looks oblique or has a strong green cast after re-ingest, run the
diagnostic in the "Troubleshooting" section below before making any further changes.

---

## DEFINITION OF DONE

- [ ] `make test` shows **≥ 89 passed**, 0 failed
- [ ] `make lint` passes (zero ruff errors)
- [ ] Circle count after re-ingest: **15–45**, all with radius **< 95 px**
- [ ] Blue ring visible in preview: **> 300 blue-dominant pixels** in the PNG
- [ ] Preview G_mean **< R_mean + 60** (no excessive green cast)
- [ ] Auto-ring detected with **confidence ≥ 0.40** (if detectable; None is acceptable)
- [ ] Visual inspection: ~30 individual apples countable in the web UI annotation page

---

## KNOWN CONSTRAINTS — do not violate

1. **No colour-based green masking** anywhere in the pipeline. Future scans include green
   apples. Any filter that suppresses green-dominant pixels must not be introduced.

2. **`from __future__ import annotations`** must NOT be present in `scans.py` — it breaks
   FastAPI form/file parameter injection through the `@require_login` decorator.

3. **Do not delete Batch 2 or Scan 4** from the DB at any point during this sprint.

4. **The 75 mm ring diameter is the calibration reference** — the ring detection must
   return the outer circle boundary, not any inner edge.

5. **No PCA rotation** — the fix intentionally removes it. If a future scan type requires
   PCA (e.g., an OBJ/PLY mesh export with a different coordinate system), add a
   `format`-based branch in `normalize_top_down`, not a general-purpose PCA path.

---

## TROUBLESHOOTING

### Preview still shows oblique view after re-ingest

Run this diagnostic to confirm the normalizer is using Y as vertical:

```python
from pathlib import Path
from apple_caliber_scan.scan.loader import load_polycam_raw_zip
from apple_caliber_scan.scan.normalizer import normalize_top_down
import numpy as np

pts = load_polycam_raw_zip(Path("/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip"))
norm = normalize_top_down(pts, top_percentile=0.20)

print(f"Normalized {len(norm)} points")
print(f"RGB means: R={float(norm[:,3].mean()):.0f} G={float(norm[:,4].mean()):.0f} B={float(norm[:,5].mean()):.0f}")
blue_dom = (norm[:,5] > 60) & (norm[:,5] > norm[:,3]*1.3) & (norm[:,5] > norm[:,4]*1.3)
print(f"Blue-dominant points: {blue_dom.sum():,}")
```

Expected output:
- Blue-dominant points > 1500 (the ring should be in the top layer)
- If blue_dom = 0, the Y-sign guard may have triggered incorrectly. Check by printing
  `y = pts[:, 1]; print(y.max(), y.min(), (y >= y.max() - 0.2*(y.max()-y.min())).sum())`.

### Circle count still too high (> 50)

Check `effective_max` was changed. The fix is a one-line change in `detector.py`.
Verify: `grep "effective_max" apple_caliber_scan/scan/detector.py` — must show `// 11`.

### Ring not detected (auto_ring is None)

After removing CLAHE from preview, the ring may be slightly darker. Try manually calling:
```python
from apple_caliber_scan.scan.detector import detect_calibration_ring
from pathlib import Path
result = detect_calibration_ring(
    Path("data/previews/scan_4_batch_2.png"),
    min_radius_px=30, max_radius_px=120
)
print(result)
```

If `result is None`, lower the blue threshold in `detect_calibration_ring` from `B > 60`
to `B > 45` and re-test. The ring colour in the preview is the definitive guide for tuning.
