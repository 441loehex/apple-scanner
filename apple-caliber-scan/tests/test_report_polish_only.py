"""Tests confirming report content is Polish and no English headings slip in."""

from __future__ import annotations

from apple_caliber_scan.services.estimation import CaliberDistribution, estimate_batch
from apple_caliber_scan.services.reporting import build_report_context, render_html_report

_BANNED_ENGLISH = [
    "Analytical Report",
    "Caliber Distribution",
    "Batch Projection",
    "Seller Information",
    "Ground Truth",
    "High Confidence",
    "Low Confidence",
    "Disclaimer",
    "Certificate",
    "Measurement Result",
]

_REQUIRED_POLISH = [
    "RAPORT",
    "kalibraż",
    "Freshora",
    "jabłek",
]


def _make_ctx() -> dict:
    dist = CaliberDistribution()
    for label in ["75-80", "80-85"]:
        dist.add(label)
    estimates = estimate_batch(dist, total_weight_kg=100.0)
    batch = {
        "seller_name": "Testowy",
        "seller_address": "ul. Testowa 1",
        "variety": "Jonagold",
        "price_pln_per_kg": 2.0,
        "ca_opening_date": "2026-05-01",
        "operator_batch_id": "PL-001",
        "notes": None,
        "number_of_crates": 5,
        "total_weight_kg": 100.0,
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


def test_no_banned_english_headings():
    """None of the English-only heading strings should appear in the Polish report."""
    html = render_html_report(_make_ctx())
    for phrase in _BANNED_ENGLISH:
        assert phrase not in html, (
            f"English phrase found in Polish report: '{phrase}'"
        )


def test_required_polish_terms_present():
    """Required Polish terms must appear in report (case-insensitive)."""
    html = render_html_report(_make_ctx())
    html_lower = html.lower()
    for term in _REQUIRED_POLISH:
        assert term.lower() in html_lower, f"Required Polish term missing: '{term}'"


def test_freshora_company_name_is_polish_legal_form():
    """Company name must include the Polish legal suffix 'Sp. Z. o. o.' or 'Sp.z o.o.'."""
    html = render_html_report(_make_ctx())
    has_legal = "Sp. Z. o. o." in html or "Sp.z o.o." in html or "sp. z o.o." in html.lower()
    assert has_legal, "Freshora Polish legal form must appear in report"
