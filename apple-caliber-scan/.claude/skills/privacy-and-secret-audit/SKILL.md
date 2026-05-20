---
name: privacy-and-secret-audit
description: Audits secrets, logs, env handling, raw scan deletion, stored personal/business data, and /deletebatch behavior.
---

Required checks:

1. Search for hardcoded secrets:
   `grep -rn "ACS_WEB_PASSWORD\|ACS_WEB_SECRET_KEY\|ACS_TELEGRAM_TOKEN\|password=\|secret=" apple_caliber_scan tests`
2. Verify secrets are env-only: check `config.py` only reads from `os.environ`.
3. Verify `.env` is in `.gitignore`.
4. Verify all non-login routes have `@require_login`.
5. Verify raw scan file deletion: `ingest.py` uses try/finally with `tmp_path.unlink()`.
6. Verify only allowed data stored: seller name/address, variety, preview PNG, caliber distribution, reports.
7. Verify `/batches/{id}/delete` route calls `delete_batch(conn, batch_id)` and removes preview/report files.
8. Add tests for any missing guarantee (lifecycle test, deletebatch test, log redaction test).

Never commit actual secrets. Never paste secrets in memory or logs.
