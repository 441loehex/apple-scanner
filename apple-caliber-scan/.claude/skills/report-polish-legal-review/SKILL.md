---
name: report-polish-legal-review
description: Checks Polish report output for legal/domain wording, Freshora branding, caliber bins, 75+ share, estimate labels, and banned claims.
---

Check every report template and generated output for:

1. Polish-only wording (no English sentences in report body).
2. Freshora Sp. Z. o. o. branding present in header/footer.
3. 75+ share (Udział jabłek ≥ 75mm) prominently displayed as a KPI badge.
4. Top-layer distribution clearly labeled: "warstwa widoczna" or "wynik pomiaru warstwy górnej".
5. Whole-batch estimate marked: SZACUNEK, niska pewność / LOW confidence.
6. Legal disclaimer present: KLAUZULA OGRANICZENIA or equivalent Polish legal notice.
7. No certification claim: no "certyfikat", "certyfikacja", "kalibrowany instrument".
8. No machine-sorter equivalence: no "AWETA", "sortownik mechaniczny", "pełny pomiar partii".
9. No fake accuracy claim: no "dokładność X%", "precyzja", "gwarancja kalibracji".
10. All 8 caliber classes present in distribution table (even if 0 count).
