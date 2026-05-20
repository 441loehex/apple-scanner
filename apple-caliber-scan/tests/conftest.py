"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def set_required_env(tmp_path, monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("ACS_WEB_PASSWORD", "test-password-123")
    monkeypatch.setenv("ACS_WEB_SECRET_KEY", "test-secret-key-32-bytes-xxxxxxxx")
    monkeypatch.setenv("ACS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ACS_DB_PATH", str(tmp_path / "data" / "test.db"))
    # Reload config with new env
    import apple_caliber_scan.config as cfg
    cfg._WEB_PASSWORD = os.environ["ACS_WEB_PASSWORD"]
    cfg._WEB_SECRET_KEY = os.environ["ACS_WEB_SECRET_KEY"]
    cfg.DATA_DIR = Path(os.environ["ACS_DATA_DIR"])
    cfg.DB_PATH = Path(os.environ["ACS_DB_PATH"])
    cfg.ensure_data_dirs()


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite database with initialized schema."""
    db_path = tmp_path / "test.db"
    from apple_caliber_scan.database.connection import initialize_schema
    from apple_caliber_scan.database.crud import seed_varieties

    initialize_schema(db_path)
    seed_varieties(db_path)
    return db_path


@pytest.fixture
def synthetic_points():
    """Synthetic point cloud for testing."""
    from apple_caliber_scan.scan.fixtures import generate_synthetic_crate
    return generate_synthetic_crate(n_apples=20, seed=42)


@pytest.fixture
def test_client(tmp_db):
    """FastAPI test client with authenticated session."""
    from fastapi.testclient import TestClient

    import apple_caliber_scan.config as cfg
    from apple_caliber_scan.web.app import create_app

    cfg.DB_PATH = tmp_db
    app = create_app()
    client = TestClient(app, raise_server_exceptions=True)
    return client


@pytest.fixture
def auth_client(test_client):
    """Authenticated test client."""
    test_client.post(
        "/login",
        data={"username": "freshora", "password": "test-password-123"},
        follow_redirects=True,
    )
    return test_client
