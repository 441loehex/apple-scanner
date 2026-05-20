# Architecture — Apple Caliber Scan

**Freshora Sp. Z. o. o.**

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       Operator Interface                         │
│  ┌─────────────────────┐       ┌──────────────────────────────┐ │
│  │    Telegram Bot      │       │       Web UI (FastAPI)       │ │
│  │  (httpx long-poll)   │       │       localhost:8000         │ │
│  └──────────┬──────────┘       └──────────────┬───────────────┘ │
│             │                                  │                  │
│             └────────────┬─────────────────────┘                 │
│                          ▼                                        │
│              ┌───────────────────────┐                           │
│              │   Service Layer       │                           │
│              │  ingest / calibration │                           │
│              │  estimation / report  │                           │
│              └──────────┬────────────┘                          │
│                         │                                        │
│            ┌────────────┴──────────────┐                        │
│            ▼                           ▼                        │
│  ┌──────────────────┐     ┌───────────────────────┐            │
│  │   Scan Pipeline  │     │   SQLite Database      │           │
│  │  loader          │     │   (WAL mode)           │           │
│  │  normalizer      │     │   sellers, batches     │           │
│  │  preview         │     │   scans, circles       │           │
│  │  detector        │     │   reports, GT          │           │
│  └────────┬─────────┘     └───────────────────────┘            │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │  Google Drive    │                                           │
│  │  (gdown)         │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Package Structure

```
apple_caliber_scan/
├── __init__.py          — CLI entry point (main, init-db, sample-report, run-web, run-bot)
├── __main__.py          — python -m apple_caliber_scan support
├── config.py            — all settings from environment variables
│
├── database/
│   ├── schema.sql       — table definitions, indexes
│   ├── connection.py    — db_conn() context manager, WAL config, schema init
│   └── crud.py          — all read/write operations (no ORM)
│
├── scan/
│   ├── loader.py        — PLY/OBJ/GLB/USDZ/LAS loading
│   ├── normalizer.py    — PCA top-down normalization
│   ├── preview.py       — density projection PNG generation
│   ├── detector.py      — Hough circle detection
│   └── fixtures.py      — synthetic crate generator (tests + sample-report)
│
├── services/
│   ├── ingest.py        — orchestrates scan pipeline, deletes raw file after
│   ├── calibration.py   — ring-based scale factor computation
│   ├── estimation.py    — caliber classification, 75+ share, confidence
│   ├── reporting.py     — HTML/PDF/JSON report generation
│   └── groundtruth.py   — grader ground-truth import and comparison
│
├── storage/
│   └── drive.py         — Google Drive URL parsing and download (gdown)
│
├── web/
│   ├── app.py           — FastAPI app factory, middleware, router registration
│   ├── auth.py          — cookie session auth, require_login decorator
│   ├── routes/
│   │   ├── batches.py   — batch CRUD, variety API, ground-truth upload
│   │   ├── scans.py     — scan attachment, review/annotation, report trigger
│   │   └── reports.py   — HTML and PDF report delivery
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── batches_list.html
│   │   ├── batch_detail.html
│   │   ├── scan_attach.html
│   │   ├── scan_review.html
│   │   └── report_pl.html  — Polish report template
│   └── static/
│       └── review.js    — canvas annotation UI (vanilla JS)
│
└── telegram/
    └── bot.py           — TelegramBot class, FSM, all Polish messages
```

---

## Data Flow — Scan Ingest

```
1. Operator pastes Google Drive link (Telegram /attachscan or Web UI)
2. storage/drive.py extracts file_id from URL
3. gdown downloads file to temp path
4. services/ingest.py calls _process_local_file():
   a. scan/loader.py loads point cloud → numpy (N,3)
   b. scan/normalizer.py PCA-normalizes → (M,3) top-layer points
   c. scan/preview.py renders 1024×1024 density PNG → saved to data/previews/
   d. scan/detector.py runs Hough detection → list of Circle objects
   e. Circles inserted into DB (scan_circles table)
   f. RAW SCAN FILE DELETED (os.unlink)
5. Scan record status updated to 'processed'
```

---

## Data Flow — Annotation and Report

```
1. Operator opens /batches/{id}/scans/{sid}/review
2. review.js loads circle data from DOM, renders canvas
3. Operator marks one circle as "ring", others as apple/exclude
4. POST /batches/{id}/scans/{sid}/annotate:
   a. services/calibration.py computes scale_factor from ring circle
   b. All apple circles: diameter_mm = diameter_px × scale_factor
   c. DB updated: scan_circles, annotations tables
5. POST /batches/{id}/scans/{sid}/report:
   a. services/estimation.py classifies each apple diameter → 8-class distribution
   b. Confidence determined (LOW unless GT entered)
   c. services/reporting.py renders Jinja2 → HTML, WeasyPrint → PDF, JSON
   d. Report records saved to DB (reports table)
   e. Files saved to data/reports/
```

---

## Database Schema Summary

| Table | Purpose |
|-------|---------|
| sellers | Seller name + address (operator-entered) |
| varieties | Apple variety names (16 pre-seeded + custom) |
| batches | One batch per crate group: seller, variety, price, CA date, notes |
| scans | One scan per batch, status (pending/processed/error), file format |
| scan_circles | Detected circles: center x/y, radius px, is_ring, diameter_mm |
| annotations | Per-scan annotation record with scale_factor and calibration confidence |
| reports | Report records: type (html/pdf/json), file path, generated_at |
| ground_truth | Grader-provided caliber distribution for validation |
| telegram_sessions | Telegram FSM state per chat_id |

---

## Authentication

The web UI uses cookie-based session authentication:
- Single username: `freshora` (hardcoded)
- Password: `ACS_WEB_PASSWORD` environment variable
- Session signed with `ACS_WEB_SECRET_KEY` via Starlette SessionMiddleware
- Session max age: 8 hours
- All non-login routes require `require_login` decorator

The Telegram bot has no authentication — it is designed for single-operator use on a
private bot (only the operator knows the bot token). Add Telegram `allowed_users` list
to `config.py` if multi-user isolation is needed.

---

## Key Design Decisions

**No ORM** — Direct `sqlite3` for simplicity, full control over WAL config and schema.

**No framework for bot** — Pure `httpx` long-polling avoids the `python-telegram-bot`
dependency weight and version conflicts.

**Vanilla JS canvas** — No build step, no npm. The annotation UI is a single `review.js`
file served as a static asset.

**Delete raw scans** — Privacy-by-design. Only the derived preview PNG and caliber data
are retained. Raw PLY/OBJ files may contain operator-facing geometry that shouldn't be stored.

**Jinja2 for reports** — Templated Polish HTML report ensures consistent legal clause
placement. WeasyPrint converts to PDF server-side without browser automation.
