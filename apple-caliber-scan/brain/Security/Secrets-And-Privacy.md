# Security and Privacy

## Secrets
All secrets from env vars only:
- `ACS_WEB_PASSWORD` — web UI login password
- `ACS_WEB_SECRET_KEY` — session signing key (32-byte hex)
- `ACS_TELEGRAM_TOKEN` — Telegram Bot API token

Never logged, never committed, never in test fixtures.
`.env` is in `.gitignore`.

## Authentication
- `@require_login` decorator on all non-login FastAPI routes
- Session via Starlette SessionMiddleware, 8h max age, lax same-site, https_only=False (local deployment)
- Login: single-operator, username=admin (ACS_WEB_USERNAME from config), password from env

## Data Privacy
Stored per batch:
- seller name, seller address (operator-entered)
- variety, price, dates, notes
- preview PNG (derived from scan, not raw scan data)
- caliber distribution (counts per class)
- report HTML/PDF

NOT stored:
- Raw scan files (deleted immediately after ingest)
- Biometric or customer personal data
- Full point clouds

## /deletebatch Guarantee
- `delete_batch(conn, batch_id)` removes DB record and cascades to scans, circles, reports
- Route must also delete preview files and report files from filesystem
- Irreversible: no soft-delete

## Scan File Lifecycle
1. Create temp file in DATA_DIR
2. Download/copy scan → temp file
3. Process: load → normalize → preview → detect
4. Delete temp file in `finally` block (always, even on error)
5. Only preview PNG and derived DB data remain
