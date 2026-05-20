"""Report generation and serving routes."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from apple_caliber_scan import config
from apple_caliber_scan.database.connection import db_conn
from apple_caliber_scan.database.crud import (
    create_report,
    get_batch,
    get_circles_for_scan,
    get_report,
    get_scan,
    has_ground_truth,
)
from apple_caliber_scan.services.estimation import (
    CaliberDistribution,
    classify_diameter,
    estimate_batch,
)
from apple_caliber_scan.services.groundtruth import (
    compare_with_ground_truth,
    get_latest_ground_truth,
)
from apple_caliber_scan.services.reporting import (
    build_report_context,
    generate_html_report,
    generate_json_report,
    generate_pdf_report,
)
from apple_caliber_scan.web.auth import require_login

router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.post("/batches/{batch_id}/scans/{scan_id}/report")
@require_login
async def generate_report(request: Request, batch_id: int, scan_id: int):
    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
        scan = get_scan(conn, scan_id)
        if not batch or not scan:
            return HTMLResponse("Nie znaleziono.", status_code=404)

        circles = get_circles_for_scan(conn, scan_id)
        has_gt = has_ground_truth(conn, batch_id)
        gt_data = get_latest_ground_truth(conn, batch_id)

    apple_circles = [c for c in circles if not c["is_ring"] and not c["is_excluded"]]

    distribution = CaliberDistribution()
    sideways_count = 0
    orientation_counts: dict[str, int] = {
        o: 0 for o in ("upright", "sideways", "angled", "unknown")
    }
    for c in apple_circles:
        major = c["ellipse_major_px"] or 0.0
        minor = c["ellipse_minor_px"] or 0.0
        if major > 0 and minor > 0 and (major / minor) > 1.25:
            sideways_count += 1
        orient = c["orientation"] if "orientation" in c.keys() else "unknown"
        orientation_counts[orient or "unknown"] = orientation_counts.get(orient or "unknown", 0) + 1
        if c["caliber_class"]:
            distribution.add(c["caliber_class"])
        elif c["diameter_mm"]:
            distribution.add(classify_diameter(c["diameter_mm"]))

    estimates = estimate_batch(distribution, total_weight_kg=batch["total_weight_kg"])

    gt_rows = None
    if gt_data:
        scan_dist_counts = dict(distribution.counts)
        gt_rows = compare_with_ground_truth(scan_dist_counts, gt_data)

    context = build_report_context(
        batch=dict(batch),
        scan=dict(scan),
        distribution=distribution,
        class_estimates=estimates,
        calibration_confidence=scan["calibration_confidence"] or "uncalibrated",
        calibration_warning=scan["calibration_warning"],
        scale_factor=scan["scale_factor_mm_per_px"],
        has_ground_truth=has_gt,
        ground_truth_rows=gt_rows,
        sideways_count=sideways_count,
        orientation_counts=orientation_counts,
    )

    reports_dir = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    with db_conn() as conn:
        report_id = create_report(conn, batch_id, scan_id)

    html_path = reports_dir / f"report_{report_id}.html"
    pdf_path = reports_dir / f"report_{report_id}.pdf"
    json_path = reports_dir / f"report_{report_id}.json"

    generate_html_report(context, html_path)
    generate_pdf_report(html_path, pdf_path)
    generate_json_report(context, json_path)

    with db_conn() as conn:

        conn.execute(
            "UPDATE reports SET html_path=?, pdf_path=?, json_path=? WHERE id=?",
            (str(html_path), str(pdf_path), str(json_path), report_id),
        )

    return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)


@router.get("/reports/{report_id}.html", response_class=HTMLResponse)
@require_login
async def serve_report_html(request: Request, report_id: int):
    with db_conn() as conn:
        report = get_report(conn, report_id)
    if not report or not report["html_path"]:
        return HTMLResponse("Raport nie znaleziony.", status_code=404)
    path = Path(report["html_path"])
    if not path.exists():
        return HTMLResponse("Plik raportu nie istnieje.", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/reports/{report_id}.pdf")
@require_login
async def serve_report_pdf(request: Request, report_id: int):
    with db_conn() as conn:
        report = get_report(conn, report_id)
    if not report or not report["pdf_path"]:
        return HTMLResponse("Raport PDF nie znaleziony.", status_code=404)
    path = Path(report["pdf_path"])
    if not path.exists():
        return HTMLResponse("Plik PDF nie istnieje.", status_code=404)
    return FileResponse(str(path), media_type="application/pdf")
