"""75+ share, confidence guardrail, weight estimation tests."""

from apple_caliber_scan.services.estimation import (
    CaliberDistribution,
    ConfidenceLevel,
    batch_projection_confidence,
    compute_distribution,
    estimate_batch,
)


def test_75_plus_share_correct():
    dist = CaliberDistribution()
    for label in ["70-75", "70-75", "75-80", "75-80", "80-85"]:
        dist.add(label)
    # 3 apples ≥75mm out of 5 → 60%
    assert abs(dist.above_75_share - 60.0) < 0.01


def test_75_plus_share_zero():
    dist = CaliberDistribution()
    for label in ["0-60", "60-65", "65-70", "70-75"]:
        dist.add(label)
    assert dist.above_75_share == 0.0


def test_75_plus_share_all():
    dist = CaliberDistribution()
    for label in ["75-80", "80-85", "85-90", "90+"]:
        dist.add(label)
    assert dist.above_75_share == 100.0


def test_batch_confidence_low_without_gt():
    conf = batch_projection_confidence(has_ground_truth=False, calibration_ok=True)
    assert conf == ConfidenceLevel.LOW


def test_batch_confidence_high_with_gt():
    conf = batch_projection_confidence(has_ground_truth=True, calibration_ok=True)
    assert conf == ConfidenceLevel.HIGH


def test_batch_confidence_uncalibrated():
    conf = batch_projection_confidence(has_ground_truth=True, calibration_ok=False)
    assert conf == ConfidenceLevel.UNCALIBRATED


def test_no_high_confidence_without_ground_truth():
    # System must never return HIGH confidence without grader ground truth
    for gt in [False]:
        conf = batch_projection_confidence(has_ground_truth=gt, calibration_ok=True)
        assert conf != ConfidenceLevel.HIGH


def test_estimate_batch_totals():
    dist = CaliberDistribution()
    for label in ["75-80", "75-80", "80-85", "90+"]:
        dist.add(label)

    estimates = estimate_batch(dist, total_weight_kg=300.0)

    total_weight = sum(e.weight_kg for e in estimates)
    total_weight_pct = sum(e.weight_pct for e in estimates)
    total_count = sum(e.count for e in estimates)

    assert total_count == 4
    assert abs(total_weight - 300.0) < 1.0  # within 1kg due to rounding
    assert abs(total_weight_pct - 100.0) < 1.0


def test_estimate_batch_8_classes():
    dist = CaliberDistribution()
    dist.add("75-80")
    estimates = estimate_batch(dist, total_weight_kg=300.0)
    assert len(estimates) == 8


def test_compute_distribution():
    diameters = [55.0, 62.0, 67.0, 72.0, 77.0, 82.0, 87.0, 92.0]
    dist = compute_distribution(diameters)
    assert dist.total == 8
    assert dist.counts["0-60"] == 1
    assert dist.counts["60-65"] == 1
    assert dist.counts["90+"] == 1
    assert dist.above_75_share == 50.0
