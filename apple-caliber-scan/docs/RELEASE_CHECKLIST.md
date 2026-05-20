# Release Checklist

**Branch:** overhaul/universal-method-apple-caliber  
**Date:** 2026-05-20

## Pre-merge Gates

- [x] Dedicated branch used: `overhaul/universal-method-apple-caliber`
- [x] `/ultraplan` accepted (docs/ULTRAPLAN.md)
- [x] 17-fork coverage matrix complete (docs/TOOLING_COVERAGE_MATRIX.md)
- [x] Non-repo tool implementation matrix complete (docs/NON_REPO_TOOL_IMPLEMENTATION.md)
- [x] Graphify output exists (graphify-out/) + summary (docs/ARCHITECTURE_GRAPH_SUMMARY.md)
- [x] RTK verification complete (docs/RTK_VERIFICATION.md)
- [x] AGENTS.md present with domain/security review rules
- [x] Project-local Claude skills present (.claude/skills/ — 6 skills)
- [x] Requirements traceability complete (docs/REQUIREMENTS_TRACEABILITY.md)
- [x] Baseline test results documented (docs/BASELINE_TEST_RESULTS.md)
- [x] make test passes — 115 tests
- [x] make lint passes — 0 errors
- [x] make typecheck passes — 0 errors
- [ ] make smoke passes (run in WP-G)
- [ ] make sample-report generated and manually reviewed (WP-G)
- [x] No paid external API added
- [x] No secrets committed
- [x] Raw scan deletion tested (test_scan_file_lifecycle.py)
- [x] /deletebatch tested (test_deletebatch_privacy.py)
- [x] Report Polish/legal wording verified (test_report_disclaimers.py, test_report_polish_only.py)
- [x] Secret redaction tested (test_secret_redaction.py)
- [x] Evidence ledger complete (docs/EVIDENCE_LEDGER.md)
- [x] Memory and brain/ notes updated

## Post-merge (future)
- [ ] Telegram bot mocked tests
- [ ] qmd installed for brain/ search
- [ ] GitHub remote + PR opened for Codex review
