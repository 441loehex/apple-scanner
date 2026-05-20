"""Synthetic ingest pipeline tests."""

from __future__ import annotations


def test_synthetic_crate_not_empty(synthetic_points):
    assert len(synthetic_points) > 0


def test_synthetic_crate_shape(synthetic_points):
    assert synthetic_points.ndim == 2
    assert synthetic_points.shape[1] == 3


def test_synthetic_crate_deterministic():
    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate
    a = generate_synthetic_crate(seed=42)
    b = generate_synthetic_crate(seed=42)
    assert (a == b).all()


def test_synthetic_crate_different_seeds():

    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate
    a = generate_synthetic_crate(seed=1)
    b = generate_synthetic_crate(seed=2)
    assert not (a == b).all()


def test_normalize_top_down_xy_range(synthetic_points):
    from apple_caliber_scan.scan.normalizer import normalize_top_down
    normalized = normalize_top_down(synthetic_points)
    assert normalized.shape[1] == 3
    assert normalized[:, 0].min() >= -0.01
    assert normalized[:, 0].max() <= 1.01
    assert normalized[:, 1].min() >= -0.01
    assert normalized[:, 1].max() <= 1.01


def test_render_preview_creates_file(synthetic_points, tmp_path):
    from apple_caliber_scan.scan.normalizer import normalize_top_down
    from apple_caliber_scan.scan.preview import render_preview

    normalized = normalize_top_down(synthetic_points)
    out = tmp_path / "test_preview.png"
    render_preview(normalized, out, width=256, height=256)
    assert out.exists()
    assert out.stat().st_size > 0


def test_detect_circles_on_preview(synthetic_points, tmp_path):
    from apple_caliber_scan.scan.detector import detect_circles
    from apple_caliber_scan.scan.normalizer import normalize_top_down
    from apple_caliber_scan.scan.preview import render_preview

    normalized = normalize_top_down(synthetic_points)
    out = tmp_path / "preview.png"
    render_preview(normalized, out, width=512, height=512)
    circles = detect_circles(out, min_radius_px=5, max_radius_px=100)
    assert len(circles) >= 1


def test_detect_circles_returns_circle_objects(synthetic_points, tmp_path):
    from apple_caliber_scan.scan.detector import Circle, detect_circles
    from apple_caliber_scan.scan.normalizer import normalize_top_down
    from apple_caliber_scan.scan.preview import render_preview

    normalized = normalize_top_down(synthetic_points)
    out = tmp_path / "preview2.png"
    render_preview(normalized, out, width=256, height=256)
    circles = detect_circles(out)
    for c in circles:
        assert isinstance(c, Circle)
        assert c.radius_px > 0
        assert 0 <= c.cx <= 256
        assert 0 <= c.cy <= 256
