"""Full scan ingestion pipeline: download → load → preview → detect → store → cleanup."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from apple_caliber_scan import config
from apple_caliber_scan.scan.detector import (
    Circle,
    classify_orientations,
    detect_calibration_ring,
    detect_circles,
)
from apple_caliber_scan.scan.loader import load_scan
from apple_caliber_scan.scan.normalizer import normalize_top_down
from apple_caliber_scan.scan.preview import render_preview
from apple_caliber_scan.storage.drive import (
    DriveDownloadError,
    download_drive_file,
    extract_drive_file_id,
)

logger = logging.getLogger(__name__)


class IngestError(Exception):
    pass


def ingest_from_drive_url(
    drive_url: str,
    scan_id: int,
    batch_id: int,
    fmt_hint: str | None = None,
) -> tuple[Path, list[Circle], int, Circle | None]:
    """
    Full pipeline: parse URL → download → load → normalize → preview → detect circles.
    Deletes local scan file after processing.

    Returns: (preview_path, circles, point_count, auto_ring)
    Raises: IngestError on any failure.
    """
    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        raise IngestError(f"Cannot extract Google Drive file ID from URL: {drive_url}")

    config.ensure_data_dirs()

    suffix = f".{fmt_hint}" if fmt_hint else ".ply"

    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False, dir=str(config.DATA_DIR)
    ) as tf:
        tmp_path = Path(tf.name)

    try:
        try:
            download_drive_file(file_id, tmp_path, timeout_s=config.GDOWN_TIMEOUT_S)
        except DriveDownloadError as e:
            raise IngestError(str(e)) from e

        return _process_local_file(tmp_path, scan_id, batch_id)

    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
                logger.info("Deleted local scan file: %s", tmp_path)
            except OSError as e:
                logger.warning("Could not delete local scan file %s: %s", tmp_path, e)


def ingest_from_local_file(
    file_path: Path,
    scan_id: int,
    batch_id: int,
    delete_after: bool = True,
) -> tuple[Path, list[Circle], int, Circle | None]:
    """
    Ingest a local scan file (used in testing/sample-report).
    Optionally deletes the source file after processing.
    """
    try:
        return _process_local_file(file_path, scan_id, batch_id)
    finally:
        if delete_after and file_path.exists():
            try:
                file_path.unlink()
                logger.info("Deleted local scan file after ingest: %s", file_path)
            except OSError as e:
                logger.warning("Could not delete %s: %s", file_path, e)


def _process_local_file(
    file_path: Path,
    scan_id: int,
    batch_id: int,
) -> tuple[Path, list[Circle], int, Circle | None]:
    """Load → normalize → preview → detect circles → auto-ring → classify orientations."""
    logger.info("Processing scan file: %s", file_path.name)

    try:
        points = load_scan(file_path)
    except Exception as e:
        raise IngestError(f"Failed to load scan file {file_path.name}: {e}") from e

    point_count = len(points)
    logger.info("Loaded %d points from %s", point_count, file_path.name)

    if point_count == 0:
        raise IngestError(f"Scan file {file_path.name} contains no points.")

    # Use 80% crop so the full apple surface is visible for human annotation.
    preview_pts = normalize_top_down(points, top_percentile=0.80)

    preview_dir = config.DATA_DIR / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"scan_{scan_id}_batch_{batch_id}.png"
    preview_path = preview_dir / preview_filename

    render_preview(preview_pts, preview_path)
    logger.info("Preview saved: %s", preview_path)

    circles = detect_circles(preview_path)
    logger.info("Detected %d circles", len(circles))

    # Auto-detect calibration ring from blue channel in the preview.
    auto_ring = detect_calibration_ring(preview_path)
    logger.info(
        "Auto ring detection: %s",
        (
            f"cx={auto_ring.cx:.0f} cy={auto_ring.cy:.0f} r={auto_ring.radius_px:.0f} "
            f"conf={auto_ring.confidence:.2f}"
        ) if auto_ring else "not found",
    )

    # Classify apple orientation from 3D Z-height profile.
    circles = classify_orientations(circles, preview_pts, preview_width=1024, preview_height=1024)
    orient_counts = {
        o: sum(1 for c in circles if c.orientation == o)
        for o in ("upright", "sideways", "angled", "unknown")
    }
    logger.info("Orientation classification: %s", orient_counts)

    return preview_path, circles, point_count, auto_ring


def ingest_synthetic(
    points: object,
    scan_id: int,
    batch_id: int,
) -> tuple[Path, list[Circle], int, Circle | None]:
    """Ingest a pre-loaded point cloud array (for sample-report and tests)."""
    import numpy as np

    if not isinstance(points, np.ndarray):
        raise IngestError("Expected numpy array")

    config.ensure_data_dirs()

    normalized = normalize_top_down(points)
    point_count = len(normalized)

    preview_dir = config.DATA_DIR / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_filename = f"scan_{scan_id}_batch_{batch_id}.png"
    preview_path = preview_dir / preview_filename

    render_preview(normalized, preview_path)
    circles = detect_circles(preview_path)
    auto_ring = detect_calibration_ring(preview_path)
    circles = classify_orientations(circles, normalized, preview_width=1024, preview_height=1024)

    return preview_path, circles, point_count, auto_ring
