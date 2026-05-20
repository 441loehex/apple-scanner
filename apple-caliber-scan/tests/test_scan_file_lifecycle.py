"""Tests proving raw scan file deletion after ingest (privacy requirement)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


def _write_minimal_ply(path: Path) -> None:
    """Write a valid 3-point PLY file for testing."""
    content = (
        "ply\n"
        "format ascii 1.0\n"
        "element vertex 3\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "end_header\n"
        "0.0 0.0 0.5\n"
        "0.1 0.0 0.5\n"
        "0.0 0.1 0.5\n"
    )
    path.write_text(content)


def test_ingest_from_local_file_deletes_source(tmp_path):
    """After ingest_from_local_file, the source file must not exist."""
    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate

    # Build a scan file using plyfile to write synthetic data
    try:
        import plyfile
    except ImportError:
        pytest.skip("plyfile not available")

    points = generate_synthetic_crate(n_apples=10, seed=0)
    scan_file = tmp_path / "test_scan.ply"

    # Write a proper PLY via plyfile
    vertices = np.array(
        [(r[0], r[1], r[2]) for r in points],
        dtype=[("x", "f4"), ("y", "f4"), ("z", "f4")],
    )
    el = plyfile.PlyElement.describe(vertices, "vertex")
    plyfile.PlyData([el]).write(str(scan_file))

    assert scan_file.exists()

    from apple_caliber_scan.services.ingest import ingest_from_local_file

    preview_path, circles, count, auto_ring = ingest_from_local_file(
        scan_file, scan_id=1, batch_id=1, delete_after=True
    )

    assert not scan_file.exists(), "Raw scan file must be deleted after ingest"
    assert preview_path.exists(), "Preview PNG must be created"


def test_ingest_from_local_file_delete_after_false_preserves_file(tmp_path):
    """With delete_after=False, source file must be preserved."""
    try:
        import plyfile
    except ImportError:
        pytest.skip("plyfile not available")

    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate
    from apple_caliber_scan.services.ingest import ingest_from_local_file

    points = generate_synthetic_crate(n_apples=5, seed=7)
    scan_file = tmp_path / "keep_scan.ply"

    vertices = np.array(
        [(r[0], r[1], r[2]) for r in points],
        dtype=[("x", "f4"), ("y", "f4"), ("z", "f4")],
    )
    el = plyfile.PlyElement.describe(vertices, "vertex")
    plyfile.PlyData([el]).write(str(scan_file))

    assert scan_file.exists()

    ingest_from_local_file(scan_file, scan_id=2, batch_id=1, delete_after=False)

    assert scan_file.exists(), "File must remain when delete_after=False"


def test_ingest_synthetic_creates_preview_no_scan_file(tmp_path):
    """ingest_synthetic must create a preview without leaving any scan file."""
    import apple_caliber_scan.config as cfg
    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate
    from apple_caliber_scan.services.ingest import ingest_synthetic

    points = generate_synthetic_crate(n_apples=10, seed=1)

    preview_path, circles, count, auto_ring = ingest_synthetic(points, scan_id=3, batch_id=1)

    assert preview_path.exists()
    assert count > 0
    # No leftover PLY/ZIP files in DATA_DIR
    scan_files = list(cfg.DATA_DIR.glob("*.ply")) + list(cfg.DATA_DIR.glob("*.zip"))
    assert len(scan_files) == 0, f"Leftover scan files found: {scan_files}"


def test_drive_ingest_deletes_temp_file_on_failure(tmp_path, monkeypatch):
    """On download failure, the temp file must still be deleted."""
    import apple_caliber_scan.config as cfg
    from apple_caliber_scan.services.ingest import IngestError, ingest_from_drive_url
    from apple_caliber_scan.storage.drive import DriveDownloadError

    def mock_extract(url: str) -> str | None:
        return "fake-file-id"

    def mock_download(file_id: str, dest: Path, timeout_s: int = 60) -> None:
        raise DriveDownloadError("Simulated download failure")

    monkeypatch.setattr(
        "apple_caliber_scan.services.ingest.extract_drive_file_id", mock_extract
    )
    monkeypatch.setattr(
        "apple_caliber_scan.services.ingest.download_drive_file", mock_download
    )

    with pytest.raises(IngestError):
        ingest_from_drive_url(
            "https://drive.google.com/file/d/fake-id/view",
            scan_id=4,
            batch_id=1,
        )

    # No PLY files should remain in DATA_DIR
    scan_files = list(cfg.DATA_DIR.glob("*.ply"))
    assert len(scan_files) == 0, f"Temp scan files leaked: {scan_files}"
