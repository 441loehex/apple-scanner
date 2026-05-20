# AGENTS.md — apple-caliber-scan

## Mission
Review and improve a Python 3.12 FastAPI/SQLite/OpenCV apple caliber analysis system for Freshora Sp. Z. o. o.

## Non-Negotiable Domain Rules
1. Top-layer distribution is the primary measured result. NEVER present it as full-batch measurement.
2. Whole-batch projection must be labeled SZACUNEK / estimate and LOW confidence until grader ground truth exists.
3. No certification claims. No machine-sorter equivalence claims.
4. Caliber classes must be exactly: 0-60, 60-65, 65-70, 70-75, 75-80, 80-85, 85-90, 90+.
5. 75+ share must be computed and displayed prominently in every report.
6. Reports must be Polish-only and Freshora-branded.
7. Raw scan files must be deleted after ingest; store only preview PNG + derived data.

## Security and Privacy
- Never log ACS_WEB_PASSWORD, ACS_WEB_SECRET_KEY, or ACS_TELEGRAM_TOKEN.
- Never commit .env to git.
- Secrets must come only from env vars.
- All non-login routes require authentication via @require_login decorator.
- /deletebatch must remove all batch data: DB records, preview files, report files.

## Architecture (confirmed)
```
apple_caliber_scan/
  config.py               — all settings from env
  database/               — SQLite schema + CRUD
  scan/                   — loader, normalizer, preview, detector
  services/               — ingest, calibration, estimation, reporting, groundtruth
  storage/drive.py        — Google Drive download (gdown)
  web/                    — FastAPI app, auth, routes, templates
  telegram/bot.py         — Telegram polling bot
tests/                    — all tests
```

## Stack (no paid APIs, no new runtime deps without evidence)
Python 3.12, FastAPI, SQLite, httpx, OpenCV-headless, Pillow, numpy, plyfile, trimesh, weasyprint, Jinja2, gdown, python-dotenv, itsdangerous, starlette.

## Review Priorities (in order)
1. Domain correctness: caliber classes, 75+ share, top-layer labeling, SZACUNEK, no certification claims.
2. Security/privacy: secrets, scan deletion, auth on all routes, /deletebatch.
3. Test coverage: scan lifecycle, deletebatch, report wording, secret redaction, web auth.
4. Type safety: mypy errors must be zero before merge.
5. Lint: ruff must pass with zero errors.
6. No paid external API, no hallucinated dependency.

## Required Gates (all must pass before merge)
```
make test       — all tests pass
make lint       — ruff zero errors
make typecheck  — mypy zero errors
make smoke      — import + init-db + sample-report
```

## Diagnose-Before-Patch Rule
For every bug:
1. Reproduce with smallest command.
2. Capture logs (no secrets).
3. Add failing test.
4. Explain root cause.
5. Only then patch.
6. Run targeted test + full gate after.

## Banned Patterns
- `print()` in source (use logger)
- Secrets in log messages or test fixtures
- Functions over ~50 lines
- Untested refactors (test must exist before refactor)
- Claims of certification, grader equivalence, or full-batch accuracy
- English strings in Polish report templates
