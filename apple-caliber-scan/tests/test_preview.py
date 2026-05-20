"""Tests for preview.py — colour rendering and blue ring preservation."""

import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from apple_caliber_scan.scan.preview import render_preview


def test_no_green_cast_from_clahe():
    """
    A scene with red apples and a green background must render with R > G for the
    apple region.  The CLAHE removal means green is not amplified into apple areas.
    """
    rng = np.random.default_rng(99)
    # Red apple points (top layer, col2 = height ~1.0)
    apples = np.zeros((2000, 6), dtype=np.float32)
    apples[:, 0] = rng.uniform(0.2, 0.8, 2000)  # X
    apples[:, 1] = rng.uniform(0.2, 0.8, 2000)  # Z (horizontal in image)
    apples[:, 2] = 1.0                           # Y_norm = 1.0 (top)
    apples[:, 3] = 200
    apples[:, 4] = 40
    apples[:, 5] = 40  # red

    # Green background points (lower layer, col2 = 0.0)
    bg = np.zeros((2000, 6), dtype=np.float32)
    bg[:, 0] = rng.uniform(0, 1, 2000)
    bg[:, 1] = rng.uniform(0, 1, 2000)
    bg[:, 2] = 0.0
    bg[:, 3] = 30
    bg[:, 4] = 170
    bg[:, 5] = 130  # green

    pts = np.vstack([apples, bg])
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        img = np.array(Image.open(out))
        # Centre region should be predominantly red (apple tops)
        centre = img[350:650, 350:650]
        assert float(centre[:, :, 0].mean()) > float(centre[:, :, 2].mean()), \
            "Centre region should be red-dominant (apple tops, not green background)"
    finally:
        out.unlink(missing_ok=True)


def test_colored_preview_preserves_blue_ring():
    """Blue ring pixels must survive rendering without being bleached to grey."""
    rng = np.random.default_rng(0)

    apples = np.zeros((1000, 6), dtype=np.float32)
    apples[:, 0] = rng.uniform(0.1, 0.9, 1000)
    apples[:, 1] = rng.uniform(0.1, 0.9, 1000)
    apples[:, 2] = rng.uniform(0.8, 1.0, 1000)
    apples[:, 3] = 200
    apples[:, 4] = 30
    apples[:, 5] = 30

    theta = np.linspace(0, 2 * np.pi, 200)
    ring = np.zeros((200, 6), dtype=np.float32)
    ring[:, 0] = 0.5 + 0.08 * np.cos(theta)
    ring[:, 1] = 0.5 + 0.08 * np.sin(theta)
    ring[:, 2] = 0.95
    ring[:, 3] = 10
    ring[:, 4] = 30
    ring[:, 5] = 220

    pts = np.vstack([apples, ring])
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        img = np.array(Image.open(out))
        blue_dom = (
            (img[:, :, 2].astype(int) > 80) &
            (img[:, :, 2].astype(int) > img[:, :, 0].astype(int) * 1.3) &
            (img[:, :, 2].astype(int) > img[:, :, 1].astype(int) * 1.3)
        )
        assert blue_dom.sum() > 50, \
            f"Blue ring not visible after rendering ({blue_dom.sum()} blue-dominant px)"
    finally:
        out.unlink(missing_ok=True)


def test_dark_background():
    """With the new BG=40 setting, the mean pixel value should be darker than the old 160."""
    rng = np.random.default_rng(1)
    pts = np.zeros((500, 6), dtype=np.float32)
    # Very sparse scan in a small corner — most canvas stays background
    pts[:, 0] = rng.uniform(0.01, 0.05, 500)
    pts[:, 1] = rng.uniform(0.01, 0.05, 500)
    pts[:, 2] = 0.9
    pts[:, 3] = 200
    pts[:, 4] = 50
    pts[:, 5] = 50

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        img = np.array(Image.open(out))
        mean_all = img.mean()
        # The dominant background at BG=40 keeps the image dark
        assert mean_all < 120, f"Image too bright ({mean_all:.1f}) — background should be dark"
    finally:
        out.unlink(missing_ok=True)


def test_render_xyz_only_fallback():
    """Height-based fallback (no colour) must produce a valid PNG."""
    rng = np.random.default_rng(2)
    pts = rng.uniform(size=(500, 3)).astype(np.float32)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        out = Path(f.name)
    try:
        render_preview(pts, out)
        assert out.exists()
        img = np.array(Image.open(out))
        assert img.shape == (1024, 1024, 3)
    finally:
        out.unlink(missing_ok=True)
