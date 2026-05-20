# Implementation Plan — Apple Caliber Scan MVP

**Freshora Sp. Z. o. o.**
Status: MVP complete. This document records the build order and design decisions.

---

## Build Order (Completed)

### Phase 1 — Core Infrastructure
1. `pyproject.toml` — dependencies, build config
2. `Makefile` — dev workflow targets
3. `.env.example` — all 14 env vars documented
4. `.gitignore` — secrets, venv, artifacts excluded
5. `apple_caliber_scan/config.py` — settings from env with validation
6. `apple_caliber_scan/database/schema.sql` — 10 tables
7. `apple_caliber_scan/database/connection.py` — WAL mode context manager
8. `apple_caliber_scan/database/crud.py` — all CRUD operations

### Phase 2 — Scan Pipeline
9. `apple_caliber_scan/scan/fixtures.py` — synthetic crate generator
10. `apple_caliber_scan/scan/loader.py` — PLY/OBJ/GLB/USDZ/LAS loading
11. `apple_caliber_scan/scan/normalizer.py` — PCA top-down normalization
12. `apple_caliber_scan/scan/preview.py` — density projection PNG
13. `apple_caliber_scan/scan/detector.py` — Hough circle detection

### Phase 3 — Services
14. `apple_caliber_scan/services/calibration.py` — ring scale factor
15. `apple_caliber_scan/services/estimation.py` — caliber classification, 75+ share
16. `apple_caliber_scan/services/ingest.py` — pipeline orchestration + file deletion
17. `apple_caliber_scan/services/groundtruth.py` — grader GT import
18. `apple_caliber_scan/services/reporting.py` — HTML/PDF/JSON generation

### Phase 4 — Storage
19. `apple_caliber_scan/storage/drive.py` — Google Drive URL parsing + download

### Phase 5 — Web UI
20. `apple_caliber_scan/web/app.py` — FastAPI factory
21. `apple_caliber_scan/web/auth.py` — session auth
22. `apple_caliber_scan/web/routes/batches.py`
23. `apple_caliber_scan/web/routes/scans.py`
24. `apple_caliber_scan/web/routes/reports.py`
25. `apple_caliber_scan/web/templates/` — all HTML templates
26. `apple_caliber_scan/web/static/review.js` — canvas annotation UI

### Phase 6 — Telegram Bot
27. `apple_caliber_scan/telegram/bot.py` — FSM bot with all commands

### Phase 7 — CLI Entry Point
28. `apple_caliber_scan/__init__.py` — CLI dispatch
29. `apple_caliber_scan/__main__.py` — module invocation

### Phase 8 — Tests
30. `tests/conftest.py` — fixtures
31. `tests/test_caliber.py`
32. `tests/test_calibration.py`
33. `tests/test_drive.py`
34. `tests/test_estimation.py`
35. `tests/test_ingest.py`
36. `tests/test_reporting.py`
37. `tests/test_web.py`

### Phase 9 — Documentation
38. `README.md`
39. `CLAUDE.md`
40. `.claude/` agent and command files
41. `docs/USER_MANUAL.md`
42. `docs/CAPTURE_GUIDE.md`
43. `docs/LIMITATIONS.md`
44. `docs/ACCURACY_METHODOLOGY.md`
45. `docs/DEPLOYMENT.md`
46. `docs/ARCHITECTURE.md`
47. `docs/TESTING.md`
48. `docs/SECURITY_PRIVACY.md`

---

## Key Design Decisions

### SQLite over PostgreSQL
Single-operator field tool. SQLite in WAL mode handles concurrent reads and single-writer
access perfectly. No infrastructure to manage. The DB file is part of the backup unit.

### httpx over python-telegram-bot
Avoids version coupling with the large python-telegram-bot framework. The Telegram Bot API
is simple enough to use with direct httpx calls + a hand-rolled FSM in SQLite.

### Starlette SessionMiddleware over JWT
JWT is appropriate for stateless multi-server deployments. This is a single-server tool
with a single operator. Cookie sessions are simpler, expire naturally, and require no
token refresh logic.

### WeasyPrint over Reportlab/FPDF
WeasyPrint renders HTML→PDF, meaning the report template is maintained in one place (Jinja2
HTML) rather than maintaining a separate code-based PDF layout. fpdf2 is included as a
fallback for environments where WeasyPrint system libs can't be installed.

### Vanilla JS Canvas
No React, Vue, or build step. The annotation UI is a single file served as a static asset.
This eliminates npm dependency management for what is essentially a drag-and-click tool.

### PCA Normalization
Scaniverse exports may not be perfectly vertical. PCA on the point cloud finds the principal
axes and rotates so the camera-facing direction becomes Z. This ensures the top-down
projection is approximately orthographic regardless of scanner tilt.

---

## Future Work (Post-MVP)

Tracked items for future sprints, not in scope for MVP:

- [ ] Multi-crate batch scanning (scan multiple crates, aggregate distribution)
- [ ] Automatic variety-specific weight density lookup
- [ ] Empirical accuracy calibration against grader data (2024/2025 season)
- [ ] Export to Excel/CSV for seller comparison workflows
- [ ] Multi-user role system (admin vs. operator)
- [ ] Offline mode (scan locally without internet, sync later)
- [ ] USDZ full processing support
- [ ] LAS full processing (currently requires `laspy` extra)
