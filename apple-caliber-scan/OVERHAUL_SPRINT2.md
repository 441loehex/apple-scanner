# Apple Caliber Scan — Overhaul Sprint 2

## Mission

Fix three root-cause failures that prevent reliable caliber measurement, then clean up
stale data. **Deliver a working, tested, end-to-end system. No partial fixes.**

---

## Codebase Context (verified against current source)

```
apple_caliber_scan/
  scan/
    loader.py       — load_polycam_raw_zip() → np.ndarray (N,6) [x,y,z,r,g,b] float32
    normalizer.py   — normalize_top_down(points, top_percentile=0.20)
    preview.py      — render_preview() → _render_colored() / _render_height()
    detector.py     — Circle dataclass + detect_circles() + _fit_ellipses()
  services/
    ingest.py       — _process_local_file() → load → normalize → preview → detect
    calibration.py  — compute_scale_factor(ring_circle, ring_mm, apple_circles)
    reporting.py    — build_report_context(..., sideways_count=0)
  database/
    schema.sql      — scan_circles has: cx_px, cy_px, radius_px, ellipse_{major,minor,angle}_px
    connection.py   — initialize_schema() runs migrations (ALTER TABLE try/except)
  web/
    routes/scans.py — scan_upload_file(), scan_annotate(), _save_scan_results()
    templates/scan_review.html — two-layer canvas (#image-layer + #review-canvas)
    static/review.js — drawAnnotations(), highlightBlueChannel(), applyCanvasFilter()
```

**Data format**: point cloud is `float32 (N,6)` — columns `[x, y, z, r, g, b]` where
RGB is 0–255. After `normalize_top_down`, XY are in [0,1]. The preview is 1024×1024 px.

**Calibration ring**: physical blue ring, 75 mm diameter, with a handle
(magnifying-glass shape). Placed around one apple in the crate. Blue channel dominates
strongly vs red apples and green background/mat.

**Known scan**: `17_05_2026.zip` — 4,141,512 points. Scan 4 in Batch 2 is the only
reference-quality result so far.

---

## ROOT CAUSE ANALYSIS

Before implementing anything, understand these three bugs:

### Bug A — Circles appear as ellipses in the preview

**Location**: `normalizer.py` lines 57–63.

```python
# BROKEN — normalises X and Y with *different* scale factors
xy_min = top_pts[:, :2].min(axis=0)
xy_max = top_pts[:, :2].max(axis=0)
xy_range = xy_max - xy_min          # [x_range, y_range] — usually NOT equal
result[:, :2] = (top_pts[:, :2] - xy_min) / xy_range
```

If the crate is 1.2 m wide × 0.8 m deep, `xy_range = [1.2, 0.8]`. A physically
circular ring of radius R becomes:
- horizontal radius in preview = R / 1.2 × 1024 px
- vertical radius in preview   = R / 0.8 × 1024 px
- apparent aspect ratio = 1.2 / 0.8 = **1.5 — a very obvious ellipse**

**Fix**: use a single `max_range` for both axes (preserve aspect ratio), then centre
the content in the [0, 1] square.

```python
# CORRECT
max_range = xy_range.max()
result[:, :2] = (top_pts[:, :2] - xy_min) / max_range
# Content is now correctly proportioned; shorter axis won't reach 1.0 — that's fine.
# Centre it so neither axis is hugging a wall:
offsets = (1.0 - xy_range / max_range) / 2.0   # e.g. [0.0, 0.167]
result[:, :2] += offsets
```

### Bug B — Preview looks "mangled" / washed-out grey

**Location**: `preview.py` `_render_colored()` lines 74–76.

```python
# Gaussian blur radius 9 px on a 1024×1024 canvas with 4 M points
# = every pixel is already filled. Blur just destroys colour fidelity.
canvas_r = cv2.GaussianBlur(canvas_r, (9, 9), 2)   ← kills colour
```

With 4 M points on 1 M pixels, the canvas is dense. The `(9,9)` blur smears red
apple pixels into the 160-grey background and vice versa. Fix: use a much tighter
blur only to fill *actual* gaps, and brighten the result with a mild CLAHE pass.

### Bug C — No automatic ring detection

The operator must manually click the ring in the review UI. With ~25 apples visible,
finding the one blue ring and clicking it accurately is error-prone. Since the ring
is distinctively blue and physically circular, it can be auto-detected from either the
3D point cloud or the 2D preview.

---

## TASK 1 — Fix `normalize_top_down` to preserve aspect ratio

**File**: `apple_caliber_scan/scan/normalizer.py`

Replace the broken normalisation block (lines 57–63) with the aspect-preserving
version shown in Bug A above. The change is ~5 lines.

**Edge cases**:
- If `xy_range[0] < 1e-9` or `xy_range[1] < 1e-9` (degenerate cloud), keep existing
  `xy_range[xy_range < 1e-9] = 1.0` guard before computing `max_range`.
- Z normalisation (lines 66–68) is unaffected — do not touch it.

**Test** (`tests/test_normalizer.py`):
```python
def test_aspect_ratio_preserved():
    """A circle in 3D space must project to a circle in 2D, not an ellipse."""
    # Create a flat disc of points: radius 0.05 in a 1.2 × 0.8 bounding box
    rng = np.random.default_rng(42)
    theta = rng.uniform(0, 2 * np.pi, 500)
    disc = np.column_stack([
        0.6 + 0.05 * np.cos(theta),   # X centred in 1.2m span
        0.4 + 0.05 * np.sin(theta),   # Y centred in 0.8m span
        np.ones(500) * 0.02,           # all at the same Z (top layer)
    ]).astype(np.float32)
    # Pad with a flat floor far below
    floor = rng.uniform(size=(2000, 3)).astype(np.float32)
    floor[:, 2] = 0.0
    floor[:, 0] *= 1.2
    floor[:, 1] *= 0.8
    pts = np.vstack([disc, floor])

    norm = normalize_top_down(pts, top_percentile=0.05)

    # The disc after normalisation should still be circular
    disc_norm = norm[:500, :2]          # first 500 rows are the disc points
    cx, cy = disc_norm[:, 0].mean(), disc_norm[:, 1].mean()
    dx = disc_norm[:, 0] - cx
    dy = disc_norm[:, 1] - cy
    rx = np.sqrt((dx ** 2).mean())      # RMS radius in X
    ry = np.sqrt((dy ** 2).mean())      # RMS radius in Y
    aspect = max(rx, ry) / (min(rx, ry) + 1e-9)
    assert aspect < 1.05, f"Aspect ratio {aspect:.3f} — circle distorted into ellipse"
```

---

## TASK 2 — Fix preview colour rendering

**File**: `apple_caliber_scan/scan/preview.py` — `_render_colored()`

Apply these changes:
1. **Darker background**: change `160` → `40` so the grey background is dark and
   colourful apple pixels stand out without bleaching.
2. **Replace (9,9) Gaussian with a gap-filling minimum blur**: apply blur only where
   the canvas is still background (i.e., unpainted pixels).
3. **Post-render contrast lift**: apply `cv2.equalizeHist` or CLAHE per channel so
   the image is never washed-out grey.

Concrete implementation:

```python
def _render_colored(points, output_path, width, height):
    xs = np.clip(points[:, 0], 0.0, 1.0)
    ys = np.clip(points[:, 1], 0.0, 1.0)
    rs = np.clip(points[:, 3], 0, 255).astype(np.uint8)
    gs = np.clip(points[:, 4], 0, 255).astype(np.uint8)
    bs = np.clip(points[:, 5], 0, 255).astype(np.uint8)

    px = (xs * (width - 1)).astype(np.int32)
    py = ((1.0 - ys) * (height - 1)).astype(np.int32)

    BG = 40  # dark background — apple colours stand out clearly
    canvas_r = np.full((height, width), BG, dtype=np.uint8)
    canvas_g = np.full((height, width), BG, dtype=np.uint8)
    canvas_b = np.full((height, width), BG, dtype=np.uint8)
    painted = np.zeros((height, width), dtype=bool)

    canvas_r[py, px] = rs
    canvas_g[py, px] = gs
    canvas_b[py, px] = bs
    painted[py, px] = True

    # Fill only *actual* holes (unpainted pixels) with a tight blur
    if not painted.all():
        mask = (~painted).astype(np.uint8) * 255
        for ch, canvas in [(0, canvas_r), (1, canvas_g), (2, canvas_b)]:
            blurred = cv2.GaussianBlur(canvas, (5, 5), 1)
            canvas[mask > 0] = blurred[mask > 0]

    # CLAHE per channel to lift any remaining grey flatness
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    canvas_r = clahe.apply(canvas_r)
    canvas_g = clahe.apply(canvas_g)
    canvas_b = clahe.apply(canvas_b)

    rgb = np.stack([canvas_r, canvas_g, canvas_b], axis=-1)
    Image.fromarray(rgb, mode="RGB").save(str(output_path))
```

**Test** (`tests/test_preview.py` — add):
```python
def test_colored_preview_preserves_blue_ring():
    """Blue ring pixels must survive rendering without being bleached to grey."""
    rng = np.random.default_rng(0)
    # ~1000 red apple points
    apples = np.zeros((1000, 6), dtype=np.float32)
    apples[:, 0] = rng.uniform(0.1, 0.9, 1000)
    apples[:, 1] = rng.uniform(0.1, 0.9, 1000)
    apples[:, 2] = rng.uniform(0.8, 1.0, 1000)
    apples[:, 3] = 200; apples[:, 4] = 30; apples[:, 5] = 30  # red

    # ~200 blue ring points arranged in a circle
    theta = np.linspace(0, 2 * np.pi, 200)
    ring = np.zeros((200, 6), dtype=np.float32)
    ring[:, 0] = 0.5 + 0.08 * np.cos(theta)
    ring[:, 1] = 0.5 + 0.08 * np.sin(theta)
    ring[:, 2] = 0.95
    ring[:, 3] = 10; ring[:, 4] = 30; ring[:, 5] = 220  # blue

    pts = np.vstack([apples, ring])
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        img = np.array(Image.open(out))
        blue_dom = (img[:, :, 2].astype(int) > 80) & \
                   (img[:, :, 2].astype(int) > img[:, :, 0].astype(int) * 1.3) & \
                   (img[:, :, 2].astype(int) > img[:, :, 1].astype(int) * 1.3)
        assert blue_dom.sum() > 50, \
            f"Blue ring not visible after rendering ({blue_dom.sum()} blue-dominant px)"
    finally:
        out.unlink(missing_ok=True)
```

---

## TASK 3 — Automatic calibration ring detection

### 3A — New function `detect_calibration_ring()` in `detector.py`

The function operates on the preview PNG (already rendered, used by the operator).
It is independent of Hough circle detection — different algorithm, separate function.

```python
def detect_calibration_ring(
    preview_path: Path,
    min_radius_px: int = 15,
    max_radius_px: int = 150,
) -> Circle | None:
    """
    Detect the blue calibration ring in the preview image.

    Strategy:
      1. Build a binary mask of blue-dominant pixels:
             B > 80  AND  B > R * 1.35  AND  B > G * 1.35
      2. Morphological close to join the ring arc with any handle blob.
      3. Find the largest connected component.
      4. Run HoughCircles on the dilated blue mask (single-channel white-on-black).
      5. Return the best circle whose radius is in [min_radius_px, max_radius_px].

    Returns None if no reliable ring is found (confidence is logged).
    The caller should NOT abort on None — just leave the ring unset for the operator.
    """
    img = cv2.imread(str(preview_path))
    if img is None:
        return None

    b = img[:, :, 0].astype(np.int32)   # OpenCV is BGR
    g = img[:, :, 1].astype(np.int32)
    r = img[:, :, 2].astype(np.int32)

    blue_mask = (
        (b > 80) &
        (b > (r * 1.35).astype(np.int32)) &
        (b > (g * 1.35).astype(np.int32))
    ).astype(np.uint8) * 255

    # Morphological close — joins the ring arc and the handle into one region
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    closed = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)

    # Keep only the largest blue region (ignore stray blue pixels)
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    if n_labels < 2:
        logger.info("detect_calibration_ring: no blue regions found")
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    best_label = int(np.argmax(areas)) + 1
    roi_mask = (labels == best_label).astype(np.uint8) * 255

    # Dilate slightly for Hough to find the arc
    dilated = cv2.dilate(roi_mask, np.ones((5, 5), np.uint8), iterations=2)

    # Hough on the blue region only
    raw = cv2.HoughCircles(
        dilated,
        cv2.HOUGH_GRADIENT_ALT,
        dp=1,
        minDist=min_radius_px * 2,
        param1=50,
        param2=0.4,
        minRadius=min_radius_px,
        maxRadius=max_radius_px,
    )
    if raw is None:
        # Fall back: fit circle to the bounding extent of the blue region
        ys, xs = np.where(roi_mask > 0)
        if len(xs) < 20:
            return None
        cx = float(xs.mean())
        cy = float(ys.mean())
        r_est = float(np.sqrt(((xs - cx) ** 2 + (ys - cy) ** 2).mean()))
        if not (min_radius_px <= r_est <= max_radius_px):
            return None
        logger.info("detect_calibration_ring: fallback fit cx=%.0f cy=%.0f r=%.0f", cx, cy, r_est)
        return Circle(cx=cx, cy=cy, radius_px=r_est, confidence=0.5)

    circles = np.round(raw[0]).astype(np.float32)
    # Pick the one with the largest radius inside bounds (ring > handle)
    valid = [(cx, cy, r) for cx, cy, r in circles if min_radius_px <= r <= max_radius_px]
    if not valid:
        return None
    cx, cy, r = max(valid, key=lambda t: t[2])
    logger.info("detect_calibration_ring: found cx=%.0f cy=%.0f r=%.0f", cx, cy, r)
    return Circle(cx=float(cx), cy=float(cy), radius_px=float(r), confidence=0.9)
```

### 3B — Wire ring detection into ingest pipeline

**File**: `apple_caliber_scan/services/ingest.py` — `_process_local_file()`

After `circles = detect_circles(preview_path)`, add:

```python
from apple_caliber_scan.scan.detector import detect_calibration_ring

auto_ring = detect_calibration_ring(preview_path)
logger.info(
    "Auto ring detection: %s",
    f"cx={auto_ring.cx:.0f} cy={auto_ring.cy:.0f} r={auto_ring.radius_px:.0f} "
    f"conf={auto_ring.confidence:.2f}" if auto_ring else "not found",
)
return preview_path, circles, point_count, auto_ring
```

Update the return type annotation:
```python
) -> tuple[Path, list[Circle], int, Circle | None]:
```

Update all callers — `ingest_from_drive_url`, `ingest_from_local_file`, `ingest_synthetic`
— to propagate the new 4th element.

### 3C — Store auto-ring result in DB

**Schema migration** — add columns to `scans` table in `schema.sql`:
```sql
auto_ring_cx_px   REAL,
auto_ring_cy_px   REAL,
auto_ring_radius_px REAL,
auto_ring_confidence REAL DEFAULT 0.0,
```

Add migration in `connection.py` `initialize_schema()`:
```python
for col, typ in [
    ("auto_ring_cx_px", "REAL"),
    ("auto_ring_cy_px", "REAL"),
    ("auto_ring_radius_px", "REAL"),
    ("auto_ring_confidence", "REAL DEFAULT 0.0"),
]:
    try:
        conn.execute(f"ALTER TABLE scans ADD COLUMN {col} {typ}")
    except Exception:
        pass
```

**Update `_save_scan_results()`** in `web/routes/scans.py` to accept and store
`auto_ring: Circle | None`:
```python
if auto_ring:
    update_scan(conn, scan_id,
        auto_ring_cx_px=auto_ring.cx,
        auto_ring_cy_px=auto_ring.cy,
        auto_ring_radius_px=auto_ring.radius_px,
        auto_ring_confidence=auto_ring.confidence,
    )
```

### 3D — Auto-apply the ring in `scan_review.html` / `review.js`

In `scan_review.html`, pass the auto-ring to the JS context:
```html
const AUTO_RING = {{ auto_ring_json | tojson | safe }};
// e.g. {"cx": 202, "cy": 672, "radius": 38, "confidence": 0.9} or null
```

In `scan_review` route (`scans.py`), add to template context:
```python
auto_ring_json = None
if scan["auto_ring_cx_px"] and scan["auto_ring_confidence"] and \
   scan["auto_ring_confidence"] >= 0.5:
    auto_ring_json = {
        "cx": scan["auto_ring_cx_px"],
        "cy": scan["auto_ring_cy_px"],
        "radius": scan["auto_ring_radius_px"],
        "confidence": scan["auto_ring_confidence"],
    }
```

In `review.js`, after `drawAll()` loads, if `AUTO_RING` is set and no circle is
already marked as ring:
```javascript
function applyAutoRing() {
    if (!AUTO_RING) return;
    const alreadyRinged = circles.some(c => c.is_ring);
    if (alreadyRinged) return;

    // Find the existing circle closest to the auto-detected ring centre
    let best = null, bestDist = Infinity;
    for (const c of circles) {
        const d = Math.hypot(c.cx - AUTO_RING.cx, c.cy - AUTO_RING.cy);
        if (d < bestDist) { bestDist = d; best = c; }
    }

    // Accept if close enough (within 1 ring radius)
    if (best && bestDist < AUTO_RING.radius * 1.5) {
        best.is_ring = true;
        showToast(`Ring automatycznie wykryty (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`);
    } else {
        // Inject the ring as a new synthetic circle (operator can move it)
        const newCircle = {
            id: null,
            cx: AUTO_RING.cx,
            cy: AUTO_RING.cy,
            radius: AUTO_RING.radius,
            is_ring: true,
            is_excluded: false,
            diameter_mm: null,
            caliber_class: null,
            confidence: AUTO_RING.confidence,
        };
        circles.push(newCircle);
        showToast(`Pierścień dodany automatycznie (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`);
    }
    drawAll();
}
```

Show a dismissible banner in the review page if `AUTO_RING` is set:
```html
{% if auto_ring_json %}
<div class="alert alert-info alert-dismissible fade show" role="alert">
  Pierścień kalibracyjny wykryty automatycznie
  (pewność: {{ "%.0f"|format(auto_ring_json.confidence * 100) }}%).
  Sprawdź poprawność zaznaczenia przed zatwierdzeniem.
  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
</div>
{% endif %}
```

**Test** (`tests/test_detector.py` — add):
```python
def test_detect_calibration_ring_on_synthetic_preview():
    """Blue ring placed at known position must be found within 5% of its radius."""
    import tempfile
    from PIL import Image

    W, H = 512, 512
    img = np.full((H, W, 3), 40, dtype=np.uint8)  # dark background (BGR)
    # Draw a blue ring arc: centre (256, 256), radius 60 px
    cx, cy, r = 256, 256, 60
    for angle in np.linspace(0, 2 * np.pi, 500):
        x = int(cx + r * np.cos(angle))
        y = int(cy + r * np.sin(angle))
        if 0 <= x < W and 0 <= y < H:
            img[y, x] = [220, 30, 10]   # OpenCV BGR → strong blue

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)
    cv2.imwrite(str(path), img)
    try:
        result = detect_calibration_ring(path, min_radius_px=30, max_radius_px=120)
        assert result is not None, "Ring not detected"
        assert abs(result.cx - cx) < r * 0.10, f"cx off by {abs(result.cx - cx):.1f}px"
        assert abs(result.cy - cy) < r * 0.10, f"cy off by {abs(result.cy - cy):.1f}px"
        assert abs(result.radius_px - r) < r * 0.15, f"radius off by {abs(result.radius_px - r):.1f}px"
    finally:
        path.unlink(missing_ok=True)
```

---

## TASK 4 — Apple orientation classification from 3D Z-profile

### Why this matters for caliber accuracy

An upright apple (stem-up or calyx-up) projects its widest cross-section (equator) into
the top-down view → `radius_px * 2` directly equals the equatorial diameter.

A sideways apple projects only half its cross-section → the minor axis of the detected
ellipse equals the equatorial diameter. The existing `caliber_diameter_px` property
already handles this correctly via `ellipse_minor_px`.

A *tilted* apple (neither upright nor flat on its side) projects an intermediate view,
and both measurements over- or under-estimate. The `orientation` field lets the operator
and the report highlight uncertain measurements.

### 4A — Add `orientation` field to `Circle`

**File**: `apple_caliber_scan/scan/detector.py`

```python
@dataclass
class Circle:
    cx: float
    cy: float
    radius_px: float
    confidence: float = 1.0
    ellipse_major_px: float = 0.0
    ellipse_minor_px: float = 0.0
    ellipse_angle_deg: float = 0.0
    orientation: str = "unknown"    # "upright" | "sideways" | "angled" | "unknown"

    @property
    def orientation_label_pl(self) -> str:
        return {
            "upright":  "pionowo",
            "sideways": "na boku",
            "angled":   "ukośnie",
            "unknown":  "—",
        }.get(self.orientation, "—")
```

The `is_sideways` property is now superseded by `orientation == "sideways"`, but keep it
for backwards compatibility.

### 4B — New function `classify_orientations()` in `detector.py`

This function takes the normalized point cloud and the list of circles (in preview-pixel
coordinates) and enriches each `Circle` with an `orientation` label.

```python
def classify_orientations(
    circles: list[Circle],
    points: np.ndarray,
    preview_width: int = 1024,
    preview_height: int = 1024,
) -> list[Circle]:
    """
    For each detected circle, extract the 3D points within the corresponding
    cylinder and classify apple orientation from the local Z-height profile.

    points: normalized (N, 3+) array, XY in [0,1], Z in [0,1].
    The preview maps X→px and Y→(1-py), same as _render_colored.

    Classification rules:
      dome_ratio = (Z_centre_mean - Z_edge_mean) / (Z_max - Z_min + ε)
        > 0.25  → "upright"  (hemisphere dome from above)
        < 0.05  AND is_sideways → "sideways"
        otherwise → "angled"
      If fewer than 20 points in cylinder: "unknown"
    """
    if len(points) == 0 or points.shape[1] < 3:
        return circles

    xs = points[:, 0]
    ys = points[:, 1]
    zs = points[:, 2]

    W, H = preview_width, preview_height

    for circle in circles:
        # Convert circle centre from preview pixels to normalised [0,1]
        cx_n = circle.cx / (W - 1)
        cy_n = 1.0 - circle.cy / (H - 1)   # Y is flipped in render
        r_n  = circle.radius_px / (W - 1)   # approximate — use W for both axes

        dist2 = (xs - cx_n) ** 2 + (ys - cy_n) ** 2
        inner_mask = dist2 < (r_n * 0.4) ** 2          # central 40 % of radius
        outer_mask = (dist2 > (r_n * 0.6) ** 2) & (dist2 < (r_n * 1.1) ** 2)

        in_cylinder = dist2 < (r_n * 1.1) ** 2
        pts_in = zs[in_cylinder]

        if len(pts_in) < 20:
            circle.orientation = "unknown"
            continue

        z_min, z_max = pts_in.min(), pts_in.max()
        z_range = z_max - z_min

        pts_inner = zs[inner_mask]
        pts_outer = zs[outer_mask]

        if len(pts_inner) < 5 or len(pts_outer) < 5:
            circle.orientation = "unknown"
            continue

        z_centre = pts_inner.mean()
        z_edge   = pts_outer.mean()
        dome_ratio = (z_centre - z_edge) / (z_range + 1e-9)

        if dome_ratio > 0.25:
            circle.orientation = "upright"
        elif circle.is_sideways and dome_ratio < 0.10:
            circle.orientation = "sideways"
        else:
            circle.orientation = "angled"

    return circles
```

### 4C — Call it in `ingest.py` `_process_local_file()`

After `circles = detect_circles(preview_path)` and the new auto_ring call, add:

```python
from apple_caliber_scan.scan.detector import classify_orientations

circles = classify_orientations(circles, preview_pts, preview_width=1024, preview_height=1024)
orient_counts = {o: sum(1 for c in circles if c.orientation == o)
                 for o in ("upright", "sideways", "angled", "unknown")}
logger.info("Orientation classification: %s", orient_counts)
```

Note: `preview_pts` is already in scope (the normalized point cloud).

### 4D — Schema migration for `orientation` column

In `schema.sql` add to `scan_circles`:
```sql
orientation TEXT DEFAULT 'unknown',
```

In `connection.py` `initialize_schema()`:
```python
try:
    conn.execute("ALTER TABLE scan_circles ADD COLUMN orientation TEXT DEFAULT 'unknown'")
except Exception:
    pass
```

### 4E — Store orientation in `_save_scan_results()`

In `web/routes/scans.py` `_save_scan_results()`, add `"orientation": c.orientation`
to the `circle_dicts` list.

### 4F — Pass orientation to `scan_annotate()` and review UI

In `scan_review.html` / `review.js`, display orientation next to each circle tooltip:
```javascript
// In the circle tooltip/info panel:
`${c.caliber_class || "—"} mm · ${orientationLabel(c.orientation)}`

function orientationLabel(o) {
    return {upright: "pionowo", sideways: "na boku", angled: "ukośnie"}[o] || "—";
}
```

### 4G — Add orientation summary to the report

In `reports.py` `generate_report()`, compute:
```python
orientation_counts = {
    o: sum(1 for c in apple_circles if c.get("orientation") == o)
    for o in ("upright", "sideways", "angled", "unknown")
}
```

Pass to `build_report_context(orientation_counts=orientation_counts)`.

In `reporting.py`, add `orientation_counts: dict[str, int] | None = None` parameter
and include it in the returned context dict.

In `report_pl.html`, after the sideways note, add:
```html
{% if orientation_counts %}
<p class="sideways-note">
  Orientacja jabłek:
  pionowo {{ orientation_counts.get('upright', 0) }} szt. ·
  na boku {{ orientation_counts.get('sideways', 0) }} szt. ·
  ukośnie {{ orientation_counts.get('angled', 0) }} szt.
  {% if orientation_counts.get('angled', 0) > 0 %}
  — <em>jabłka ukośne mogą mieć niedoszacowany kaliber</em>
  {% endif %}
</p>
{% endif %}
```

**Test** (`tests/test_detector.py` — add):
```python
def test_upright_apple_classified_correctly():
    """Dome-shaped Z profile must classify as 'upright'."""
    cx_n, cy_n, r_n = 0.5, 0.5, 0.04
    rng = np.random.default_rng(1)
    theta = rng.uniform(0, 2 * np.pi, 300)
    radii = rng.uniform(0, r_n, 300)
    x = cx_n + radii * np.cos(theta)
    y = cy_n + radii * np.sin(theta)
    # Dome: Z is highest at centre, tapers at edge (hemisphere)
    z = 0.8 + 0.15 * (1.0 - (radii / r_n) ** 2)
    pts = np.column_stack([x, y, z]).astype(np.float32)

    circle = Circle(cx=512.0, cy=512.0, radius_px=40.0)  # r_n ≈ 40/1023
    result = classify_orientations([circle], pts, 1024, 1024)
    assert result[0].orientation == "upright", f"Got {result[0].orientation}"


def test_sideways_apple_classified_correctly():
    """Flat Z profile with ellipse aspect ratio must classify as 'sideways'."""
    cx_n, cy_n, r_n = 0.5, 0.5, 0.04
    rng = np.random.default_rng(2)
    theta = rng.uniform(0, 2 * np.pi, 300)
    radii = rng.uniform(0, r_n * 1.05, 300)
    x = cx_n + radii * np.cos(theta)
    y = cy_n + radii * np.sin(theta)
    z = np.full(300, 0.85) + rng.normal(0, 0.002, 300)  # flat Z — no dome
    pts = np.column_stack([x, y, z]).astype(np.float32)

    # Simulate sideways: ellipse major > 1.25 × minor
    circle = Circle(cx=512.0, cy=512.0, radius_px=40.0,
                    ellipse_major_px=60.0, ellipse_minor_px=40.0)
    result = classify_orientations([circle], pts, 1024, 1024)
    assert result[0].orientation == "sideways", f"Got {result[0].orientation}"
```

---

## TASK 5 — Database cleanup

Connect to the SQLite DB at `data/apple_caliber_scan.db` and run these statements.
**Verify row counts before deletion. Do not delete batch 2.**

```sql
-- Preview what will be deleted:
SELECT 'batch', id, seller_name, (SELECT COUNT(*) FROM scans WHERE batch_id=batches.id) as scan_count
FROM batches ORDER BY id;

-- Delete bad scans from batch 2 (scans 1, 2, 3 — keep scan 4 only)
DELETE FROM scan_circles WHERE scan_id IN (SELECT id FROM scans WHERE batch_id=2 AND id != 4);
DELETE FROM annotations WHERE scan_id IN (SELECT id FROM scans WHERE batch_id=2 AND id != 4);
DELETE FROM scans WHERE batch_id=2 AND id != 4;

-- Delete batches 1, 3, 4, 5, 6 entirely (cascades to scans + circles)
DELETE FROM batches WHERE id IN (1, 3, 4, 5, 6);

-- Verify
SELECT id, seller_name FROM batches;
SELECT id, batch_id, status, format FROM scans;
```

Expose this via a web route or just run as a one-off CLI:
```bash
cd apple-caliber-scan
.venv/bin/python -c "
from apple_caliber_scan.database.connection import db_conn
with db_conn() as conn:
    conn.execute('DELETE FROM scan_circles WHERE scan_id IN (SELECT id FROM scans WHERE batch_id=2 AND id != 4)')
    conn.execute('DELETE FROM annotations WHERE scan_id IN (SELECT id FROM scans WHERE batch_id=2 AND id != 4)')
    conn.execute('DELETE FROM scans WHERE batch_id=2 AND id != 4')
    conn.execute('DELETE FROM batches WHERE id IN (1,3,4,5,6)')
    rows = conn.execute('SELECT id, seller_name FROM batches').fetchall()
    print('Remaining batches:', list(rows))
    rows = conn.execute('SELECT id, batch_id, status FROM scans').fetchall()
    print('Remaining scans:', list(rows))
"
```

Also delete stale preview files for deleted scans/batches:
```bash
cd apple-caliber-scan
ls data/previews/
# Keep only: scan_4_batch_2.png
# Delete everything else manually or via:
.venv/bin/python -c "
from pathlib import Path
keep = {'scan_4_batch_2.png'}
for f in Path('data/previews').glob('*.png'):
    if f.name not in keep:
        f.unlink()
        print('Deleted:', f.name)
"
```

---

## TASK 6 — Re-ingest scan 4 in batch 2 with all fixes applied

After completing Tasks 1–5, re-ingest the reference scan to regenerate the preview
with the fixed normalizer and renderer, and to populate the new `orientation` and
`auto_ring` fields:

1. Start the web server: `make run-web`
2. Navigate to Batch 2 → Scan 4 → **"Ponownie przetwórz"** (re-ingest button)
3. Verify in the review page:
   - The calibration ring appears as a **circle** (not ellipse) in the preview
   - The blue ring is highlighted by the ring-highlight button
   - A banner appears saying the ring was auto-detected with confidence ≥ 50%
   - Each apple's orientation label is shown in the circle tooltip
4. Accept or correct the auto-detected ring, then submit the annotation

If the re-ingest button isn't available for scan 4 (it requires a stored `drive_url`),
alternatively upload `17_05_2026.zip` again via "Prześlij plik lokalny" in Batch 2.

---

## IMPLEMENTATION ORDER

Execute tasks in this exact order to avoid dependency issues:

1. `normalizer.py` aspect-ratio fix (Task 1) — nothing else depends on it, safest first
2. `preview.py` colour rendering fix (Task 2) — also standalone
3. `schema.sql` + `connection.py` migrations (Tasks 3C, 4D) — must come before routes
4. `detector.py` — add `orientation` field, add `detect_calibration_ring()`, add
   `classify_orientations()` (Tasks 3A, 4A, 4B)
5. `ingest.py` — wire auto_ring and orientation into pipeline (Tasks 3B, 4C)
6. `web/routes/scans.py` — update `_save_scan_results()`, review context (Tasks 3C, 4E)
7. `web/templates/scan_review.html` + `review.js` — UI for auto-ring and orientation (Tasks 3D, 4F)
8. `reporting.py` + `report_pl.html` — orientation summary (Task 4G)
9. `tests/` — add all tests listed above, run full suite
10. Database cleanup (Task 5)
11. Re-ingest scan 4 (Task 6)

---

## TEST COMMANDS

```bash
# All tests must pass before any PR / demo
cd apple-caliber-scan
make test                 # pytest — must show ≥ 65 passed (current baseline)

# Smoke test: ingest the reference ZIP end-to-end
.venv/bin/python -c "
from pathlib import Path
from apple_caliber_scan.services.ingest import ingest_from_local_file
import shutil, tempfile, numpy as np

zip_src = Path('/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip')
tmp = Path(tempfile.mktemp(suffix='.zip'))
shutil.copy(zip_src, tmp)

preview_path, circles, point_count, auto_ring = ingest_from_local_file(
    tmp, scan_id=999, batch_id=999, delete_after=False
)
print(f'Points: {point_count:,}')
print(f'Circles: {len(circles)}')
print(f'Auto ring: {auto_ring}')
print(f'Orientations: {[(c.orientation, c.caliber_diameter_px) for c in circles[:5]]}')

# Verify circles are not ellipses (aspect ratio < 1.3 for all non-sideways circles)
from PIL import Image
import numpy as np
img = np.array(Image.open(preview_path))
print(f'Preview size: {img.shape}')
print(f'R/G/B means: {img[:,:,0].mean():.0f}/{img[:,:,1].mean():.0f}/{img[:,:,2].mean():.0f}')
blue_dom = (img[:,:,2].astype(int) > 80) & (img[:,:,2].astype(int) > img[:,:,0].astype(int)*1.35)
print(f'Blue-dominant pixels: {blue_dom.sum()} (ring visible if > 500)')
tmp.unlink(missing_ok=True)
"
```

---

## DEFINITION OF DONE

- [ ] `make test` shows **≥ 75 passed** (65 existing + ≥ 10 new from this sprint)
- [ ] The reference scan preview shows circles that are **visually round** (not ellipses)
- [ ] The ring is **auto-detected** on the reference scan with confidence ≥ 0.5
- [ ] At least one apple has `orientation = "upright"` in the DB after re-ingest
- [ ] DB contains exactly **1 batch (id=2)** with **1 scan (id=4)** after cleanup
- [ ] `make lint` passes (zero ruff errors)
- [ ] The report for scan 4 / batch 2 shows orientation breakdown and sideways note
- [ ] No `from __future__ import annotations` in any file that uses `Annotated[UploadFile, ...]`

---

## KNOWN PITFALLS

- `from __future__ import annotations` in `scans.py` breaks FastAPI form/file parameter
  injection when the `@require_login` decorator wraps the function (the wrapper's
  `__globals__` is `auth.py` which does not import `Form`/`UploadFile`). Do not re-add it.

- `create_app()` in `app.py` must call `initialize_schema()` to auto-run migrations.
  Do not remove this — it was added at the end of Sprint 1.

- When `classify_orientations()` converts circle pixel coordinates back to normalised
  [0,1] space, use the SAME coordinate transformation as `_render_colored`:
  `cx_n = circle.cx / (W-1)`, `cy_n = 1.0 - circle.cy / (H-1)`. The Y-flip is critical.

- The `detect_calibration_ring()` blue threshold (`B > 80`, `B > R*1.35`, `B > G*1.35`)
  was tuned for a **dark background** (Task 2 sets BG=40). If Task 2 is not applied
  first, the thresholds will need adjustment. Always apply Task 2 before testing Task 3.
