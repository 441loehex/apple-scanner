"""Synthetic point cloud generator for testing and sample report generation."""

from __future__ import annotations

import math

import numpy as np


def generate_synthetic_crate(
    n_apples: int = 40,
    diameter_distribution: dict[str, float] | None = None,
    seed: int = 42,
    crate_size_m: float = 0.6,
    ring_mm: float = 75.0,
) -> np.ndarray:
    """
    Generate a (N, 3) float32 point cloud representing a crate top layer.
    Places spherical apple clusters at random XY positions.
    Includes one measuring ring (simulated as a circle of points) at a fixed position.
    Returns deterministic array for given seed.
    """
    rng = np.random.default_rng(seed)

    if diameter_distribution is None:
        diameter_distribution = {
            "0-60": 0.05, "60-65": 0.10, "65-70": 0.15, "70-75": 0.20,
            "75-80": 0.25, "80-85": 0.15, "85-90": 0.07, "90+": 0.03,
        }

    class_diameters = {
        "0-60": 50.0, "60-65": 62.0, "65-70": 67.0, "70-75": 72.0,
        "75-80": 77.0, "80-85": 82.0, "85-90": 87.0, "90+": 95.0,
    }

    # Build apple diameter list from distribution
    apple_diameters_mm: list[float] = []
    labels = list(diameter_distribution.keys())
    fracs = np.array([diameter_distribution[lb] for lb in labels], dtype=float)
    fracs /= fracs.sum()
    counts = (fracs * n_apples).astype(int)
    counts[-1] = n_apples - counts[:-1].sum()  # fix rounding

    for label, count in zip(labels, counts):
        base_d = class_diameters[label]
        for _ in range(count):
            d = float(rng.normal(base_d, 2.0))
            d = max(40.0, min(120.0, d))
            apple_diameters_mm.append(d)

    all_points: list[np.ndarray] = []

    # Place apples in a grid-like pattern with jitter
    grid_n = math.ceil(math.sqrt(n_apples)) + 1
    spacing = crate_size_m / grid_n
    positions: list[tuple[float, float]] = []

    for i in range(grid_n):
        for j in range(grid_n):
            x = (i + 0.5) * spacing + float(rng.uniform(-spacing * 0.3, spacing * 0.3))
            y = (j + 0.5) * spacing + float(rng.uniform(-spacing * 0.3, spacing * 0.3))
            positions.append((x, y))

    rng.shuffle(positions)  # type: ignore[arg-type]
    positions = positions[:n_apples]

    for (cx, cy), d_mm in zip(positions, apple_diameters_mm):
        r_m = (d_mm / 1000.0) / 2.0
        n_pts = max(20, int(n_apples * 3))
        # Sample hemisphere top surface
        theta = rng.uniform(0, 2 * math.pi, n_pts)
        phi = rng.uniform(0, math.pi / 2, n_pts)
        xs = cx + r_m * np.sin(phi) * np.cos(theta)
        ys = cy + r_m * np.sin(phi) * np.sin(theta)
        zs = 0.5 + r_m * np.cos(phi)  # base height 0.5
        pts = np.column_stack([xs, ys, zs]).astype(np.float32)
        all_points.append(pts)

    # Measuring ring: simulate as a thin ring of points at a fixed corner position
    ring_r_m = (ring_mm / 1000.0) / 2.0
    ring_cx = crate_size_m * 0.85
    ring_cy = crate_size_m * 0.85
    ring_z = 0.5
    n_ring_pts = 80
    angles = np.linspace(0, 2 * math.pi, n_ring_pts, endpoint=False)
    rx = ring_cx + ring_r_m * np.cos(angles)
    ry = ring_cy + ring_r_m * np.sin(angles)
    rz = np.full(n_ring_pts, ring_z, dtype=np.float32)
    ring_pts = np.column_stack([rx, ry, rz]).astype(np.float32)
    all_points.append(ring_pts)

    return np.vstack(all_points).astype(np.float32)


# Known fixture info for the default seed=42 crate
SYNTHETIC_RING_POSITION = (0.85, 0.85)  # normalized (before normalization step)
SYNTHETIC_RING_MM = 75.0
