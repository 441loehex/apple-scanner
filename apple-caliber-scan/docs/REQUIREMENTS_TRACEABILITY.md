# Requirements Traceability

**Source of truth:** `../apple-caliber-scan MVP.pdf` + `CLAUDE.md`  
**Date:** 2026-05-20  
**Branch:** overhaul/universal-method-apple-caliber

## Domain Requirements

| Req | Description | Code | Tests | Status |
|---|---|---|---|---|
| D1 | Caliber classes exactly 0-60, 60-65, 65-70, 70-75, 75-80, 80-85, 85-90, 90+ | `services/estimation.py: CALIBER_CLASS_LABELS` | `test_caliber.py` (14 tests) | ✅ |
| D2 | 75+ share computed and prominent in every report | `services/estimation.py: above_75_share()` | `test_estimation.py`, `test_report_disclaimers.py` | ✅ |
| D3 | Top-layer distribution = measured result, never full-batch | `web/templates/report_pl.html` label | `test_report_disclaimers.py: test_top_layer_label_present` | ✅ |
| D4 | Whole-batch projection = SZACUNEK, LOW confidence until GT | `services/estimation.py: batch_projection_confidence()` | `test_estimation.py`, `test_report_disclaimers.py: test_szacunek_label_present_for_projection` | ✅ |
| D5 | No certification claims in reports/UI | Template legal clause | `test_report_disclaimers.py: test_no_certification_claim` | ✅ |
| D6 | No machine-sorter equivalence claims | Template legal clause | `test_report_disclaimers.py: test_no_full_batch_measurement_claim` | ✅ |
| D7 | Reports in Polish only | `web/templates/report_pl.html` | `test_report_polish_only.py` (3 tests) | ✅ |
| D8 | Freshora Sp. Z. o. o. branding | Template header | `test_report_disclaimers.py: test_freshora_branding_present` | ✅ |
| D9 | Legal disclaimer clause in every report | Template footer | `test_reporting.py: test_legal_clause_in_html`, `test_report_disclaimers.py: test_legal_disclaimer_clause_present` | ✅ |
| D10 | All 8 caliber classes shown in report (even if 0 count) | Template distribution table | `test_report_disclaimers.py: test_all_8_caliber_classes_present` | ✅ |

## Privacy and Security Requirements

| Req | Description | Code | Tests | Status |
|---|---|---|---|---|
| P1 | Raw scan file deleted after ingest | `services/ingest.py: finally` block | `test_scan_file_lifecycle.py` (4 tests) | ✅ |
| P2 | Only preview PNG + derived data stored | `services/ingest.py` + data model | `test_scan_file_lifecycle.py: test_ingest_synthetic_creates_preview_no_scan_file` | ✅ |
| P3 | /deletebatch removes all batch data | `web/routes/batches.py: batch_delete()` | `test_deletebatch_privacy.py` (5 tests) | ✅ |
| P4 | Secrets are env-only, never logged | `config.py: os.environ.get()` | `test_secret_redaction.py` (5 tests) | ✅ |
| P5 | .env never committed | `.gitignore` | — | ✅ (manual) |
| P6 | All non-login routes require auth | `@require_login` on all routes | `test_web.py`, `test_deletebatch_privacy.py: test_deletebatch_requires_auth` | ✅ |

## Functional Requirements (Scan Pipeline)

| Req | Description | Code | Tests | Status |
|---|---|---|---|---|
| F1 | Load PLY/OBJ/ZIP scan files | `scan/loader.py: load_scan()` | `test_ingest.py` | ✅ |
| F2 | Point cloud normalization (top-down view) | `scan/normalizer.py: normalize_top_down()` | `test_normalizer.py` (7 tests) | ✅ |
| F3 | Preview PNG generation from depth map | `scan/preview.py: render_preview()` | `test_preview.py` (4 tests) | ✅ |
| F4 | Circle detection via Hough | `scan/detector.py: detect_circles()` | `test_detector.py` (8 tests) | ✅ |
| F5 | Calibration ring auto-detection (blue, 75mm) | `scan/detector.py: detect_calibration_ring()` | `test_detector.py: test_detect_calibration_ring_*` | ✅ |
| F6 | Apple orientation classification | `scan/detector.py: classify_orientations()` | `test_detector.py: test_*_apple_classified` | ✅ |
| F7 | Scale factor from ring (mm/px) | `services/calibration.py: compute_scale_factor()` | `test_calibration.py` (6 tests) | ✅ |
| F8 | Caliber distribution from circles | `services/estimation.py: compute_distribution()` | `test_estimation.py` | ✅ |
| F9 | Whole-batch projection with confidence | `services/estimation.py: estimate_batch()` | `test_estimation.py` | ✅ |
| F10 | HTML + PDF + JSON report generation | `services/reporting.py: generate_report()` | `test_reporting.py` (8 tests) | ✅ |
| F11 | Google Drive scan download | `storage/drive.py: download_drive_file()` | `test_drive.py` (8 tests) | ✅ |
| F12 | Telegram bot operator commands | `telegram/bot.py` | — | ⚠️ Manual only (httpx bot, no mock tests yet) |

## Web UI Requirements

| Req | Description | Code | Tests | Status |
|---|---|---|---|---|
| W1 | Login with ACS_WEB_PASSWORD | `web/app.py, web/auth.py` | `test_web.py: test_login_*` | ✅ |
| W2 | Batch list, create, detail, delete | `web/routes/batches.py` | `test_web.py`, `test_deletebatch_privacy.py` | ✅ |
| W3 | Scan upload (Drive URL / local) | `web/routes/scans.py` | Partial (test_ingest.py synthetic) | ⚠️ |
| W4 | Scan annotation UI (canvas, ring, circles) | `web/static/review.js` | — | ⚠️ JS only |
| W5 | Report view and download | `web/routes/reports.py` | `test_reporting.py` | ✅ |
| W6 | Session expiry (8h) | `web/app.py SessionMiddleware` | — | ✅ (config) |

## Gaps / Open Items

| Gap | Risk | Path to close |
|---|---|---|
| Telegram bot unit tests | Low | Add mocked bot tests (WP-G optional) |
| Scan annotation JS tests | Low | JS unit tests require browser test setup |
| Local scan upload (non-Drive) integration test | Low | Add in future sprint |
