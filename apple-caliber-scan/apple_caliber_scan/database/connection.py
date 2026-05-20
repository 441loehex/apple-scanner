"""SQLite connection factory with WAL mode."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from apple_caliber_scan import config


def get_db_path() -> Path:
    return config.DB_PATH


def init_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    conn = sqlite3.connect(str(path))
    init_connection(conn)
    return conn


@contextmanager
def db_conn(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_schema(db_path: Path | None = None) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    sql = schema_path.read_text()
    with db_conn(db_path) as conn:
        conn.executescript(sql)
        # Migration: add ellipse columns for existing databases
        for col, default in [
            ("ellipse_major_px", "0.0"),
            ("ellipse_minor_px", "0.0"),
            ("ellipse_angle_deg", "0.0"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE scan_circles ADD COLUMN {col} REAL DEFAULT {default}"
                )
            except Exception:
                pass  # Column already exists

        # Migration: orientation column for scan_circles
        try:
            conn.execute("ALTER TABLE scan_circles ADD COLUMN orientation TEXT DEFAULT 'unknown'")
        except Exception:
            pass

        # Migration: auto-ring columns for scans
        for col, typ in [
            ("auto_ring_cx_px", "REAL"),
            ("auto_ring_cy_px", "REAL"),
            ("auto_ring_radius_px", "REAL"),
            ("auto_ring_confidence", "REAL DEFAULT 0.0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE scans ADD COLUMN {col} {typ}")
            except Exception:
                pass
