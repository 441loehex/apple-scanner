# Evidence Ledger

**Date:** 2026-05-20  
**Branch:** overhaul/universal-method-apple-caliber

| Claim / Requirement | Evidence | Result | Confidence |
|---|---|---|---|
| Exact caliber bins preserved | `tests/test_caliber.py` (14 tests) + `make test` | ✅ PASS | HIGH |
| 75+ share computed and shown | `tests/test_estimation.py`, `tests/test_report_disclaimers.py: test_75_plus_share_present` | ✅ PASS | HIGH |
| Raw scan deleted after ingest | `tests/test_scan_file_lifecycle.py` (4 tests) | ✅ PASS | HIGH |
| /deletebatch removes batch data | `tests/test_deletebatch_privacy.py` (5 tests) | ✅ PASS | HIGH |
| Reports are Polish-only (no English headings) | `tests/test_report_polish_only.py` (3 tests) | ✅ PASS | HIGH |
| Required Polish terms present | `tests/test_report_polish_only.py: test_required_polish_terms_present` | ✅ PASS | HIGH |
| No certification claims | `tests/test_report_disclaimers.py: test_no_certification_claim` | ✅ PASS | HIGH |
| SZACUNEK label present | `tests/test_report_disclaimers.py: test_szacunek_label_present_for_projection` | ✅ PASS | HIGH |
| Legal disclaimer clause | `tests/test_reporting.py: test_legal_clause_in_html`, `tests/test_report_disclaimers.py` | ✅ PASS | HIGH |
| Auth protects non-login routes | `tests/test_web.py`, `tests/test_deletebatch_privacy.py: test_deletebatch_requires_auth` | ✅ PASS | HIGH |
| Secrets are env-only and not logged | `tests/test_secret_redaction.py` (5 tests) | ✅ PASS | HIGH |
| 17 forks analyzed | `docs/TOOLING_COVERAGE_MATRIX.md` | ✅ Done | HIGH |
| Non-repo tools implemented/analyzed | `docs/NON_REPO_TOOL_IMPLEMENTATION.md` | ✅ Done | HIGH |
| Lint: 0 errors | `make lint` → `All checks passed!` | ✅ PASS | HIGH |
| Mypy: 0 errors | `make typecheck` → `Success: no issues found` | ✅ PASS | HIGH |
| Full test suite | `make test` → `115 passed, 1 warning` | ✅ PASS | HIGH |
| make smoke | Pending WP-G | TBD | — |
| make sample-report | Pending WP-G | TBD | — |
