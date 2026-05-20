# Test Gates

## Required gates (all must pass before merge)
```
make test       — pytest tests/ -v (currently 89 tests)
make lint       — ruff check (zero tolerance)
make typecheck  — mypy (zero errors)
make smoke      — import + init-db + sample-report
```

## Baseline (Sprint 4 / 2026-05-19)
- 89 tests pass
- 3 lint errors (line length)
- 15 mypy errors (type annotations)
- smoke: OK

## Current overhaul targets
- 0 lint errors (WP-B)
- 0 mypy errors (WP-B)
- 94+ tests (WP-C adds 5 new test files)

## Test Coverage Gaps (as of 2026-05-19)
| Area | Current | Gap |
|---|---|---|
| Caliber classes | test_caliber.py ✓ | None |
| Calibration | test_calibration.py ✓ | None |
| Detector | test_detector.py ✓ | None |
| Normalizer | test_normalizer.py ✓ | None |
| Preview | test_preview.py ✓ | None |
| Estimation | test_estimation.py ✓ | None |
| Reporting | test_reporting.py ✓ | Basic |
| Web/auth | test_web.py ✓ | Login only |
| Drive | test_drive.py ✓ | Mocked |
| Ingest | test_ingest.py ✓ | Basic |
| **Scan lifecycle** | MISSING | Add test_scan_file_lifecycle.py |
| **Deletebatch** | MISSING | Add test_deletebatch_privacy.py |
| **Report disclaimers** | MISSING | Add test_report_disclaimers.py |
| **Polish-only** | MISSING | Add test_report_polish_only.py |
| **Secret redaction** | MISSING | Add test_secret_redaction.py |
