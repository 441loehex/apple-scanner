"""Hough circle detection on preview PNG."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Circle:
    cx: float
    cy: float
    radius_px: float
    confidence: float = 1.0
    # Ellipse fitting (0.0 = not fitted — fall back to radius_px)
    ellipse_major_px: float = 0.0   # full major-axis length in pixels
    ellipse_minor_px: float = 0.0   # full minor-axis length in pixels
    ellipse_angle_deg: float = 0.0  # rotation of major axis, degrees
    orientation: str = "unknown"    # "upright" | "sideways" | "angled" | "unknown"

    @property
    def caliber_diameter_px(self) -> float:
        """
        Conservative caliber diameter in pixels.
        Uses the ellipse minor axis when available — equals the equatorial
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

    @property
    def orientation_label_pl(self) -> str:
        return {
            "upright":  "pionowo",
            "sideways": "na boku",
            "angled":   "ukośnie",
            "unknown":  "—",
        }.get(self.orientation, "—")


def detect_circles(
    preview_path: Path,
    min_radius_px: int = 20,
    max_radius_px: int = 200,
    max_circles: int = 200,
) -> list[Circle]:
    """
    Load preview PNG and run Hough circle detection.

    Pre-processing:
      - CLAHE equalisation to boost local contrast on low-contrast depth images
      - Gaussian blur before HoughCircles (reduces noise)

    Tries progressively less-strict Hough parameters so that real scans with
    imperfect circular apples are still found before returning empty list.
    """
    img = cv2.imread(str(preview_path))
    if img is None:
        logger.error("Cannot read preview image: %s", preview_path)
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    blurred = cv2.GaussianBlur(gray, (9, 9), 2)

    h, w = gray.shape
    # Cap at 1/11 of image (floor 50px).
    # At typical scan scale (1663 px/m, 1024-px canvas), this gives ~93 px max radius,
    # which covers apple-sized circles (~75 px) without matching the full scan boundary
    # arc (~127 px) that the previous cap of // 8 = 128 px allowed.
    effective_max = min(max_radius_px, max(min(h, w) // 11, 50))
    effective_min = max(min_radius_px, 5)

    circles: list[Circle] = []
    # Minimum acceptable circle count: continue to looser params if below this.
    # Set to 15 so the ladder continues past early levels that find only a few
    # obvious circles — a full tray of 30 apples needs at least 15 detections.
    min_acceptable = 15

    param_ladder = [
        (cv2.HOUGH_GRADIENT_ALT, 300, 0.8),
        (cv2.HOUGH_GRADIENT_ALT, 200, 0.65),
        (cv2.HOUGH_GRADIENT_ALT, 100, 0.5),
        (cv2.HOUGH_GRADIENT_ALT, 100, 0.4),
        (cv2.HOUGH_GRADIENT_ALT, 100, 0.3),
        (cv2.HOUGH_GRADIENT,     50,  25),
        (cv2.HOUGH_GRADIENT,     30,  15),
    ]

    for method, param1, param2 in param_ladder:
        try:
            raw = cv2.HoughCircles(
                blurred,
                method,
                dp=1,
                minDist=max(effective_min * 3, 50),
                param1=param1,
                param2=param2,
                minRadius=effective_min,
                maxRadius=effective_max,
            )
            if raw is not None and len(raw[0]) >= min_acceptable:
                raw = np.round(raw[0]).astype(np.float32)
                for cx, cy, r in raw:
                    circles.append(Circle(cx=float(cx), cy=float(cy), radius_px=float(r)))
                logger.info(
                    "Hough found %d circles (method=%s p1=%s p2=%s)",
                    len(circles), method, param1, param2,
                )
                break
            elif raw is not None:
                logger.debug(
                    "Hough p1=%s p2=%s found only %d circles — trying looser params",
                    param1, param2, len(raw[0]),
                )
        except cv2.error as e:
            logger.debug("Hough method %s failed: %s", method, e)
            continue

    # If no step met min_acceptable, take the best (most circles) we found
    if not circles:
        best_raw, best_n = None, 0
        for method, param1, param2 in param_ladder:
            try:
                raw = cv2.HoughCircles(
                    blurred, method, dp=1, minDist=max(effective_min * 3, 50),
                    param1=param1, param2=param2,
                    minRadius=effective_min, maxRadius=effective_max,
                )
                if raw is not None and len(raw[0]) > best_n:
                    best_raw, best_n = raw, len(raw[0])
                    best_params = (method, param1, param2)
            except cv2.error:
                continue
        if best_raw is not None:
            for cx, cy, r in np.round(best_raw[0]).astype(np.float32):
                circles.append(Circle(cx=float(cx), cy=float(cy), radius_px=float(r)))
            logger.info(
                "Hough best-effort: %d circles (method=%s p1=%s p2=%s)",
                len(circles), *best_params,
            )


    if not circles:
        logger.warning(
            "No circles detected in %s — canvas will be empty; operator must annotate manually",
            preview_path.name,
        )
        return []

    circles = circles[:max_circles]
    circles = _fit_ellipses(circles, gray)
    before_nms = len(circles)
    circles = _deduplicate_circles(circles)
    logger.info(
        "After NMS: %d → %d circles (removed %d concentric duplicates)",
        before_nms, len(circles), before_nms - len(circles),
    )
    logger.info(
        "Ellipse fitting complete. Sideways apples: %d / %d",
        sum(1 for c in circles if c.is_sideways), len(circles),
    )
    return circles


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


def classify_orientations(
    circles: list[Circle],
    points: np.ndarray,
    preview_width: int = 1024,
    preview_height: int = 1024,
) -> list[Circle]:
    """
    For each detected circle, extract 3D points within the corresponding cylinder
    and classify apple orientation from the local Z-height profile.

    points: normalized (N, 3+) array, XY in [0,1], Z in [0,1].
    The preview maps X→px and Y→(1-py), same as _render_colored.

    Classification (dome_ratio = (Z_centre_mean - Z_edge_mean) / (Z_range + ε)):
      > 0.25  → "upright"
      < 0.10 AND is_sideways → "sideways"
      otherwise → "angled"
      < 20 pts in cylinder → "unknown"
    """
    if len(points) == 0 or points.shape[1] < 3:
        return circles

    xs = points[:, 0]
    ys = points[:, 1]
    zs = points[:, 2]

    W, H = preview_width, preview_height

    for circle in circles:
        cx_n = circle.cx / (W - 1)
        cy_n = 1.0 - circle.cy / (H - 1)   # Y-flip must match _render_colored
        r_n  = circle.radius_px / (W - 1)

        dist2 = (xs - cx_n) ** 2 + (ys - cy_n) ** 2
        inner_mask = dist2 < (r_n * 0.4) ** 2
        outer_mask = (dist2 > (r_n * 0.6) ** 2) & (dist2 < (r_n * 1.1) ** 2)
        in_cylinder = dist2 < (r_n * 1.1) ** 2

        pts_in = zs[in_cylinder]
        if len(pts_in) < 20:
            circle.orientation = "unknown"
            continue

        z_min, z_max = pts_in.min(), pts_in.max()
        z_range = z_max - z_min

        # Focus on the top 40% of Z within the cylinder: these are the actual
        # apple surface points.  Floor and stalk body pull the mean down and
        # dilute the dome signal when top_percentile=0.80 is used.
        z_surface_threshold = z_min + 0.60 * z_range
        surface_mask = zs >= z_surface_threshold
        inner_top = inner_mask & surface_mask
        outer_top = outer_mask & surface_mask

        pts_inner = zs[inner_top]
        pts_outer = zs[outer_top]
        if len(pts_inner) < 5 or len(pts_outer) < 5:
            # Fallback to full cylinder if not enough surface points
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


def _deduplicate_circles(
    circles: list[Circle],
    overlap_ratio: float = 0.6,
) -> list[Circle]:
    """
    Remove concentric and heavily-overlapping circle detections.

    Two circles are "the same detection" when their centres are within
    overlap_ratio × min(r1, r2) pixels of each other.

    Selection rule: keep the LARGER circle. The outer boundary of an apple
    equals its equatorial diameter; inner-edge Hough artifacts (r=30, r=48
    vs. correct r=60) cause underestimation of apple size.

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


def _fit_ellipses(circles: list[Circle], gray: np.ndarray) -> list[Circle]:
    """
    For each Hough circle, extract the local ROI, find edge contours,
    and fit an ellipse to refine the shape estimate.
    """
    h, w = gray.shape
    for circle in circles:
        cx, cy, r = int(circle.cx), int(circle.cy), int(circle.radius_px)
        pad = max(int(r * 0.3), 5)
        x1, y1 = max(cx - r - pad, 0), max(cy - r - pad, 0)
        x2, y2 = min(cx + r + pad, w), min(cy + r + pad, h)
        roi = gray[y1:y2, x1:x2]
        if roi.size < 100:
            continue

        edges = cv2.Canny(roi, threshold1=30, threshold2=90)
        cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not cnts:
            continue

        all_pts = np.vstack([c.reshape(-1, 2) for c in cnts])
        if len(all_pts) < 5:
            continue

        try:
            (ex, ey), (ma, minor_a), angle = cv2.fitEllipse(all_pts)
        except cv2.error:
            continue

        if not (r * 0.4 < ma / 2 < r * 2.5 and r * 0.4 < minor_a / 2 < r * 2.5):
            continue

        circle.ellipse_major_px = float(ma)
        circle.ellipse_minor_px = float(minor_a)
        circle.ellipse_angle_deg = float(angle)

    return circles
