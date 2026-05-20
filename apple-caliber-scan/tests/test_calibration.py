"""Scale factor correctness and suspicious scale warning tests."""

from apple_caliber_scan.scan.detector import Circle
from apple_caliber_scan.services.calibration import compute_scale_factor


def test_scale_factor_basic():
    # 75mm ring at 100px diameter → scale = 75/100 = 0.75 mm/px
    ring = Circle(cx=100, cy=100, radius_px=50.0)
    result = compute_scale_factor(ring, ring_mm=75.0)
    assert abs(result.scale_factor_mm_per_px - 0.75) < 1e-9
    assert result.confidence == "ok"
    assert result.warning is None


def test_scale_factor_small_ring_low_confidence():
    # A ring detected at very small size → LOW confidence
    ring = Circle(cx=100, cy=100, radius_px=2.0)  # 4px diameter — suspicious
    result = compute_scale_factor(ring, ring_mm=75.0)
    assert result.confidence == "low"
    assert result.warning is not None


def test_scale_factor_suspicious_apple_mean_too_small():
    # Ring at 100px radius, scale=0.75 → apple at 10px radius → 15mm → suspicious
    ring = Circle(cx=200, cy=200, radius_px=50.0)
    tiny_apples = [Circle(cx=100, cy=100, radius_px=10.0) for _ in range(5)]
    result = compute_scale_factor(ring, ring_mm=75.0, apple_circles=tiny_apples)
    # 10 * 2 * 0.75 = 15mm → far below 40mm → LOW confidence
    assert result.confidence == "low"


def test_scale_factor_suspicious_apple_mean_too_large():
    # Ring at 50px radius, scale=0.75 → apple at 100px radius → 150mm → suspicious
    ring = Circle(cx=200, cy=200, radius_px=50.0)
    huge_apples = [Circle(cx=100, cy=100, radius_px=100.0) for _ in range(5)]
    result = compute_scale_factor(ring, ring_mm=75.0, apple_circles=huge_apples)
    assert result.confidence == "low"


def test_scale_applied_to_circle_diameter():
    ring = Circle(cx=100, cy=100, radius_px=50.0)  # scale = 0.75 mm/px
    result = compute_scale_factor(ring, ring_mm=75.0)
    # Circle with 80px radius → diameter = 160px → 160 * 0.75 = 120mm
    apple_diameter_mm = 80.0 * 2 * result.scale_factor_mm_per_px
    assert abs(apple_diameter_mm - 120.0) < 0.01
    from apple_caliber_scan.services.estimation import classify_diameter
    assert classify_diameter(apple_diameter_mm) == "90+"


def test_scale_factor_plausible_apples():
    # Ring at 100px diameter (50px radius), scale=0.75
    # Apples at ~50-60px radius → 75-90mm → plausible
    ring = Circle(cx=500, cy=500, radius_px=50.0)
    apples = [Circle(cx=x * 100, cy=100, radius_px=52.0) for x in range(5)]
    result = compute_scale_factor(ring, ring_mm=75.0, apple_circles=apples)
    assert result.confidence == "ok"
