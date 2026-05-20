-- schema.sql — apple-caliber-scan SQLite schema

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sellers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    address     TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS varieties (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    use_count   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id           INTEGER REFERENCES sellers(id) ON DELETE SET NULL,
    seller_name         TEXT NOT NULL,
    seller_address      TEXT,
    variety             TEXT NOT NULL,
    price_pln_per_kg    REAL,
    ca_opening_date     TEXT,
    operator_batch_id   TEXT,
    notes               TEXT,
    number_of_crates    INTEGER NOT NULL DEFAULT 1,
    total_weight_kg     REAL NOT NULL DEFAULT 300,
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    telegram_chat_id    INTEGER
);

CREATE TABLE IF NOT EXISTS scans (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id                INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    drive_url               TEXT,
    drive_file_id           TEXT,
    format                  TEXT,
    preview_path            TEXT,
    point_count             INTEGER,
    calibration_ring_mm     REAL NOT NULL DEFAULT 75.0,
    scale_factor_mm_per_px  REAL,
    calibration_confidence  TEXT NOT NULL DEFAULT 'uncalibrated',
    calibration_warning     TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending',
    error_message           TEXT,
    ingested_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    auto_ring_cx_px         REAL,
    auto_ring_cy_px         REAL,
    auto_ring_radius_px     REAL,
    auto_ring_confidence    REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS scan_circles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    cx_px           REAL NOT NULL,
    cy_px           REAL NOT NULL,
    radius_px       REAL NOT NULL,
    ellipse_major_px REAL DEFAULT 0.0,
    ellipse_minor_px REAL DEFAULT 0.0,
    ellipse_angle_deg REAL DEFAULT 0.0,
    orientation     TEXT DEFAULT 'unknown',
    diameter_mm     REAL,
    caliber_class   TEXT,
    is_ring         INTEGER NOT NULL DEFAULT 0,
    is_excluded     INTEGER NOT NULL DEFAULT 0,
    confidence      REAL,
    annotated_by    TEXT
);

CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ring_circle_id  INTEGER REFERENCES scan_circles(id) ON DELETE SET NULL,
    annotated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    annotated_by    TEXT,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    scan_id         INTEGER REFERENCES scans(id) ON DELETE SET NULL,
    html_path       TEXT,
    pdf_path        TEXT,
    json_path       TEXT,
    generated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    is_deleted      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ground_truth (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    source          TEXT NOT NULL DEFAULT 'manual',
    grader_results  TEXT NOT NULL,
    weight_kg       REAL,
    graded_at       TEXT,
    imported_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS telegram_sessions (
    chat_id         INTEGER PRIMARY KEY,
    state           TEXT NOT NULL DEFAULT 'idle',
    context         TEXT NOT NULL DEFAULT '{}',
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
CREATE INDEX IF NOT EXISTS idx_scans_batch_id ON scans(batch_id);
CREATE INDEX IF NOT EXISTS idx_scan_circles_scan_id ON scan_circles(scan_id);
CREATE INDEX IF NOT EXISTS idx_reports_batch_id ON reports(batch_id);
