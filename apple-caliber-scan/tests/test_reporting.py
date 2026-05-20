"""Report total consistency and legal clause presence tests."""

from apple_caliber_scan.services.estimation import CaliberDistribution, estimate_batch
from apple_caliber_scan.services.reporting import build_report_context, render_html_report


def make_sample_context(above_75_pct=50.0):
    dist = CaliberDistribution()
    # 4 apples: 2 below, 2 above 75mm
    for label in ["65-70", "70-75", "75-80", "80-85"]:
        dist.add(label)

    estimates = estimate_batch(dist, total_weight_kg=300.0)
    batch = {
        "seller_name": "Test Seller",
        "seller_address": "Test Address",
        "variety": "Jonagold",
        "price_pln_per_kg": 1.80,
        "ca_opening_date": "2026-04-01",
        "operator_batch_id": "TEST-001",
        "notes": None,
        "number_of_crates": 1,
        "total_weight_kg": 300.0,
    }
    scan = {
        "calibration_ring_mm": 75.0,
        "scale_factor_mm_per_px": 0.75,
        "calibration_confidence": "ok",
    }
    return build_report_context(
        batch=batch,
        scan=scan,
        distribution=dist,
        class_estimates=estimates,
        calibration_confidence="ok",
        calibration_warning=None,
        scale_factor=0.75,
        has_ground_truth=False,
    )


def test_report_class_count_sum():
    ctx = make_sample_context()
    estimates = ctx["class_estimates"]
    total = sum(e.count for e in estimates)
    assert total == ctx["distribution"].total


def test_report_pct_sums_to_100():
    ctx = make_sample_context()
    estimates = ctx["class_estimates"]
    nonzero = [e for e in estimates if e.count > 0]
    total_pct = sum(e.pct for e in nonzero)
    # Each class pct = count/total*100, sum should be ~100
    assert abs(total_pct - 100.0) < 0.1


def test_legal_clause_in_html():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    assert "KLAUZULA OGRANICZENIA ODPOWIEDZIALNOŚCI" in html


def test_company_name_in_html():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    assert "Freshora Sp. Z. o. o." in html


def test_report_title_in_html():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    assert "HANDLOWY RAPORT ANALITYCZNY" in html


def test_above_75_share_displayed():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    assert "≥ 75 mm" in html or "75 mm" in html


def test_8_caliber_classes_in_report():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    for label in ["0-60", "60-65", "65-70", "70-75", "75-80", "80-85", "85-90", "90+"]:
        assert label in html


def test_low_confidence_projection_warning():
    ctx = make_sample_context()
    dist = CaliberDistribution()
    dist.add("75-80")
    ctx_low = build_report_context(
        batch=ctx["batch"],
        scan={
            "calibration_ring_mm": 75.0,
            "scale_factor_mm_per_px": None,
            "calibration_confidence": "uncalibrated",
        },
        distribution=dist,
        class_estimates=estimate_batch(dist, 300.0),
        calibration_confidence="uncalibrated",
        calibration_warning="Brak kalibracji",
        scale_factor=None,
        has_ground_truth=False,
    )
    html = render_html_report(ctx_low)
    assert "niedostępna" in html or "NISKA" in html or "niska" in html


def test_seller_name_in_report():
    ctx = make_sample_context()
    html = render_html_report(ctx)
    assert "Test Seller" in html
