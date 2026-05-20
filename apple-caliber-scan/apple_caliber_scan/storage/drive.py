"""Google Drive URL parsing and file download via gdown."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class DriveDownloadError(Exception):
    pass


def extract_drive_file_id(url: str) -> str | None:
    """
    Extract Google Drive file ID from common URL formats.
    Returns file ID string or None if not a recognized Drive URL.
    """
    if not url:
        return None

    # https://drive.google.com/file/d/{ID}/view...
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)

    parsed = urlparse(url)
    if "google.com" not in parsed.netloc and "docs.google.com" not in parsed.netloc:
        return None

    # ?id={ID}
    qs = parse_qs(parsed.query)
    if "id" in qs:
        return qs["id"][0]

    return None


def download_drive_file(
    file_id: str,
    dest_path: Path,
    timeout_s: int = 120,
) -> Path:
    """
    Download file from Google Drive to dest_path using gdown.
    Raises DriveDownloadError on failure.
    """
    try:
        import gdown
    except ImportError as e:
        raise DriveDownloadError("gdown is not installed — run: pip install gdown") from e

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        logger.info("Downloading Drive file %s → %s", file_id, dest_path)
        # gdown >= 6.0 removed fuzzy kwarg; use id= directly instead of constructing URL
        gdown.download(id=file_id, output=str(dest_path), quiet=False)
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise DriveDownloadError(f"gdown failed for file_id={file_id}: {e}") from e

    if not dest_path.exists() or dest_path.stat().st_size == 0:
        dest_path.unlink(missing_ok=True)
        raise DriveDownloadError(
            f"Download completed but file is missing or empty: {dest_path}"
        )

    logger.info("Download complete: %s (%d bytes)", dest_path, dest_path.stat().st_size)
    return dest_path
