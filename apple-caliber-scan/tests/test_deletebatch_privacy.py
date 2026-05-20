"""Tests proving /batches/{id}/delete removes all batch data (privacy requirement)."""

from __future__ import annotations

import sqlite3


def test_deletebatch_removes_db_record(tmp_db, auth_client):
    """After /delete, the batch must not appear in list or detail."""
    r = auth_client.post(
        "/batches",
        data={
            "seller_name": "Delete Test",
            "seller_address": "Addr",
            "variety": "Jonagold",
            "operator_batch_id": "DEL-001",
            "number_of_crates": 1,
            "total_weight_kg": 100.0,
            "price_pln_per_kg": 2.0,
            "ca_opening_date": "2026-05-19",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    location = r.headers.get("location", "")
    batch_id = int(location.rstrip("/").split("/")[-1])

    # Batch should exist
    detail = auth_client.get(f"/batches/{batch_id}")
    assert detail.status_code == 200

    # Delete the batch
    del_r = auth_client.post(f"/batches/{batch_id}/delete", follow_redirects=False)
    assert del_r.status_code in (302, 303)

    # Batch must no longer be found — detail returns 404 or redirect
    detail_after = auth_client.get(f"/batches/{batch_id}")
    assert detail_after.status_code in (404, 302, 303)


def test_deletebatch_removes_scans_from_db(tmp_db, auth_client, monkeypatch):
    """After /delete, no scan records for the batch should remain in DB."""
    # Create a batch first
    r = auth_client.post(
        "/batches",
        data={
            "seller_name": "Scan Privacy Test",
            "seller_address": "Addr",
            "variety": "Jonagold",
            "operator_batch_id": "PRIV-002",
            "number_of_crates": 1,
            "total_weight_kg": 50.0,
            "price_pln_per_kg": 1.5,
            "ca_opening_date": "2026-05-19",
            "notes": "",
        },
        follow_redirects=False,
    )
    location = r.headers.get("location", "")
    batch_id = int(location.rstrip("/").split("/")[-1])

    # Insert a scan record directly into DB to simulate an ingested scan
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO scans
              (batch_id, drive_url, status, preview_path, point_count, ingested_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (batch_id, None, "done", None, 0),
        )
        conn.commit()

    # Verify scan exists
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id FROM scans WHERE batch_id=?", (batch_id,)).fetchall()
        assert len(rows) >= 1

    # Delete the batch
    auth_client.post(f"/batches/{batch_id}/delete", follow_redirects=False)

    # Scans must be gone (FK cascade or explicit delete)
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        rows_after = conn.execute(
            "SELECT id FROM scans WHERE batch_id=?", (batch_id,)
        ).fetchall()
        assert len(rows_after) == 0, "Scan records must be removed when batch is deleted"


def test_deletebatch_preview_file_removed(tmp_db, auth_client, tmp_path, monkeypatch):
    """After /delete, preview PNG files for scans in that batch must be removed."""
    import apple_caliber_scan.config as cfg

    # Create batch
    r = auth_client.post(
        "/batches",
        data={
            "seller_name": "Preview Privacy",
            "seller_address": "Addr",
            "variety": "Golden",
            "operator_batch_id": "PREV-003",
            "number_of_crates": 1,
            "total_weight_kg": 50.0,
            "price_pln_per_kg": 1.5,
            "ca_opening_date": "2026-05-19",
            "notes": "",
        },
        follow_redirects=False,
    )
    location = r.headers.get("location", "")
    batch_id = int(location.rstrip("/").split("/")[-1])

    # Create a fake preview file
    previews_dir = cfg.DATA_DIR / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    preview_file = previews_dir / f"scan_99_batch_{batch_id}.png"
    preview_file.write_bytes(b"\x89PNG\r\n")  # minimal PNG header

    # Insert scan with preview_path
    with sqlite3.connect(str(tmp_db)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO scans
              (batch_id, drive_url, status, preview_path, point_count, ingested_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (batch_id, None, "done", str(preview_file), 0),
        )
        conn.commit()

    assert preview_file.exists()

    # Delete the batch
    auth_client.post(f"/batches/{batch_id}/delete", follow_redirects=False)

    assert not preview_file.exists(), "Preview PNG must be deleted with the batch"


def test_deletebatch_nonexistent_returns_404(auth_client):
    """Attempting to delete a non-existent batch must return 404."""
    r = auth_client.post("/batches/99999/delete")
    assert r.status_code == 404


def test_deletebatch_requires_auth(test_client):
    """Unauthenticated /delete request must redirect to login."""
    r = test_client.post("/batches/1/delete", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "login" in r.headers.get("location", "").lower()
