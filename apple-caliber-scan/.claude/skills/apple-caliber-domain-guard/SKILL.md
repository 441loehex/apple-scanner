---
name: apple-caliber-domain-guard
description: Enforces apple-caliber-scan domain rules before any code, report, UI, or data model change.
---

Before approving any change, verify:

1. Caliber classes are exactly: 0-60, 60-65, 65-70, 70-75, 75-80, 80-85, 85-90, 90+. No other classes.
2. 75+ share is computed and prominent in every report.
3. Top-layer distribution is labeled as the measured result (widoczna warstwa / top layer).
4. Whole-batch projection is labeled SZACUNEK and LOW confidence until grader GT is imported.
5. No certification claim appears anywhere (no "certyfikat", "certyfikacja", "kalibrowane").
6. No machine-sorter equivalence claim (no "AWETA", "sortownik", "pełny pomiar").
7. Reports are Polish-only. Freshora Sp. Z. o. o. branding present.
8. Raw scan files are deleted after ingest. Only preview PNG + derived data remain.
9. Any code comment or UI text implying fake precision must be rejected.
10. `above_75_share()` function is called and its result displayed in every report context.
