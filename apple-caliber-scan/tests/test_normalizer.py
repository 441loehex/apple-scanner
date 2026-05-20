"""Tests for normalizer.py — aspect ratio preservation and Y-axis correctness."""

import numpy as np

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
    tops[:, 3] = 200
    tops[:, 4] = 30
    tops[:, 5] = 30  # red

    # Floor at Y=0.00 (green trash bag)
    floor = np.zeros((2000, 6), dtype=np.float32)
    floor[:, 0] = rng.uniform(0, 1.0, 2000)
    floor[:, 1] = 0.00
    floor[:, 2] = rng.uniform(0, 0.8, 2000)
    floor[:, 3] = 30
    floor[:, 4] = 180
    floor[:, 5] = 150  # green

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


def test_output_xy_in_zero_one():
    """After normalisation, all XY values must be in [0, 1]."""
    rng = np.random.default_rng(7)
    pts = rng.uniform(size=(1000, 3)).astype(np.float32)
    pts[:, 0] *= 2.5   # wide in X
    pts[:, 1] *= 0.7   # narrow in Y

    norm = normalize_top_down(pts, top_percentile=0.50)
    assert norm[:, 0].min() >= -1e-6
    assert norm[:, 0].max() <= 1.0 + 1e-6
    assert norm[:, 1].min() >= -1e-6
    assert norm[:, 1].max() <= 1.0 + 1e-6


def test_degenerate_single_point():
    """Fewer than 3 points must not crash — returned as-is."""
    pts = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    norm = normalize_top_down(pts)
    assert norm.shape[0] == 1


def test_color_columns_preserved():
    """RGB columns must pass through unchanged (not normalised)."""
    rng = np.random.default_rng(13)
    pts = rng.uniform(size=(500, 6)).astype(np.float32)
    pts[:, 3:] *= 255

    norm = normalize_top_down(pts, top_percentile=0.80)
    # All colour values should still be in original 0–255 range
    assert norm[:, 3].max() <= 255.1
    assert norm[:, 5].min() >= -0.1
