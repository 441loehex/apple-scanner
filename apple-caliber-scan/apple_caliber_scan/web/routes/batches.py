"""Batch list, create, detail, and delete routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from apple_caliber_scan import config
from apple_caliber_scan.database.connection import db_conn
from apple_caliber_scan.database.crud import (
    create_batch,
    delete_batch,
    get_batch,
    list_batches,
    list_reports_for_batch,
    list_scans_for_batch,
    list_varieties,
    upsert_variety,
)
from apple_caliber_scan.web.auth import require_login

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
@require_login
async def batch_list(request: Request):
    with db_conn() as conn:
        batches = list_batches(conn)
    return templates.TemplateResponse(request, "batch_list.html", {"batches": batches})


@router.get("/batches/new", response_class=HTMLResponse)
@require_login
async def batch_new_form(request: Request):
    with db_conn() as conn:
        varieties = [row["name"] for row in list_varieties(conn)]
    return templates.TemplateResponse(
        request,
        "batch_new.html",
        {"varieties": varieties, "default_weight": config.DEFAULT_CRATE_WEIGHT_KG, "preset": {}},
    )


@router.get("/batches/new-field-test", response_class=HTMLResponse)
@require_login
async def batch_new_field_test(request: Request):
    """Pre-filled form for a 30-apple Polycam ground scan with 75mm calibration ring."""
    with db_conn() as conn:
        varieties = [row["name"] for row in list_varieties(conn)]
        upsert_variety(conn, "TEST - Polycam")
    date_tag = datetime.now().strftime("%Y%m%d")
    preset = {
        "seller_name": "Test Terenowy",
        "variety": "TEST - Polycam",
        "operator_batch_id": f"POLYCAM-TEST-{date_tag}",
        "notes": (
            "30 jabłek rozsypanych na ziemi / 1 niebieski pierścień kalibracyjny 75mm"
            " / skan 3D Polycam / iPhone 17 Pro"
        ),
        "number_of_crates": 1,
        "total_weight_kg": 0.0,
    }
    return templates.TemplateResponse(
        request,
        "batch_new.html",
        {
            "varieties": varieties,
            "default_weight": config.DEFAULT_CRATE_WEIGHT_KG,
            "preset": preset,
        },
    )


@router.post("/batches", response_class=HTMLResponse)
@require_login
async def batch_create(request: Request):
    form = await request.form()
    seller_name = str(form.get("seller_name", "")).strip()
    variety = str(form.get("variety", "")).strip()
    seller_address = str(form.get("seller_address", "")).strip() or None
    price_str = str(form.get("price_pln_per_kg", "")).strip()
    ca_date = str(form.get("ca_opening_date", "")).strip() or None
    op_batch_id = str(form.get("operator_batch_id", "")).strip() or None
    notes = str(form.get("notes", "")).strip() or None
    crates_str = str(form.get("number_of_crates", "1")).strip()
    weight_str = str(form.get("total_weight_kg", "")).strip()

    if not seller_name or not variety:
        with db_conn() as conn:
            varieties = [row["name"] for row in list_varieties(conn)]
        return templates.TemplateResponse(
            request,
            "batch_new.html",
            {
                "varieties": varieties,
                "error": "Imię sprzedawcy i odmiana są wymagane.",
                "default_weight": config.DEFAULT_CRATE_WEIGHT_KG,
            },
        )

    try:
        price = float(price_str) if price_str else None
    except ValueError:
        price = None

    try:
        crates = int(crates_str)
    except ValueError:
        crates = 1

    try:
        default_w = float(crates) * config.DEFAULT_CRATE_WEIGHT_KG
        weight_kg = float(weight_str) if weight_str else default_w
    except ValueError:
        weight_kg = float(crates) * config.DEFAULT_CRATE_WEIGHT_KG

    with db_conn() as conn:
        batch_id = create_batch(
            conn,
            seller_name=seller_name,
            variety=variety,
            seller_address=seller_address,
            price_pln_per_kg=price,
            ca_opening_date=ca_date,
            operator_batch_id=op_batch_id,
            notes=notes,
            number_of_crates=crates,
            total_weight_kg=weight_kg,
        )
        upsert_variety(conn, variety)

    return RedirectResponse(url=f"/batches/{batch_id}", status_code=303)


@router.get("/batches/{batch_id}", response_class=HTMLResponse)
@require_login
async def batch_detail(request: Request, batch_id: int):
    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
        if batch is None:
            return HTMLResponse("Partia nie znaleziona.", status_code=404)
        scans = list_scans_for_batch(conn, batch_id)
        reports = list_reports_for_batch(conn, batch_id)

    weight_warning = None
    if batch["total_weight_kg"] > config.MAX_TRUCK_WEIGHT_KG:
        weight_warning = (
            f"Uwaga: masa partii ({batch['total_weight_kg']} kg) "
            "przekracza typowy ładunek ciężarówki."
        )

    return templates.TemplateResponse(
        request,
        "batch_detail.html",
        {
            "batch": batch,
            "scans": scans,
            "reports": reports,
            "weight_warning": weight_warning,
        },
    )


@router.post("/batches/{batch_id}/delete")
@require_login
async def batch_delete(request: Request, batch_id: int):
    """Delete batch and all associated data."""
    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
        if batch is None:
            return HTMLResponse("Partia nie znaleziona.", status_code=404)
        scans = list_scans_for_batch(conn, batch_id)
        reports = list_reports_for_batch(conn, batch_id)

        # Delete physical files
        for scan in scans:
            if scan["preview_path"]:
                p = config.DATA_DIR / "previews" / Path(scan["preview_path"]).name
                p.unlink(missing_ok=True)

        for report in reports:
            for field in ("html_path", "pdf_path", "json_path"):
                if report[field]:
                    Path(report[field]).unlink(missing_ok=True)

        delete_batch(conn, batch_id)

    return RedirectResponse(url="/", status_code=303)


@router.get("/api/varieties", response_class=JSONResponse)
async def api_varieties(request: Request):
    with db_conn() as conn:
        varieties = [row["name"] for row in list_varieties(conn, limit=50)]
    return JSONResponse({"varieties": varieties})


@router.post("/api/groundtruth/{batch_id}")
@require_login
async def api_import_groundtruth(request: Request, batch_id: int):
    from apple_caliber_scan.services.groundtruth import import_ground_truth

    body = await request.json()
    grader_results = body.get("grader_results", {})
    weight_kg = body.get("weight_kg")
    graded_at = body.get("graded_at")
    notes = body.get("notes")

    try:
        with db_conn() as conn:
            gt_id = import_ground_truth(
                conn, batch_id, grader_results,
                weight_kg=weight_kg, graded_at=graded_at, notes=notes
            )
        return JSONResponse({"id": gt_id, "status": "imported"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
