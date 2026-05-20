# apple-caliber-scan — Complete Authoritative Build Prompt

> **STATUS: PHASE 2 — BUILD IMMEDIATELY.**
> All 10 discovery questions have been answered below and encoded into technical decisions.
> No further clarification is permitted or needed. Make the most optimal reasonable choice
> wherever a gap exists and document the assumption. Begin implementation on the first token.

---

## 0. Operator Instructions for the Executing AI

You are Claude Code running inside a WSL2 development environment.
Your task is to build the `apple-caliber-scan` project from scratch as a complete,
runnable, tested, production-quality MVP.

- Working directory: `/mnt/c/Users/balce/Downloads/apple scanner/`
- Build target: `./apple-caliber-scan/` subdirectory inside that working directory
- Python available: 3.12.3 at `/usr/bin/python3`
- pip available: `pip3` / `pip`
- Pre-installed packages: `httpx` only — you must install everything else
- Internet access: available — use `pip install` freely
- This is NOT a git repo yet — initialize one inside `./apple-caliber-scan/`

**RTK MAX MODE rules (apply throughout):**
- Use `rtk git status`, `rtk git diff`, `rtk grep`, `rtk find`, `rtk pytest` when rtk is available
- Prefer targeted file reads over broad full-file reads
- Run tests after every meaningful code change
- Fix all test failures before reporting done

---

## 1. Non-Negotiable Safety and Privacy Rules

1. Never read `.env` files, private keys, SSH keys, tokens, credentials, browser profiles.
2. Create `.env.example` only. Never create or print real secrets.
3. All API tokens, bot tokens, service URLs, credentials via environment variables only.
4. Never log secrets.
5. Minimize personal data storage. Store only derived caliber distributions and metadata — never raw personal data beyond seller name/address entered by operator.
6. After scan ingestion and preview generation, **delete the local scan file**. Store only: preview PNG, caliber distribution JSON, batch metadata in SQLite.
7. Provide full deletion support: `/deletebatch` deletes all stored data (SQLite rows + preview PNG + PDF/HTML reports) for a batch.
8. No paid API or cloud AI dependencies.
9. No cloud AI dependencies.
10. Keep all work inside `./apple-caliber-scan/`.

---

## 2. Source-of-Truth Document

The file `./apple-caliber-scan MVP.pdf` in the parent directory is the primary requirements
reference. It was produced by a prior ChatGPT build session and describes the target system.
The code it references (`/home/oai/apple-caliber-scan`) does **not** exist on this machine.
You are building it fresh here.

---

## 3. Answers to the 10 Discovery Questions (Authoritative)

### Q1 — Project root placement
Build the repo as `./apple-caliber-scan/` subdirectory inside
`/mnt/c/Users/balce/Downloads/apple scanner/`.
The PDF file stays in the parent folder. Do not move it.

### Q2 — Telegram bot token
Build everything without a real token. The token is configured via `ACS_TELEGRAM_TOKEN`
env var. The bot must start cleanly with a placeholder token set and log a clear
"No valid token — set ACS_TELEGRAM_TOKEN and restart" message rather than crashing.
All bot code, conversation state machine, and Telegram workflow must be fully implemented
and ready to activate the moment the operator runs `@BotFather /newbot` and sets the token.

### Q3 — Calibration mechanism (CRITICAL — read carefully)
The physical calibration workflow is:
1. Operator selects a physical apple measuring ring (target: the **75 mm ring**, as it is
   the most commercially critical threshold).
2. Operator places the ring next to an apple that fits it well, inside the crate.
3. Operator scans with iPhone LiDAR (Scaniverse → export PLY/OBJ).
4. The measuring ring appears as a recognizable circular shape in the scan point cloud.
5. The software generates a top-down 2D preview image (bird's-eye PNG).
6. In the preview, the ring appears as a circle of **known physical diameter: 75 mm**.
7. The annotation UI runs Hough circle detection on the preview.
8. Operator selects/confirms which detected circle is the measuring ring.
9. **Scale factor** = `75.0 / ring_detected_diameter_px` (mm per pixel).
10. Every other detected circle: `diameter_mm = detected_diameter_px × scale_factor`.
11. Each apple maps to a caliber class by its `diameter_mm`.
12. If the inferred scale factor is suspicious (e.g., implying apples smaller than 40 mm
    or larger than 120 mm on average), emit a **confidence downgrade warning** in the
    report and label the calibration as LOW CONFIDENCE.
13. Operator can manually override the ring diameter value (default 75 mm) if a different
    ring size was used on a given scan.

### Q4 — PDF generation library
Use **`weasyprint`** (HTML → PDF via CSS rendering engine).
Rationale: Freshora reports need professional typography, Polish diacritics, company
branding with a header, and structured tabular data. WeasyPrint handles all of this from
the same Jinja2 HTML template used for the browser preview, eliminating a separate
PDF template. Document the required system libraries in README and Makefile.

Required system packages (add to `make install-system-deps`):
```
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info libgirepository1.0-dev
```

If `weasyprint` fails to install or the system libs are unavailable, fall back to
**`fpdf2`** (pure Python, UTF-8, no system deps) with a pre-built minimal PDF layout.
Document both paths clearly in `docs/DEPLOYMENT.md`.

### Q5 — Apple variety entry
Free-text entry, but with intelligent auto-suggestion:
- SQLite `varieties` table stores every variety string ever entered (deduplicated).
- Telegram bot: after asking "Podaj odmianę jabłek:", sends an inline keyboard showing
  all previously used variety names as clickable buttons, plus a final button
  "Inna odmiana..." which prompts free-text input.
- Web UI: `<input>` with `<datalist>` populated from the varieties table (autocomplete).
- New free-text entries are automatically added to the varieties table for future reuse.
- Pre-populate the varieties table with these Polish commercial standards:
  Red Cap, Red Chief, Jeromine, Jeronimo, Golden Delicious, Ligol, Szampion, Idared,
  Jonagold, Jonagored, Gala, Fuji, Elstar, Lobo, Champion, Cortland.

### Q6 — Report branding
Company name: **Freshora Sp. Z. o. o.**
- All Polish customer reports must display "Freshora Sp. Z. o. o." in the header.
- Report title: **HANDLOWY RAPORT ANALITYCZNY (DO SPRZEDAŻY)**
- Color scheme for reports: clean white background, dark green (`#1a5c2e`) header bar,
  white header text. Professional, agricultural-business aesthetic.
- No logo image file required for MVP — use text-based header with company name.
  Reserve an `ACS_LOGO_PATH` env var for a future logo PNG/SVG.

### Q7 — Batch weight and units
- **Default crate weight**: 300 kg of unsorted apples (`ACS_DEFAULT_CRATE_WEIGHT_KG = 300`).
- **Maximum truck load**: 20,000 kg (~66 crates) — use for validation warnings only.
- Batch data model stores: `number_of_crates` (integer, default 1) and
  `total_weight_kg` (computed: `number_of_crates × ACS_DEFAULT_CRATE_WEIGHT_KG`,
  overridable by operator).
- The estimation engine calculates per-caliber-class weight using the visible top-layer
  distribution projected across the full batch weight — always labeled **SZACUNEK**.
- Truck-load context: if `total_weight_kg > 20000`, show a soft validation warning in
  the web UI ("Uwaga: masa partii przekracza typowy ładunek ciężarówki").

### Q8 — Scan file delivery: Google Drive workflow
Telegram scan file upload is **not used**. All scan files come from Google Drive.

**Workflow:**
1. Operator uploads the `.ply` / `.obj` scan file to a shared Google Drive folder
   (the folder is set up manually by the operator — no Drive folder management in MVP).
2. Operator sets the Drive share permission to "Anyone with the link can view".
3. Operator sends the share URL to the Telegram bot via `/attachscan <batch_id>`.
   Bot then asks: "Podaj link do pliku skanowania z Google Drive:".
4. Alternatively, operator pastes the Drive URL directly in the web UI scan upload form.
5. System downloads the file using **`gdown`** (`pip install gdown`).
   `gdown` handles the Google Drive download confirmation page for large files.
6. After the scan is ingested (point cloud loaded, top-down preview PNG generated,
   Hough circles detected), the **local scan file is immediately deleted**.
7. Only the following are persisted:
   - Preview PNG (stored in `ACS_DATA_DIR/previews/`)
   - Detected circles JSON (stored in SQLite `scan_circles` table)
   - Batch metadata in SQLite
8. Operator can delete the Drive source file manually at any time.
9. `/deletebatch <batch_id>` deletes: all SQLite rows for batch + all scans + preview
   PNGs + generated HTML/PDF reports for that batch. Irreversible — bot asks for
   confirmation: "Czy na pewno chcesz usunąć partię {batch_id}? Odpowiedz TAK."

**Google Drive URL formats supported:**
- `https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing`
- `https://drive.google.com/open?id={FILE_ID}`
- `https://drive.google.com/uc?id={FILE_ID}`
- Direct extraction of FILE_ID from any of the above, then download via
  `gdown.download(id=FILE_ID, output=local_path, quiet=False)`

### Q9 — Web UI authentication
Cookie-based session login (not HTTP Basic Auth — sessions are better UX for a multi-page web app).

Implementation:
- Use `starlette.middleware.sessions.SessionMiddleware` (bundled with FastAPI/Starlette).
- `ACS_WEB_SECRET_KEY` env var (required, 32+ random bytes, used to sign session cookie).
- `ACS_WEB_USERNAME` env var (default: `freshora`).
- `ACS_WEB_PASSWORD` env var (required — app refuses to start without it).
- Login form at `GET /login` + `POST /login`.
- Session cookie named `acs_session`, 8-hour expiry, `httponly=True`, `samesite=lax`.
- All non-login routes redirect to `/login` if not authenticated.
- `GET /logout` clears session and redirects to `/login`.
- After login, redirect to `/` (batch list).
- Failed login shows: "Nieprawidłowy login lub hasło." (Polish error message).

### Q10 — Definition of done
Full end-to-end system working:
- `make setup` installs all Python and system dependencies cleanly.
- `make init-db` creates the SQLite schema.
- `make sample-report` generates a complete Polish HTML + PDF sample report with
  Freshora branding, all 8 caliber classes, 75+ summary, and legal clauses.
- `make test` runs all tests with ≥ 8 passing, 0 failing.
- `make lint` passes with 0 errors.
- `make run-web` starts the FastAPI web UI on `http://localhost:8000`.
- `make run-bot` starts the Telegram polling bot (logs a ready message or token warning).
- The web UI login page works, the batch list loads, the scan review canvas renders.
- The sample report is visually complete and could be shown to an apple seller.

---

## 4. Domain Rules (Non-Negotiable)

These rules govern every module. No code may violate them.

1. **Top-layer primacy**: The visible top-layer distribution is the ONLY directly measured
   result. Label it "Wynik pomiaru warstwy wierzchniej" everywhere.
2. **Batch projection = estimate**: Any whole-batch projection is an estimate, always
   labeled "SZACUNEK (niska pewność)" until paired grader ground truth is available.
3. **No certification claims**: The system must never state or imply certification,
   official grading, machine-sorter equivalence, or legal compliance guarantee.
4. **Caliber classes** (exactly these 8, no others):
   - `0–60 mm`
   - `60–65 mm`
   - `65–70 mm`
   - `70–75 mm`
   - `75–80 mm`
   - `80–85 mm`
   - `85–90 mm`
   - `90+ mm`
5. **75+ share** must be computed and displayed prominently: sum of all apples in classes
   75–80, 80–85, 85–90, 90+, expressed as % of total visible top-layer apples.
6. **Report status line**: `HANDLOWY RAPORT ANALITYCZNY (DO SPRZEDAŻY)`
7. **Language**: All customer-facing reports are in Polish only.
8. **Calibration confidence**: If ring-based scale factor implies implausible apple sizes
   (< 40 mm or > 120 mm average), label calibration LOW CONFIDENCE and show a warning.
9. **Ground truth**: Full-crate prediction confidence remains LOW until the operator
   imports at least one paired grader result for the same batch via the ground-truth
   import API.
10. **Weight model honesty**: All per-class weight estimates are geometric heuristics.
    Never present them as weighed measurements. Label: "Szacunkowa masa (heurystyczna)".
11. **Scientific report style**: Analytical, estimated, confidence-labeled, legally limited.
12. **Polish legal clauses**: Every generated report must include the exact legal text
    defined in Section 9 of this prompt.

---

## 5. Technical Stack (Authoritative — No Substitutions Without Documenting Why)

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Available, specified |
| Web framework | FastAPI + uvicorn[standard] | Async, typed, fast |
| Templating | Jinja2 (bundled with FastAPI) | Server-rendered HTML |
| Database | SQLite via stdlib `sqlite3` | No ORM needed at this scale |
| Telegram | Direct `httpx` Bot API polling | aiogram not required; structure for swap |
| PDF reports | `weasyprint` (fallback: `fpdf2`) | Best CSS HTML→PDF |
| Image processing | `Pillow` + `opencv-python-headless` | Preview gen + Hough circles |
| Point cloud | `numpy` + `plyfile` | PLY loading without heavy deps |
| 3D mesh (OBJ/GLB) | `trimesh` | OBJ/GLB loading + projection |
| Google Drive DL | `gdown` | Handles Drive confirmation, pure Python |
| Session auth | `starlette` SessionMiddleware | Cookie sessions, bundled |
| Testing | `pytest` + `pytest-asyncio` | Standard |
| Linting | `ruff` | Fast, modern |
| Type checking | `mypy` (non-blocking — warn, don't fail CI) | Type safety |
| Async HTTP | `httpx` | Already installed |
| File uploads | `python-multipart` | FastAPI requirement |
| Env config | `python-dotenv` | Load `.env` in dev |
| Synthetic data | `numpy` (built-in to stack) | Deterministic fixtures |

**LAS files**: Accept upload, extract metadata only. Full LAS processing requires `laspy`
(optional extra). Document in LIMITATIONS.md. Graceful fallback: log "LAS preview
unavailable — install laspy for full support" and store file ID only.

**USDZ files**: Accept upload, store as-is. Full USD normalization is out of scope for MVP.
Document in LIMITATIONS.md.

---

## 6. Complete Directory Structure

```
apple-caliber-scan/
├── apple_caliber_scan/
│   ├── __init__.py              # Package + CLI entry point (init-db, sample-report)
│   ├── config.py                # All settings loaded from env vars (pydantic-free)
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.sql           # Complete SQLite DDL
│   │   ├── connection.py        # sqlite3 connection factory, WAL mode
│   │   └── crud.py              # All DB read/write functions (typed)
│   ├── scan/
│   │   ├── __init__.py
│   │   ├── loader.py            # PLY / OBJ / GLB loading → numpy point array
│   │   ├── normalizer.py        # Rotate to top-down, crop, scale normalize
│   │   ├── preview.py           # Generate top-down PNG from point array
│   │   ├── detector.py          # Hough circle detection → list[Circle]
│   │   └── fixtures.py          # Synthetic top-layer point cloud generator
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ingest.py            # Full pipeline: download → load → preview → detect → store → delete local file
│   │   ├── calibration.py       # Ring-based scale factor, confidence, suspicious scale warning
│   │   ├── estimation.py        # Caliber classification, 75+ share, weight heuristic, confidence model
│   │   ├── reporting.py         # Polish HTML + PDF report generation (Jinja2 + weasyprint)
│   │   └── groundtruth.py       # AWETA/grader ground-truth import stub + comparison hooks
│   ├── storage/
│   │   ├── __init__.py
│   │   └── drive.py             # Google Drive URL parsing + gdown download
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py               # FastAPI app factory (create_app())
│   │   ├── auth.py              # Session middleware, login/logout, require_login decorator
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── batches.py       # GET / (list), POST /batches, GET /batches/{id}, DELETE /batches/{id}
│   │   │   ├── scans.py         # POST /batches/{id}/scans (Drive URL), GET /batches/{id}/scans/{sid}/review
│   │   │   └── reports.py       # POST /batches/{id}/scans/{sid}/report, GET /reports/{rid}.html, GET /reports/{rid}.pdf
│   │   └── templates/
│   │       ├── base.html        # Layout, nav, Freshora branding
│   │       ├── login.html       # Login form, Polish UI
│   │       ├── batch_list.html  # List of batches with status badges
│   │       ├── batch_new.html   # New batch form (seller, variety autocomplete, etc.)
│   │       ├── batch_detail.html # Batch detail + scans list + report links
│   │       ├── scan_drive.html  # Drive URL input form
│   │       ├── scan_review.html # Canvas annotation UI (Hough circles overlay, ring selection)
│   │       └── report_pl.html   # Polish report template (HTML + print CSS for PDF)
│   └── telegram/
│       ├── __init__.py
│       └── bot.py               # Direct httpx Bot API long-polling, full conversation FSM
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures: in-memory DB, synthetic scan, test client
│   ├── test_caliber.py          # Caliber class boundary tests (all 8 class edges)
│   ├── test_calibration.py      # Scale factor correctness, suspicious scale warning
│   ├── test_estimation.py       # 75+ share, confidence guardrail (no high-conf without GT)
│   ├── test_reporting.py        # Report total-consistency, legal clause presence
│   ├── test_ingest.py           # Synthetic ingest: generate → load → preview → circles
│   ├── test_drive.py            # Drive URL parsing (no network calls — mock gdown)
│   └── test_web.py              # End-to-end: login, batch create, scan attach, report generate
├── sample_data/
│   ├── synthetic/
│   │   └── README.md            # How to regenerate synthetic fixtures
│   └── example_report_pl.html   # Pre-generated Polish sample report (committed artifact)
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── USER_MANUAL.md           # Written for a non-technical apple trade operator, in Polish
│   ├── CAPTURE_GUIDE.md         # iPhone + Scaniverse capture SOP, measuring ring placement
│   ├── TESTING.md
│   ├── DEPLOYMENT.md            # WSL2 local + Vultr VPS
│   ├── SECURITY_PRIVACY.md
│   ├── LIMITATIONS.md
│   └── ACCURACY_METHODOLOGY.md  # Scientific basis, confidence model, what is and is not claimed
├── CLAUDE.md
├── .claude/
│   ├── agents/
│   │   ├── implementation-reviewer.md
│   │   ├── test-engineer.md
│   │   ├── security-privacy-reviewer.md
│   │   └── docs-reviewer.md
│   └── commands/
│       ├── test.md
│       ├── lint.md
│       ├── smoke.md
│       ├── review.md
│       ├── adversarial-review.md
│       └── run-local.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── Makefile
└── README.md
```

---

## 7. Database Schema (Complete SQLite DDL)

```sql
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

-- Pre-populated standard Polish varieties (insert via init-db)

CREATE TABLE IF NOT EXISTS batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id           INTEGER REFERENCES sellers(id) ON DELETE SET NULL,
    seller_name         TEXT NOT NULL,          -- denormalized for report immutability
    seller_address      TEXT,
    variety             TEXT NOT NULL,
    price_pln_per_kg    REAL,
    ca_opening_date     TEXT,                   -- ISO date string
    operator_batch_id   TEXT,                   -- operator's own ID/reference
    notes               TEXT,
    number_of_crates    INTEGER NOT NULL DEFAULT 1,
    total_weight_kg     REAL NOT NULL DEFAULT 300,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending | scanned | annotated | reported | deleted
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    telegram_chat_id    INTEGER                 -- which Telegram chat created this batch
);

CREATE TABLE IF NOT EXISTS scans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id            INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    drive_url           TEXT,                   -- original Drive share URL
    drive_file_id       TEXT,                   -- extracted Google Drive file ID
    format              TEXT,                   -- ply | obj | glb | usdz | las
    preview_path        TEXT,                   -- relative path inside ACS_DATA_DIR/previews/
    point_count         INTEGER,
    calibration_ring_mm REAL NOT NULL DEFAULT 75.0,  -- physical ring diameter used
    scale_factor_mm_per_px REAL,               -- computed after annotation
    calibration_confidence TEXT NOT NULL DEFAULT 'uncalibrated',  -- uncalibrated | ok | low
    calibration_warning TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending | previewed | annotated | failed
    error_message       TEXT,
    ingested_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS scan_circles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    cx_px           REAL NOT NULL,
    cy_px           REAL NOT NULL,
    radius_px       REAL NOT NULL,
    diameter_mm     REAL,                   -- NULL until calibrated
    caliber_class   TEXT,                   -- e.g. "75-80" — NULL until calibrated
    is_ring         INTEGER NOT NULL DEFAULT 0,   -- 1 if this circle is the measuring ring
    is_excluded     INTEGER NOT NULL DEFAULT 0,   -- 1 if operator excluded this circle
    confidence      REAL,                   -- detection confidence 0–1
    annotated_by    TEXT                    -- 'auto' | 'operator'
);

CREATE TABLE IF NOT EXISTS annotations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id         INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    ring_circle_id  INTEGER REFERENCES scan_circles(id) ON DELETE SET NULL,
    annotated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    annotated_by    TEXT,                   -- telegram username or 'web'
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
    source          TEXT NOT NULL DEFAULT 'manual',  -- manual | aweta | api
    grader_results  TEXT NOT NULL,          -- JSON: {class: count} from actual grader
    weight_kg       REAL,
    graded_at       TEXT,
    imported_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS telegram_sessions (
    chat_id         INTEGER PRIMARY KEY,
    state           TEXT NOT NULL DEFAULT 'idle',
    context         TEXT NOT NULL DEFAULT '{}',  -- JSON blob
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);
CREATE INDEX IF NOT EXISTS idx_scans_batch_id ON scans(batch_id);
CREATE INDEX IF NOT EXISTS idx_scan_circles_scan_id ON scan_circles(scan_id);
CREATE INDEX IF NOT EXISTS idx_reports_batch_id ON reports(batch_id);
```

---

## 8. Configuration (config.py)

All settings via environment variables with sensible defaults:

```python
# Every setting must be readable from env. No hardcoded secrets. No .env loading in prod.
# In dev, python-dotenv loads .env if present.

ACS_DATA_DIR                # Default: ./data — directory for previews, reports
ACS_DB_PATH                 # Default: ./data/apple_caliber_scan.db
ACS_PUBLIC_BASE_URL         # Default: http://localhost:8000 — used in Telegram links
ACS_WEB_BASE_URL            # Default: http://localhost:8000
ACS_WEB_USERNAME            # Default: freshora
ACS_WEB_PASSWORD            # REQUIRED — app refuses to start without it
ACS_WEB_SECRET_KEY          # REQUIRED — 32+ bytes, signs session cookies
ACS_TELEGRAM_TOKEN          # Optional — bot skips polling if not set, logs warning
ACS_LOG_LEVEL               # Default: INFO
ACS_DEFAULT_CRATE_WEIGHT_KG # Default: 300
ACS_DEFAULT_RING_MM         # Default: 75.0 — physical calibration ring diameter
ACS_MAX_TRUCK_WEIGHT_KG     # Default: 20000 — triggers validation warning
ACS_LOGO_PATH               # Optional — path to company logo PNG/SVG for reports
ACS_GDOWN_TIMEOUT_S         # Default: 120 — Google Drive download timeout
```

`.env.example` must contain all of the above with comments explaining each one in English.

---

## 9. Polish Report Specification

### 9.1 Header
```
Freshora Sp. Z. o. o.
HANDLOWY RAPORT ANALITYCZNY (DO SPRZEDAŻY)
```
Dark green background (`#1a5c2e`), white text, full-width banner.

### 9.2 Metadata block (left column)
```
Sprzedawca:        {seller_name}
Adres:             {seller_address}
Odmiana:           {variety}
Cena:              {price_pln_per_kg} PLN/kg
Data otwarcia CA:  {ca_opening_date}
Numer partii:      {operator_batch_id}
Uwagi:             {notes}
Liczba skrzynek:   {number_of_crates}
Łączna masa:       {total_weight_kg} kg
Data raportu:      {generated_at}
```

### 9.3 Calibration details block
```
Kalibracja: Pierścień pomiarowy {calibration_ring_mm} mm
Współczynnik skali: {scale_factor:.4f} mm/px
Pewność kalibracji: {calibration_confidence} {calibration_warning_if_any}
```

### 9.4 Main results table — visible top layer only
Columns: `Klasa kalibrażu | Sztuki | % | Szac. masa (kg) | % masy`

Rows (exactly these 8, always present even if count = 0):
```
0–60 mm
60–65 mm
65–70 mm
70–75 mm
75–80 mm
80–85 mm
85–90 mm
90+ mm
─────────────────────────────────────────
RAZEM (warstwa wierzchnia)
```

After the table:
```
Udział jabłek ≥75 mm (warstwa wierzchnia): XX.X%
```
Displayed prominently in a colored badge: green if ≥ 60%, yellow if 40–60%, red if < 40%.

### 9.5 Full-batch projection (always labeled SZACUNEK)
```
SZACUNEK PEŁNEJ PARTII (niska pewność)
Podstawa: rozkład warstwy wierzchniej × łączna masa {total_weight_kg} kg
Pewność: NISKA — brak sparowanych danych z sortownicy

[Same table structure, values labeled as estimates]

⚠ Dane te są szacunkiem statystycznym. Nie stanowią pomiaru mechanicznego.
```
Show a full-crate projection table only if the calibration confidence is `ok`.
If `uncalibrated` or `low`, show a warning box instead:
```
⚠ Projekcja pełnej partii niedostępna — kalibracja niskiej pewności lub brak kalibracji.
```

### 9.6 Ground truth comparison (if available)
If `ground_truth` records exist for the batch, show a side-by-side comparison table:
```
Porównanie z danymi sortownicy:
[Klasa | Wynik skanowania (%) | Wynik sortownicy (%) | Odchylenie]
```

### 9.7 Legal limitation clauses (MANDATORY — exact Polish text)
```
KLAUZULA OGRANICZENIA ODPOWIEDZIALNOŚCI

Niniejszy raport ma charakter wyłącznie analityczny i szacunkowy. Wyniki opierają się
na analizie widocznej górnej warstwy skrzyni jabłek przy użyciu skanowania LiDAR i nie
stanowią pomiaru certyfikowanego, klasyfikacji mechanicznej ani gwarancji jakości,
ceny, sprzedaży lub zgodności z obowiązującymi normami jakościowymi.

Rozkład kalibrażu całej partii jest szacunkiem statystycznym o niskiej pewności i może
odbiegać od wyników sortownicy mechanicznej (np. AWETA). Pewność projekcji wzrośnie
dopiero po zgromadzeniu sparowanych danych pomiarowych z sortownicy dla tej samej
partii.

Niniejszy raport może być stosowany wyłącznie jako materiał pomocniczy w negocjacjach
handlowych. Freshora Sp. Z. o. o. nie ponosi odpowiedzialności za decyzje handlowe
podjęte wyłącznie na podstawie niniejszego raportu.

Freshora Sp. Z. o. o. — dokument wygenerowany automatycznie {generated_at}
```

---

## 10. Calibration and Estimation Algorithm Spec

### 10.1 Ring detection and scale factor
```python
def compute_scale_factor(ring_circle: Circle, ring_mm: float = 75.0) -> tuple[float, str, str | None]:
    """
    Returns (scale_factor_mm_per_px, confidence, warning_message | None).
    
    Scale factor = ring_mm / (ring_circle.radius_px * 2)
    
    Sanity check: apply scale to all detected circles.
    If mean apple diameter would be < 40 mm or > 120 mm → LOW confidence + warning.
    If scale factor would imply the ring is smaller than 10 px → LOW confidence + warning.
    """
```

### 10.2 Caliber classification
```python
CALIBER_CLASSES: list[tuple[float, float, str]] = [
    (0,   60,  "0-60"),
    (60,  65,  "60-65"),
    (65,  70,  "65-70"),
    (70,  75,  "70-75"),
    (75,  80,  "75-80"),
    (80,  85,  "80-85"),
    (85,  90,  "85-90"),
    (90,  float("inf"), "90+"),
]

def classify_diameter(diameter_mm: float) -> str:
    """Returns caliber class string. 75.0 mm → "75-80". 75.0 is inclusive lower bound."""
    for low, high, label in CALIBER_CLASSES:
        if low <= diameter_mm < high:
            return label
    return "90+"
```

Boundary rule: lower bound inclusive, upper bound exclusive (standard apple trade convention).
`60.0 mm` → `"60-65"`. `75.0 mm` → `"75-80"`. `90.0 mm` → `"90+"`.

### 10.3 Weight estimation heuristic
Apple mass from diameter using empirical polynomial for commercial apple varieties:
```python
def diameter_to_mass_g(diameter_mm: float) -> float:
    """
    Heuristic: mass_g ≈ density * (4/3 * π * (d/2)^3) * 0.85
    where density ≈ 0.85 g/cm³ (typical for commercial apples),
    and 0.85 correction for non-spherical shape.
    This is a geometric estimate, NOT a weighed measurement.
    """
    radius_cm = (diameter_mm / 2) / 10
    volume_cm3 = (4 / 3) * 3.14159 * (radius_cm ** 3)
    return volume_cm3 * 0.85 * 0.85
```

### 10.4 Confidence model
```python
class ConfidenceLevel(str, Enum):
    HIGH = "wysoka"      # Only possible with paired grader ground truth
    MEDIUM = "średnia"   # Not used in MVP — reserved for future empirical calibration
    LOW = "niska"        # Default for all whole-batch projections without ground truth
    UNCALIBRATED = "brak kalibracji"  # No ring annotation done yet

def batch_projection_confidence(has_ground_truth: bool, calibration_ok: bool) -> ConfidenceLevel:
    if not calibration_ok:
        return ConfidenceLevel.UNCALIBRATED
    if not has_ground_truth:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.HIGH
```

---

## 11. Google Drive Integration Spec

### 11.1 URL parsing
```python
def extract_drive_file_id(url: str) -> str | None:
    """
    Handles all common Drive URL formats:
    - https://drive.google.com/file/d/{ID}/view
    - https://drive.google.com/open?id={ID}
    - https://drive.google.com/uc?id={ID}
    - https://docs.google.com/...
    Returns file ID string or None if not a recognized Drive URL.
    """
```

### 11.2 Download
```python
import gdown

def download_drive_file(file_id: str, dest_path: Path, timeout_s: int = 120) -> Path:
    """
    Downloads file from Google Drive to dest_path using gdown.
    Raises DriveDownloadError on failure.
    Deletes dest_path if download fails partway.
    """
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, str(dest_path), quiet=False, fuzzy=True)
    if not dest_path.exists():
        raise DriveDownloadError(f"Download failed: {file_id}")
    return dest_path
```

### 11.3 Post-ingest cleanup
After `load_point_cloud()` + `generate_preview()` + `detect_circles()` complete successfully,
immediately call `dest_path.unlink()`. Log the deletion. If deletion fails, log a warning
but do not fail the ingest.

---

## 12. Telegram Bot Spec

### 12.1 Implementation
Direct `httpx` Bot API long-polling client. No aiogram. Structure the code so swapping to
aiogram v3 requires only replacing the I/O layer, not the business logic.

### 12.2 Conversation state machine (stored in `telegram_sessions` SQLite table)
States:
```
idle
awaiting_seller_name
awaiting_seller_address
awaiting_variety
awaiting_price
awaiting_ca_date
awaiting_batch_id
awaiting_notes
awaiting_crates_count
awaiting_drive_url
awaiting_delete_confirmation
```

### 12.3 Bot commands
```
/start          — Welcome message in Polish, list available commands
/newbatch       — Start new batch entry flow (FSM)
/batches        — List last 10 batches with status and inline buttons
/attachscan <batch_id>  — Prompt for Google Drive URL for a scan
/report <batch_id>      — Return links to latest HTML and PDF reports
/web <batch_id>         — Return direct web UI link for review/annotation
/deletebatch <batch_id> — Request confirmation, then delete all batch data
/cancel         — Cancel current operation, return to idle
/help           — Command list in Polish
```

### 12.4 Variety suggestion flow
After "Podaj odmianę jabłek:", query `varieties` table ordered by `use_count DESC LIMIT 10`.
Build inline keyboard: each variety as a button, plus "Inna odmiana..." as final option.
On "Inna odmiana...", ask user to type the variety name freely.
On variety selection (button or text), upsert into `varieties` table (increment `use_count`).

### 12.5 Token validation on startup
```python
if not ACS_TELEGRAM_TOKEN:
    logger.warning("ACS_TELEGRAM_TOKEN not set — Telegram bot disabled. "
                   "Set the token and restart to enable.")
    return  # Do not start polling loop
```
The web app must work fully without the bot running.

### 12.6 Polish UI strings
All bot messages in Polish. Examples:
- "Podaj imię i nazwisko sprzedawcy:"
- "Podaj adres sprzedawcy (lub wyślij /skip):"
- "Wybierz odmianę lub wpisz nową:"
- "Podaj cenę w PLN/kg (lub /skip):"
- "Podaj datę otwarcia CA (RRRR-MM-DD lub /skip):"
- "Podaj numer partii/referencję:"
- "Podaj liczbę skrzynek (domyślnie 1):"
- "Podaj link Google Drive do pliku skanowania:"
- "Partia #{batch_id} utworzona pomyślnie. Użyj /attachscan {batch_id} aby dołączyć skan."
- "Czy na pewno chcesz usunąć partię #{batch_id} i wszystkie powiązane dane? Odpowiedz TAK."

---

## 13. Web UI Spec

### 13.1 Routes
```
GET  /login                     — Login form
POST /login                     — Authenticate, set session cookie
GET  /logout                    — Clear session, redirect to /login
GET  /                          — Batch list (requires auth)
GET  /batches/new               — New batch form
POST /batches                   — Create batch, redirect to batch detail
GET  /batches/{id}              — Batch detail: metadata, scans, reports
DELETE /batches/{id}            — Delete batch + all data (HTMX or JS confirm)
GET  /batches/{id}/scan/new     — Drive URL input form
POST /batches/{id}/scan         — Trigger Drive download + ingest, redirect to review
GET  /batches/{id}/scans/{sid}/review  — Canvas annotation UI
POST /batches/{id}/scans/{sid}/annotate — Save annotation (ring selection + circle edits)
POST /batches/{id}/scans/{sid}/report   — Generate Polish HTML+PDF report
GET  /reports/{rid}.html        — Serve HTML report
GET  /reports/{rid}.pdf         — Serve PDF report
GET  /api/varieties             — JSON list of varieties (for datalist autocomplete)
POST /api/groundtruth/{bid}     — Import grader ground truth JSON
```

### 13.2 Scan review canvas UI (`scan_review.html`)
- Display preview PNG on an HTML5 `<canvas>` element, full width.
- Overlay detected circles using Canvas 2D API:
  - Unselected auto-detected circles: **blue** outline
  - Operator-selected ring circle: **red** outline with "PIERŚCIEŃ" label
  - Confirmed apple circles: **green** outline
  - Excluded circles: **grey** dashed outline
- Interaction:
  - **Click** a circle → popover: "Oznacz jako: Pierścień kalibracyjny | Jabłko | Wyklucz"
  - **Drag** circle edge → resize radius
  - **Double-click** empty area → add new circle (drag to set radius)
  - **Right-click** circle → delete
- Once ring is selected: immediately compute and display scale factor + per-circle diameter estimates in a sidebar table.
- Sidebar shows live-updating caliber distribution as circles are confirmed/excluded.
- "Zapisz adnotację i generuj raport" button → POST to annotate endpoint.
- Implement entirely in vanilla JavaScript (no framework). Keep the JS in a `static/review.js` file.

### 13.3 Templates
- All templates extend `base.html` which includes:
  - Freshora Sp. Z. o. o. logo text in nav
  - Polish navigation links
  - Dark green (`#1a5c2e`) nav bar
  - Bootstrap 5 (CDN, no local copy needed for MVP)
  - Flash message support

---

## 14. Scan Processing Pipeline Spec

### 14.1 PLY loading (`loader.py`)
```python
def load_ply(path: Path) -> np.ndarray:
    """
    Returns (N, 3) float32 array of XYZ points.
    Uses plyfile.PlyData. Strips color/normal channels.
    Falls back to binary parsing if plyfile unavailable.
    """
```

### 14.2 OBJ/GLB loading (`loader.py`)
```python
def load_mesh(path: Path) -> np.ndarray:
    """
    Load OBJ or GLB using trimesh. Extract vertex array as (N, 3) float32.
    """
```

### 14.3 Top-down projection + preview (`normalizer.py`, `preview.py`)
```python
def normalize_top_down(points: np.ndarray) -> np.ndarray:
    """
    1. Find principal axis of point cloud (PCA).
    2. Rotate so the dominant flat plane becomes XY (top-down view is Z-axis).
    3. Crop to top Z percentile (top 20% of Z range = visible top layer).
    4. Normalize XY to [0, 1] range.
    Returns (N, 3) float32, XY in [0,1], Z in [0,1].
    """

def render_preview(points: np.ndarray, output_path: Path,
                   width: int = 1024, height: int = 1024) -> Path:
    """
    Project normalized point cloud to top-down PNG.
    Use density-based colormap (more points → brighter).
    Return path to saved PNG.
    """
```

### 14.4 Circle detection (`detector.py`)
```python
def detect_circles(preview_path: Path,
                   min_radius_px: int = 20,
                   max_radius_px: int = 200) -> list[Circle]:
    """
    Load preview PNG.
    Convert to grayscale, apply Gaussian blur.
    Run cv2.HoughCircles (HOUGH_GRADIENT_ALT preferred, fallback HOUGH_GRADIENT).
    Return list of Circle(cx, cy, radius_px, confidence) sorted by confidence DESC.
    Limit to max 200 circles.
    """
```

### 14.5 Synthetic fixture generator (`fixtures.py`)
```python
def generate_synthetic_crate(
    n_apples: int = 40,
    diameter_distribution: dict[str, float] | None = None,
    seed: int = 42,
) -> np.ndarray:
    """
    Generate a (N, 3) float32 point cloud representing a crate top layer.
    Places spherical apple clusters at random XY positions with Z heights
    sampled from a truncated normal distribution.
    Includes one measuring ring at a fixed position (75 mm diameter).
    Returns deterministic array for given seed.
    diameter_distribution: {class_label: fraction} — defaults to uniform.
    """
```

---

## 15. CLI Entry Point Spec (`__init__.py` / `__main__.py`)

```bash
# Initialize DB (creates tables, inserts default varieties)
python -m apple_caliber_scan init-db

# Generate sample report with synthetic data
python -m apple_caliber_scan sample-report --output-dir ./sample-output

# Start web app (convenience wrapper)
python -m apple_caliber_scan run-web [--host 0.0.0.0] [--port 8000]

# Start Telegram bot
python -m apple_caliber_scan run-bot
```

`sample-report` must:
1. Create an in-memory or temp DB.
2. Generate a synthetic crate scan using `generate_synthetic_crate(seed=42)`.
3. Simulate ring annotation (use the fixture's known ring circle).
4. Run calibration + estimation.
5. Generate Polish HTML report → `{output_dir}/sample_report.html`.
6. Generate Polish PDF report → `{output_dir}/sample_report.pdf`.
7. Generate JSON payload → `{output_dir}/sample_report.json`.
8. Generate preview PNG → `{output_dir}/sample_preview.png`.
9. Print a summary table to stdout showing caliber distribution.
10. Exit 0 on success.

---

## 16. Test Requirements (Minimum — All Must Pass)

### `test_caliber.py` — Caliber class boundary tests
```python
# Must cover all 8 class edges:
# classify_diameter(0.0) == "0-60"
# classify_diameter(59.9) == "0-60"
# classify_diameter(60.0) == "60-65"
# classify_diameter(64.9) == "60-65"
# classify_diameter(65.0) == "65-70"
# classify_diameter(75.0) == "75-80"
# classify_diameter(90.0) == "90+"
# classify_diameter(150.0) == "90+"
```

### `test_calibration.py` — Scale factor and warnings
```python
# A ring detected at 100 px diameter → scale = 75/100 = 0.75 mm/px
# A ring detected at 10 px diameter → suspicious → LOW confidence
# scale_factor applied to circle of 80 px radius → diameter = 80*2*0.75 = 120 mm → "90+"
```

### `test_estimation.py` — 75+ share and confidence guardrail
```python
# Given circles with known diameters, 75+ share must be sum(≥75mm) / total
# batch_projection_confidence(has_ground_truth=False, calibration_ok=True) == LOW
# batch_projection_confidence(has_ground_truth=True, calibration_ok=True) == HIGH
# Report must NOT claim HIGH confidence without ground truth
```

### `test_reporting.py` — Report total consistency
```python
# Sum of all caliber class counts == total visible apples
# Sum of all caliber class percentages ≈ 100% (within floating point tolerance)
# Legal clause text is present in generated HTML
# "Freshora Sp. Z. o. o." appears in generated HTML
# "HANDLOWY RAPORT ANALITYCZNY" appears in generated HTML
```

### `test_ingest.py` — Synthetic ingest pipeline
```python
# generate_synthetic_crate(seed=42) returns (N, 3) array with N > 0
# normalize_top_down() returns array with XY in [0,1]
# render_preview() creates a PNG file > 0 bytes
# detect_circles() returns at least 1 circle on the synthetic preview
```

### `test_drive.py` — URL parsing (no network)
```python
# extract_drive_file_id("https://drive.google.com/file/d/ABC123/view") == "ABC123"
# extract_drive_file_id("https://drive.google.com/open?id=ABC123") == "ABC123"
# extract_drive_file_id("https://drive.google.com/uc?id=ABC123") == "ABC123"
# extract_drive_file_id("https://example.com/file.ply") == None
```

### `test_web.py` — End-to-end web flow (using FastAPI TestClient)
```python
# Login with correct credentials → 200 + session cookie
# Login with wrong password → 200 (form re-shown with error message)
# GET / without auth → redirect to /login
# POST /batches (auth'd) → 303 redirect to batch detail
# GET /batches/{id} (auth'd) → 200, batch metadata visible
# GET /api/varieties → 200, JSON list contains pre-seeded varieties
```

---

## 17. Documentation Requirements

### `README.md`
Must include exact commands for:
1. System dependency installation (weasyprint libs, Python deps)
2. Virtual environment setup
3. `.env` configuration (copy `.env.example`, set required vars)
4. DB initialization
5. Running the web app
6. Running the Telegram bot
7. Running tests
8. Generating a sample report
9. Loading the web UI and logging in
10. Known limitations (top-layer-only, LAS partial, USDZ partial, heuristic weights)

### `docs/USER_MANUAL.md`
Written for a **non-technical apple trade operator**. Language: **Polish**.
Include step-by-step instructions for:
1. Jak wykonać skanowanie (Scaniverse + iPhone + pierścień pomiarowy)
2. Jak wgrać plik na Google Drive i udostępnić go
3. Jak utworzyć nową partię w Telegramie
4. Jak dołączyć skan przez link Google Drive
5. Jak przejść do panelu przeglądu i wykonać adnotację
6. Jak wygenerować i pobrać raport
7. Jak usunąć partię

### `docs/CAPTURE_GUIDE.md`
iPhone LiDAR + Scaniverse standard operating procedure:
1. Place the 75 mm measuring ring next to a representative apple in the top layer
2. Open Scaniverse → New Scan → Room/Object mode
3. Scan from directly above, covering full crate top surface
4. Process on device
5. Export as PLY (recommended) or OBJ
6. Upload to shared Google Drive folder with "Anyone with link can view" permission
7. Copy share link → paste into Telegram bot or web UI

### `docs/LIMITATIONS.md`
Must state clearly:
- Top-layer-only: hidden apples cannot be measured
- Projection is heuristic until grader ground truth is available
- LAS: metadata only without laspy
- USDZ: ingested but not fully processed
- Weight model is geometric, not calibrated by variety or storage condition
- Reports are NOT certified, NOT machine-sorted output, NOT legal quality compliance

### `docs/ACCURACY_METHODOLOGY.md`
Explain:
- What is directly measured vs. estimated
- The ring-based calibration method and its limitations
- The Hough circle detection approach and expected false positive/negative rate
- The weight estimation formula and its assumptions
- What "confidence" means in this system
- The path to improving confidence (paired grader data collection)

---

## 18. Makefile (Complete)

```makefile
.PHONY: all setup install-system-deps install-python-deps init-db test lint typecheck \
        smoke sample-report run-web run-bot clean help

help:
	@echo "apple-caliber-scan — available commands:"
	@echo "  make setup              — install all deps (system + python)"
	@echo "  make init-db            — initialize SQLite database"
	@echo "  make sample-report      — generate Polish sample report"
	@echo "  make test               — run all tests"
	@echo "  make lint               — run ruff linter"
	@echo "  make typecheck          — run mypy"
	@echo "  make smoke              — quick smoke test (import + init-db + sample-report)"
	@echo "  make run-web            — start FastAPI web app on :8000"
	@echo "  make run-bot            — start Telegram bot"
	@echo "  make clean              — remove generated artifacts"

setup: install-system-deps install-python-deps

install-system-deps:
	sudo apt-get update -qq
	sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
	  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info libgirepository1.0-dev \
	  python3-dev python3-pip

install-python-deps:
	pip3 install -e ".[dev]"

init-db:
	PYTHONPATH=. python3 -m apple_caliber_scan init-db

sample-report:
	mkdir -p sample-output
	PYTHONPATH=. python3 -m apple_caliber_scan sample-report --output-dir sample-output

test:
	PYTHONPATH=. pytest tests/ -v

lint:
	ruff check apple_caliber_scan tests

typecheck:
	mypy apple_caliber_scan --ignore-missing-imports

smoke:
	PYTHONPATH=. python3 -c "import apple_caliber_scan; print('Import OK')"
	make init-db
	make sample-report
	@echo "Smoke test passed."

run-web:
	PYTHONPATH=. uvicorn apple_caliber_scan.web.app:create_app --factory \
	  --host 0.0.0.0 --port 8000 --reload

run-bot:
	PYTHONPATH=. python3 -m apple_caliber_scan run-bot

clean:
	rm -rf sample-output/ data/generated/ __pycache__/ .mypy_cache/ .pytest_cache/ \
	       apple_caliber_scan/__pycache__/ tests/__pycache__/
```

---

## 19. `pyproject.toml` (Complete)

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "apple-caliber-scan"
version = "0.1.0"
description = "Apple caliber analysis system for Polish apple trade — Freshora Sp. Z. o. o."
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "httpx>=0.28.0",
    "Pillow>=10.3.0",
    "numpy>=1.26.0",
    "opencv-python-headless>=4.9.0",
    "plyfile>=1.0.3",
    "trimesh>=4.3.0",
    "weasyprint>=62.0",
    "Jinja2>=3.1.4",
    "gdown>=5.2.0",
    "python-multipart>=0.0.9",
    "python-dotenv>=1.0.1",
    "itsdangerous>=2.2.0",
    "starlette>=0.37.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.28.0",  # for TestClient
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
las = ["laspy>=2.5.0"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 20. `.env.example` (Complete)

```bash
# apple-caliber-scan environment configuration
# Copy this file to .env and fill in required values.
# NEVER commit .env to git.

# --- REQUIRED ---
# Web UI password (required — app will not start without this)
ACS_WEB_PASSWORD=changeme_strong_password_here

# Web session secret key (required — use: python3 -c "import secrets; print(secrets.token_hex(32))")
ACS_WEB_SECRET_KEY=changeme_generate_with_secrets_module

# --- OPTIONAL ---
# Web UI username (default: freshora)
ACS_WEB_USERNAME=freshora

# Telegram bot token from @BotFather (leave blank to disable bot)
ACS_TELEGRAM_TOKEN=

# Data directory for previews, reports, and DB (default: ./data)
ACS_DATA_DIR=./data

# SQLite database path (default: ./data/apple_caliber_scan.db)
ACS_DB_PATH=./data/apple_caliber_scan.db

# Public base URL used in Telegram links (default: http://localhost:8000)
ACS_PUBLIC_BASE_URL=http://localhost:8000

# Web UI base URL (default: http://localhost:8000)
ACS_WEB_BASE_URL=http://localhost:8000

# Log level: DEBUG | INFO | WARNING | ERROR (default: INFO)
ACS_LOG_LEVEL=INFO

# Default crate weight in kg (default: 300)
ACS_DEFAULT_CRATE_WEIGHT_KG=300

# Physical calibration ring diameter in mm (default: 75.0)
ACS_DEFAULT_RING_MM=75.0

# Maximum truck load in kg for validation warning (default: 20000)
ACS_MAX_TRUCK_WEIGHT_KG=20000

# Path to company logo PNG/SVG for reports (optional — text header used if not set)
ACS_LOGO_PATH=

# Google Drive download timeout in seconds (default: 120)
ACS_GDOWN_TIMEOUT_S=120
```

---

## 21. `.gitignore` (Complete)

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.eggs/
*.egg

# Virtual environments
.venv/
venv/
env/

# Environment / secrets
.env
*.env.local

# Data and generated files
data/
sample-output/
*.db
*.db-shm
*.db-wal

# Testing
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
```

---

## 22. CLAUDE.md (Complete — Place at Repo Root)

```markdown
# apple-caliber-scan — CLAUDE.md

## Project Overview
Apple caliber analysis system for Polish apple trade.
Operator: Freshora Sp. Z. o. o.
Stack: Python 3.12, FastAPI, SQLite, Telegram Bot API (httpx), Google Drive (gdown),
weasyprint, OpenCV, Pillow, trimesh, plyfile.

## Source of Truth
- Requirements: `../apple-caliber-scan MVP.pdf` (parent directory)
- This CLAUDE.md (project-specific rules)

## Development Commands
- `make setup` — install all deps
- `make init-db` — initialize DB (run after first clone)
- `make run-web` — start web UI on :8000
- `make run-bot` — start Telegram bot
- `make sample-report` — generate synthetic Polish sample report

## Test Commands
- `make test` — run all tests (must pass before any PR)
- `make lint` — ruff linter (zero tolerance)
- `make typecheck` — mypy (warnings allowed, errors fix)
- `make smoke` — quick smoke test

## Architecture Map
- `apple_caliber_scan/config.py` — all settings from env
- `apple_caliber_scan/database/` — SQLite schema + CRUD
- `apple_caliber_scan/scan/` — point cloud loading, preview, circle detection
- `apple_caliber_scan/services/` — ingest, calibration, estimation, reporting, groundtruth
- `apple_caliber_scan/storage/drive.py` — Google Drive download
- `apple_caliber_scan/web/` — FastAPI app, auth, routes, templates
- `apple_caliber_scan/telegram/bot.py` — Telegram polling bot
- `tests/` — all tests

## Non-Negotiable Domain Rules
1. Top-layer distribution = primary measured result. NEVER present as full-batch measurement.
2. Whole-batch projection = ESTIMATE (SZACUNEK), always LOW confidence until grader GT.
3. No certification claims. No machine-sorter equivalence claims.
4. Caliber classes: 0-60, 60-65, 65-70, 70-75, 75-80, 80-85, 85-90, 90+. Exactly these.
5. 75+ share must be computed and displayed prominently in every report.
6. Reports in Polish only. Legal clauses in Polish. Freshora Sp. Z. o. o. branding.
7. After scan ingest: delete local scan file immediately. Store only preview + derived data.

## Security Rules
- Never log ACS_WEB_PASSWORD, ACS_WEB_SECRET_KEY, or ACS_TELEGRAM_TOKEN.
- Never commit .env to git.
- All secrets via environment variables only.
- Web UI requires authenticated session (ACS_WEB_PASSWORD) for all non-login routes.

## Data Privacy Rules
- Store only: seller name/address (entered by operator), variety, scan preview PNG,
  caliber distribution, reports. No biometric or personal customer data.
- /deletebatch removes all stored data for a batch. Irreversible.
- Scan files are deleted immediately after ingest.

## Graph Navigation
- If graphify-out/ exists, query it first before reading raw files.

## RTK Shell Usage
- Prefer: rtk git status | rtk grep | rtk find | rtk pytest
- Avoid broad full-file reads. Read exact line ranges.

## Code Style
- Small, testable functions. No function over ~50 lines.
- Typed signatures everywhere (mypy-compatible).
- No silent failures. Log errors clearly.
- No fake accuracy claims in code comments or output.
- Prefer deterministic sample data (fixed seed).
- Run tests after every meaningful change.
```

---

## 23. `.claude/` Agent and Command Files

### `.claude/commands/test.md`
```markdown
Run: PYTHONPATH=. pytest tests/ -v
Fix all failures before reporting done.
```

### `.claude/commands/lint.md`
```markdown
Run: ruff check apple_caliber_scan tests
Fix all errors. Warnings may be documented.
```

### `.claude/commands/smoke.md`
```markdown
Run in order:
1. python3 -c "import apple_caliber_scan; print('Import OK')"
2. PYTHONPATH=. python3 -m apple_caliber_scan init-db
3. PYTHONPATH=. python3 -m apple_caliber_scan sample-report --output-dir /tmp/acs-smoke
Report pass/fail for each step.
```

### `.claude/commands/run-local.md`
```markdown
1. Copy .env.example to .env if .env doesn't exist.
2. Set ACS_WEB_PASSWORD and ACS_WEB_SECRET_KEY in .env.
3. Run: make init-db
4. Run: make run-web
5. Open: http://localhost:8000
Login with username from ACS_WEB_USERNAME (default: freshora) and your ACS_WEB_PASSWORD.
```

### `.claude/commands/review.md`
```markdown
Review the last meaningful change for:
1. Domain rule compliance (top-layer-only, no cert claims, caliber classes correct)
2. Security (no hardcoded secrets, auth required)
3. Test coverage (did you add tests for new logic?)
4. Polish text correctness (reports, bot messages)
5. Legal clause presence in reports
```

### `.claude/commands/adversarial-review.md`
```markdown
Act as an adversarial reviewer. Check for:
1. Any code path that could claim high confidence without grader ground truth
2. Any report that omits the legal limitation clauses
3. Any route accessible without authentication
4. Any secret logged or printed to stdout
5. Any scan file left on disk after ingest
6. Any caliber class boundary off-by-one error
7. Any Polish report missing the 75+ share summary
8. Any non-Polish text in customer-facing report templates
```

### `.claude/agents/implementation-reviewer.md`
```markdown
---
name: implementation-reviewer
description: Reviews implementation for domain rule compliance, correctness, and completeness.
---
Focus areas: caliber class correctness, confidence model honesty, report total consistency,
Polish text completeness, Freshora branding, legal clauses, auth on all routes,
scan file deletion after ingest. Check tests cover all reviewed areas.
```

### `.claude/agents/test-engineer.md`
```markdown
---
name: test-engineer
description: Writes and validates tests for apple-caliber-scan.
---
Priority: caliber boundary tests, calibration scale tests, confidence guardrail tests,
report total-consistency tests, synthetic ingest tests, Drive URL parsing tests,
end-to-end web flow tests. All tests must be deterministic (fixed seeds, no network).
```

### `.claude/agents/security-privacy-reviewer.md`
```markdown
---
name: security-privacy-reviewer
description: Reviews for security and privacy compliance.
---
Check: no secrets in logs, auth on all routes, scan file deleted after ingest,
/deletebatch removes all data, no personal data beyond operator-entered fields,
.env not committed, ACS_WEB_PASSWORD required to start.
```

### `.claude/agents/docs-reviewer.md`
```markdown
---
name: docs-reviewer
description: Reviews documentation for completeness and accuracy.
---
Check: README commands actually work, USER_MANUAL is in Polish, LIMITATIONS.md is honest,
ACCURACY_METHODOLOGY.md does not overclaim, CAPTURE_GUIDE.md matches Scaniverse workflow,
legal clauses in LIMITATIONS match report template clauses exactly.
```

---

## 24. Build Order (Follow Exactly)

Execute in this sequence to ensure each layer builds on a working foundation:

1. `git init` inside `apple-caliber-scan/`
2. Create directory structure (all folders)
3. Write `pyproject.toml`
4. Write `.env.example`
5. Write `.gitignore`
6. Write `apple_caliber_scan/config.py`
7. Write `apple_caliber_scan/database/schema.sql` + `connection.py` + `crud.py`
8. Write `apple_caliber_scan/scan/fixtures.py` (needed for tests before real scan loading)
9. Write `apple_caliber_scan/scan/loader.py` + `normalizer.py` + `preview.py` + `detector.py`
10. Write `apple_caliber_scan/services/calibration.py` + `estimation.py`
11. Write `apple_caliber_scan/storage/drive.py`
12. Write `apple_caliber_scan/services/ingest.py`
13. Write `apple_caliber_scan/services/reporting.py` + `web/templates/report_pl.html`
14. Write `apple_caliber_scan/services/groundtruth.py`
15. Write `apple_caliber_scan/__init__.py` (CLI entry point including `sample-report`)
16. Write all test files under `tests/`
17. **Run `make install-python-deps`** — install deps
18. **Run `make test`** — fix all failures before continuing
19. Write `apple_caliber_scan/web/` (app, auth, routes, templates)
20. Write `apple_caliber_scan/telegram/bot.py`
21. **Run `make test`** again — all tests including web tests
22. **Run `make lint`** — fix all issues
23. **Run `make smoke`** — confirm end-to-end
24. Write all docs (`README.md`, `docs/`, `CLAUDE.md`, `.claude/`)
25. Write `Makefile`
26. **Run `make sample-report`** — confirm Polish HTML+PDF generated
27. **Verify** sample report visually: correct Freshora branding, 8 caliber classes, 75+ share, legal clauses
28. `git add` and `git commit -m "feat: initial apple-caliber-scan MVP"`

---

## 25. Final Output Format Required

After building, return exactly these sections:

1. **What I built** — complete feature list
2. **How to run locally** — exact commands
3. **How to use the local demo/application** — step by step
4. **How to generate or load sample data** — exact command
5. **How to run tests** — exact command + results
6. **Deployment notes** — WSL2 + optional Vultr VPS
7. **Known limitations** — honest list
8. **Remaining risks / assumptions** — what was assumed
9. **Next calibration or improvement steps** — paired data collection path
10. **Exact commands run** — every shell command executed
11. **Test results** — exact pytest output
12. **Important files created/changed** — complete file list

Do not claim success unless `make test` and `make sample-report` actually ran and passed.
If something failed, state exactly what failed and what was verified instead.

---

## 26. The Single Hardest Part — Do Not Shortcut It

The canvas-based annotation UI (`scan_review.html` + `static/review.js`) is the most
technically complex part of this MVP. Do **not** replace it with a form-based workaround.
The interactive canvas is essential for the operator to:
- See the scan preview
- Identify which circle is the measuring ring
- Correct false-positive/negative circle detections
- Confirm the annotation before generating the report

Build it with vanilla JavaScript and HTML5 Canvas. It does not need to be perfect —
it needs to be functional: click to select ring, drag to resize circles, sidebar updates live.
This is what makes the MVP usable in the field, not just technically correct in tests.

---

*End of build prompt — apple-caliber-scan v0.1.0 — Freshora Sp. Z. o. o.*
*Generated: 2026-05-16 | Status: READY TO BUILD — all questions answered*
