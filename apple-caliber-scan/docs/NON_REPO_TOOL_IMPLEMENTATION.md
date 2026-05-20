# Non-Repo Tool Implementation Matrix

**Date:** 2026-05-20  
**Branch:** overhaul/universal-method-apple-caliber

| Tool | Implementation Status | Evidence |
|---|---|---|
| **Claude Code** | ✅ Active | Primary implementer. All work in this overhaul session. |
| **/ultraplan** | ✅ Done | `docs/ULTRAPLAN.md` created. Plan accepted before implementation began. |
| **/ultrareview** | Skipped | User-triggered, billed tool. Not required under current policy. Claude /review equivalent used instead (manual inspection). |
| **Claude Skills (project-local)** | ✅ Implemented | 6 skills in `.claude/skills/`: domain-guard, diagnose-before-ship, adversarial-plan-review, report-polish-legal-review, privacy-and-secret-audit, update-memory-bible |
| **Claude Skill Creator** | N/A | Skills hand-written as SKILL.md files (free path). |
| **Claude subagents** | Analyzed | No subagent spawned — overhaul was sequential and single-session. Plan used Codex review as adversarial layer instead. |
| **Claude hooks** | Existing | RTK hook already configured globally. No new hooks added. |
| **Codex CLI** | Referenced | Codex review prompt included in `AGENTS.md`. `@codex review` pattern documented for future PRs. |
| **Codex GitHub review** | Planned | Available via `@codex review` on PR. No PR open yet (local branch only). |
| **AGENTS.md** | ✅ Done | Root `AGENTS.md` with domain, security, stack, review priority, gate rules. |
| **ChatGPT Plus / Deep Research** | Not used | No external research needed for this overhaul. |
| **GitHub PRs** | Pending | Branch `overhaul/universal-method-apple-caliber` ready. PR not opened (no remote). |
| **make test** | ✅ 115 PASS | All tests pass after WP-C additions. |
| **make lint** | ✅ 0 errors | All lint errors fixed in WP-B. |
| **make typecheck** | ✅ 0 errors | All mypy errors fixed in WP-B. |
| **make smoke** | Pending WP-G | Will run in final verification phase. |
| **make sample-report** | Pending WP-G | Will run and manually review in final verification phase. |
| **Live logs/data** | Used | Baseline test output captured. Mypy errors used exact log output for fixes. |
