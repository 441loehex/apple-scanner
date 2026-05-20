# Architecture Graph Summary

**Generated from:** `graphify-out/GRAPH_REPORT.md` (2026-05-18)  
**Stats:** 686 nodes · 1226 edges · 28 communities

## Module Map (confirmed vs CLAUDE.md)

```
apple_caliber_scan/
├── config.py                 — ACS_WEB_PASSWORD, ACS_WEB_SECRET_KEY, ACS_TELEGRAM_TOKEN,
│                               DATA_DIR, GDOWN_TIMEOUT_S, DEFAULT_CRATE_WEIGHT_KG
├── __main__.py               — CLI: init-db, sample-report, run-bot
├── database/
│   ├── connection.py         — db_conn() context manager, initialize_schema()
│   ├── crud.py               — create/get/list/delete for batches, scans, circles, reports
│   └── schema.sql            — SQLite DDL: batches, scans, circles, varieties, reports, ground_truth
├── scan/
│   ├── loader.py             — load_scan(), load_polycam_raw_zip(), load_ply(), load_obj()
│   ├── normalizer.py         — normalize_top_down() — Y-axis, top 20% crop, scale to [0,1]
│   ├── preview.py            — render_preview() — depth colormap PNG
│   ├── detector.py           — detect_circles(), detect_calibration_ring(),
│   │                           classify_orientations(), Circle dataclass
│   └── fixtures.py           — synthetic point cloud fixtures for tests
├── services/
│   ├── ingest.py             — ingest_from_drive_url(), ingest_from_local_file() — DELETE raw
│   ├── calibration.py        — compute_scale_factor(), CalibrationResult
│   ├── estimation.py         — CaliberDistribution, compute_distribution(), above_75_share(),
│   │                           batch_projection_confidence(), ConfidenceLevel
│   ├── reporting.py          — generate_report(), HTML + PDF + JSON outputs
│   └── groundtruth.py        — import_groundtruth(), ground truth CRUD
├── storage/
│   └── drive.py              — download_drive_file(), extract_drive_file_id() (gdown)
├── web/
│   ├── app.py                — create_app() FastAPI factory, SessionMiddleware
│   ├── auth.py               — require_login, is_authenticated, login_user, logout_user
│   ├── routes/
│   │   ├── batches.py        — CRUD: list, new, detail, delete; Polycam preset
│   │   ├── scans.py          — scan upload (Drive URL / local ZIP), review, annotate
│   │   └── reports.py        — generate, view, download report
│   ├── templates/            — Jinja2: base, login, batch_list/new/detail, scan_drive/review,
│   │                           report_pl (Polish), report_sample
│   └── static/
│       └── review.js         — Canvas annotation UI: circles, ring highlight, brightness
└── telegram/
    └── bot.py                — Polling bot: /start /lista /partia /raport /usun /pomoc
```

## Full graphify output: `graphify-out/GRAPH_REPORT.md`
