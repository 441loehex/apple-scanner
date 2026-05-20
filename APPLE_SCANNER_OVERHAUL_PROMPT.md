# Apple Scanner — Complete System Overhaul

## Mission

You are implementing a complete overhaul of the apple-caliber-scan project.
This is not a patch session. Every issue must be solved permanently and completely.
Do not offer workarounds. Do not defer tasks. Ship the finished product.

---

## Context

**Project root:** `/mnt/c/Users/balce/Downloads/apple scanner/apple-caliber-scan/`
**Python venv:** `apple-caliber-scan/.venv/` (always activate before running Python)
**Test scan ZIP:** `/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip`

This is a FastAPI web app that ingests 3D scans (iPhone LiDAR via Polycam),
renders a top-down 2D preview PNG, runs Hough circle detection on apples,
lets an operator annotate which circle is the calibration ring,
and generates a caliber-distribution PDF report.

**Critical files:**
```
apple_caliber_scan/
  scan/
    loader.py          ← load PLY / mesh → numpy array
    normalizer.py      ← PCA rotation + crop to top layer
    preview.py         ← render (N,6) point cloud → PNG
    detector.py        ← Hough circle detection on PNG
  services/
    ingest.py          ← full pipeline: file → preview + circles
    calibration.py     ← ring circle → mm/px scale factor
    reporting.py       ← caliber distribution + PDF
  web/
    routes/scans.py    ← Drive URL form, reingest, annotation review
    templates/
      scan_drive.html  ← form for Drive URL + ring_mm
      scan_review.html ← annotation canvas + detected circles
    static/
      review.js        ← canvas annotation JavaScript
  storage/
    drive.py           ← gdown-based Google Drive download
```

**Data format key facts (verified from 17_05_2026.zip):**
- Polycam "Raw" export ZIP contains: `keyframes/images/*.jpg` (RGB, 1024×768),
  `keyframes/depth/*.png` (uint16, 256×192, 1 unit = 1 mm),
  `keyframes/confidence/*.png` (uint8, values: 0=none, 54=medium, 255=high),
  `keyframes/cameras/*.json` (camera intrinsics + pose), `mesh_info.json`
- Camera JSON fields: `fx, fy, cx, cy` (in RGB-image resolution), `width=1024, height=768`,
  `t_RC` fields for 3×4 camera-to-world transform where R=row, C=col (t_00 to t_23)
- Depth scale: **1 uint16 unit = 1 mm** (verified: center_depth=0.170 m, center pixel=167)
- Confidence: use pixels where `conf >= 54` (medium or high)
- `mesh_info.json` contains `alignmentTransform`: 16 floats, column-major 4×4 homogeneous matrix

---

## Task 1: Polycam Raw ZIP → Colored Point Cloud (CRITICAL BLOCKER)

**Why:** The root cause of every preview quality problem is that the code only ever
had a PLY from Polycam's paid-export tier. The user's raw ZIP already contains
all RGB + LiDAR depth data needed to reconstruct a fully colored point cloud
without a subscription. Implement this and the preview quality problem is solved.

### 1a. Add `load_polycam_raw_zip()` to `apple_caliber_scan/scan/loader.py`

Append after the existing `load_scan()` function. Do NOT modify existing functions.

```python
def load_polycam_raw_zip(
    zip_path: Path,
    min_confidence: int = 54,
    max_depth_m: float = 5.0,
    subsample: int = 1,
) -> np.ndarray:
    """
    Reconstruct colored (N, 6) float32 point cloud from a Polycam 'Raw' export ZIP.

    Depth scale: 1 uint16 unit = 1 mm (verified from center_depth field).
    Confidence thresholds: 0=none, 54=medium, 255=high.
    Returns (N, 6) array: [X_world, Y_world, Z_world, R, G, B] in world coordinates.
    R/G/B are float32 values in [0, 255].

    Args:
        zip_path: Path to the Polycam raw export .zip file.
        min_confidence: Minimum confidence value to include a pixel (default 54 = medium+).
        max_depth_m: Maximum depth in metres to include (default 5.0 m).
        subsample: Take every Nth frame (1 = all frames, 2 = every other, etc.).
    """
    import io
    import json
    import zipfile

    zf = zipfile.ZipFile(str(zip_path))
    nameset = set(zf.namelist())

    # Collect camera files sorted by timestamp
    cam_files = sorted(
        [f for f in nameset if f.startswith("keyframes/cameras/") and f.endswith(".json")]
    )
    if not cam_files:
        raise ValueError(f"No camera files found in {zip_path.name}. Is this a Polycam Raw export?")

    # Optional: load alignment transform from mesh_info.json (gravity-aligned Y-up)
    align_mat = None
    if "mesh_info.json" in nameset:
        mi = json.loads(zf.read("mesh_info.json"))
        if "alignmentTransform" in mi:
            align_mat = np.array(mi["alignmentTransform"], dtype=np.float64).reshape(4, 4, order="F")

    all_points: list[np.ndarray] = []
    all_colors: list[np.ndarray] = []

    for idx, cam_file in enumerate(cam_files):
        if subsample > 1 and idx % subsample != 0:
            continue

        ts = cam_file.split("/")[-1].replace(".json", "")
        depth_file = f"keyframes/depth/{ts}.png"
        image_file = f"keyframes/images/{ts}.jpg"
        conf_file = f"keyframes/confidence/{ts}.png"

        if depth_file not in nameset or image_file not in nameset:
            continue

        cam = json.loads(zf.read(cam_file))

        # Camera intrinsics are given at RGB resolution (1024×768)
        fx_rgb = float(cam["fx"])
        fy_rgb = float(cam["fy"])
        cx_rgb = float(cam["cx"])
        cy_rgb = float(cam["cy"])
        rgb_w = int(cam.get("width", 1024))
        rgb_h = int(cam.get("height", 768))

        # Load depth image (uint16, 256×192, 1 unit = 1 mm)
        from PIL import Image  # deferred import
        depth_arr = np.array(Image.open(io.BytesIO(zf.read(depth_file))), dtype=np.float32)
        d_h, d_w = depth_arr.shape[:2]

        # Scale intrinsics from RGB resolution down to depth image resolution
        sx = d_w / rgb_w
        sy = d_h / rgb_h
        fx = fx_rgb * sx
        fy = fy_rgb * sy
        cx_d = cx_rgb * sx
        cy_d = cy_rgb * sy

        # Confidence mask
        if conf_file in nameset:
            conf_arr = np.array(Image.open(io.BytesIO(zf.read(conf_file))), dtype=np.uint8)
        else:
            conf_arr = np.full((d_h, d_w), 255, dtype=np.uint8)

        # Build validity mask
        depth_m = depth_arr / 1000.0  # mm → metres
        valid = (conf_arr >= min_confidence) & (depth_m > 0.05) & (depth_m < max_depth_m)

        v_idx, u_idx = np.where(valid)
        if len(v_idx) == 0:
            continue

        d = depth_m[v_idx, u_idx]

        # Unproject to camera space: X = (u - cx) * d / fx
        x_cam = (u_idx.astype(np.float64) - cx_d) * d / fx
        y_cam = (v_idx.astype(np.float64) - cy_d) * d / fy
        z_cam = d.astype(np.float64)

        # Camera-to-world 4×4 transform from t_RC fields
        T = np.array(
            [
                [cam["t_00"], cam["t_01"], cam["t_02"], cam["t_03"]],
                [cam["t_10"], cam["t_11"], cam["t_12"], cam["t_13"]],
                [cam["t_20"], cam["t_21"], cam["t_22"], cam["t_23"]],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        pts_cam = np.stack([x_cam, y_cam, z_cam, np.ones_like(z_cam)], axis=1)  # N×4
        pts_world = (T @ pts_cam.T).T[:, :3]  # N×3

        # Optionally apply alignment transform (gravity-aligned world)
        if align_mat is not None:
            pts_h = np.column_stack([pts_world, np.ones(len(pts_world))])
            pts_world = (align_mat @ pts_h.T).T[:, :3]

        # Sample RGB from high-res image at scaled coordinates
        rgb_img = np.array(Image.open(io.BytesIO(zf.read(image_file))))
        rgb_u = np.clip((u_idx / sx).astype(np.int32), 0, rgb_w - 1)
        rgb_v = np.clip((v_idx / sy).astype(np.int32), 0, rgb_h - 1)
        colors = rgb_img[rgb_v, rgb_u].astype(np.float32)  # N×3, values 0–255

        all_points.append(pts_world.astype(np.float32))
        all_colors.append(colors)

    if not all_points:
        return np.zeros((0, 6), dtype=np.float32)

    points = np.vstack(all_points)   # (N, 3)
    colors = np.vstack(all_colors)   # (N, 3)
    return np.column_stack([points, colors]).astype(np.float32)
```

Then update `load_scan()` at the bottom to handle ZIP files:

```python
def load_scan(path: Path) -> np.ndarray:
    """Auto-detect format and load point cloud. Returns (N, 3) or (N, 6) float32."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return load_polycam_raw_zip(path)
    elif suffix == ".ply":
        return load_ply(path)
    elif suffix in (".obj", ".glb", ".gltf"):
        return load_mesh(path)
    elif suffix in (".usdz", ".usd"):
        logger.warning("USDZ/USD loading not supported — returning empty cloud.")
        return np.zeros((0, 3), dtype=np.float32)
    elif suffix in (".las", ".laz"):
        logger.warning("LAS preview unavailable — install laspy. Returning empty cloud.")
        return np.zeros((0, 3), dtype=np.float32)
    else:
        raise ValueError(f"Unsupported scan format: {suffix}")
```

### 1b. Add `ingest_from_local_zip()` to `apple_caliber_scan/services/ingest.py`

Add after `ingest_from_local_file()`:

```python
def ingest_from_local_zip(
    zip_path: Path,
    scan_id: int,
    batch_id: int,
    delete_after: bool = False,
) -> tuple[Path, list[Circle], int]:
    """
    Ingest a Polycam raw export ZIP file from the local filesystem.
    Reconstructs colored point cloud, renders preview, detects circles.
    """
    if not zip_path.exists():
        raise IngestError(f"ZIP file not found: {zip_path}")

    config.ensure_data_dirs()

    try:
        return _process_local_file(zip_path, scan_id, batch_id)
    finally:
        if delete_after and zip_path.exists():
            try:
                zip_path.unlink()
                logger.info("Deleted local ZIP after ingest: %s", zip_path)
            except OSError as e:
                logger.warning("Could not delete %s: %s", zip_path, e)
```

### 1c. Add file-upload route to `apple_caliber_scan/web/routes/scans.py`

Add the following imports at the top of the file (after existing imports):

```python
import shutil
import tempfile

from fastapi import File, Form, UploadFile
```

Add this route after `scan_attach`:

```python
@router.post("/batches/{batch_id}/scan/upload")
@require_login
async def scan_upload_file(
    request: Request,
    batch_id: int,
    file: UploadFile = File(...),
    ring_mm_str: str = Form("75"),
):
    """Accept direct file upload (ZIP or PLY). Ingest immediately."""
    try:
        ring_mm = float(ring_mm_str)
    except ValueError:
        ring_mm = 75.0

    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
    if batch is None:
        return HTMLResponse("Partia nie znaleziona.", status_code=404)

    suffix = Path(file.filename or "upload").suffix.lower() or ".zip"
    allowed = {".zip", ".ply", ".obj", ".glb"}
    if suffix not in allowed:
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": f"Nieobsługiwany format pliku: {suffix}. Dozwolone: {', '.join(allowed)}"},
        )

    config.ensure_data_dirs()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=str(config.DATA_DIR)) as tf:
        tmp_path = Path(tf.name)

    try:
        # Stream upload to temp file
        with tmp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        with db_conn() as conn:
            scan_id = create_scan(
                conn, batch_id,
                drive_url=None,
                drive_file_id=None,
                fmt=suffix.lstrip("."),
                calibration_ring_mm=ring_mm,
            )

        from apple_caliber_scan.services.ingest import ingest_from_local_file

        preview_path, circles, point_count = ingest_from_local_file(
            tmp_path, scan_id=scan_id, batch_id=batch_id, delete_after=True
        )

        _save_scan_results(scan_id, preview_path, circles, point_count, status="previewed")

    except Exception as exc:
        logger.exception("Upload ingest failed: %s", exc)
        with db_conn() as conn:
            update_scan(conn, scan_id, status="error", error_message=str(exc))
        with db_conn() as conn:
            batch = get_batch(conn, batch_id)
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": f"Błąd przetwarzania pliku: {exc}"},
        )
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return RedirectResponse(url=f"/batches/{batch_id}/scans/{scan_id}/review", status_code=303)
```

Also update `create_scan()` in `crud.py` to allow `drive_url=None` and `drive_file_id=None`
(check that the SQL INSERT handles NULL for those columns — if not, add default `NULL` handling).

### 1d. Add file upload form to `scan_drive.html`

In the template, add a second form panel below the existing Google Drive form:

```html
<div class="mt-6 border-t pt-6">
  <h3 class="font-semibold text-gray-700 mb-3">LUB: Prześlij plik lokalny</h3>
  <form method="post" action="/batches/{{ batch.id }}/scan/upload"
        enctype="multipart/form-data" class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700">
        Plik ZIP (Polycam Raw) lub PLY / OBJ / GLB
      </label>
      <input type="file" name="file" accept=".zip,.ply,.obj,.glb"
             required
             class="mt-1 block w-full border border-gray-300 rounded px-3 py-2 text-sm" />
      <p class="text-xs text-gray-500 mt-1">
        Polycam: Eksport → Raw → Pobierz ZIP. Następnie prześlij tutaj.
      </p>
    </div>
    <input type="hidden" name="ring_mm_str" value="{{ batch.calibration_ring_mm | default('75') }}" />
    <button type="submit"
            class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 text-sm">
      Prześlij i przetwórz
    </button>
  </form>
</div>
```

### 1e. Verify the ZIP ingestion end-to-end

Run in the venv:

```bash
cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan
source .venv/bin/activate
python3 -c "
from pathlib import Path
from apple_caliber_scan.scan.loader import load_polycam_raw_zip
pts = load_polycam_raw_zip(Path('/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip'))
print('Shape:', pts.shape)        # expect (N, 6)
print('Z range (m):', pts[:,2].min(), 'to', pts[:,2].max())
print('R mean:', pts[:,3].mean(), 'G mean:', pts[:,4].mean(), 'B mean:', pts[:,5].mean())
"
```

Expected: shape (N, 6) with N > 100,000, Z range roughly 0–2m, RGB means look like real outdoor colors (~100–160 each).

If N < 10,000 or all RGB is 0: debug the confidence threshold (try `min_confidence=0`) and depth scale.

---

## Task 2: Preview System Overhaul

**Why:** Even with the correct colored PLY, the preview UI needs client-side brightness/contrast
controls and a ring-highlight mode so operators can always find the blue ring,
regardless of scan lighting or rendering artifacts.

### 2a. Replace the grid fallback in `detector.py`

The current `_grid_fallback()` generates 12 fake circles that mislead the operator.
Replace the fallback with an empty list and a clear log message:

```python
    if not circles:
        logger.warning(
            "No circles detected in %s — canvas will be empty; operator must annotate manually",
            preview_path.name,
        )
        # Empty canvas is correct: operator double-clicks to add circles.
        # The old grid fallback produced fake circles that were worse than nothing.
        return []
```

Delete the entire `_grid_fallback()` function.

### 2b. Add brightness/contrast slider and ring-highlight to `scan_review.html`

Find the section in `scan_review.html` that contains the canvas element.
Add these controls directly below the canvas:

```html
<!-- Preview controls -->
<div class="flex flex-wrap items-center gap-4 mt-3 mb-2">
  <label class="text-sm text-gray-600 flex items-center gap-2">
    Jasność
    <input type="range" id="brightness-slider" min="50" max="300" value="100"
           class="w-28 accent-blue-500" />
    <span id="brightness-val" class="text-xs w-8">100%</span>
  </label>
  <label class="text-sm text-gray-600 flex items-center gap-2">
    Kontrast
    <input type="range" id="contrast-slider" min="50" max="300" value="100"
           class="w-28 accent-blue-500" />
    <span id="contrast-val" class="text-xs w-8">100%</span>
  </label>
  <button id="ring-highlight-btn"
          class="px-3 py-1 text-xs rounded border border-blue-400 text-blue-700 hover:bg-blue-50">
    Podświetl pierścień (niebieski)
  </button>
  <button id="reset-view-btn"
          class="px-3 py-1 text-xs rounded border border-gray-400 text-gray-600 hover:bg-gray-50">
    Resetuj widok
  </button>
</div>
```

### 2c. Update `review.js` to implement the controls

Add these functions to `review.js` (after the existing `drawAll()` function):

```javascript
// ── Preview controls ────────────────────────────────────────────────────────

let ringHighlightActive = false;
let originalImageData = null;  // stores the unmodified canvas pixels after image draw

function applyCanvasFilter() {
    const brightness = document.getElementById('brightness-slider')?.value ?? 100;
    const contrast   = document.getElementById('contrast-slider')?.value ?? 100;
    const imgCanvas = document.getElementById('image-layer') ?? canvas;
    // Apply CSS filter to the image underneath the annotation overlay
    imgCanvas.style.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
    document.getElementById('brightness-val').textContent = brightness + '%';
    document.getElementById('contrast-val').textContent   = contrast + '%';
}

function highlightBlueChannel() {
    // Work on a temporary offscreen canvas so we don't corrupt annotation data
    const offscreen = document.createElement('canvas');
    offscreen.width  = canvas.width;
    offscreen.height = canvas.height;
    const octx = offscreen.getContext('2d');

    // Draw the preview image (without annotations)
    if (imgObj && imgObj.complete && imgObj.naturalWidth > 0) {
        octx.drawImage(imgObj, 0, 0, canvas.width, canvas.height);
    }

    const imageData = octx.getImageData(0, 0, offscreen.width, offscreen.height);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
        const r = data[i], g = data[i + 1], b = data[i + 2];
        // A pixel is "blue" when its blue channel significantly dominates red and green
        if (b > 100 && b > r * 1.4 && b > g * 1.4) {
            // Render as bright neon cyan so the ring is unmissable
            data[i]     = 0;
            data[i + 1] = 255;
            data[i + 2] = 255;
        }
    }

    octx.putImageData(imageData, 0, 0);

    // Draw the highlighted image onto the main canvas, then redraw annotations on top
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(offscreen, 0, 0);
    drawAll();  // re-draws circles on top of the highlighted background
}

function initPreviewControls() {
    const brightnessSlider = document.getElementById('brightness-slider');
    const contrastSlider   = document.getElementById('contrast-slider');
    const ringBtn          = document.getElementById('ring-highlight-btn');
    const resetBtn         = document.getElementById('reset-view-btn');

    if (brightnessSlider) {
        brightnessSlider.addEventListener('input', applyCanvasFilter);
    }
    if (contrastSlider) {
        contrastSlider.addEventListener('input', applyCanvasFilter);
    }
    if (ringBtn) {
        ringBtn.addEventListener('click', () => {
            ringHighlightActive = !ringHighlightActive;
            ringBtn.classList.toggle('bg-blue-100', ringHighlightActive);
            ringBtn.classList.toggle('text-blue-900', ringHighlightActive);
            if (ringHighlightActive) {
                highlightBlueChannel();
            } else {
                drawAll();  // restore normal view
            }
        });
    }
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            ringHighlightActive = false;
            if (brightnessSlider) brightnessSlider.value = 100;
            if (contrastSlider)   contrastSlider.value   = 100;
            applyCanvasFilter();
            drawAll();
        });
    }
}
```

At the end of the `loadImage()` function (after `drawAll()` is called), add:

```javascript
    initPreviewControls();
```

Also: if `ringHighlightActive` is true at the time `drawAll()` is called (e.g., after adding
a circle), re-apply the highlight so the background doesn't reset. Inside `drawAll()`,
before returning, add:

```javascript
    if (ringHighlightActive) {
        // Re-highlight after every redraw (async, so the annotations paint first)
        requestAnimationFrame(highlightBlueChannel);
    }
```

### 2d. Add a two-layer canvas architecture (image layer + annotation layer)

The current code draws both the preview image and circles onto a single canvas.
This causes the ring-highlight function to corrupt annotation data.

Wrap the existing canvas with a container div and add a second canvas on top:

In `scan_review.html`, replace:
```html
<canvas id="canvas" ...></canvas>
```
with:
```html
<div style="position:relative; display:inline-block;">
  <canvas id="image-layer"  style="display:block;"></canvas>
  <canvas id="canvas"       style="position:absolute; top:0; left:0; background:transparent;"></canvas>
</div>
```

In `review.js`:
- `imgLayer` = `document.getElementById('image-layer')` — used only for drawing the preview PNG
- `canvas`   = `document.getElementById('canvas')` — used only for circles and interaction
- Move all `ctx.drawImage(imgObj, ...)` calls to use `imgLayer`'s context
- The annotation canvas is transparent background so the image shows through
- `highlightBlueChannel()` operates on `imgLayer` only

This cleanly separates concerns and makes the highlight toggle instant and non-destructive.

---

## Task 3: Orientation-Independent Apple Sizing

**Why:** Apples laid on their side show their HEIGHT profile, not their EQUATORIAL diameter,
when viewed from above. The caliber standard is equatorial diameter. Using `radius_px * 2`
on a side-up apple overestimates (height ≈ equatorial in many varieties) or
underestimates (height < equatorial in flat varieties). Fitting an ellipse and using
the **minor axis** as the caliber diameter is the correct, orientation-agnostic solution.
This also improves ring detection: a slightly-tilted ring projects as an ellipse,
and its minor axis is the true inner diameter.

### 3a. Update the `Circle` dataclass in `detector.py`

Replace the existing `Circle` dataclass with:

```python
@dataclass
class Circle:
    cx: float
    cy: float
    radius_px: float        # fallback: used when ellipse fitting fails
    confidence: float = 1.0
    # Ellipse fitting (0.0 = not fitted — fall back to radius_px)
    ellipse_major_px: float = 0.0   # full major-axis length in pixels (OpenCV returns full axis)
    ellipse_minor_px: float = 0.0   # full minor-axis length in pixels
    ellipse_angle_deg: float = 0.0  # rotation of major axis, degrees

    @property
    def caliber_diameter_px(self) -> float:
        """
        Conservative caliber diameter in pixels.
        Uses the ellipse minor axis when available — this equals the equatorial
        diameter regardless of whether the apple is stem-up or side-up.
        Falls back to radius_px * 2 if ellipse fitting was not performed.
        """
        if self.ellipse_minor_px > 0:
            return self.ellipse_minor_px
        return self.radius_px * 2.0

    @property
    def is_sideways(self) -> bool:
        """Heuristic: aspect ratio > 1.25 suggests the apple is on its side."""
        if self.ellipse_major_px > 0 and self.ellipse_minor_px > 0:
            return (self.ellipse_major_px / self.ellipse_minor_px) > 1.25
        return False
```

### 3b. Add ellipse fitting post-processing to `detect_circles()` in `detector.py`

After the existing Hough detection loop (after `circles = circles[:max_circles]`),
add a function and a call to it:

```python
def _fit_ellipses(circles: list[Circle], gray: np.ndarray) -> list[Circle]:
    """
    For each Hough circle, extract the local ROI, find edge contours,
    and fit an ellipse to refine the shape estimate.
    Updates ellipse_major_px, ellipse_minor_px, ellipse_angle_deg in-place.
    Returns the same list with ellipse data added where fitting succeeded.
    """
    h, w = gray.shape
    for circle in circles:
        cx, cy, r = int(circle.cx), int(circle.cy), int(circle.radius_px)
        # Expand ROI slightly beyond the Hough radius
        pad = max(int(r * 0.3), 5)
        x1, y1 = max(cx - r - pad, 0), max(cy - r - pad, 0)
        x2, y2 = min(cx + r + pad, w), min(cy + r + pad, h)
        roi = gray[y1:y2, x1:x2]
        if roi.size < 100:
            continue

        # Edge detection on the ROI
        edges = cv2.Canny(roi, threshold1=30, threshold2=90)

        # Find all contour points
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue

        # Combine all contour points from this ROI
        all_pts = np.vstack([c.reshape(-1, 2) for c in cnts])

        # Need at least 5 points to fit an ellipse
        if len(all_pts) < 5:
            continue

        try:
            (ex, ey), (ma, minor_a), angle = cv2.fitEllipse(all_pts)
        except cv2.error:
            continue

        # ma = full major axis length, minor_a = full minor axis length (OpenCV convention)
        # Sanity check: ellipse axes should be in a plausible range relative to Hough radius
        if not (r * 0.4 < ma / 2 < r * 2.5 and r * 0.4 < minor_a / 2 < r * 2.5):
            continue

        circle.ellipse_major_px = float(ma)
        circle.ellipse_minor_px = float(minor_a)
        circle.ellipse_angle_deg = float(angle)

    return circles
```

At the end of `detect_circles()`, before the final `return circles`:

```python
    circles = _fit_ellipses(circles, gray)
    logger.info("Ellipse fitting complete. Sideways apples: %d / %d",
                sum(1 for c in circles if c.is_sideways), len(circles))
    return circles
```

### 3c. Update `calibration.py` to use `caliber_diameter_px`

In `compute_scale_factor()`, replace:
```python
ring_diameter_px = ring_circle.radius_px * 2.0
```
with:
```python
ring_diameter_px = ring_circle.caliber_diameter_px
```

And in the apple sanity check, replace:
```python
apple_diameters = [c.radius_px * 2.0 * scale for c in apple_circles]
```
with:
```python
apple_diameters = [c.caliber_diameter_px * scale for c in apple_circles]
```

### 3d. Update reporting to flag sideways apples

In `apple_caliber_scan/services/reporting.py`, wherever individual apple diameters
are computed from circles, replace `c.radius_px * 2 * scale_factor` with
`c.caliber_diameter_px * scale_factor`.

Add a count of sideways apples to the report context:
```python
sideways_count = sum(1 for c in apple_circles if c.is_sideways)
```
Pass this to the Jinja2 report template and display it as a note:
```
Jabłka leżące na boku (wykryte): {{ sideways_count }} szt. (kaliber = oś mniejsza elipsy)
```

### 3e. Verify ellipse fitting

Run in venv:
```bash
python3 -c "
from pathlib import Path
from apple_caliber_scan.scan.detector import detect_circles

# Use any existing preview PNG
import glob
previews = glob.glob('apple_caliber_scan/../data/previews/*.png')
if previews:
    circles = detect_circles(Path(previews[0]))
    for c in circles[:5]:
        print(f'cx={c.cx:.0f} cy={c.cy:.0f} r={c.radius_px:.1f} '
              f'major={c.ellipse_major_px:.1f} minor={c.ellipse_minor_px:.1f} '
              f'sideways={c.is_sideways}')
else:
    print('No previews yet — run ingestion first')
"
```

Expected: most circles show `major ≈ minor ≈ radius*2` (stem-up apples are roughly circular).
Sideways apples show `major > minor * 1.25`.

---

## Task 4: Research and Document Polycam Alternatives

**Important discovery:** The user's Polycam "Raw" export ZIP already contains everything
needed to reconstruct a colored point cloud without paying for PLY export.
Task 1 implements this. However, a scanning app is still needed for capture.

Research the following questions using web browsing (mandatory):

### 4a. Verify Scaniverse free export capabilities

Search: `site:scaniverse.com export formats` AND `"scaniverse" "free" "PLY" OR "OBJ" export 2025`

Scaniverse (by Niantic Labs) is already listed in this project's `CAPTURE_GUIDE.md` as
the primary scanner. The code already loads OBJ via trimesh (`loader.py:load_mesh`).

Determine:
1. Does Scaniverse export OBJ/GLB with vertex positions on the free tier?
2. Does it export PLY with per-vertex RGB for free?
3. What is the current iOS App Store rating and last update date?

### 4b. Research other free/cheap iOS LiDAR apps

Search: `"iPhone" "LiDAR" "point cloud" export free 2025 app`
Search: `"Record3D" price export format`
Search: `"3D Scanner App" free PLY export iOS 2025`
Search: `"KIRI Engine" mobile free export PLY`

For each app found, determine:
- Price (free / one-time / subscription)
- Export formats (PLY with color? OBJ? GLB?)
- Works on iPhone 17 Pro (LiDAR)?
- Quality level (photogrammetry vs LiDAR depth)

### 4c. Check whether Polycam "Raw" export requires subscription

Search: `polycam raw export subscription free tier 2025`

The user already has the raw ZIP. Determine if they can continue exporting
raw ZIPs for free, or if they need a subscription even for that.

### 4d. Write a definitive recommendation

After researching, write a file `SCANNER_ALTERNATIVES.md` in the project root with:
1. The immediate solution (Polycam Raw ZIP — now works with new code in Task 1)
2. The best completely-free alternative (likely Scaniverse — verify)
3. The cheapest paid alternative if free option doesn't meet quality requirements
4. Export instructions for each recommended app (exactly what settings to use)
5. A comparison table: App | Price | Format | Color | LiDAR | Notes

---

## Task 5: Database Schema — Allow NULL drive_url

The `create_scan()` function in `crud.py` was written assuming Google Drive is always used.
The new file-upload route creates scans without a Drive URL. Verify the database schema
and CRUD layer handle `drive_url=None` and `drive_file_id=None` correctly:

1. Check the `CREATE TABLE scans` statement in `crud.py` or migrations.
   `drive_url` and `drive_file_id` must allow NULL (no `NOT NULL` constraint).
2. Check `create_scan()` — ensure it passes `drive_url` and `drive_file_id` as NULL
   when the caller passes `None`.
3. Check `scan_reingest()` route — it reads `scan["drive_url"]`. Add a guard:
   ```python
   if not drive_url:
       return HTMLResponse("Ten skan nie ma URL Google Drive — nie można ponownie pobrać.", status_code=400)
   ```

---

## Task 6: Full End-to-End Test with the Real Scan

After all the above is implemented, run the full pipeline on the actual test scan:

```bash
cd /mnt/c/Users/balce/Downloads/apple\ scanner/apple-caliber-scan
source .venv/bin/activate

# Test: reconstruct colored point cloud from ZIP
python3 -c "
from pathlib import Path
from apple_caliber_scan.scan.loader import load_polycam_raw_zip
from apple_caliber_scan.scan.normalizer import normalize_top_down
from apple_caliber_scan.scan.preview import render_preview

pts = load_polycam_raw_zip(Path('/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip'))
print('Loaded:', pts.shape)

norm = normalize_top_down(pts, top_percentile=0.80)
print('Normalized:', norm.shape)

out = Path('/tmp/test_preview.png')
render_preview(norm, out)
print('Preview written to:', out)
print('Open /tmp/test_preview.png — you should see apples with natural colors and a blue ring')
"
```

Copy `/tmp/test_preview.png` to a Windows-accessible location and open it in a browser:
```bash
cp /tmp/test_preview.png /mnt/c/Users/balce/Downloads/test_preview.png
```

The preview **must** show:
- Natural red/green apple colors
- A clearly visible BLUE ring (not white, not grey)
- Recognizable top-down oval/circular apple shapes

If the blue ring is not visible, run the ring-highlight to verify it exists in the point cloud:
```bash
python3 -c "
import numpy as np
from pathlib import Path
from apple_caliber_scan.scan.loader import load_polycam_raw_zip

pts = load_polycam_raw_zip(Path('/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip'))
r, g, b = pts[:,3], pts[:,4], pts[:,5]
# Count pixels where blue dominates
blue_dominant = (b > 100) & (b > r * 1.4) & (b > g * 1.4)
print(f'Blue-dominant points: {blue_dominant.sum()} / {len(pts)} ({100*blue_dominant.mean():.1f}%)')
print('If this is near 0%, the ring may not be visible in the scan from above.')
print('Ring position (world coords):')
print(pts[blue_dominant, :3].mean(axis=0) if blue_dominant.sum() > 0 else 'No blue points')
"
```

Then start the server and upload the ZIP through the web UI:
```bash
make run-web  # or: uvicorn apple_caliber_scan.web.app:create_app --factory --reload --port 8000
```

1. Navigate to the batch → "Dodaj skan" (Add scan)
2. Use the new "Prześlij plik lokalny" form
3. Upload `/mnt/c/Users/balce/Downloads/apple scanner/17_05_2026.zip`
4. On the review page: verify the colored preview is visible
5. Click "Podświetl pierścień" — the blue ring must turn neon cyan
6. Annotate the ring and apples
7. Generate the report

---

## Definition of Done

Every item below must be true before this session is considered complete:

- [ ] `load_polycam_raw_zip()` reconstructs (N≥100k, 6) colored points from `17_05_2026.zip`
- [ ] The preview PNG from the real ZIP shows natural apple colors AND a visible blue ring
- [ ] File upload route `/batches/{id}/scan/upload` accepts ZIP and processes it
- [ ] The "Prześlij plik lokalny" form is visible in the scan attachment page
- [ ] Brightness and contrast sliders appear on the review page and work
- [ ] "Podświetl pierścień" button turns blue pixels to neon cyan on the canvas
- [ ] Grid fallback (`_grid_fallback`) is deleted; no circles = empty canvas
- [ ] `Circle.caliber_diameter_px` returns ellipse minor axis when fitted
- [ ] `compute_scale_factor()` uses `ring_circle.caliber_diameter_px`
- [ ] `SCANNER_ALTERNATIVES.md` exists with verified, cited app recommendations
- [ ] `pytest` passes (run: `pytest tests/ -x`)
- [ ] Server starts without errors: `make run-web`

---

## Run Order

1. Implement Task 1 (ZIP loader) first — all other tasks depend on having real scan data.
2. Test Task 1 with the standalone Python script before touching the web layer.
3. Implement Task 5 (NULL drive_url) alongside Task 1c.
4. Implement Tasks 2 and 3 in parallel (they are independent).
5. Run Task 6 (full end-to-end test) to confirm everything works together.
6. Research Task 4 while the server is running the first test.
7. Run `pytest` last — fix any regressions before declaring done.
