# Security & Privacy — Apple Caliber Scan

**Freshora Sp. Z. o. o.**

---

## Authentication

### Web UI

All non-login routes require an authenticated session.

```python
@require_login
async def route_handler(request: Request) -> Response:
    ...
```

- Username: `freshora` (hardcoded)
- Password: `ACS_WEB_PASSWORD` environment variable (required at startup)
- Sessions: signed cookies via Starlette `SessionMiddleware`
- Secret key: `ACS_WEB_SECRET_KEY` (64+ random hex chars, required at startup)
- Session lifetime: 8 hours
- No "remember me" — sessions expire on browser close or after 8 hours

**The app will refuse to start if `ACS_WEB_PASSWORD` or `ACS_WEB_SECRET_KEY` are unset.**

### Telegram Bot

The bot is secured by token — only someone with the bot token can interact with it.
The token is stored in `ACS_TELEGRAM_TOKEN` (environment variable only, never logged).

For multi-user deployments, add an allowlist of Telegram `chat_id` values in `config.py`.
The current MVP assumes a single-operator private bot.

---

## Secrets Management

| Secret | Variable | Rules |
|--------|----------|-------|
| Web UI password | `ACS_WEB_PASSWORD` | Never logged, never in HTML output |
| Session signing key | `ACS_WEB_SECRET_KEY` | Never logged, never in error messages |
| Telegram bot token | `ACS_TELEGRAM_TOKEN` | Never logged, bot logs "token set" not the value |

**Never commit `.env` to git.** The `.gitignore` excludes `.env` by default.

Verify your `.gitignore` contains:
```
.env
*.env
```

---

## Data Privacy

### What Is Stored

| Data Type | Stored? | Where |
|-----------|---------|-------|
| Apple caliber distribution | Yes | SQLite (scan_circles, annotations) |
| Scan preview PNG | Yes | data/previews/ |
| HTML/PDF/JSON reports | Yes | data/reports/ |
| Seller name + address | Yes | SQLite (sellers, batches) — operator-entered |
| Apple variety | Yes | SQLite (varieties) |
| Raw PLY/OBJ scan file | **No** | Deleted immediately after ingest |
| Buyer information | No | Not collected |
| Consumer personal data | No | Not collected |

### Scan File Deletion

After `ingest._process_local_file()` generates the preview PNG, the raw scan file is
unconditionally deleted:

```python
os.unlink(local_path)
```

This runs even if circle detection fails. Only the 1024×1024 density PNG is retained.
The PNG contains no personally identifiable information — it is a top-down density image
of the apple surface.

### Batch Deletion

`/deletebatch` (Telegram) and the "Usuń partię" button (Web UI) delete:
- The `batches` row and all related foreign-key rows (cascading delete)
- The scan preview PNG from disk
- All HTML/PDF/JSON report files from disk

This is **irreversible**. The confirmation step ("Odpowiedz TAK" / "Potwierdź") is
mandatory before deletion proceeds.

### GDPR Considerations

The system stores seller names and addresses as entered by the operator. This is personal
data under GDPR if sellers are natural persons. Freshora as the data controller should:

1. Inform sellers their data is stored for batch tracking purposes
2. Provide a deletion mechanism (the /deletebatch command fulfills this for individual batches)
3. Not transfer this data to third parties
4. Document the legal basis (legitimate interest in trade documentation)

The system does not collect data on end consumers.

---

## Secrets in Logs

The application explicitly avoids logging secrets:

- Config module logs `"web password configured"` not the password value
- Bot startup logs `"Telegram token configured"` not the token
- Session middleware errors do not expose the secret key
- Report generation does not include auth credentials

If you add logging, follow the pattern: log the presence of a secret, never its value.

---

## Network Security

### Local Deployment

The web UI binds to `localhost:8000` by default (`ACS_HOST=127.0.0.1`).
It is not accessible from outside the machine without explicit configuration.

### VPS Deployment

When deployed on a VPS:
- Run behind Nginx reverse proxy (see `docs/DEPLOYMENT.md`)
- Enable HTTPS via Let's Encrypt
- Set `ACS_HOST=127.0.0.1` — Nginx handles external-facing TLS
- Firewall: block port 8000 from external access, allow only Nginx on 443/80

### Google Drive

Scan files must be shared as "anyone with the link" — they are publicly accessible by
anyone who knows the link. This is acceptable for scan geometry data (not personal data),
but operators should be aware that scan files are effectively public while the link is active.

---

## Dependency Supply Chain

Dependencies are pinned in `pyproject.toml`. Before deploying:

```bash
.venv/bin/pip list --format=json | python3 -c \
    "import json,sys; [print(p['name'], p['version']) for p in json.load(sys.stdin)]"
```

Review for known CVEs using `pip-audit`:

```bash
.venv/bin/pip install pip-audit
.venv/bin/pip-audit
```

---

## Security Checklist

Before production deployment:

- [ ] `ACS_WEB_PASSWORD` set to a strong password (≥16 chars)
- [ ] `ACS_WEB_SECRET_KEY` set to 64+ random hex chars
- [ ] `.env` not committed to git (`git status` clean)
- [ ] Nginx HTTPS configured with valid certificate
- [ ] Port 8000 blocked on firewall (Nginx only)
- [ ] `ACS_HOST=127.0.0.1` in `.env` (not 0.0.0.0)
- [ ] Backups configured for `data/` directory
- [ ] Telegram bot token rotated if accidentally exposed
