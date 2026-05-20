---
name: adversarial-plan-review
description: Reviews a plan adversarially for missing requirements, hidden paid APIs, weak tests, domain violations, and unsafe refactors.
---

Critique the plan against:

1. CLAUDE.md rules (domain, security, privacy, code style).
2. Apple caliber domain rules (caliber classes, 75+, SZACUNEK, top-layer, no certification).
3. Security/privacy rules (secrets, scan deletion, auth, deletebatch).
4. No-paid-API policy (every import/dep must be in pyproject.toml).
5. Test/lint/type/smoke gates must all pass.
6. 17-fork coverage requirement documented.
7. Rollback/feature branch exists before implementation.
8. Documentation and memory updates planned.
9. Any overbroad refactor risk (test must precede refactor).
10. Any missing diagnose-before-patch step.

Return: BLOCKERS (must fix before proceed), HIGH RISK (fix or document), OPTIONAL (nice to have).
Do not praise. Be adversarial and concrete.
