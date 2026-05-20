"""All application settings loaded from environment variables."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(f"Required environment variable {name!r} is not set.")
    return val


def _get(name: str, default: str) -> str:
    return os.environ.get(name, default) or default


DATA_DIR = Path(_get("ACS_DATA_DIR", "./data"))
DB_PATH = Path(_get("ACS_DB_PATH", "./data/apple_caliber_scan.db"))
PUBLIC_BASE_URL = _get("ACS_PUBLIC_BASE_URL", "http://localhost:8000")
WEB_BASE_URL = _get("ACS_WEB_BASE_URL", "http://localhost:8000")
WEB_USERNAME = _get("ACS_WEB_USERNAME", "freshora")

LOG_LEVEL = _get("ACS_LOG_LEVEL", "INFO")
DEFAULT_CRATE_WEIGHT_KG = float(_get("ACS_DEFAULT_CRATE_WEIGHT_KG", "300"))
DEFAULT_RING_MM = float(_get("ACS_DEFAULT_RING_MM", "75.0"))
MAX_TRUCK_WEIGHT_KG = float(_get("ACS_MAX_TRUCK_WEIGHT_KG", "20000"))
LOGO_PATH: str | None = os.environ.get("ACS_LOGO_PATH") or None
GDOWN_TIMEOUT_S = int(_get("ACS_GDOWN_TIMEOUT_S", "120"))

TELEGRAM_TOKEN: str | None = os.environ.get("ACS_TELEGRAM_TOKEN") or None

# Lazy-validated: only checked when web app starts
_WEB_PASSWORD: str | None = os.environ.get("ACS_WEB_PASSWORD") or None
_WEB_SECRET_KEY: str | None = os.environ.get("ACS_WEB_SECRET_KEY") or None


def get_web_password() -> str:
    if not _WEB_PASSWORD:
        raise RuntimeError(
            "ACS_WEB_PASSWORD is not set. Set it in .env or environment before starting."
        )
    return _WEB_PASSWORD


def get_web_secret_key() -> str:
    if not _WEB_SECRET_KEY:
        raise RuntimeError(
            "ACS_WEB_SECRET_KEY is not set. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return _WEB_SECRET_KEY


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "previews").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "reports").mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
