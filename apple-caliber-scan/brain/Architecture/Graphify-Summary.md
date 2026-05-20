# Architecture — Graphify Summary

Generated: 2026-05-18 · 686 nodes · 1226 edges · 28 communities

## Core Abstractions (God Nodes)
- `Circle` — 45 edges. Central dataclass for detected apple circles.
- `db_conn()` — 29 edges. SQLite connection context manager.
- `CaliberDistribution` — 23 edges. Distribution result container.
- `classify_diameter()` — 21 edges. Maps mm diameter → caliber class label.
- `generate_report()` / `_cmd_sample_report()` — 19 edges each.
- `normalize_top_down()` / `render_preview()` — 16 edges each.

## Key Pipelines (from Graphify Hyperedges)
1. **Scan Ingest**: Google Drive → load_scan → normalize_top_down → render_preview → detect_circles → detect_calibration_ring → classify_orientations → SQLite → delete raw file
2. **Caliber Report**: Ring Calibration → CaliberDistribution → above_75_share() → Polish Report (SZACUNEK + legal clause)
3. **Web CRUD**: batch_list → batch_new → batch_detail → scan_drive → scan_review → report_pl
4. **Annotation**: canvas + popover + auto-ring alert + brightness controls → calibration confirm

## Community Map
| Community | Key nodes |
|---|---|
| App Core & Database | db_conn, CRUD, FastAPI routes |
| Scan Detection Pipeline | detect_circles, detect_calibration_ring, Hough |
| Estimation & Caliber Dist | CaliberDistribution, above_75_share, compute_distribution |
| Web UI & Report Templates | report_pl.html, batch_detail, scan_review |
| Caliber Test Suite | classify_diameter tests, boundary tests |
| Auth & Config | require_login, ACS_WEB_*, SessionMiddleware |
| Google Drive Storage | gdown, download_drive_file |

## Surprising Connections
- review.js Canvas ↔ detect_calibration_ring() (semantically similar)
- classifyDiameter (JS) ↔ compute_scale_factor() (semantically similar)
- 75+ Share ↔ Measurement Pipeline (core metric link)

## Source: `graphify-out/GRAPH_REPORT.md`
