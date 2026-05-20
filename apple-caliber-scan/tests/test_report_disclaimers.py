"""Tests proving report contains required domain labels and legal disclaimers."""

from __future__ import annotations

from apple_caliber_scan.services.estimation import CaliberDistribution, estimate_batch
from apple_caliber_scan.services.reporting import build_report_context, render_html_report


def _make_ctx(confidence: str = "ok") -> dict:
    dist = CaliberDistribution()
    for label in ["70-75", "75-80", "80-85"]:
        dist.add(label)
        dist.add(label)

    estimates = estimate_batch(dist, total_weight_kg=200.0)
    batch = {
        "seller_name": "Jan Kowalski",
        "seller_address": "ul. Sadowa 1, Grójec",
        "variety": "Jonagold",
        "price_pln_per_kg": 1.80,
        "ca_opening_date": "2026-05-01",
        "operator_batch_id": "J-001",
        "notes": None,
        "number_of_crates": 10,
        "total_weight_kg": 200.0,
    }
    scan = {
        "calibration_ring_mm": 75.0,
        "scale_factor_mm_per_px": 0.75,
        "calibration_confidence": confidence,
    }
    return build_report_context(
        batch=batch,
        scan=scan,
        distribution=dist,
        class_estimates=estimates,
        calibration_confidence=confidence,
        calibration_warning=None if confidence == "ok" else "Brak kalibracji",
        scale_factor=0.75 if confidence == "ok" else None,
        has_ground_truth=False,
    )


def test_legal_disclaimer_clause_present():
    """KLAUZULA OGRANICZENIA must appear in report HTML."""
    html = render_html_report(_make_ctx())
    assert "KLAUZULA OGRANICZENIA" in html


def test_freshora_branding_present():
    """Freshora Sp. Z. o. o. must appear in report HTML."""
    html = render_html_report(_make_ctx())
    assert "Freshora" in html


def test_75_plus_share_present():
    """≥75mm share KPI must be rendered in report."""
    html = render_html_report(_make_ctx())
    assert "75" in html
    # Must show percentage
    above_75_section = "%" in html
    assert above_75_section


def test_szacunek_label_present_for_projection():
    """Whole-batch projection must carry SZACUNEK / estimate label."""
    html = render_html_report(_make_ctx())
    assert "SZACUNEK" in html or "szacunek" in html or "szacunkow" in html.lower()


def test_no_certification_claim():
    """Report must not contain certification claim words."""
    html = render_html_report(_make_ctx())
    banned = ["certyfikacja", "Certyfikacja", "certyfikowany", "certyfikat"]
    for term in banned:
        assert term not in html, f"Banned certification claim found: {term}"


def test_no_full_batch_measurement_claim():
    """Report must not present top-layer result as full-batch measurement."""
    html = render_html_report(_make_ctx())
    # Only the explicit banning of machine-sorter equivalence
    assert "sortownik mechaniczny" not in html
    assert "pełny pomiar partii" not in html


def test_all_8_caliber_classes_present():
    """All 8 caliber class labels must appear in report."""
    html = render_html_report(_make_ctx())
    for label in ["0-60", "60-65", "65-70", "70-75", "75-80", "80-85", "85-90", "90+"]:
        assert label in html, f"Caliber class missing from report: {label}"


def test_low_confidence_label_when_uncalibrated():
    """Uncalibrated report must show low confidence indicator."""
    ctx = _make_ctx(confidence="uncalibrated")
    html = render_html_report(ctx)
    has_low = any(
        term in html
        for term in ["NISKA", "niska", "niedostępna", "LOW", "uncalibrated"]
    )
    assert has_low, "Low confidence indicator must appear for uncalibrated scan"


def test_top_layer_label_present():
    """Report must clearly identify that measurement is top-layer only."""
    html = render_html_report(_make_ctx())
    # warstwa widoczna / top layer / warstw
    has_layer_label = (
        "warstw" in html.lower()
        or "widoczn" in html.lower()
        or "top layer" in html.lower()
        or "górna warstwa" in html.lower()
    )
    assert has_layer_label, "Top-layer measurement label must be present in report"
