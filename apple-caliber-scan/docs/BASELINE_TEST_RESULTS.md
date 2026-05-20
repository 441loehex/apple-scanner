# Baseline Test Results

**Date:** 2026-05-19  
**Branch:** overhaul/universal-method-apple-caliber  
**Commit:** 28cf389 (sprint4)

## Gate Results

| Command | Pass/Fail | Notes |
|---|---|---|
| `make test` | **89 PASS** | 1 deprecation warning (python_multipart) |
| `make lint` | **3 ERRORS** | Line too long: loader.py:126, batches.py:62, batches.py:69 |
| `make typecheck` | **15 ERRORS** | fixtures.py(2), preview.py(1), loader.py(1), crud.py(4), bot.py(5), groundtruth.py(1), services/groundtruth.py(1) |
| `make smoke` | OK (expected) | Not run at baseline (will run in WP-G) |
| `make sample-report` | OK (expected) | Not run at baseline |

## Lint Errors (must fix in WP-B)
1. `loader.py:126` — E501 line too long (101 > 100)
2. `batches.py:62` — E501 line too long (126 > 100)
3. `batches.py:69` — E501 line too long (101 > 100)

## Mypy Errors (must fix in WP-B)
1. `scan/fixtures.py:73` — Incompatible types (ndarray assigned to float)
2. `scan/fixtures.py:74` — Incompatible types (ndarray assigned to float)
3. `scan/preview.py:118` — Incompatible ndarray types
4. `scan/loader.py:86` — "Geometry" has no attribute "geometry"
5-8. `database/crud.py:54,93,197,265` — Returning Any from typed function
9-10. `telegram/bot.py:61,78` — Returning Any from typed dict/list
11-14. `telegram/bot.py:322,324,325,339` — Any|None passed as int arg
15. `services/groundtruth.py:70` — Returning Any from typed Optional

## Known Baseline Issues (classified)
- Lint: Fix before merge (zero tolerance)
- Mypy: Fix before merge (zero errors policy)
- python_multipart deprecation warning: upstream lib issue, not blocking

## Do-not-fix-yet
None.

## Must-fix blockers
- All 3 lint errors
- All 15 mypy errors
