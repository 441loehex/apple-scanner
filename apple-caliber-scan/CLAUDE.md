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
