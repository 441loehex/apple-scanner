# apple-caliber-scan

Apple caliber analysis system for Polish apple trade — **Freshora Sp. Z. o. o.**

Analyzes LiDAR scans of apple crate top layers to estimate caliber distribution, 75+ share,
and batch weight projections. Generates professional Polish trade reports (HTML + PDF).

---

## 1. System Dependencies (WeasyPrint)

WeasyPrint requires system libraries for PDF generation:

```bash
sudo apt-get install -y libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 libffi-dev shared-mime-info libgirepository1.0-dev \
  python3-dev python3-pip python3-venv
```

## 2. Python Setup

```bash
cd apple-caliber-scan/
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## 3. Environment Configuration

```bash
cp .env.example .env
# Edit .env — set required variables:
# ACS_WEB_PASSWORD=your_strong_password
# ACS_WEB_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

## 4. Database Initialization

```bash
make init-db
# OR: PYTHONPATH=. .venv/bin/python -m apple_caliber_scan init-db
```

## 5. Running the Web App

```bash
make run-web
# Open: http://localhost:8000
# Login with: freshora / (your ACS_WEB_PASSWORD)
```

## 6. Running the Telegram Bot

```bash
# First set ACS_TELEGRAM_TOKEN in .env (from @BotFather)
make run-bot
```

If `ACS_TELEGRAM_TOKEN` is not set, the bot logs a warning and exits cleanly.

## 7. Running Tests

```bash
make test
# OR: PYTHONPATH=. .venv/bin/pytest tests/ -v
```

Expected: 65 passed, 0 failed.

## 8. Generating a Sample Report

```bash
make sample-report
# Output in ./sample-output/:
#   sample_preview.png   — top-down scan preview
#   sample_report.html   — Polish HTML report
#   sample_report.pdf    — PDF version
#   sample_report.json   — Machine-readable JSON
```

## 9. Web UI Usage

1. Open http://localhost:8000
2. Log in (username: `freshora`, password: `ACS_WEB_PASSWORD`)
3. Click **Nowa partia** to create a batch
4. In the batch detail, click **Dołącz skan** and paste a Google Drive link
5. Review detected circles in the annotation canvas — mark the measuring ring
6. Click **Zapisz adnotację i generuj raport**
7. Download HTML or PDF report from batch detail

## 10. Known Limitations

- **Top-layer only**: Only the visible top layer of apples is measured. Hidden apples are not accessible to the scanner.
- **Batch projection is heuristic**: Whole-batch weight estimates assume uniform distribution — always labeled SZACUNEK (estimate).
- **LAS files**: Metadata extracted only. Install `laspy` for full support (`pip install "apple-caliber-scan[las]"`).
- **USDZ files**: Accepted but not fully processed (MVP limitation).
- **Weight model**: Geometric heuristic, not calibrated by variety or storage condition.
- **Reports**: NOT certified, NOT machine-sorted output, NOT legal quality compliance.

## Architecture

```
apple_caliber_scan/
├── config.py          — Environment variable settings
├── database/          — SQLite schema + CRUD
├── scan/              — PLY/OBJ loading, normalization, preview, Hough detection
├── services/          — Calibration, estimation, reporting, ingest
├── storage/           — Google Drive download
├── web/               — FastAPI app, auth, templates, canvas annotation UI
└── telegram/          — Telegram bot (httpx polling, FSM)
```

## License

Proprietary — Freshora Sp. Z. o. o. All rights reserved.
