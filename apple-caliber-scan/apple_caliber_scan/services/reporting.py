"""Polish HTML + PDF report generation using Jinja2 and WeasyPrint."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from apple_caliber_scan.services.estimation import (
    CALIBER_CLASS_LABELS,
    CaliberDistribution,
    ClassEstimate,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "web" / "templates"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


LEGAL_CLAUSE = """KLAUZULA OGRANICZENIA ODPOWIEDZIALNOŚCI

Niniejszy raport ma charakter wyłącznie analityczny i szacunkowy. Wyniki opierają się
na analizie widocznej górnej warstwy skrzyni jabłek przy użyciu skanowania LiDAR i nie
stanowią pomiaru certyfikowanego, klasyfikacji mechanicznej ani gwarancji jakości,
ceny, sprzedaży lub zgodności z obowiązującymi normami jakościowymi.

Rozkład kalibrażu całej partii jest szacunkiem statystycznym o niskiej pewności i może
odbiegać od wyników sortownicy mechanicznej (np. AWETA). Pewność projekcji wzrośnie
dopiero po zgromadzeniu sparowanych danych pomiarowych z sortownicy dla tej samej
partii.

Niniejszy raport może być stosowany wyłącznie jako materiał pomocniczy w negocjacjach
handlowych. Freshora Sp. Z. o. o. nie ponosi odpowiedzialności za decyzje handlowe
podjęte wyłącznie na podstawie niniejszego raportu."""


def build_report_context(
    batch: dict[str, Any],
    scan: dict[str, Any] | None,
    distribution: CaliberDistribution,
    class_estimates: list[ClassEstimate],
    calibration_confidence: str,
    calibration_warning: str | None,
    scale_factor: float | None,
    has_ground_truth: bool,
    ground_truth_rows: list[dict[str, Any]] | None = None,
    sideways_count: int = 0,
    orientation_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    above_75 = distribution.above_75_share
    if above_75 >= 60:
        badge_class = "badge-green"
    elif above_75 >= 40:
        badge_class = "badge-yellow"
    else:
        badge_class = "badge-red"

    projection_ok = calibration_confidence == "ok"
    batch_confidence = ConfidenceLevel.LOW if not has_ground_truth else ConfidenceLevel.HIGH
    if not projection_ok:
        batch_confidence = ConfidenceLevel.UNCALIBRATED

    return {
        "company_name": "Freshora Sp. Z. o. o.",
        "report_title": "HANDLOWY RAPORT ANALITYCZNY (DO SPRZEDAŻY)",
        "batch": batch,
        "scan": scan,
        "distribution": distribution,
        "class_estimates": class_estimates,
        "caliber_class_labels": CALIBER_CLASS_LABELS,
        "calibration_confidence": calibration_confidence,
        "calibration_warning": calibration_warning,
        "scale_factor": scale_factor,
        "above_75_share": round(above_75, 1),
        "badge_class": badge_class,
        "projection_ok": projection_ok,
        "batch_confidence": batch_confidence,
        "has_ground_truth": has_ground_truth,
        "ground_truth_rows": ground_truth_rows or [],
        "generated_at": generated_at,
        "legal_clause": LEGAL_CLAUSE,
        "sideways_count": sideways_count,
        "orientation_counts": orientation_counts,
    }


def render_html_report(context: dict[str, Any]) -> str:
    env = _jinja_env()
    tpl = env.get_template("report_pl.html")
    return tpl.render(**context)


def generate_html_report(
    context: dict[str, Any],
    output_path: Path,
) -> Path:
    html = render_html_report(context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML report saved: %s", output_path)
    return output_path


def generate_pdf_report(
    html_path: Path,
    pdf_path: Path,
) -> Path | None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from weasyprint import HTML

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        logger.info("PDF report saved: %s", pdf_path)
        return pdf_path
    except ImportError:
        logger.warning("weasyprint not available — trying fpdf2 fallback")
        return _generate_pdf_fpdf2(html_path, pdf_path)
    except Exception as e:
        logger.error("WeasyPrint PDF generation failed: %s — trying fpdf2 fallback", e)
        return _generate_pdf_fpdf2(html_path, pdf_path)


def _generate_pdf_fpdf2(html_path: Path, pdf_path: Path) -> Path | None:
    """Minimal PDF fallback using fpdf2 when WeasyPrint is unavailable."""
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_fill_color(26, 92, 46)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 12, "Freshora Sp. Z. o. o.", fill=True, ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "HANDLOWY RAPORT ANALITYCZNY (DO SPRZEDAZY)", ln=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.ln(4)
        pdf.multi_cell(0, 5, html_path.read_text(encoding="utf-8")[:2000])
        pdf.output(str(pdf_path))
        logger.info("PDF (fpdf2 fallback) saved: %s", pdf_path)
        return pdf_path
    except Exception as e:
        logger.error("fpdf2 PDF fallback also failed: %s", e)
        return None


def generate_json_report(context: dict[str, Any], output_path: Path) -> Path:
    """Generate machine-readable JSON report."""
    payload = {
        "company": context["company_name"],
        "report_title": context["report_title"],
        "generated_at": context["generated_at"],
        "batch": context["batch"],
        "calibration": {
            "ring_mm": context["scan"].get("calibration_ring_mm") if context.get("scan") else None,
            "scale_factor_mm_per_px": context["scale_factor"],
            "confidence": context["calibration_confidence"],
            "warning": context["calibration_warning"],
        },
        "top_layer_distribution": {
            label: {
                "count": context["distribution"].counts.get(label, 0),
                "pct": round(context["distribution"].pct(label), 2),
            }
            for label in CALIBER_CLASS_LABELS
        },
        "above_75_share_pct": context["above_75_share"],
        "total_visible_apples": context["distribution"].total,
        "batch_projection": [
            {
                "label": e.label,
                "count": e.count,
                "pct": e.pct,
                "weight_kg": e.weight_kg,
                "weight_pct": e.weight_pct,
            }
            for e in context["class_estimates"]
        ],
        "batch_projection_confidence": str(context["batch_confidence"].value),
        "has_ground_truth": context["has_ground_truth"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
