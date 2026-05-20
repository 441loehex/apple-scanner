# Accuracy & Methodology — Apple Caliber Scan

**Freshora Sp. Z. o. o.**

This document describes the technical basis for caliber measurement and the known
accuracy characteristics of the system.

---

## 1. Measurement Pipeline

```
LiDAR scan (PLY/OBJ)
    ↓
Point cloud loading
    ↓
PCA-based top-down normalization
    ↓
Density projection → 1024×1024 PNG
    ↓
Hough circle detection (OpenCV)
    ↓
Ring annotation → physical scale factor
    ↓
Caliber classification → distribution table
```

---

## 2. Scale Calibration

The system uses a **physical reference ring** (default 75 mm diameter) placed in the scan
field. After Hough detection identifies the ring as a circle with diameter `d_px` pixels,
the scale factor is computed as:

```
scale_mm_per_px = ring_mm / d_px
```

Each detected apple circle with pixel diameter `d_apple_px` then has:

```
diameter_mm = d_apple_px × scale_mm_per_px
```

This approach is equivalent to a single-reference photogrammetric calibration. It corrects
for scan height variation but not for perspective distortion at the edges of large scan areas.

---

## 3. Caliber Classification

Polish apple trade uses the following caliber classes (per standard practice):

| Class | Range (mm) | Inclusive Bounds |
|-------|-----------|-----------------|
| 0-60  | < 60 mm   | lower: 0, upper: exclusive 60 |
| 60-65 | 60–65 mm  | lower inclusive, upper exclusive |
| 65-70 | 65–70 mm  | lower inclusive, upper exclusive |
| 70-75 | 70–75 mm  | lower inclusive, upper exclusive |
| 75-80 | 75–80 mm  | lower inclusive, upper exclusive |
| 80-85 | 80–85 mm  | lower inclusive, upper exclusive |
| 85-90 | 85–90 mm  | lower inclusive, upper exclusive |
| 90+   | ≥ 90 mm   | lower inclusive, no upper bound |

The **75+ share** is the sum of counts in classes 75-80, 80-85, 85-90, and 90+, expressed
as a percentage of all measured apples.

---

## 4. Expected Accuracy

Based on the measurement physics:

| Source | Typical Error |
|--------|-------------|
| Ring annotation | ±1 px → ±0.1–0.5 mm at typical scan heights |
| Circle detection (radius) | ±2–4 px → ±1–3 mm |
| Apple sphericity assumption | ±2–5 mm for irregular shapes |
| Scan height variation | ±1–3 mm over a 60×40 cm crate area |

**Combined typical error: ±3–5 mm per apple.**

At a scan height of 80 cm over a standard crate, a 1 mm depth variation corresponds to
approximately 0.15 mm error in the detected diameter — negligible relative to detection error.

---

## 5. Confidence Model

| Level | Condition | Interpretation |
|-------|----------|----------------|
| HIGH (wysoka) | Ring calibrated + grader ground truth entered | Distribution validated against machine sort |
| LOW (niska) | Ring calibrated, no ground truth | Physical scale known, unvalidated |
| UNCALIBRATED | No ring annotated | Pixel diameters only — do not interpret as mm |

**HIGH confidence is only appropriate when a grader printout is available.** The system
does not automatically produce HIGH confidence results.

---

## 6. Circle Detection — Hough Transform

The system uses OpenCV's `HoughCircles` with the following strategy:

1. Render top-down density projection (1024×1024 px, green colormap)
2. Convert to grayscale, apply Gaussian blur (kernel 5×5, σ=1)
3. Run `HOUGH_GRADIENT_ALT` (more robust to incomplete circles)
4. Fall back to `HOUGH_GRADIENT` if no circles found
5. Fall back to a uniform grid if both methods fail (produces equal-size circles — flag in report)

Detection parameters are tuned for apple-sized objects at typical iPhone scanning distances
(60–100 cm). The minimum/maximum radius bounds assume 40–120 mm physical diameter at the
expected scale.

---

## 7. Point Cloud Normalization

The input point cloud undergoes PCA-based normalization:

1. Compute covariance matrix of all points
2. Identify eigenvector with smallest eigenvalue (minimum-variance axis = vertical)
3. Rotate so this axis aligns with Z
4. Crop to top 20% of Z range (the visible apple tops)
5. Normalize XY to [0, 1]

This corrects for scanner tilt and ensures the projection plane is approximately parallel
to the apple surface.

---

## 8. Weight Estimation

Per-apple weight uses a geometric sphere model:

```
weight_g = density_g_cm3 × (4/3)π(r_cm)³
```

With assumed density ≈ 0.85 g/cm³ (typical for dessert apple varieties in CA storage).

This is a rough estimate. Actual density varies by ±15% across varieties and storage
conditions. Weight totals are labeled SZACUNEK in all reports.

---

## 9. Validation Status

As of this MVP release:
- The pipeline has been validated on synthetic data with known ground truth (see `tests/`)
- Field validation against grader output is pending
- Accuracy figures above are theoretical estimates, not empirical measurements

Freshora plans to collect grader comparisons during the 2024/2025 apple season to produce
empirical accuracy figures. Until then, confidence is capped at LOW for all field scans.

---

## 10. What This System Is Not

- It is **not** a calibrated measurement instrument (no traceable metrological certification)
- It is **not** equivalent to a mechanical grader or optical sorter
- It is **not** suitable for legal, customs, or phytosanitary documentation
- Reports are **estimative tools** to support purchasing decisions, not compliance records
