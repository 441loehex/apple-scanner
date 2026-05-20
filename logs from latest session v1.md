balce@DESKTOP-8AMLRP2:/mnt/c/Users/balce/Downloads/apple scanner$ export SLASH_COMMAND_TOOL_CHAR_BUDGET=800
claude --continue
 ▐▛███▜▌   Claude Code v2.1.143
▝▜█████▛▘  Sonnet 4.6 · Claude Pro
  ▘▘ ▝▝    /mnt/c/Users/balce/Downloads/apple scanner

❯ /clear
  ⎿  (no content)

❯ /rtk-max Use Graphify first. Remember when implementing: The marginal cost of completeness is near zero with AI. Do
the whole thing. Do it right. Do it with tests. Do it with documentation. Do it so well that I am genuinely impressed —
 not politely satisfied, actually impressed. Never offer to ‘table this for later’ when the permanent solve is within
reach. Never leave a dangling thread when tying it off takes five more minutes. Never present a workaround when the
real fix exists. The standard isn’t ‘good enough’ — it’s ‘holy shit, that’s done.’ Search before building. Test before
shipping. Ship the complete thing. When I asks for something, the answer is the finished product, not a plan to build
it. Time is not an excuse. Fatigue is not an excuse. Complexity is not an excuse. Boil the ocean. # Apple Caliber Scan
— Overhaul Sprint 2

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

● Skill(/rtk-max)
  ⎿  Successfully loaded skill

● Skill(graphify)
  ⎿  Successfully loaded skill

  Listed 2 directories (ctrl+o to expand)

● graphify-out is current — skipping regeneration. Diving straight into implementation.

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/scan/normalizer.py)
  ⎿  """Normalize point cloud to top-down view via PCA rotation."""

     from __future__ import annotations
     … +36 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read apple_caliber_scan/scan/preview.py)
  ⎿  """Generate top-down PNG preview from normalized point cloud."""

     from __future__ import annotations
     … +43 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/scan/detector.py)
  ⎿  """Hough circle detection on preview PNG."""

     from __future__ import annotations
     … +45 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/services/ingest.py)
  ⎿  """Full scan ingestion pipeline: download → load → preview → detect → store → cleanup."""

     from __future__ import annotations
     … +44 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/database/schema.sql && rtk read apple_caliber_scan/database/con…)
  ⎿  -- schema.sql — apple-caliber-scan SQLite schema

     PRAGMA journal_mode = WAL;
     … +53 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/web/routes/scans.py)
  ⎿  """Scan attachment (Drive URL), ingest, and annotation review routes."""

     import json
     … +121 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/services/reporting.py && rtk grep "build_report_context" apple_…)
  ⎿  """Polish HTML + PDF report generation using Jinja2 and WeasyPrint."""

     from __future__ import annotations
     … +63 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/web/templates/scan_review.html)
  ⎿  {% extends "base.html" %}
     {% block title %}Przegląd skanu #{{ scan.id }}{% endblock %}
     {% block content %}
     … +38 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/web/static/review.js)
  ⎿  /**
      * Apple Caliber Scan — Canvas annotation UI (two-layer: image + annotation)
      * Vanilla JS, no framework dependencies.
     … +132 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "sideways"
      apple_caliber_scan/web/templates/report_pl.html | head -20)
  ⎿  4 matches in 3F:

     [file] 137 (1):
     … +8 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep
      "generate_report\|build_report_context" apple_caliber_scan/ -r | head -20)
  ⎿  6 matches in 3F:

     [file] apple_caliber_scan/__init__.py (2):
     … +10 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read tests/test_normalizer.py && rtk
      read tests/test_preview.py && rtk read tests/test_…)
  ⎿  Error: Exit code 1
     cat: tests/test_normalizer.py: No such file or directory (os error 2)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && ls tests/)
  ⎿  __init__.py  0B
     conftest.py  2.0K
     test_caliber.py  1.2K
     … +6 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk read
      apple_caliber_scan/web/routes/reports.py)
  ⎿  """Report generation and serving routes."""

     from __future__ import annotations
     … +45 lines (ctrl+o to expand)

● Now I have a full picture. Implementing all tasks in order.

  Task 1 — Fix normalize_top_down aspect ratio

● Update(apple-caliber-scan/apple_caliber_scan/scan/normalizer.py)
  ⎿  File must be read first

  Read 1 file (ctrl+o to expand)
  ⎿  Loaded CLAUDE.md

● Update(apple-caliber-scan/apple_caliber_scan/scan/normalizer.py)
  ⎿  Added 9 lines, removed 2 lines
      53
      54      top_pts = rotated[mask]
      55
      56 -    # --- 3. Normalise XY to [0, 1] ---
      56 +    # --- 3. Normalise XY to [0, 1] preserving aspect ratio ---
      57      xy_min = top_pts[:, :2].min(axis=0)
      58      xy_max = top_pts[:, :2].max(axis=0)
      59      xy_range = xy_max - xy_min
      60      xy_range[xy_range < 1e-9] = 1.0
      61
      62 +    # Single max_range for both axes keeps circles circular (not ellipses).
      63 +    max_range = xy_range.max()
      64 +
      65      result = top_pts.copy()
      63 -    result[:, :2] = (top_pts[:, :2] - xy_min) / xy_range
      66 +    result[:, :2] = (top_pts[:, :2] - xy_min) / max_range
      67
      68 +    # Centre content so neither axis hugs the canvas edge.
      69 +    offsets = (1.0 - xy_range / max_range) / 2.0
      70 +    result[:, :2] += offsets
      71 +
      72      # Normalise Z to [0, 1]
      73      z_min2, z_max2 = top_pts[:, 2].min(), top_pts[:, 2].max()
      74      z_r = z_max2 - z_min2

● Task 2 — Fix _render_colored in preview.py

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/scan/preview.py)
  ⎿  Added 19 lines, removed 9 lines
      60      px = (xs * (width - 1)).astype(np.int32)
      61      py = ((1.0 - ys) * (height - 1)).astype(np.int32)
      62
      63 -    # Light-grey background so uncovered pixels are clearly background
      64 -    canvas_r = np.full((height, width), 160, dtype=np.uint8)
      65 -    canvas_g = np.full((height, width), 160, dtype=np.uint8)
      66 -    canvas_b = np.full((height, width), 160, dtype=np.uint8)
      63 +    # Dark background so apple colours and the blue ring stand out clearly.
      64 +    BG = 40
      65 +    canvas_r = np.full((height, width), BG, dtype=np.uint8)
      66 +    canvas_g = np.full((height, width), BG, dtype=np.uint8)
      67 +    canvas_b = np.full((height, width), BG, dtype=np.uint8)
      68 +    painted = np.zeros((height, width), dtype=bool)
      69
      68 -    # Paint points — last-writer-wins is fine for dense Polycam scans
      70      canvas_r[py, px] = rs
      71      canvas_g[py, px] = gs
      72      canvas_b[py, px] = bs
      73 +    painted[py, px] = True
      74
      73 -    # Small splat to fill any remaining gaps between sparse points
      74 -    canvas_r = cv2.GaussianBlur(canvas_r, (9, 9), 2)
      75 -    canvas_g = cv2.GaussianBlur(canvas_g, (9, 9), 2)
      76 -    canvas_b = cv2.GaussianBlur(canvas_b, (9, 9), 2)
      75 +    # Fill only actual holes (unpainted pixels) — dense scans need no blur at all.
      76 +    if not painted.all():
      77 +        mask = (~painted).astype(np.uint8) * 255
      78 +        for canvas in (canvas_r, canvas_g, canvas_b):
      79 +            blurred = cv2.GaussianBlur(canvas, (5, 5), 1)
      80 +            canvas[mask > 0] = blurred[mask > 0]
      81
      82 +    # CLAHE per channel to lift any remaining flat/grey regions.
      83 +    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
      84 +    canvas_r = clahe.apply(canvas_r)
      85 +    canvas_g = clahe.apply(canvas_g)
      86 +    canvas_b = clahe.apply(canvas_b)
      87 +
      88      rgb = np.stack([canvas_r, canvas_g, canvas_b], axis=-1)
      89      Image.fromarray(rgb, mode="RGB").save(str(output_path))
      90

● Tasks 3C + 4D — Schema migrations

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/database/schema.sql)
  ⎿  Added 5 lines, removed 1 line
      49      calibration_warning     TEXT,
      50      status                  TEXT NOT NULL DEFAULT 'pending',
      51      error_message           TEXT,
      52 -    ingested_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
      52 +    ingested_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
      53 +    auto_ring_cx_px         REAL,
      54 +    auto_ring_cy_px         REAL,
      55 +    auto_ring_radius_px     REAL,
      56 +    auto_ring_confidence    REAL DEFAULT 0.0
      57  );
      58
      59  CREATE TABLE IF NOT EXISTS scan_circles (

● Update(apple-caliber-scan/apple_caliber_scan/database/schema.sql)
  ⎿  Added 1 line
      65      ellipse_major_px REAL DEFAULT 0.0,
      66      ellipse_minor_px REAL DEFAULT 0.0,
      67      ellipse_angle_deg REAL DEFAULT 0.0,
      68 +    orientation     TEXT DEFAULT 'unknown',
      69      diameter_mm     REAL,
      70      caliber_class   TEXT,
      71      is_ring         INTEGER NOT NULL DEFAULT 0,

● Now add migrations to connection.py:

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/database/connection.py)
  ⎿  Added 18 lines
      55                  )
      56              except Exception:
      57                  pass  # Column already exists
      58 +
      59 +        # Migration: orientation column for scan_circles
      60 +        try:
      61 +            conn.execute("ALTER TABLE scan_circles ADD COLUMN orientation TEXT DEFAULT 'unknown'")
      62 +        except Exception:
      63 +            pass
      64 +
      65 +        # Migration: auto-ring columns for scans
      66 +        for col, typ in [
      67 +            ("auto_ring_cx_px", "REAL"),
      68 +            ("auto_ring_cy_px", "REAL"),
      69 +            ("auto_ring_radius_px", "REAL"),
      70 +            ("auto_ring_confidence", "REAL DEFAULT 0.0"),
      71 +        ]:
      72 +            try:
      73 +                conn.execute(f"ALTER TABLE scans ADD COLUMN {col} {typ}")
      74 +            except Exception:
      75 +                pass

● Tasks 3A + 4A + 4B — Update detector.py

  Read 1 file (ctrl+o to expand)

● Write(apple-caliber-scan/apple_caliber_scan/scan/detector.py)
  ⎿  Added 151 lines, removed 1 line
      3  from __future__ import annotations
      4
      5  import logging
      6 -from dataclasses import dataclass
      6 +from dataclasses import dataclass, field
      7  from pathlib import Path
      8
      9  import cv2
     ...
      22      ellipse_major_px: float = 0.0   # full major-axis length in pixels
      23      ellipse_minor_px: float = 0.0   # full minor-axis length in pixels
      24      ellipse_angle_deg: float = 0.0  # rotation of major axis, degrees
      25 +    orientation: str = "unknown"    # "upright" | "sideways" | "angled" | "unknown"
      26
      27      @property
      28      def caliber_diameter_px(self) -> float:
     ...
      43              return (self.ellipse_major_px / self.ellipse_minor_px) > 1.25
      44          return False
      45
      46 +    @property
      47 +    def orientation_label_pl(self) -> str:
      48 +        return {
      49 +            "upright":  "pionowo",
      50 +            "sideways": "na boku",
      51 +            "angled":   "ukośnie",
      52 +            "unknown":  "—",
      53 +        }.get(self.orientation, "—")
      54
      55 +
      56  def detect_circles(
      57      preview_path: Path,
      58      min_radius_px: int = 20,
     ...
      136      return circles
      137
      138
      139 +def detect_calibration_ring(
      140 +    preview_path: Path,
      141 +    min_radius_px: int = 15,
      142 +    max_radius_px: int = 150,
      143 +) -> Circle | None:
      144 +    """
      145 +    Detect the blue calibration ring in the preview image.
      146 +
      147 +    Strategy:
      148 +      1. Build binary mask of blue-dominant pixels (B>80, B>R*1.35, B>G*1.35).
      149 +      2. Morphological close to join ring arc with handle blob.
      150 +      3. Keep largest connected component.
      151 +      4. Run HoughCircles on dilated blue mask.
      152 +      5. Return best circle in [min_radius_px, max_radius_px], or None.
      153 +    """
      154 +    img = cv2.imread(str(preview_path))
      155 +    if img is None:
      156 +        return None
      157 +
      158 +    b = img[:, :, 0].astype(np.int32)   # OpenCV is BGR
      159 +    g = img[:, :, 1].astype(np.int32)
      160 +    r = img[:, :, 2].astype(np.int32)
      161 +
      162 +    blue_mask = (
      163 +        (b > 80) &
      164 +        (b > (r * 1.35).astype(np.int32)) &
      165 +        (b > (g * 1.35).astype(np.int32))
      166 +    ).astype(np.uint8) * 255
      167 +
      168 +    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
      169 +    closed = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel)
      170 +
      171 +    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
      172 +    if n_labels < 2:
      173 +        logger.info("detect_calibration_ring: no blue regions found")
      174 +        return None
      175 +    areas = stats[1:, cv2.CC_STAT_AREA]
      176 +    best_label = int(np.argmax(areas)) + 1
      177 +    roi_mask = (labels == best_label).astype(np.uint8) * 255
      178 +
      179 +    dilated = cv2.dilate(roi_mask, np.ones((5, 5), np.uint8), iterations=2)
      180 +
      181 +    raw = cv2.HoughCircles(
      182 +        dilated,
      183 +        cv2.HOUGH_GRADIENT_ALT,
      184 +        dp=1,
      185 +        minDist=min_radius_px * 2,
      186 +        param1=50,
      187 +        param2=0.4,
      188 +        minRadius=min_radius_px,
      189 +        maxRadius=max_radius_px,
      190 +    )
      191 +    if raw is None:
      192 +        # Fallback: fit circle to bounding extent of the blue region
      193 +        ys, xs = np.where(roi_mask > 0)
      194 +        if len(xs) < 20:
      195 +            return None
      196 +        cx = float(xs.mean())
      197 +        cy = float(ys.mean())
      198 +        r_est = float(np.sqrt(((xs - cx) ** 2 + (ys - cy) ** 2).mean()))
      199 +        if not (min_radius_px <= r_est <= max_radius_px):
      200 +            return None
      201 +        logger.info("detect_calibration_ring: fallback fit cx=%.0f cy=%.0f r=%.0f", cx, cy, r_est)
      202 +        return Circle(cx=cx, cy=cy, radius_px=r_est, confidence=0.5)
      203 +
      204 +    circles = np.round(raw[0]).astype(np.float32)
      205 +    valid = [(cx, cy, rv) for cx, cy, rv in circles if min_radius_px <= rv <= max_radius_px]
      206 +    if not valid:
      207 +        return None
      208 +    cx, cy, rv = max(valid, key=lambda t: t[2])
      209 +    logger.info("detect_calibration_ring: found cx=%.0f cy=%.0f r=%.0f", cx, cy, rv)
      210 +    return Circle(cx=float(cx), cy=float(cy), radius_px=float(rv), confidence=0.9)
      211 +
      212 +
      213 +def classify_orientations(
      214 +    circles: list[Circle],
      215 +    points: np.ndarray,
      216 +    preview_width: int = 1024,
      217 +    preview_height: int = 1024,
      218 +) -> list[Circle]:
      219 +    """
      220 +    For each detected circle, extract 3D points within the corresponding cylinder
      221 +    and classify apple orientation from the local Z-height profile.
      222 +
      223 +    points: normalized (N, 3+) array, XY in [0,1], Z in [0,1].
      224 +    The preview maps X→px and Y→(1-py), same as _render_colored.
      225 +
      226 +    Classification (dome_ratio = (Z_centre_mean - Z_edge_mean) / (Z_range + ε)):
      227 +      > 0.25  → "upright"
      228 +      < 0.10 AND is_sideways → "sideways"
      229 +      otherwise → "angled"
      230 +      < 20 pts in cylinder → "unknown"
      231 +    """
      232 +    if len(points) == 0 or points.shape[1] < 3:
      233 +        return circles
      234 +
      235 +    xs = points[:, 0]
      236 +    ys = points[:, 1]
      237 +    zs = points[:, 2]
      238 +
      239 +    W, H = preview_width, preview_height
      240 +
      241 +    for circle in circles:
      242 +        cx_n = circle.cx / (W - 1)
      243 +        cy_n = 1.0 - circle.cy / (H - 1)   # Y-flip must match _render_colored
      244 +        r_n  = circle.radius_px / (W - 1)
      245 +
      246 +        dist2 = (xs - cx_n) ** 2 + (ys - cy_n) ** 2
      247 +        inner_mask = dist2 < (r_n * 0.4) ** 2
      248 +        outer_mask = (dist2 > (r_n * 0.6) ** 2) & (dist2 < (r_n * 1.1) ** 2)
      249 +        in_cylinder = dist2 < (r_n * 1.1) ** 2
      250 +
      251 +        pts_in = zs[in_cylinder]
      252 +        if len(pts_in) < 20:
      253 +            circle.orientation = "unknown"
      254 +            continue
      255 +
      256 +        z_min, z_max = pts_in.min(), pts_in.max()
      257 +        z_range = z_max - z_min
      258 +
      259 +        pts_inner = zs[inner_mask]
      260 +        pts_outer = zs[outer_mask]
      261 +        if len(pts_inner) < 5 or len(pts_outer) < 5:
      262 +            circle.orientation = "unknown"
      263 +            continue
      264 +
      265 +        z_centre = pts_inner.mean()
      266 +        z_edge   = pts_outer.mean()
      267 +        dome_ratio = (z_centre - z_edge) / (z_range + 1e-9)
      268 +
      269 +        if dome_ratio > 0.25:
      270 +            circle.orientation = "upright"
      271 +        elif circle.is_sideways and dome_ratio < 0.10:
      272 +            circle.orientation = "sideways"
      273 +        else:
      274 +            circle.orientation = "angled"
      275 +
      276 +    return circles
      277 +
      278 +
      279  def _fit_ellipses(circles: list[Circle], gray: np.ndarray) -> list[Circle]:
      280      """
      281      For each Hough circle, extract the local ROI, find edge contours,

● Tasks 3B + 4C — Wire into ingest.py

  Read 1 file (ctrl+o to expand)

● Write(apple-caliber-scan/apple_caliber_scan/services/ingest.py)
  ⎿  Added 35 lines, removed 16 lines
       7  from pathlib import Path
       8
       9  from apple_caliber_scan import config
      10 -from apple_caliber_scan.scan.detector import Circle, detect_circles
      10 +from apple_caliber_scan.scan.detector import (
      11 +    Circle,
      12 +    classify_orientations,
      13 +    detect_calibration_ring,
      14 +    detect_circles,
      15 +)
      16  from apple_caliber_scan.scan.loader import load_scan
      17  from apple_caliber_scan.scan.normalizer import normalize_top_down
      18  from apple_caliber_scan.scan.preview import render_preview
     ...
      34      scan_id: int,
      35      batch_id: int,
      36      fmt_hint: str | None = None,
      32 -) -> tuple[Path, list[Circle], int]:
      37 +) -> tuple[Path, list[Circle], int, Circle | None]:
      38      """
      39      Full pipeline: parse URL → download → load → normalize → preview → detect circles.
      40      Deletes local scan file after processing.
      41
      37 -    Returns: (preview_path, circles, point_count)
      42 +    Returns: (preview_path, circles, point_count, auto_ring)
      43      Raises: IngestError on any failure.
      44      """
      45      file_id = extract_drive_file_id(drive_url)
     ...
      48
      49      config.ensure_data_dirs()
      50
      46 -    # Determine filename suffix
      51      suffix = f".{fmt_hint}" if fmt_hint else ".ply"
      52
      53      with tempfile.NamedTemporaryFile(
     ...
      64          return _process_local_file(tmp_path, scan_id, batch_id)
      65
      66      finally:
      63 -        # Always delete the local scan file — store only derived data
      67          if tmp_path.exists():
      68              try:
      69                  tmp_path.unlink()
     ...
      77      scan_id: int,
      78      batch_id: int,
      79      delete_after: bool = True,
      77 -) -> tuple[Path, list[Circle], int]:
      80 +) -> tuple[Path, list[Circle], int, Circle | None]:
      81      """
      82      Ingest a local scan file (used in testing/sample-report).
      83      Optionally deletes the source file after processing.
     ...
       97      file_path: Path,
       98      scan_id: int,
       99      batch_id: int,
       97 -) -> tuple[Path, list[Circle], int]:
       98 -    """Load → normalize → preview → detect circles. Does NOT delete the file."""
      100 +) -> tuple[Path, list[Circle], int, Circle | None]:
      101 +    """Load → normalize → preview → detect circles → auto-ring → classify orientations."""
      102      logger.info("Processing scan file: %s", file_path.name)
      103
      104      try:
     ...
      112      if point_count == 0:
      113          raise IngestError(f"Scan file {file_path.name} contains no points.")
      114
      112 -    # Render preview PNG
      113 -    # Use 80 % crop so the full apple surface is visible for human annotation.
      114 -    # Circle detection runs on the saved PNG (not the point cloud directly),
      115 -    # so the detector sees the same rich image the operator annotates.
      115 +    # Use 80% crop so the full apple surface is visible for human annotation.
      116      preview_pts = normalize_top_down(points, top_percentile=0.80)
      117
      118      preview_dir = config.DATA_DIR / "previews"
     ...
      123      render_preview(preview_pts, preview_path)
      124      logger.info("Preview saved: %s", preview_path)
      125
      126 -    # Detect circles on the saved preview
      126      circles = detect_circles(preview_path)
      127      logger.info("Detected %d circles", len(circles))
      128
      130 -    return preview_path, circles, point_count
      129 +    # Auto-detect calibration ring from blue channel in the preview.
      130 +    auto_ring = detect_calibration_ring(preview_path)
      131 +    logger.info(
      132 +        "Auto ring detection: %s",
      133 +        (
      134 +            f"cx={auto_ring.cx:.0f} cy={auto_ring.cy:.0f} r={auto_ring.radius_px:.0f} "
      135 +            f"conf={auto_ring.confidence:.2f}"
      136 +        ) if auto_ring else "not found",
      137 +    )
      138
      139 +    # Classify apple orientation from 3D Z-height profile.
      140 +    circles = classify_orientations(circles, preview_pts, preview_width=1024, preview_height=1024)
      141 +    orient_counts = {
      142 +        o: sum(1 for c in circles if c.orientation == o)
      143 +        for o in ("upright", "sideways", "angled", "unknown")
      144 +    }
      145 +    logger.info("Orientation classification: %s", orient_counts)
      146
      147 +    return preview_path, circles, point_count, auto_ring
      148 +
      149 +
      150  def ingest_synthetic(
      151      points: object,
      152      scan_id: int,
      153      batch_id: int,
      137 -) -> tuple[Path, list[Circle], int]:
      154 +) -> tuple[Path, list[Circle], int, Circle | None]:
      155      """Ingest a pre-loaded point cloud array (for sample-report and tests)."""
      156      import numpy as np
      157
     ...
      170
      171      render_preview(normalized, preview_path)
      172      circles = detect_circles(preview_path)
      173 +    auto_ring = detect_calibration_ring(preview_path)
      174 +    circles = classify_orientations(circles, normalized, preview_width=1024, preview_height=1024)
      175
      157 -    return preview_path, circles, point_count
      176 +    return preview_path, circles, point_count, auto_ring

● Task 3C/4E — Update scans.py routes

  Now update _save_scan_results, the review context, and all ingest callers:

  Read 1 file (ctrl+o to expand)

● Write(apple-caliber-scan/apple_caliber_scan/web/routes/scans.py)
  ⎿  Added 34 lines, removed 9 lines
      78      try:
      79          from apple_caliber_scan.services.ingest import ingest_from_drive_url
      80
      81 -        preview_path, circles, point_count = ingest_from_drive_url(
      81 +        preview_path, circles, point_count, auto_ring = ingest_from_drive_url(
      82              drive_url, scan_id=scan_id, batch_id=batch_id, fmt_hint=fmt_hint
      83          )
      84 -        _save_scan_results(scan_id, preview_path, circles, point_count, status="previewed")
      84 +        _save_scan_results(scan_id, preview_path, circles, point_count, auto_ring, status="previewed")
      85
      86      except Exception as e:
      87          logger.error("Ingest failed for scan %d: %s", scan_id, e)
     ...
      148
      149          from apple_caliber_scan.services.ingest import ingest_from_local_file
      150
      151 -        preview_path, circles, point_count = ingest_from_local_file(
      151 +        preview_path, circles, point_count, auto_ring = ingest_from_local_file(
      152              tmp_path, scan_id=scan_id, batch_id=batch_id, delete_after=True
      153          )
      154 -        _save_scan_results(scan_id, preview_path, circles, point_count, status="previewed")
      154 +        _save_scan_results(scan_id, preview_path, circles, point_count, auto_ring, status="previewed")
      155
      156      except Exception as exc:
      157          logger.exception("Upload ingest failed: %s", exc)
     ...
      180      preview_path: Path,
      181      circles: list[Circle],
      182      point_count: int,
      183 +    auto_ring: Circle | None,
      184      status: str,
      185  ) -> None:
      186      preview_rel = str(preview_path.relative_to(config.DATA_DIR / "previews"))
     ...
      192              point_count=point_count,
      193              status=status,
      194          )
      195 +        if auto_ring:
      196 +            update_scan(
      197 +                conn,
      198 +                scan_id,
      199 +                auto_ring_cx_px=auto_ring.cx,
      200 +                auto_ring_cy_px=auto_ring.cy,
      201 +                auto_ring_radius_px=auto_ring.radius_px,
      202 +                auto_ring_confidence=auto_ring.confidence,
      203 +            )
      204          circle_dicts = [
      205              {
      206                  "cx_px": c.cx,
     ...
      209                  "ellipse_major_px": c.ellipse_major_px,
      210                  "ellipse_minor_px": c.ellipse_minor_px,
      211                  "ellipse_angle_deg": c.ellipse_angle_deg,
      212 +                "orientation": c.orientation,
      213                  "confidence": c.confidence,
      214                  "annotated_by": "auto",
      215              }
     ...
      240              "diameter_mm": c["diameter_mm"],
      241              "caliber_class": c["caliber_class"],
      242              "confidence": c["confidence"],
      243 +            "orientation": c["orientation"] if "orientation" in c.keys() else "unknown",
      244          }
      245          for c in circles
      246      ]
     ...
      249      if scan["preview_path"]:
      250          preview_url = f"/previews/{scan['preview_path']}"
      251
      252 +    # Build auto-ring JSON if detection confidence is sufficient.
      253 +    auto_ring_json = None
      254 +    scan_dict = dict(scan)
      255 +    if (
      256 +        scan_dict.get("auto_ring_cx_px")
      257 +        and scan_dict.get("auto_ring_confidence")
      258 +        and scan_dict["auto_ring_confidence"] >= 0.5
      259 +    ):
      260 +        auto_ring_json = {
      261 +            "cx": scan_dict["auto_ring_cx_px"],
      262 +            "cy": scan_dict["auto_ring_cy_px"],
      263 +            "radius": scan_dict["auto_ring_radius_px"],
      264 +            "confidence": scan_dict["auto_ring_confidence"],
      265 +        }
      266 +
      267      return templates.TemplateResponse(
      268          request,
      269          "scan_review.html",
     ...
      273              "circles_json": json.dumps(circles_data),
      274              "preview_url": preview_url,
      275              "ring_mm": scan["calibration_ring_mm"] or 75.0,
      276 +            "auto_ring_json": auto_ring_json,
      277          },
      278      )
      279
     ...
      292          if scan is None:
      293              return JSONResponse({"error": "Scan not found"}, status_code=404)
      294
      267 -        # Update individual circles
      295          for cu in circle_updates:
      296              cid = cu.get("id")
      297              if cid:
     ...
      335                  ring_circle, ring_mm=ring_mm, apple_circles=apple_circles
      336              )
      337
      311 -            # Update circles with mm diameters using caliber_diameter_px (ellipse-aware)
      338              for r, ac in zip(apple_rows, apple_circles):
      339                  d_mm = ac.caliber_diameter_px * scale_result.scale_factor_mm_per_px
      340                  update_circle(
     ...
      376      if not drive_url:
      377          return HTMLResponse("Brak zapisanego URL Drive dla tego skanu.", status_code=400)
      378
      353 -    # Clear previous circles and preview so stale data is not mixed in
      379      with db_conn() as conn:
      380          delete_scan_circles(conn, scan_id)
      381          update_scan(conn, scan_id, status="pending", error_message=None)
     ...
      383      try:
      384          from apple_caliber_scan.services.ingest import ingest_from_drive_url
      385
      361 -        preview_path, circles, point_count = ingest_from_drive_url(
      386 +        preview_path, circles, point_count, auto_ring = ingest_from_drive_url(
      387              drive_url, scan_id=scan_id, batch_id=batch_id, fmt_hint=fmt_hint
      388          )
      364 -        _save_scan_results(scan_id, preview_path, circles, point_count, status="previewed")
      389 +        _save_scan_results(scan_id, preview_path, circles, point_count, auto_ring, status="previewed")
      390      except Exception as e:
      391          logger.error("Re-ingest failed for scan %d: %s", scan_id, e)
      392          with db_conn() as conn:

● Now check if insert_circles and update_scan support the new fields:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "def insert_circles\|def
      update_scan" apple_caliber_scan/database/crud.py)
  ⎿  2 matches in 2F:

     [file] 102 (1):
     … +4 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && sed -n '100,145p'
      apple_caliber_scan/database/crud.py)
  ⎿  def update_scan(conn: sqlite3.Connection, scan_id: int, **kwargs: Any) -> None:
         if not kwargs:
             return
     … +38 lines (ctrl+o to expand)

● Need to update insert_circles to include orientation:

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/database/crud.py)
  ⎿  Added 4 lines, removed 2 lines
      121      conn.executemany(
      122          """INSERT INTO scan_circles
      123             (scan_id, cx_px, cy_px, radius_px, ellipse_major_px, ellipse_minor_px,
      124 -            ellipse_angle_deg, confidence, annotated_by)
      124 +            ellipse_angle_deg, orientation, confidence, annotated_by)
      125             VALUES (:scan_id, :cx_px, :cy_px, :radius_px, :ellipse_major_px,
      126 -                   :ellipse_minor_px, :ellipse_angle_deg, :confidence, :annotated_by)""",
      126 +                   :ellipse_minor_px, :ellipse_angle_deg, :orientation,
      127 +                   :confidence, :annotated_by)""",
      128          [
      129              {
      130                  "scan_id": scan_id,
      131                  "ellipse_major_px": 0.0,
      132                  "ellipse_minor_px": 0.0,
      133                  "ellipse_angle_deg": 0.0,
      134 +                "orientation": "unknown",
      135                  **c,
      136              }
      137              for c in circles

● Task 3D — Update scan_review.html with auto-ring banner and JS data

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/templates/scan_review.html)
  ⎿  Added 9 lines
      12    Przeciągnij krawędź, aby zmienić rozmiar. Dwukrotne kliknięcie pustego obszaru dodaje nowy okrąg.
      13  </div>
      14
      15 +{% if auto_ring_json %}
      16 +<div class="alert alert-success alert-dismissible fade show" role="alert">
      17 +  <strong>Pierścień kalibracyjny wykryty automatycznie</strong>
      18 +  (pewność: {{ "%.0f"|format(auto_ring_json.confidence * 100) }}%).
      19 +  Sprawdź poprawność zaznaczenia przed zatwierdzeniem.
      20 +  <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      21 +</div>
      22 +{% endif %}
      23 +
      24  <div class="row">
      25    <div class="col-lg-8">
      26      <div class="card p-2">

● Update(apple-caliber-scan/apple_caliber_scan/web/templates/scan_review.html)
  ⎿  Added 1 line
       95  const BATCH_ID = {{ batch.id }};
       96  const ANNOTATE_URL = "/batches/" + BATCH_ID + "/scans/" + SCAN_ID + "/annotate";
       97  const REPORT_URL = "/batches/" + BATCH_ID + "/scans/" + SCAN_ID + "/report";
       98 +const AUTO_RING = {{ auto_ring_json | tojson | safe }};
       99  </script>
      100  <script src="/static/review.js"></script>
      101  {% endblock %}

● Task 4F — Update review.js with applyAutoRing and orientation label

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/static/review.js)
  ⎿  Added 45 lines
      37      return "90+";
      38    }
      39
      40 +  function orientationLabel(o) {
      41 +    return { upright: "pionowo", sideways: "na boku", angled: "ukośnie" }[o] || "—";
      42 +  }
      43 +
      44 +  function showToast(msg) {
      45 +    const t = document.createElement("div");
      46 +    t.textContent = msg;
      47 +    t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a5c2
         +e;color:#fff;padding:8px 18px;border-radius:6px;z-index:9999;font-size:14px;";
      48 +    document.body.appendChild(t);
      49 +    setTimeout(() => t.remove(), 4000);
      50 +  }
      51 +
      52 +  function applyAutoRing() {
      53 +    if (!AUTO_RING) return;
      54 +    const alreadyRinged = circles.some((c) => c.is_ring);
      55 +    if (alreadyRinged) return;
      56 +
      57 +    let best = null, bestDist = Infinity;
      58 +    for (const c of circles) {
      59 +      const d = Math.hypot(c.cx - AUTO_RING.cx, c.cy - AUTO_RING.cy);
      60 +      if (d < bestDist) { bestDist = d; best = c; }
      61 +    }
      62 +
      63 +    if (best && bestDist < AUTO_RING.radius * 1.5) {
      64 +      best.is_ring = true;
      65 +      showToast(`Pierścień wykryty automatycznie (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`
         +);
      66 +    } else {
      67 +      circles.push({
      68 +        id: null,
      69 +        cx: AUTO_RING.cx,
      70 +        cy: AUTO_RING.cy,
      71 +        radius: AUTO_RING.radius,
      72 +        is_ring: true,
      73 +        is_excluded: false,
      74 +        diameter_mm: null,
      75 +        caliber_class: null,
      76 +        confidence: AUTO_RING.confidence,
      77 +        orientation: "unknown",
      78 +      });
      79 +      showToast(`Pierścień dodany automatycznie (pewność ${(AUTO_RING.confidence * 100).toFixed(0)}%)`)
         +;
      80 +    }
      81 +    computeScale();
      82 +    drawAll();
      83 +  }
      84 +
      85    // ── Image layer ────────────────────────────────────────────────────────────
      86
      87    function drawImageLayer() {

● Now add orientation to the circle label in drawAnnotations and call applyAutoRing on init:

● Update(apple-caliber-scan/apple_caliber_scan/web/static/review.js)
  ⎿  Added 2 lines, removed 1 line
      250
      251        if (scaleFactor && !c.is_ring && !c.is_excluded) {
      252          const d = c.radius * 2 * scaleFactor;
      253 +        const orient = c.orientation ? ` · ${orientationLabel(c.orientation)}` : "";
      254          ctx.fillStyle = "#fff";
      255          ctx.font = "10px sans-serif";
      255 -        ctx.fillText(`${d.toFixed(0)}mm`, c.cx - 18, c.cy);
      256 +        ctx.fillText(`${d.toFixed(0)}mm${orient}`, c.cx - 18, c.cy);
      257        }
      258      });
      259

● Update(apple-caliber-scan/apple_caliber_scan/web/static/review.js)
  ⎿  Added 4 lines
      507
      508    // Init
      509    loadImage();
      510 +  // Apply auto-ring after image loads (deferred so circles are drawn first)
      511 +  if (typeof AUTO_RING !== "undefined" && AUTO_RING) {
      512 +    setTimeout(applyAutoRing, 200);
      513 +  }
      514  })();

● Task 4G — reporting.py + report_pl.html

● Update(apple-caliber-scan/apple_caliber_scan/services/reporting.py)
  ⎿  File must be read first

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/services/reporting.py)
  ⎿  Added 2 lines
      57      has_ground_truth: bool,
      58      ground_truth_rows: list[dict[str, Any]] | None = None,
      59      sideways_count: int = 0,
      60 +    orientation_counts: dict[str, int] | None = None,
      61  ) -> dict[str, Any]:
      62      generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
      63      above_75 = distribution.above_75_share
     ...
      93          "generated_at": generated_at,
      94          "legal_clause": LEGAL_CLAUSE,
      95          "sideways_count": sideways_count,
      96 +        "orientation_counts": orientation_counts,
      97      }
      98
      99

● Now update generate_report in reports.py to compute and pass orientation_counts:

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/routes/reports.py)
  ⎿  Added 4 lines
      58
      59      distribution = CaliberDistribution()
      60      sideways_count = 0
      61 +    orientation_counts: dict[str, int] = {o: 0 for o in ("upright", "sideways", "angled", "unknown")}
      62      for c in apple_circles:
      63          major = c["ellipse_major_px"] or 0.0
      64          minor = c["ellipse_minor_px"] or 0.0
      65          if major > 0 and minor > 0 and (major / minor) > 1.25:
      66              sideways_count += 1
      67 +        orient = c["orientation"] if "orientation" in c.keys() else "unknown"
      68 +        orientation_counts[orient or "unknown"] = orientation_counts.get(orient or "unknown", 0) + 1
      69          if c["caliber_class"]:
      70              distribution.add(c["caliber_class"])
      71          elif c["diameter_mm"]:
     ...
      89          has_ground_truth=has_gt,
      90          ground_truth_rows=gt_rows,
      91          sideways_count=sideways_count,
      92 +        orientation_counts=orientation_counts,
      93      )
      94
      95      reports_dir = config.DATA_DIR / "reports"

● Now add orientation breakdown to report_pl.html:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && sed -n '130,145p'
      apple_caliber_scan/web/templates/report_pl.html)
  ⎿          <td>100%</td>
           </tr>
         </tbody>
     … +13 lines (ctrl+o to expand)

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/templates/report_pl.html)
  ⎿  Added 12 lines
      139    </p>
      140    {% endif %}
      141
      142 +  {% if orientation_counts %}
      143 +  <p class="sideways-note">
      144 +    Orientacja jabłek:
      145 +    pionowo <strong>{{ orientation_counts.get('upright', 0) }}</strong> szt. ·
      146 +    na boku <strong>{{ orientation_counts.get('sideways', 0) }}</strong> szt. ·
      147 +    ukośnie <strong>{{ orientation_counts.get('angled', 0) }}</strong> szt.
      148 +    {% if orientation_counts.get('angled', 0) > 0 %}
      149 +    — <em>jabłka ukośne mogą mieć niedoszacowany kaliber</em>
      150 +    {% endif %}
      151 +  </p>
      152 +  {% endif %}
      153 +
      154    <!-- Full-batch projection -->
      155    <div class="section-title">
      156      Projekcja pełnej partii

● Task 9 — Write all tests

● Write(apple-caliber-scan/tests/test_normalizer.py)
  ⎿  Wrote 67 lines to apple-caliber-scan/tests/test_normalizer.py
       1 """Tests for normalizer.py — aspect ratio preservation."""
       2
       3 import numpy as np
       4 import pytest
       5
       6 from apple_caliber_scan.scan.normalizer import normalize_top_down
       7
       8
       9 def test_aspect_ratio_preserved():
      10     """A circle in 3D space must project to a circle in 2D, not an ellipse."""
     … +57 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && ls tests/test_preview.py 2>/dev/null && head
       -5 tests/test_preview.py || echo "NEW")
  ⎿  NEW

● Write(apple-caliber-scan/tests/test_preview.py)
  ⎿  Wrote 88 lines to apple-caliber-scan/tests/test_preview.py
       1 """Tests for preview.py — colour rendering and blue ring preservation."""
       2
       3 import tempfile
       4 from pathlib import Path
       5
       6 import numpy as np
       7 import pytest
       8 from PIL import Image
       9
      10 from apple_caliber_scan.scan.preview import render_preview
     … +78 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && head -5 tests/test_detector.py)
  ⎿  Error: Exit code 1
     cat: tests/test_detector.py: No such file or directory (os error 2)

● Write(apple-caliber-scan/tests/test_detector.py)
  ⎿  Wrote 117 lines to apple-caliber-scan/tests/test_detector.py
       1 """Tests for detector.py — calibration ring detection and orientation classification."""
       2
       3 import tempfile
       4 from pathlib import Path
       5
       6 import cv2
       7 import numpy as np
       8 import pytest
       9
      10 from apple_caliber_scan.scan.detector import (
     … +107 lines (ctrl+o to expand)

● Now run the full test suite:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m pytest tests/ -x -q 2>&1
       | tail -40)
  ⎿          """A single point cloud must not crash."""
             pts = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
     >       norm = normalize_top_down(pts)
     … +24 lines (ctrl+o to expand)

● The single-point PCA crashes. Fix the normalizer to guard against degenerate inputs:

● Update(apple-caliber-scan/apple_caliber_scan/scan/normalizer.py)
  ⎿  Added 1 line, removed 1 line
      21        2. Crop to top `top_percentile` of the Z range (visible top layer).
      22        3. Normalise XY to [0, 1] and Z to [0, 1].
      23      """
      24 -    if len(points) == 0:
      24 +    if len(points) < 3:
      25          return points.astype(np.float32)
      26
      27      has_color = points.shape[1] >= 6

● Update(apple-caliber-scan/tests/test_normalizer.py)
  ⎿  Added 1 line, removed 1 line
      49
      50
      51  def test_degenerate_single_point():
      52 -    """A single point cloud must not crash."""
      52 +    """Fewer than 3 points must not crash — returned as-is."""
      53      pts = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
      54      norm = normalize_top_down(pts)
      55      assert norm.shape[0] == 1

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m pytest tests/ -x -q 2>&1
       | tail -30)
  ⎿  ........................................................................ [ 91%]
     .......                                                                  [100%]
     =============================== warnings summary ===============================
     … +7 lines (ctrl+o to expand)

● 79 passed (up from 65 baseline). Now run lint:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check
      apple_caliber_scan/ tests/ 2>&1 | head -30)
  ⎿  F401 [*] `dataclasses.field` imported but unused
      --> apple_caliber_scan/scan/detector.py:6:36
       |
     … +29 lines (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/scan/detector.py)
  ⎿  Added 1 line, removed 1 line
      3  from __future__ import annotations
      4
      5  import logging
      6 -from dataclasses import dataclass, field
      6 +from dataclasses import dataclass
      7  from pathlib import Path
      8
      9  import cv2

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check
      apple_caliber_scan/ tests/ 2>&1 | grep -v "loader.py\|batche…)
  ⎿  E501 Line too long (101 > 100)
         |
     124 |         mi = json.loads(zf.read("mesh_info.json"))
     … +18 lines (ctrl+o to expand)

● Both remaining E501s are in pre-existing files I didn't touch. My changes are lint-clean:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check
      apple_caliber_scan/scan/detector.py apple_caliber_scan/scan/…)
  ⎿  Error: Exit code 1
     E501 Line too long (101 > 100)
       --> apple_caliber_scan/web/routes/reports.py:61:101
        |
     59 |     distribution = CaliberDistribution()
     60 |     sideways_count = 0
     61 |     orientation_counts: dict[str, int] = {o: 0 for o in ("upright", "sideways", "angled", "unknown")}
        |                                                                                                     ^
     62 |     for c in apple_circles:
     63 |         major = c["ellipse_major_px"] or 0.0
     … +133 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check --fix
      apple_caliber_scan/web/routes/scans.py tests/test_dete…)
  ⎿  Error: Exit code 1
     E501 Line too long (102 > 100)
       --> apple_caliber_scan/web/routes/scans.py:83:101
        |
     81 |             drive_url, scan_id=scan_id, batch_id=batch_id, fmt_hint=fmt_hint
     82 |         )
     83 |         _save_scan_results(scan_id, preview_path, circles, point_count, auto_ring, status="previewed")
        |                                                                                                     ^^
     84 |
     85 |     except Exception as e:
     … +46 lines (ctrl+o to expand)

● Fix the remaining E501 violations in my files:

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/routes/reports.py)
  ⎿  Added 3 lines, removed 1 line
      58
      59      distribution = CaliberDistribution()
      60      sideways_count = 0
      61 -    orientation_counts: dict[str, int] = {o: 0 for o in ("upright", "sideways", "angled", "unknown")}
      61 +    orientation_counts: dict[str, int] = {
      62 +        o: 0 for o in ("upright", "sideways", "angled", "unknown")
      63 +    }
      64      for c in apple_circles:
      65          major = c["ellipse_major_px"] or 0.0
      66          minor = c["ellipse_minor_px"] or 0.0

  Read 1 file (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && sed -i 's/
      _save_scan_results(scan_id, preview_path, circles, point_count, auto_ring…)
  ⎿  (No output)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check
      apple_caliber_scan/web/routes/scans.py apple_caliber_scan/we…)
  ⎿  Error: Exit code 1
     E501 Line too long (121 > 100)
        --> apple_caliber_scan/web/routes/scans.py:129:101
         |
     127 |             request,
     128 |             "scan_drive.html",
     129 |             {"batch": batch, "error": f"Nieobsługiwany format pliku: {suffix}. Dozwolone: {',
     '.join(sorted(allowed))}"},
         |
     ^^^^^^^^^^^^^^^^^^^^^
     130 |         )
         |
     … +13 lines (ctrl+o to expand)

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/apple_caliber_scan/web/routes/scans.py)
  ⎿  Added 4 lines, removed 1 line
      126          return templates.TemplateResponse(
      127              request,
      128              "scan_drive.html",
      129 -            {"batch": batch, "error": f"Nieobsługiwany format pliku: {suffix}. Dozwolone: {', '.join(s
          -orted(allowed))}"},
      129 +            {"batch": batch, "error": (
      130 +                f"Nieobsługiwany format pliku: {suffix}. "
      131 +                f"Dozwolone: {', '.join(sorted(allowed))}"
      132 +            )},
      133          )
      134
      135      config.ensure_data_dirs()

  Read 1 file (ctrl+o to expand)

● Update(apple-caliber-scan/tests/test_detector.py)
  ⎿  Added 2 lines, removed 1 line
      32          assert result is not None, "Ring not detected"
      33          assert abs(result.cx - cx) < r * 0.15, f"cx off by {abs(result.cx - cx):.1f}px"
      34          assert abs(result.cy - cy) < r * 0.15, f"cy off by {abs(result.cy - cy):.1f}px"
      35 -        assert abs(result.radius_px - r) < r * 0.20, f"radius off by {abs(result.radius_px - r):.1f}px"
      35 +        err_r = abs(result.radius_px - r)
      36 +        assert err_r < r * 0.20, f"radius off by {err_r:.1f}px"
      37      finally:
      38          path.unlink(missing_ok=True)
      39

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m ruff check
      apple_caliber_scan/web/routes/scans.py apple_caliber_scan/we…)
  ⎿  All checks passed!

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -m pytest tests/ -q 2>&1 |
      tail -10)
  ⎿  ........................................................................ [ 91%]
     .......                                                                  [100%]
     =============================== warnings summary ===============================
     … +7 lines (ctrl+o to expand)

● 79/79 pass. Now run the DB migrations and cleanup (Task 5):

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -c "
      from apple_caliber_scan.database.connection import initialize_schema,…)
  ⎿  Schema migrations applied.
     Current batches:
       Batch 1: Jan Kowalski (0 scans)
     … +12 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -c "
      from apple_caliber_scan.database.connection import db_conn…)
  ⎿  Remaining batches: [(2, 'Test Terenowy')]
     Remaining scans: [(4, 2, 'previewed')]

● DB is clean. Now delete stale preview files:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && .venv/bin/python -c "
      from pathlib import Path…)
  ⎿  Preview files found: ['scan_3_batch_2.png', 'scan_4_batch_2.png', 'scan_5_batch_5.png', 'scan_6_batch_6.png',
     'scan_999_batch_999.png']
     Deleted: scan_3_batch_2.png
     … +4 lines (ctrl+o to expand)

● Now check that __init__.py callers of ingest_synthetic are updated for the new 4-tuple return:

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep
      "ingest_from_local_file\|ingest_synthetic\|ingest_from_drive" apple_caliber_scan/_…)
  ⎿  0 matches for 'ingest_from_local_file\|ingest_synthetic\|ingest_from_drive'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "preview_path, circles,
      point_count" apple_caliber_scan/ -r | head -20)
  ⎿  9 matches in 2F:

     [file] apple_caliber_scan/services/ingest.py (3):
     … +11 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep
      "ingest_synthetic\|ingest_from_local_file\|ingest_from_drive_url" apple_caliber_sc…)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from_local_file\|ingest_from_drive_url'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "ingest_synthetic\|ingest_from"
      tests/ -r | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && cat tests/test_ingest.py | head -50)
  ⎿  """Synthetic ingest pipeline tests."""

     from __future__ import annotations
     … +39 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest_synthetic\|ingest_from"
      tests/test_ingest.py | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -rn
      "ingest_synthetic\|ingest_from_local\|ingest_from_drive" . --include="*.py" | grep…)
  ⎿  No matches found

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest_synthetic\|ingest_from"
      apple_caliber_scan/__init__.py | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest"
      apple_caliber_scan/__init__.py | head -20)
  ⎿  0 matches for 'ingest'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n
      "preview_path.*circles.*point_count\|point_count.*circles.*preview_path" apple_cali…)
  ⎿  0 matches for 'preview_path.*circles.*point_count\|point_count.*circles.*preview_path'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep
      "ingest_from_local_file\|ingest_synthetic\|ingest_from_drive" apple_caliber_scan/_…)
  ⎿  0 matches for 'ingest_from_local_file\|ingest_synthetic\|ingest_from_drive'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "preview_path, circles,
      point_count" apple_caliber_scan/ -r | head -20)
  ⎿  9 matches in 2F:

     [file] apple_caliber_scan/services/ingest.py (3):
     … +11 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep
      "ingest_synthetic\|ingest_from_local_file\|ingest_from_drive_url" apple_caliber_sc…)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from_local_file\|ingest_from_drive_url'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && rtk grep "ingest_synthetic\|ingest_from"
      tests/ -r | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && cat tests/test_ingest.py | head -50)
  ⎿  """Synthetic ingest pipeline tests."""

     from __future__ import annotations
     … +45 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest_synthetic\|ingest_from"
      tests/test_ingest.py | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -rn
      "ingest_synthetic\|ingest_from_local\|ingest_from_drive" . --include="*.py" | grep…)
  ⎿  No matches found

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest_synthetic\|ingest_from"
      apple_caliber_scan/__init__.py | head -20)
  ⎿  0 matches for 'ingest_synthetic\|ingest_from'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "ingest" apple_caliber_scan/__init__.py | head -20)
  ⎿  0 matches for 'ingest'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "preview_path.*circles.*point_count\|point_count.*circles.*preview_path" apple_cali…)
  ⎿  0 matches for 'preview_path.*circles.*point_count\|point_count.*circles.*preview_path'

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && grep -n "preview_path\|circles\|point_count" apple_caliber_scan/__init__.py | head -20)
  ⎿  14 matches in 6F:

     [file] 100 (1):
     … +17 lines (ctrl+o to expand)

● Bash(cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan && sed -n '85,200p' apple_caliber_scan/__init__.py)
  ⎿      from apple_caliber_scan.services.reporting import (
             build_report_context,
             generate_html_report,
     … +80 lines (ctrl+o to expand)
  ⎿  You've hit your limit · resets 2:50am (Europe/Warsaw)
     /upgrade or /extra-usage to finish what you’re working on.

✻ Brewed for 9m 10s

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  This session is 17h 52m old and 160.6k tokens.

  Resuming the full session will consume a substantial portion of your usage limits. We recommend resuming from a summary.

  ❯ 1. Resume from summary (recommended)
    2. Resume full session as-is
    3. Don't ask me again

  Enter to confirm · Esc to cancel