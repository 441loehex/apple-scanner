# Domain Rules — Apple Caliber Classification

## Caliber Classes (exact, immutable)
| Class | Range (mm) | Note |
|---|---|---|
| 0-60 | [0, 60) | Below trade minimum |
| 60-65 | [60, 65) | |
| 65-70 | [65, 70) | |
| 70-75 | [70, 75) | |
| 75-80 | [75, 80) | ← 75+ boundary |
| 80-85 | [80, 85) | |
| 85-90 | [85, 90) | |
| 90+ | [90, ∞) | |

**Lower bound inclusive, upper bound exclusive.**

## 75+ Share
- `above_75_share(dist: CaliberDistribution) -> float`
- Sum of counts for 75-80, 80-85, 85-90, 90+ divided by total.
- Must be the primary KPI in every report.
- Polish label: "Udział jabłek ≥ 75mm"

## Measurement Layers
- **Measured result**: top-layer only (visible apples in LiDAR scan)
- **Whole-batch projection**: SZACUNEK, LOW confidence, always labeled as estimate
- These MUST be separated in DB schema, UI, and reports

## Confidence Model
| Condition | Confidence |
|---|---|
| No grader ground truth | LOW / UNCALIBRATED |
| Grader GT imported | HIGH (after calibration) |

## Banned Claims
- "certyfikat" / "certification" — NEVER in reports/UI
- "sortownik mechaniczny" / "machine sorter" — NEVER in reports/UI
- "pełny pomiar partii" / "full-batch measurement" — NEVER applied to scan result
- Fake accuracy percentages (e.g. "dokładność 95%")

## Polish Report Requirements
- Language: Polish only in report body
- Brand: Freshora Sp. Z. o. o.
- Legal clause: KLAUZULA OGRANICZENIA (not a certified instrument)
- All 8 caliber classes shown even if count = 0
