"""Tests for detector.py — calibration ring detection and orientation classification."""

import tempfile
from pathlib import Path

import cv2
import numpy as np

from apple_caliber_scan.scan.detector import (
    Circle,
    _deduplicate_circles,
    classify_orientations,
    detect_calibration_ring,
    detect_circles,
)


def test_detect_calibration_ring_on_synthetic_preview():
    """Blue ring placed at known position must be found within 10% of its radius."""
    W, H = 512, 512
    img = np.full((H, W, 3), 40, dtype=np.uint8)
    cx, cy, r = 256, 256, 60
    for angle in np.linspace(0, 2 * np.pi, 500):
        x = int(cx + r * np.cos(angle))
        y = int(cy + r * np.sin(angle))
        if 0 <= x < W and 0 <= y < H:
            img[y, x] = [220, 30, 10]  # OpenCV BGR — strong blue

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)
    cv2.imwrite(str(path), img)
    try:
        result = detect_calibration_ring(path, min_radius_px=30, max_radius_px=120)
        assert result is not None, "Ring not detected"
        assert abs(result.cx - cx) < r * 0.15, f"cx off by {abs(result.cx - cx):.1f}px"
        assert abs(result.cy - cy) < r * 0.15, f"cy off by {abs(result.cy - cy):.1f}px"
        err_r = abs(result.radius_px - r)
        assert err_r < r * 0.20, f"radius off by {err_r:.1f}px"
    finally:
        path.unlink(missing_ok=True)


def test_detect_calibration_ring_no_blue_returns_none():
    """A purely red image must return None."""
    W, H = 256, 256
    img = np.full((H, W, 3), [0, 0, 200], dtype=np.uint8)  # BGR → red
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = Path(f.name)
    cv2.imwrite(str(path), img)
    try:
        result = detect_calibration_ring(path)
        assert result is None
    finally:
        path.unlink(missing_ok=True)


def test_upright_apple_classified_correctly():
    """Dome-shaped Z profile must classify as 'upright'."""
    cx_n, cy_n, r_n = 0.5, 0.5, 0.04
    rng = np.random.default_rng(1)
    theta = rng.uniform(0, 2 * np.pi, 300)
    radii = rng.uniform(0, r_n, 300)
    x = cx_n + radii * np.cos(theta)
    y = cy_n + radii * np.sin(theta)
    z = 0.8 + 0.15 * (1.0 - (radii / r_n) ** 2)
    pts = np.column_stack([x, y, z]).astype(np.float32)

    circle = Circle(cx=512.0, cy=512.0, radius_px=40.0)
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
    z = np.full(300, 0.85) + rng.normal(0, 0.002, 300)
    pts = np.column_stack([x, y, z]).astype(np.float32)

    circle = Circle(cx=512.0, cy=512.0, radius_px=40.0,
                    ellipse_major_px=60.0, ellipse_minor_px=40.0)
    result = classify_orientations([circle], pts, 1024, 1024)
    assert result[0].orientation == "sideways", f"Got {result[0].orientation}"


def test_empty_points_returns_circles_unchanged():
    """classify_orientations with zero points must not crash."""
    circles = [Circle(cx=100.0, cy=100.0, radius_px=30.0)]
    result = classify_orientations(circles, np.zeros((0, 3), dtype=np.float32))
    assert result[0].orientation == "unknown"


def test_too_few_points_yields_unknown():
    """Fewer than 20 points in cylinder must give 'unknown'."""
    rng = np.random.default_rng(3)
    pts = np.column_stack([
        rng.uniform(0.49, 0.51, 5),
        rng.uniform(0.49, 0.51, 5),
        rng.uniform(0.8, 0.9, 5),
    ]).astype(np.float32)
    circle = Circle(cx=512.0, cy=512.0, radius_px=40.0)
    result = classify_orientations([circle], pts, 1024, 1024)
    assert result[0].orientation == "unknown"


def test_orientation_label_pl():
    """orientation_label_pl must return correct Polish strings."""
    c = Circle(cx=0, cy=0, radius_px=1, orientation="upright")
    assert c.orientation_label_pl == "pionowo"
    c.orientation = "sideways"
    assert c.orientation_label_pl == "na boku"
    c.orientation = "angled"
    assert c.orientation_label_pl == "ukośnie"
    c.orientation = "unknown"
    assert c.orientation_label_pl == "—"


def test_deduplicate_removes_concentric_circles():
    """Three concentric circles at the same centre must collapse to one."""
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
    # Groups A and B each collapse to 1; the other 5 standalones are kept → 7 total
    assert len(result) == 7, f"Expected 7 circles after NMS, got {len(result)}"
    # Verify group A kept largest
    group_a = [c for c in result if abs(c.cx - 508) < 5 and abs(c.cy - 410) < 5]
    assert len(group_a) == 1 and group_a[0].radius_px == 60.0
    # Verify group B kept largest
    group_b = [c for c in result if abs(c.cx - 668) < 5 and abs(c.cy - 402) < 5]
    assert len(group_b) == 1 and group_b[0].radius_px == 47.0


def test_max_radius_cap_excludes_boundary_artifacts():
    """
    A preview-sized canvas with a large boundary arc (radius ~127 px) must not be
    detected as a circle after the // 11 cap (max ~93 px).
    """
    W, H = 1024, 1024
    img = np.full((H, W, 3), 40, dtype=np.uint8)

    # Draw a large arc near the boundary (radius 500 px) — the old code found these
    cx_b, cy_b, r_big = 512, 512, 500
    for angle in np.linspace(0, 2 * np.pi, 3000):
        x = int(cx_b + r_big * np.cos(angle))
        y = int(cy_b + r_big * np.sin(angle))
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


def test_ring_detection_with_handle():
    """
    A magnifying-glass shaped blue region (circle + short handle) must produce
    a detection centred on the circular part, not pulled toward the handle.
    """
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
    cv2.imwrite(str(path), img)
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
