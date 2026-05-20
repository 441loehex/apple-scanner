# Apple-Caliber-Scan Complete Overhaul — ULTRAPLAN

**Date:** 2026-05-19  
**Branch:** overhaul/universal-method-apple-caliber  
**Baseline commit:** 28cf389 (Sprint 4 committed)

---

## Source Inventory Findings

### Baseline state (confirmed before this plan)
| Gate | Status | Details |
|---|---|---|
| `make test` | **89 PASS** | All sprint4 tests passing |
| `make lint` | **3 ERRORS** | Line too long: loader.py:126, batches.py:62, batches.py:69 |
| `make typecheck` | **15 ERRORS** | fixtures.py(2), preview.py(1), loader.py(1), crud.py(4), bot.py(4), groundtruth.py(1), services/groundtruth.py(1) + bot.py type errors |
| `make smoke` | **OK** (expected) | Import + init-db + sample-report work |

### Architecture match vs CLAUDE.md
All 7 listed modules confirmed present. No gaps.

### Domain rules audit
- `@require_login` confirmed on all non-login routes ✓
- Scan deletion confirmed in `ingest.py` (finally block) ✓  
- Secrets: env-only, never logged ✓
- 75+, Polish, Freshora, SZACUNEK in templates ✓
- Legal clause in report_pl.html ✓
- Certification ban: docs/ACCURACY_METHODOLOGY.md says "not a calibrated measurement instrument" ✓

### MVP PDF
Confirmed at: `../apple-caliber-scan MVP.pdf` ✓

### Missing tests (vs playbook requirements)
- `tests/test_scan_file_lifecycle.py` — scan deletion proof
- `tests/test_deletebatch_privacy.py` — /deletebatch removes all batch data
- `tests/test_report_polish_only.py` — Polish-only wording in reports
- `tests/test_report_disclaimers.py` — SZACUNEK, top-layer, 75+, legal clause in PDF/HTML
- `tests/test_secret_redaction.py` — secrets never logged (log capture test)

### Missing docs
- `docs/TOOLING_COVERAGE_MATRIX.md`
- `docs/NON_REPO_TOOL_IMPLEMENTATION.md`
- `docs/RTK_VERIFICATION.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/OVERHAUL_BASELINE_AUDIT.md`
- `docs/BASELINE_TEST_RESULTS.md`
- `docs/EVIDENCE_LEDGER.md`
- `docs/ARCHITECTURE_GRAPH_SUMMARY.md`
- `docs/RELEASE_CHECKLIST.md`

### Missing scaffolding
- `AGENTS.md` root file
- `.claude/skills/*/SKILL.md` (6 skills)
- `brain/` memory notes (7 files)

---

## Implementation Plan — Phased Work Packages

### WP-0: ALREADY DONE
- [x] Sprint 4 committed to master
- [x] Overhaul branch created: `overhaul/universal-method-apple-caliber`
- [x] Baseline test run captured
- [x] Source inventory complete

### WP-A: Tooling and Memory Scaffolding (NO code changes)
**Deliverables:** AGENTS.md, 6 project skills, brain/ notes, RTK+graphify docs
**Gates:** `make lint`, `make typecheck` (no regressions from docs-only changes)
**Risk:** None (additive only)

Steps:
1. Write `AGENTS.md` with domain/security/review rules
2. Write all 6 `.claude/skills/*/SKILL.md` files
3. Write `brain/NorthStar.md`, `brain/Architecture/Graphify-Summary.md`, `brain/Domain/Apple-Caliber-Rules.md`, `brain/Security/Secrets-And-Privacy.md`, `brain/Testing/Test-Gates.md`, `brain/Decisions/000-index.md`, `brain/Sessions/2026-05-19-overhaul-start.md`
4. Write `docs/RTK_VERIFICATION.md`
5. Write `docs/ARCHITECTURE_GRAPH_SUMMARY.md` (from graphify-out)

### WP-B: Fix Gates (lint + typecheck)
**Deliverables:** 0 lint errors, 0 mypy errors  
**Gates:** `make lint` passes, `make typecheck` passes  
**Risk:** Low — targeted line fixes only

Fixes:
1. `loader.py:126` — wrap long string
2. `batches.py:62` — wrap notes string
3. `batches.py:69` — split dict literal
4. `fixtures.py:73-74` — fix type annotations (float → np.floating)
5. `preview.py:118` — fix ndarray type annotation
6. `loader.py:86` — fix trimesh Geometry attribute access
7. `crud.py:54,93,197,265` — add explicit `cast()` or return type annotations
8. `bot.py:61,78,322,324,325,339` — fix return types and Optional[int] handling
9. `groundtruth.py:70` — fix Optional return

### WP-C: Missing Safety-Critical Tests
**Deliverables:** 5 new test files, 100+ total tests  
**Gates:** `make test` passes (no regression + new tests green)  
**Risk:** Low — tests only, no source changes

Files to add:
1. `tests/test_scan_file_lifecycle.py` — proves raw scan deleted after ingest (both success and failure paths)
2. `tests/test_deletebatch_privacy.py` — proves /deletebatch removes DB records, previews, reports
3. `tests/test_report_disclaimers.py` — SZACUNEK, top-layer label, 75+ share, legal clause, no certification claim
4. `tests/test_report_polish_only.py` — no English strings in report output (key terms)
5. `tests/test_secret_redaction.py` — secrets don't appear in log output

### WP-D: 17-Fork Coverage Matrix (Research + Docs)
**Deliverables:** `docs/TOOLING_COVERAGE_MATRIX.md`, `docs/NON_REPO_TOOL_IMPLEMENTATION.md`  
**Risk:** None (docs only)

For each of the 17 forks, classify using known information and local install status:
- graphify: IMPLEMENTED (installed, graphify-out/ generated)
- rtk: IMPLEMENTED (verified in system)
- Other 15: documented as Analyzed/Optional/Excluded based on role and policy

### WP-E: Requirements Traceability
**Deliverables:** `docs/REQUIREMENTS_TRACEABILITY.md`  
**Risk:** None (docs only)

Map MVP PDF requirements → code modules → tests → gaps.

### WP-F: Documentation Closeout
**Deliverables:** `docs/BASELINE_TEST_RESULTS.md`, `docs/EVIDENCE_LEDGER.md`, `docs/RELEASE_CHECKLIST.md`, `README.md` update
**Risk:** None

### WP-G: Final Verification Harness
Run full gate and manually verify:
- `make test` — must pass
- `make lint` — must pass (0 errors)
- `make typecheck` — must pass (0 errors)
- `make smoke` — must pass
- `make sample-report` — must produce Polish report
- grep for banned terms (certification, machine sorter equivalence)
- grep for SZACUNEK, 75+, Freshora in report

---

## 17-Fork Decision Table (Summary)

| # | Repo | Decision | Reason |
|---|---|---|---|
| 1 | obsidian-mind | Compatible layout, manual brain/ | Install not feasible in WSL2 without Obsidian binary |
| 2 | claude-mem | Fallback only, not active | Conflicts with project memory system |
| 3 | andrej-karpathy-skills | Extract principles → SKILL.md | Reference implementation |
| 4 | awesome-agent-skills | Templates → skills | Copy reviewer/QA templates |
| 5 | cli | Excluded | Only gdown needed for Drive |
| 6 | notebooklm-py | Analyzed/Optional | Google login path not available |
| 7 | ruflo | Excluded | No parallel orchestration needed |
| 8 | llm_wiki | Reference only | Not a runtime dep |
| 9 | graphify | **IMPLEMENTED** | graphify-out/ exists |
| 10 | rtk | **IMPLEMENTED** | Verified in system |
| 11 | qmd | Analyze/optional | Index brain/ if install succeeds |
| 12 | obsidian-releases | Reference only | No runtime dep |
| 13 | obsidian-skills | Implement if compatible | Brain/ note skills |
| 14 | RAG-Anything | Excluded | No multimodal RAG needed |
| 15 | autoresearch | Excluded | Not relevant to business app |
| 16 | gstack | Templates → AGENTS.md | Role prompts extracted |
| 17 | llm-council | **EXCLUDED** | Requires paid API keys |

---

## Acceptance Criteria Check (post-plan)

- [x] Branch exists
- [x] Repo inspected before implementation
- [ ] TOOLING_COVERAGE_MATRIX.md (WP-D)
- [ ] NON_REPO_TOOL_IMPLEMENTATION.md (WP-D)
- [ ] Graphify exists (graphify-out/ ✓), ARCHITECTURE_GRAPH_SUMMARY.md (WP-A)
- [ ] RTK verification (WP-A)
- [ ] AGENTS.md (WP-A)
- [ ] Project skills (WP-A)
- [ ] brain/ notes (WP-A)
- [ ] Requirements traceability (WP-E)
- [ ] Domain invariant tests (existing ✓ + WP-C adds more)
- [ ] Security/privacy tests (WP-C)
- [ ] Report wording tests (WP-C)
- [ ] Web auth tests (existing test_web.py covers login ✓)
- [ ] Scan deletion tests (WP-C)
- [ ] make test passes (89 ✓ → 100+ after WP-C)
- [ ] make lint passes (WP-B)
- [ ] make typecheck 0 errors (WP-B)
- [ ] make smoke passes (✓)
- [ ] make sample-report reviewed (WP-G)
- [ ] No paid external APIs added ✓
- [ ] No secrets committed ✓
- [ ] Documentation updated (WP-F)
