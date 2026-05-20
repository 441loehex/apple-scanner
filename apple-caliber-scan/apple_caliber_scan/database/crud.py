"""All database read/write functions."""

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from apple_caliber_scan.database.connection import db_conn

DEFAULT_VARIETIES = [
    "Red Cap", "Red Chief", "Jeromine", "Jeronimo", "Golden Delicious",
    "Ligol", "Szampion", "Idared", "Jonagold", "Jonagored",
    "Gala", "Fuji", "Elstar", "Lobo", "Champion", "Cortland",
    "TEST - Polycam",
]


def seed_varieties(db_path: Path | None = None) -> None:
    with db_conn(db_path) as conn:
        for name in DEFAULT_VARIETIES:
            conn.execute(
                "INSERT OR IGNORE INTO varieties (name, use_count) VALUES (?, 1)",
                (name,),
            )


# --- Batches ---

def create_batch(
    conn: sqlite3.Connection,
    seller_name: str,
    variety: str,
    seller_address: str | None = None,
    price_pln_per_kg: float | None = None,
    ca_opening_date: str | None = None,
    operator_batch_id: str | None = None,
    notes: str | None = None,
    number_of_crates: int = 1,
    total_weight_kg: float = 300.0,
    telegram_chat_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO batches
           (seller_name, seller_address, variety, price_pln_per_kg, ca_opening_date,
            operator_batch_id, notes, number_of_crates, total_weight_kg, telegram_chat_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (seller_name, seller_address, variety, price_pln_per_kg, ca_opening_date,
         operator_batch_id, notes, number_of_crates, total_weight_kg, telegram_chat_id),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_batch(conn: sqlite3.Connection, batch_id: int) -> sqlite3.Row | None:
    return cast(
        "sqlite3.Row | None",
        conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone(),
    )


def list_batches(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM batches ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


def update_batch_status(conn: sqlite3.Connection, batch_id: int, status: str) -> None:
    conn.execute(
        "UPDATE batches SET status=?, updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
        (status, batch_id),
    )


def delete_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))


# --- Scans ---

def create_scan(
    conn: sqlite3.Connection,
    batch_id: int,
    drive_url: str | None = None,
    drive_file_id: str | None = None,
    fmt: str | None = None,
    calibration_ring_mm: float = 75.0,
) -> int:
    cur = conn.execute(
        """INSERT INTO scans (batch_id, drive_url, drive_file_id, format, calibration_ring_mm)
           VALUES (?,?,?,?,?)""",
        (batch_id, drive_url, drive_file_id, fmt, calibration_ring_mm),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_scan(conn: sqlite3.Connection, scan_id: int) -> sqlite3.Row | None:
    return cast(
        "sqlite3.Row | None",
        conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone(),
    )


def list_scans_for_batch(conn: sqlite3.Connection, batch_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM scans WHERE batch_id=? ORDER BY ingested_at DESC", (batch_id,)
    ).fetchall()


def update_scan(conn: sqlite3.Connection, scan_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [scan_id]
    conn.execute(f"UPDATE scans SET {sets} WHERE id=?", vals)


def delete_scan_circles(conn: sqlite3.Connection, scan_id: int) -> None:
    conn.execute("DELETE FROM scan_circles WHERE scan_id=?", (scan_id,))


# --- Scan Circles ---

def insert_circles(
    conn: sqlite3.Connection,
    scan_id: int,
    circles: list[dict[str, Any]],
) -> None:
    conn.executemany(
        """INSERT INTO scan_circles
           (scan_id, cx_px, cy_px, radius_px, ellipse_major_px, ellipse_minor_px,
            ellipse_angle_deg, orientation, confidence, annotated_by)
           VALUES (:scan_id, :cx_px, :cy_px, :radius_px, :ellipse_major_px,
                   :ellipse_minor_px, :ellipse_angle_deg, :orientation,
                   :confidence, :annotated_by)""",
        [
            {
                "scan_id": scan_id,
                "ellipse_major_px": 0.0,
                "ellipse_minor_px": 0.0,
                "ellipse_angle_deg": 0.0,
                "orientation": "unknown",
                **c,
            }
            for c in circles
        ],
    )


def get_circles_for_scan(conn: sqlite3.Connection, scan_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM scan_circles WHERE scan_id=? ORDER BY confidence DESC",
        (scan_id,),
    ).fetchall()


def update_circle(conn: sqlite3.Connection, circle_id: int, **kwargs: Any) -> None:
    if not kwargs:
        return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [circle_id]
    conn.execute(f"UPDATE scan_circles SET {sets} WHERE id=?", vals)


def mark_ring_circle(conn: sqlite3.Connection, scan_id: int, circle_id: int) -> None:
    conn.execute("UPDATE scan_circles SET is_ring=0 WHERE scan_id=?", (scan_id,))
    conn.execute("UPDATE scan_circles SET is_ring=1 WHERE id=?", (circle_id,))


# --- Annotations ---

def create_annotation(
    conn: sqlite3.Connection,
    scan_id: int,
    ring_circle_id: int | None,
    annotated_by: str = "web",
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO annotations (scan_id, ring_circle_id, annotated_by, notes) VALUES (?,?,?,?)",
        (scan_id, ring_circle_id, annotated_by, notes),
    )
    return cur.lastrowid  # type: ignore[return-value]


# --- Reports ---

def create_report(
    conn: sqlite3.Connection,
    batch_id: int,
    scan_id: int | None,
    html_path: str | None = None,
    pdf_path: str | None = None,
    json_path: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO reports"
        " (batch_id, scan_id, html_path, pdf_path, json_path) VALUES (?,?,?,?,?)",
        (batch_id, scan_id, html_path, pdf_path, json_path),
    )
    return cur.lastrowid  # type: ignore[return-value]


def get_report(conn: sqlite3.Connection, report_id: int) -> sqlite3.Row | None:
    return cast(
        "sqlite3.Row | None",
        conn.execute(
            "SELECT * FROM reports WHERE id=? AND is_deleted=0", (report_id,)
        ).fetchone(),
    )


def list_reports_for_batch(conn: sqlite3.Connection, batch_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reports WHERE batch_id=? AND is_deleted=0 ORDER BY generated_at DESC",
        (batch_id,),
    ).fetchall()


def soft_delete_reports_for_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    conn.execute("UPDATE reports SET is_deleted=1 WHERE batch_id=?", (batch_id,))


# --- Varieties ---

def list_varieties(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT name FROM varieties ORDER BY use_count DESC, name ASC LIMIT ?", (limit,)
    ).fetchall()


def upsert_variety(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        """INSERT INTO varieties (name, use_count) VALUES (?, 1)
           ON CONFLICT(name) DO UPDATE SET use_count = use_count + 1""",
        (name,),
    )


# --- Ground Truth ---

def insert_ground_truth(
    conn: sqlite3.Connection,
    batch_id: int,
    grader_results: dict[str, Any],
    source: str = "manual",
    weight_kg: float | None = None,
    graded_at: str | None = None,
    notes: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO ground_truth
           (batch_id, source, grader_results, weight_kg, graded_at, notes)
           VALUES (?,?,?,?,?,?)""",
        (batch_id, source, json.dumps(grader_results), weight_kg, graded_at, notes),
    )
    return cur.lastrowid  # type: ignore[return-value]


def has_ground_truth(conn: sqlite3.Connection, batch_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM ground_truth WHERE batch_id=? LIMIT 1", (batch_id,)
    ).fetchone()
    return row is not None


def get_ground_truth(conn: sqlite3.Connection, batch_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ground_truth WHERE batch_id=? ORDER BY imported_at DESC", (batch_id,)
    ).fetchall()


# --- Telegram Sessions ---

def get_telegram_session(conn: sqlite3.Connection, chat_id: int) -> sqlite3.Row | None:
    return cast(
        "sqlite3.Row | None",
        conn.execute(
            "SELECT * FROM telegram_sessions WHERE chat_id=?", (chat_id,)
        ).fetchone(),
    )


def upsert_telegram_session(
    conn: sqlite3.Connection, chat_id: int, state: str, context: dict[str, Any]
) -> None:
    conn.execute(
        """INSERT INTO telegram_sessions (chat_id, state, context)
           VALUES (?,?,?)
           ON CONFLICT(chat_id) DO UPDATE SET
             state=excluded.state,
             context=excluded.context,
             updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
        (chat_id, state, json.dumps(context)),
    )
