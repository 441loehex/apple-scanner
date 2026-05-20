# Apple Caliber Scan — Sprint 3: Preview Recovery + Hough NMS Fix

You are working on the `apple-caliber-scan` project.

**Working directory**: `/mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan`  
**Reference ZIP**: `/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip` (24.3 MB, confirmed present)  
**Target**: Scan 4, Batch 2 — `data/previews/scan_4_batch_2.png`

---

## What the correct scan should look like

Reference image: `/mnt/c/Users/balce/Downloads/apple scanner/WhatsApp Image 2026-05-17 at 23.48.38.jpeg`

Read this image with vision before starting. It shows the desired output state:
- ~25–30 individual red/pink apples visible as distinct circles viewed **directly from above** (top-down, not oblique)
- A **teal-green background** from torn green trash bag sheets placed under the apples as a surface (NOT bare floor)
- A physical blue 75 mm calibration ring visible in the lower-left area of the scan
- Each apple is clearly separable — no spatial distortion or 3D perspective warping
- The UI is Freshora's scan_review.html page ("Adnotacja skanu #4 — Partia #2")

---

## Current broken state — confirmed

`data/previews/scan_4_batch_2.png` currently shows the crate from an **oblique 3D perspective** — crate edges visible as a trapezoid, apples wrapped around a 3D surface instead of laid flat, teal-cyan CLAHE tint over everything. This is **not** a top-down view.

**DB state confirmed**:
- Batch 2, Scan 4 exists: `status='previewed'`, `format='ply'`, `point_count=4141512`
- 10 circles stored — confirmed concentric duplicates at (508, 410) with radii 60, 48, 30 px; and at (668, 402) with radii 47, 37 px
- Auto-ring: `cx=353, cy=407, r=52, confidence=0.5`
- All circles have `orientation='angled'` — Sprint 2 orientation code is active

---

## Root cause analysis — understand before touching code

### Root Cause 1: PCA axis identification fails on full 3D Polycam scans

`normalize_top_down()` uses PCA to identify the floor normal, then rotates that direction to become Z. This works for **planar scans** but fails for full 360° Polycam scans where the operator scanned the crate from multiple angles, including the sides.

With side-scan data included:
- The crate walls contribute large variance in the vertical direction
- The floor normal is no longer clearly the minimum-variance axis
- PCA may choose a **diagonal axis through the crate walls** as the "minimum variance" direction
- The resulting "top-down view" is actually an oblique view from that diagonal

This is the root cause of the scrambled preview. The `np.linalg.eigh` eigenvector sign is also arbitrary — if the chosen Z-axis eigenvector points down instead of up, the `top_percentile` crop grabs the floor rather than the apple tops.

**The fix**: Two-part improvement to `normalize_top_down()`:

**Part A — Robust axis selection**: Before PCA, identify the vertical axis by finding the axis with the smallest IQR (interquartile range). IQR is robust to wall outliers. The floor is a large flat surface → the height axis has the most uniform (smallest IQR) distribution. Once the approximate vertical axis is identified, run PCA on only the **central 60% of points** along that axis (removes crate walls and extreme outliers that confuse PCA).

**Part B — Z-sign guard**: After PCA rotation, verify the Z direction makes sense. Apple tops should form a non-trivial fraction of the total points. If the top-percentile crop yields fewer than 0.5% of all input points, the PCA returned a Z-down eigenvector → flip Z.

### Root Cause 2: Hough finds concentric ring-edge artifacts instead of apple centres

`minDist = effective_min * 2 = 40px` — too small. With apple radius ~45–65 px, two detections at the same apple's inner and outer edges (separated by 0–30 px) are both accepted.

No post-processing removes concentric duplicates. Result: 10 circles with groups like (508,410)@r=60, (508,410)@r=48, (508,410)@r=30 — all the same apple.

### Root Cause 3: Green trash bags — no colour masking permitted

The green bags form a "mountain range" of folded plastic — parts reach near apple height. They appear in the **correct preview** as the teal-green background (visible in the WhatsApp reference image — this is EXPECTED and CORRECT).

**Critical constraint**: Future scans will include **green apples**. Any colour-based green masking would suppress green apples. Do NOT implement colour-based masking. The bags are handled by better Hough parameters and NMS, not by masking.

---

## TASK 1 — Fix `normalize_top_down()` for full 3D Polycam scans

**File**: `apple_caliber_scan/scan/normalizer.py`

Replace the entire function with the implementation below. Read the current file first. The key changes:

1. **Robust axis selection via IQR** — identify the up axis without relying on PCA alone
2. **PCA on filtered central slice** — exclude wall outliers before PCA
3. **Z-sign guard** — flip Z if top crop is nearly empty
4. **Preserve all Sprint 2 fixes** — aspect ratio preservation and centering offsets

```python
"""Normalize point cloud to top-down view — robust to full 3D Polycam scans."""

from __future__ import annotations

import numpy as np


def normalize_top_down(
    points: np.ndarray,
    top_percentile: float = 0.20,
) -> np.ndarray:
    """
    Project point cloud to a top-down view and normalise to [0, 1].

    Accepts (N, 3) XYZ or (N, 6) XYZ+RGB — colour columns are preserved.

    Steps:
      1. Identify the vertical axis via IQR (most uniform spread = floor axis).
      2. Filter to central 60% along that axis before PCA (removes wall outliers).
      3. PCA on filtered subset → precise floor-normal rotation applied to ALL points.
      4. Z-sign guard: if the top-percentile crop is nearly empty, flip Z.
      5. Crop to top `top_percentile` of Z range (visible apple top layer).
      6. Normalise XY to [0, 1] with uniform scale (preserves circles as circles).
      7. Centre content; normalise Z to [0, 1].
    """
    if len(points) < 3:
        return points.astype(np.float32)

    has_color = points.shape[1] >= 6
    xyz = points[:, :3].astype(np.float64)
    colors = points[:, 3:6] if has_color else None

    # --- 1. Identify approximate vertical axis via IQR ---
    # The floor (and apple tops) form a flat layer → small height IQR.
    # Wall outliers inflate std but not IQR (robust to outliers).
    q75 = np.percentile(xyz, 75, axis=0)
    q25 = np.percentile(xyz, 25, axis=0)
    axis_iqr = q75 - q25
    axis_iqr[axis_iqr < 1e-9] = 1e-9  # avoid zero division
    vert_guess = int(np.argmin(axis_iqr))

    # --- 2. Filter to central 60% along guessed vertical axis ---
    # This removes crate walls and scan-periphery points that confuse PCA.
    v = xyz[:, vert_guess]
    v_lo, v_hi = np.percentile(v, [20, 80])
    central_mask = (v >= v_lo) & (v <= v_hi)
    xyz_for_pca = xyz[central_mask] if central_mask.sum() >= 50 else xyz

    # --- 3. PCA rotation on filtered subset ---
    centroid = xyz_for_pca.mean(axis=0)
    centered_for_pca = xyz_for_pca - centroid
    cov = np.cov(centered_for_pca.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)  # ascending: smallest variance → index 0
    # Reorder: largest → X, middle → Y, smallest → Z (floor normal)
    rotation = eigenvectors[:, [order[2], order[1], order[0]]]

    # Apply rotation to ALL points
    centered_all = xyz - centroid
    rotated = centered_all @ rotation  # (N, 3)

    # --- 4. Z-sign guard ---
    # np.linalg.eigh eigenvectors have arbitrary sign. If Z points down,
    # the top-percentile crop grabs the floor instead of apple tops.
    # Detect: if the "top" crop is nearly empty (<0.5% of all points), flip Z.
    z = rotated[:, 2]
    z_range_probe = z.max() - z.min()
    if z_range_probe > 1e-9:
        probe_threshold = z.max() - top_percentile * z_range_probe
        top_count_probe = int((z >= probe_threshold).sum())
        if top_count_probe < max(10, int(0.005 * len(z))):
            rotated[:, 2] = -z

    # --- 5. Crop to top layer ---
    z = rotated[:, 2]
    z_min, z_max = z.min(), z.max()
    z_range = z_max - z_min
    if z_range < 1e-9:
        threshold = z_min
    else:
        threshold = z_max - top_percentile * z_range

    mask = z >= threshold
    if mask.sum() < 10:
        mask = np.ones(len(rotated), dtype=bool)  # fallback: keep all

    top_pts = rotated[mask]

    # --- 6. Normalise XY to [0, 1] preserving aspect ratio ---
    xy_min = top_pts[:, :2].min(axis=0)
    xy_max = top_pts[:, :2].max(axis=0)
    xy_range = xy_max - xy_min
    xy_range[xy_range < 1e-9] = 1.0

    max_range = xy_range.max()  # single scale → circles stay circular

    result = top_pts.copy()
    result[:, :2] = (top_pts[:, :2] - xy_min) / max_range

    # Centre content so neither axis hugs the canvas edge
    offsets = (1.0 - xy_range / max_range) / 2.0
    result[:, :2] += offsets

    # --- 7. Normalise Z to [0, 1] ---
    z_min2, z_max2 = top_pts[:, 2].min(), top_pts[:, 2].max()
    z_r = z_max2 - z_min2
    result[:, 2] = 0.0 if z_r < 1e-9 else (top_pts[:, 2] - z_min2) / z_r

    xyz_result = result.astype(np.float32)

    if has_color and colors is not None:
        return np.column_stack([xyz_result, colors[mask]])

    return xyz_result
```

**Tests to add** in `tests/test_normalizer.py`:

```python
def test_aspect_ratio_preserved():
    """A circle in 3D space must project to a circle in 2D, not an ellipse."""
    rng = np.random.default_rng(42)
    theta = rng.uniform(0, 2 * np.pi, 500)
    disc = np.column_stack([
        0.6 + 0.05 * np.cos(theta),
        0.4 + 0.05 * np.sin(theta),
        np.ones(500) * 0.02,
    ]).astype(np.float32)
    floor = rng.uniform(size=(2000, 3)).astype(np.float32)
    floor[:, 2] = 0.0
    floor[:, 0] *= 1.2
    floor[:, 1] *= 0.8
    pts = np.vstack([disc, floor])
    norm = normalize_top_down(pts, top_percentile=0.05)
    disc_norm = norm[:500, :2]
    cx, cy = disc_norm[:, 0].mean(), disc_norm[:, 1].mean()
    dx, dy = disc_norm[:, 0] - cx, disc_norm[:, 1] - cy
    rx = float(np.sqrt((dx ** 2).mean()))
    ry = float(np.sqrt((dy ** 2).mean()))
    aspect = max(rx, ry) / (min(rx, ry) + 1e-9)
    assert aspect < 1.10, f"Aspect ratio {aspect:.3f} — circle distorted"


def test_z_sign_guard_prevents_empty_crop():
    """The Z-sign guard must keep the result non-empty even if PCA flips Z down."""
    rng = np.random.default_rng(77)
    # Floor layer (2000 pts, should end up at z_min after correct orientation)
    floor = np.column_stack([
        rng.uniform(0, 1.2, 2000),
        rng.uniform(0, 0.8, 2000),
        np.zeros(2000),
    ]).astype(np.float32)
    # Apple tops (sparse, 30 pts — guard must not lose these)
    tops = np.column_stack([
        rng.uniform(0.1, 1.1, 30),
        rng.uniform(0.1, 0.7, 30),
        np.full(30, 0.30),
    ]).astype(np.float32)
    pts = np.vstack([floor, tops])
    norm = normalize_top_down(pts, top_percentile=0.20)
    assert len(norm) >= 10, f"Expected >= 10 points, got {len(norm)}"
    assert float(norm[:, 2].min()) >= 0.0
    assert float(norm[:, 2].max()) <= 1.0


def test_wall_outliers_do_not_break_rotation():
    """Crate wall points extending vertically must not corrupt the PCA rotation."""
    rng = np.random.default_rng(55)
    # Apple tops at Z=0.3 (the highest layer)
    apple_tops = np.column_stack([
        rng.uniform(0.1, 1.1, 200),
        rng.uniform(0.1, 0.7, 200),
        np.full(200, 0.30),
    ]).astype(np.float32)
    # Floor at Z=0
    floor = np.column_stack([
        rng.uniform(0, 1.2, 1000),
        rng.uniform(0, 0.8, 1000),
        np.zeros(1000),
    ]).astype(np.float32)
    # Crate walls: extend from Z=0 to Z=0.5 at X=0 and X=1.2
    walls = np.column_stack([
        np.concatenate([np.zeros(500), np.full(500, 1.2)]),
        rng.uniform(0, 0.8, 1000),
        rng.uniform(0, 0.5, 1000),
    ]).astype(np.float32)
    pts = np.vstack([apple_tops, floor, walls])
    norm = normalize_top_down(pts, top_percentile=0.20)
    # Result must be non-degenerate and in [0,1]
    assert len(norm) >= 50, f"Too few points: {len(norm)}"
    assert float(norm[:, 0].max()) <= 1.0
    assert float(norm[:, 1].max()) <= 1.0
```

---

## TASK 2 — Add Non-Maximum Suppression to Hough detection

**File**: `apple_caliber_scan/scan/detector.py`

### Step 2A — Increase `minDist`

In `detect_circles()`, change the `minDist` argument in all `cv2.HoughCircles()` calls:

**Find**: `minDist=effective_min * 2,`  
**Replace with**: `minDist=max(effective_min * 3, 50),`

This changes minimum separation from ~40 px to ~60–90 px (depending on scan density), preventing the same apple's inner and outer edges from being counted as two separate apples. Do this for **both** occurrences in `detect_circles()` — the main ladder loop and the best-effort fallback loop.

### Step 2B — Add `_deduplicate_circles()` function

Add this function to `detector.py` after `_fit_ellipses()`:

```python
def _deduplicate_circles(
    circles: list[Circle],
    overlap_ratio: float = 0.6,
) -> list[Circle]:
    """
    Remove concentric and heavily-overlapping circle detections.

    Two circles are "the same detection" when their centres are within
    overlap_ratio × min(r1, r2) pixels of each other.

    Selection rule: keep the LARGER circle. Rationale for caliber measurement:
    the outer boundary of an apple equals its equatorial diameter.
    Inner-edge Hough artifacts (r=30, r=48 vs. correct r=60) cause
    underestimation of apple size. The largest concentric detection is the
    most conservative (never underestimates) and most accurate estimate.

    overlap_ratio=0.6 means: suppress if centres closer than 60% of the
    smaller radius. Same-spot concentric circles → suppressed (dist=0).
    Adjacent apples touching at their edges → kept (dist ≈ r1+r2 >> 0.6×r_min).
    """
    if not circles:
        return circles

    sorted_circles = sorted(circles, key=lambda c: c.radius_px, reverse=True)
    kept: list[Circle] = []

    for candidate in sorted_circles:
        suppressed = False
        for existing in kept:
            dist = float(np.sqrt(
                (candidate.cx - existing.cx) ** 2 +
                (candidate.cy - existing.cy) ** 2
            ))
            smaller_r = min(candidate.radius_px, existing.radius_px)
            if dist < overlap_ratio * smaller_r:
                suppressed = True
                break
        if not suppressed:
            kept.append(candidate)

    return kept
```

### Step 2C — Call deduplication in `detect_circles()`

**Find** (near the end of `detect_circles()`):
```python
    circles = circles[:max_circles]
    circles = _fit_ellipses(circles, gray)
    logger.info(
```

**Replace with**:
```python
    circles = circles[:max_circles]
    circles = _fit_ellipses(circles, gray)
    before_nms = len(circles)
    circles = _deduplicate_circles(circles)
    logger.info(
        "After NMS: %d → %d circles (removed %d concentric duplicates)",
        before_nms, len(circles), before_nms - len(circles),
    )
    logger.info(
```

**Tests to add** in `tests/test_detector.py`:

```python
def test_deduplicate_removes_concentric_circles():
    """Three concentric circles at the same centre must collapse to one."""
    from apple_caliber_scan.scan.detector import _deduplicate_circles, Circle

    # Exactly the DB-confirmed pattern: (508, 410) with r=60, 48, 30
    circles = [
        Circle(cx=508.0, cy=410.0, radius_px=60.0),
        Circle(cx=508.0, cy=410.0, radius_px=48.0),
        Circle(cx=508.0, cy=410.0, radius_px=30.0),
    ]
    result = _deduplicate_circles(circles)
    assert len(result) == 1, f"Expected 1 circle, got {len(result)}"
    assert result[0].radius_px == 60.0, "Should keep the largest radius"


def test_deduplicate_keeps_distinct_apples():
    """Circles far apart (different apples) must all be kept."""
    from apple_caliber_scan.scan.detector import _deduplicate_circles, Circle

    # Two apples ~200 px apart, radius ~50 px each
    circles = [
        Circle(cx=200.0, cy=200.0, radius_px=50.0),
        Circle(cx=400.0, cy=200.0, radius_px=50.0),
        Circle(cx=600.0, cy=200.0, radius_px=50.0),
    ]
    result = _deduplicate_circles(circles)
    assert len(result) == 3, f"Expected 3 distinct circles, got {len(result)}"


def test_deduplicate_keeps_larger_when_partially_overlapping():
    """Near-duplicate pair: keep larger, remove smaller."""
    from apple_caliber_scan.scan.detector import _deduplicate_circles, Circle

    # Two circles, centres 15 px apart, radii 60 and 40 px
    # 15 < 0.6 * 40 = 24 → they overlap → remove smaller
    circles = [
        Circle(cx=100.0, cy=100.0, radius_px=60.0),
        Circle(cx=115.0, cy=100.0, radius_px=40.0),
    ]
    result = _deduplicate_circles(circles)
    assert len(result) == 1
    assert result[0].radius_px == 60.0


def test_deduplicate_db_confirmed_pattern():
    """Reproduce the exact 10-circle DB state and verify reduction."""
    from apple_caliber_scan.scan.detector import _deduplicate_circles, Circle

    # Exact circles from scan 4 / batch 2 DB:
    db_circles = [
        Circle(cx=508.0, cy=410.0, radius_px=60.0),  # group A
        Circle(cx=440.0, cy=456.0, radius_px=44.0),
        Circle(cx=508.0, cy=410.0, radius_px=48.0),  # group A duplicate
        Circle(cx=508.0, cy=410.0, radius_px=30.0),  # group A duplicate
        Circle(cx=753.0, cy=511.0, radius_px=37.0),
        Circle(cx=668.0, cy=402.0, radius_px=47.0),  # group B
        Circle(cx=787.0, cy=616.0, radius_px=26.0),
        Circle(cx=668.0, cy=402.0, radius_px=37.0),  # group B duplicate
        Circle(cx=205.0, cy=636.0, radius_px=25.0),
        Circle(cx=511.0, cy=645.0, radius_px=27.0),
    ]
    result = _deduplicate_circles(db_circles)
    # Groups A and B each collapse to 1; the other 6 are kept
    assert len(result) == 8, f"Expected 8 circles after NMS, got {len(result)}"
    # Verify group A kept largest
    group_a = [c for c in result if abs(c.cx - 508) < 5 and abs(c.cy - 410) < 5]
    assert len(group_a) == 1 and group_a[0].radius_px == 60.0
    # Verify group B kept largest
    group_b = [c for c in result if abs(c.cx - 668) < 5 and abs(c.cy - 402) < 5]
    assert len(group_b) == 1 and group_b[0].radius_px == 47.0
```

---

## TASK 3 — Re-ingest scan 4 / batch 2 with all fixes applied

After Tasks 1 and 2 are implemented and tests pass, re-ingest the reference scan.

**Step 3A — Delete the stale circles and reset scan status**

```python
# Run this Python snippet from the apple-caliber-scan directory:
from apple_caliber_scan.database.connection import db_conn

with db_conn() as conn:
    deleted = conn.execute(
        "DELETE FROM scan_circles WHERE scan_id = 4"
    ).rowcount
    conn.execute(
        "UPDATE scans SET status='uploaded', scale_factor_mm_per_px=NULL, "
        "calibration_confidence='uncalibrated', auto_ring_cx_px=NULL, "
        "auto_ring_cy_px=NULL, auto_ring_radius_px=NULL, auto_ring_confidence=NULL "
        "WHERE id=4"
    )
    print(f"Cleared {deleted} stale circles; reset scan 4 to 'uploaded'")
```

**Step 3B — Re-ingest from local ZIP**

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
print(f"Auto ring       : {auto_ring}")
print(f"Orientations    : {[(c.orientation, round(c.caliber_diameter_px,1)) for c in circles[:8]]}")

# Verify the preview is now a top-down view (basic sanity checks)
from PIL import Image
import numpy as np

img = np.array(Image.open(preview_path))
print(f"Preview shape: {img.shape}")

# Colour channel sanity: red apples should dominate over blue
r_mean = float(img[:, :, 0].mean())
g_mean = float(img[:, :, 1].mean())
b_mean = float(img[:, :, 2].mean())
print(f"R/G/B channel means: {r_mean:.0f}/{g_mean:.0f}/{b_mean:.0f}")
# R should be > B for a scan of red apples (even with green background)
assert r_mean > b_mean, "Red channel should dominate over blue for red apples"

# Blue ring visibility check
blue_dom = (
    (img[:, :, 2].astype(int) > 80) &
    (img[:, :, 2].astype(int) > img[:, :, 0].astype(int) * 1.35) &
    (img[:, :, 2].astype(int) > img[:, :, 1].astype(int) * 1.35)
)
print(f"Blue-dominant pixels: {blue_dom.sum()} (ring visible if > 300)")
assert blue_dom.sum() > 300, "Blue calibration ring should be visible in preview"

print("✓ Preview sanity checks passed")
```

**Step 3C — Persist circles to DB**

The `ingest_from_local_file()` function should handle this automatically (via `_save_scan_results()`). If it does not (check the return value), manually save:

```python
from apple_caliber_scan.database.connection import db_conn
from apple_caliber_scan.web.routes.scans import _save_scan_results

with db_conn() as conn:
    _save_scan_results(conn, scan_id=4, circles=circles, auto_ring=auto_ring)
    print(f"Saved {len(circles)} circles to DB")
```

**Step 3D — Verify the review page visually**

Start the web server and navigate to Batch 2 → Scan 4:

```bash
cd /mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan
make run-web
# Navigate to http://localhost:8000, log in, open Batch 2, open Scan 4
```

The annotation page should show:
1. A **top-down view** of the crate — apples visible as distinct circular shapes from directly above, NOT an oblique 3D view
2. The **teal-green background** from the trash bag sheets is visible around the apple clusters (this is correct and expected)
3. **Blue circle overlays** appear on detected apples (after NMS, should be more than 2)
4. The **"Highlight ring (blue)" button** shows the ring clearly when clicked
5. The **auto-ring confidence banner** appears if the ring was detected
6. Circles are positioned on **individual apples**, not in the cavities between apples

---

## TASK 4 — Run full test suite

```bash
cd /mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan
make test
```

All tests must pass. The new tests from Tasks 1 and 2 must be included. If any existing test breaks, diagnose and fix it before proceeding.

Expected result: **≥ 83 passed** (79 baseline + 3 normalizer tests + 4 detector NMS tests + tolerance for any new tests).

```bash
make lint        # zero ruff errors
make typecheck   # no new mypy errors
```

---

## TASK 5 — If the preview is still oblique after re-ingest

If after running Task 3 the preview still shows an oblique 3D view (not top-down), do the following diagnostic BEFORE adding any further fixes:

```python
import zipfile, io
import numpy as np
from pathlib import Path

ZIP_SRC = Path("/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip")

with zipfile.ZipFile(ZIP_SRC) as z:
    # Find the PLY file inside
    ply_names = [n for n in z.namelist() if n.lower().endswith('.ply')]
    print("PLY files in ZIP:", ply_names)
    
    if ply_names:
        from apple_caliber_scan.scan.loader import load_ply
        ply_data = z.read(ply_names[0])
        pts = load_ply(io.BytesIO(ply_data))
        print(f"Points: {len(pts)}, columns: {pts.shape[1]}")
        
        # Axis spread analysis
        for i, label in enumerate(['X', 'Y', 'Z']):
            q75, q25 = np.percentile(pts[:, i], [75, 25])
            iqr_val = q75 - q25
            rng_val = pts[:, i].max() - pts[:, i].min()
            print(f"  Axis {label}: IQR={iqr_val:.3f}, range={rng_val:.3f}")
        
        # Which axis is most likely vertical?
        iqrs = [np.percentile(pts[:, i], 75) - np.percentile(pts[:, i], 25) for i in range(3)]
        print(f"  Smallest IQR axis (most likely vertical): {['X','Y','Z'][int(np.argmin(iqrs))]}")
```

Use this output to verify that the IQR-based axis selection in the new `normalize_top_down()` correctly identifies the vertical axis for this specific scan. If it identifies the wrong axis, adjust the `normalize_top_down()` implementation — specifically, if the correct vertical axis is the one with the **second-smallest** IQR (because crate walls inflate the smallest one), change `np.argmin(axis_iqr)` to use a different selection criterion.

Report the diagnostic output and the resulting preview visually before marking this sprint complete.

---

## DEFINITION OF DONE

- [ ] `make test` shows **≥ 83 passed**, zero failures
- [ ] `make lint` passes (zero ruff errors)
- [ ] The scan 4 / batch 2 review page shows a **top-down view** of ~25–30 apples (not an oblique 3D perspective)
- [ ] The **teal-green trash bag background** is visible as expected (NOT suppressed)
- [ ] **More than 2 circles detected** on the review page (NMS working, ideally 15–30)
- [ ] The `_deduplicate_circles` test confirms the DB-confirmed 10-circle pattern reduces to 8 after NMS
- [ ] The physical blue ring is visible and the "Highlight ring (blue)" button highlights it
- [ ] No concentric circle cluster (same centre, different radii) appears in the review page overlays
- [ ] The auto-ring banner appears if confidence ≥ 0.5

---

## KNOWN CONSTRAINTS — do not violate

1. **No colour-based masking of green pixels.** Future scans will include green apples. Any filter that suppresses green-dominant pixels would suppress green apples. The green bag background is part of the expected visual and must remain visible.

2. **The blue ring is the 75 mm calibration reference.** It is always assumed to represent exactly 75 mm diameter. The `detect_calibration_ring()` function finds it by the blue colour mask — this works because blue apples do not exist.

3. **Domain rules from CLAUDE.md are non-negotiable.** Caliber classes, Polish language in reports, SZACUNEK label, legal clause — do not touch any of these.

4. **Do not delete Batch 2 or Scan 4** from the DB at any point during this sprint.

5. **`from __future__ import annotations`** must NOT be added to `scans.py` — it breaks FastAPI form/file parameter injection. Check this after any edit to that file.
