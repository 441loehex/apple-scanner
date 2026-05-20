"""Scan attachment (Drive URL), ingest, and annotation review routes."""

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from apple_caliber_scan import config
from apple_caliber_scan.database.connection import db_conn
from apple_caliber_scan.database.crud import (
    create_annotation,
    create_scan,
    delete_scan_circles,
    get_batch,
    get_circles_for_scan,
    get_scan,
    insert_circles,
    mark_ring_circle,
    update_circle,
    update_scan,
)
from apple_caliber_scan.scan.detector import Circle
from apple_caliber_scan.services.calibration import compute_scale_factor
from apple_caliber_scan.services.estimation import classify_diameter
from apple_caliber_scan.storage.drive import extract_drive_file_id
from apple_caliber_scan.web.auth import require_login

router = APIRouter()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/batches/{batch_id}/scan/new", response_class=HTMLResponse)
@require_login
async def scan_drive_form(request: Request, batch_id: int):
    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
    if batch is None:
        return HTMLResponse("Partia nie znaleziona.", status_code=404)
    return templates.TemplateResponse(request, "scan_drive.html", {"batch": batch})


@router.post("/batches/{batch_id}/scan")
@require_login
async def scan_attach(request: Request, batch_id: int):
    """Receive Drive URL, trigger download + ingest, redirect to review."""
    form = await request.form()
    drive_url = str(form.get("drive_url", "")).strip()
    fmt_hint = str(form.get("format", "ply")).strip() or "ply"
    try:
        ring_mm = float(str(form.get("ring_mm", "75")).strip())
    except ValueError:
        ring_mm = 75.0

    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        with db_conn() as conn:
            batch = get_batch(conn, batch_id)
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": "Nieprawidłowy link Google Drive. Sprawdź format URL."},
        )

    with db_conn() as conn:
        scan_id = create_scan(
            conn, batch_id, drive_url=drive_url, drive_file_id=file_id, fmt=fmt_hint,
            calibration_ring_mm=ring_mm,
        )

    try:
        from apple_caliber_scan.services.ingest import ingest_from_drive_url

        preview_path, circles, point_count, auto_ring = ingest_from_drive_url(
            drive_url, scan_id=scan_id, batch_id=batch_id, fmt_hint=fmt_hint
        )
        _save_scan_results(
            scan_id, preview_path, circles, point_count, auto_ring, status="previewed"
        )

    except Exception as e:
        logger.error("Ingest failed for scan %d: %s", scan_id, e)
        with db_conn() as conn:
            update_scan(conn, scan_id, status="failed", error_message=str(e)[:500])
        with db_conn() as conn:
            batch = get_batch(conn, batch_id)
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": f"Błąd pobierania/przetwarzania skanu: {e}"},
        )

    return RedirectResponse(
        url=f"/batches/{batch_id}/scans/{scan_id}/review", status_code=303
    )


@router.post("/batches/{batch_id}/scan/upload")
@require_login
async def scan_upload_file(
    request: Request,
    batch_id: int,
    file: Annotated[UploadFile, File()],
    ring_mm_str: Annotated[str, Form()] = "75",
):
    """Accept direct file upload (ZIP or PLY). Ingest immediately."""
    try:
        ring_mm = float(ring_mm_str)
    except ValueError:
        ring_mm = 75.0

    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
    if batch is None:
        return HTMLResponse("Partia nie znaleziona.", status_code=404)

    suffix = Path(file.filename or "upload").suffix.lower() or ".zip"
    allowed = {".zip", ".ply", ".obj", ".glb"}
    if suffix not in allowed:
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": (
                f"Nieobsługiwany format pliku: {suffix}. "
                f"Dozwolone: {', '.join(sorted(allowed))}"
            )},
        )

    config.ensure_data_dirs()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=str(config.DATA_DIR)) as tf:
        tmp_path = Path(tf.name)

    scan_id: int | None = None
    try:
        with tmp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)

        with db_conn() as conn:
            scan_id = create_scan(
                conn, batch_id,
                drive_url=None,
                drive_file_id=None,
                fmt=suffix.lstrip("."),
                calibration_ring_mm=ring_mm,
            )

        from apple_caliber_scan.services.ingest import ingest_from_local_file

        preview_path, circles, point_count, auto_ring = ingest_from_local_file(
            tmp_path, scan_id=scan_id, batch_id=batch_id, delete_after=True
        )
        _save_scan_results(
            scan_id, preview_path, circles, point_count, auto_ring, status="previewed"
        )

    except Exception as exc:
        logger.exception("Upload ingest failed: %s", exc)
        if scan_id is not None:
            with db_conn() as conn:
                update_scan(conn, scan_id, status="error", error_message=str(exc)[:500])
        with db_conn() as conn:
            batch = get_batch(conn, batch_id)
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": f"Błąd przetwarzania pliku: {exc}"},
        )
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return RedirectResponse(url=f"/batches/{batch_id}/scans/{scan_id}/review", status_code=303)


def _save_scan_results(
    scan_id: int,
    preview_path: Path,
    circles: list[Circle],
    point_count: int,
    auto_ring: Circle | None,
    status: str,
) -> None:
    preview_rel = str(preview_path.relative_to(config.DATA_DIR / "previews"))
    with db_conn() as conn:
        update_scan(
            conn,
            scan_id,
            preview_path=preview_rel,
            point_count=point_count,
            status=status,
        )
        if auto_ring:
            update_scan(
                conn,
                scan_id,
                auto_ring_cx_px=auto_ring.cx,
                auto_ring_cy_px=auto_ring.cy,
                auto_ring_radius_px=auto_ring.radius_px,
                auto_ring_confidence=auto_ring.confidence,
            )
        circle_dicts = [
            {
                "cx_px": c.cx,
                "cy_px": c.cy,
                "radius_px": c.radius_px,
                "ellipse_major_px": c.ellipse_major_px,
                "ellipse_minor_px": c.ellipse_minor_px,
                "ellipse_angle_deg": c.ellipse_angle_deg,
                "orientation": c.orientation,
                "confidence": c.confidence,
                "annotated_by": "auto",
            }
            for c in circles
        ]
        insert_circles(conn, scan_id, circle_dicts)


@router.get("/batches/{batch_id}/scans/{scan_id}/review", response_class=HTMLResponse)
@require_login
async def scan_review(request: Request, batch_id: int, scan_id: int):
    with db_conn() as conn:
        batch = get_batch(conn, batch_id)
        scan = get_scan(conn, scan_id)
        circles = get_circles_for_scan(conn, scan_id)

    if batch is None or scan is None:
        return HTMLResponse("Nie znaleziono.", status_code=404)

    circles_data = [
        {
            "id": c["id"],
            "cx": c["cx_px"],
            "cy": c["cy_px"],
            "radius": c["radius_px"],
            "is_ring": bool(c["is_ring"]),
            "is_excluded": bool(c["is_excluded"]),
            "diameter_mm": c["diameter_mm"],
            "caliber_class": c["caliber_class"],
            "confidence": c["confidence"],
            "orientation": c["orientation"] if "orientation" in c.keys() else "unknown",
        }
        for c in circles
    ]

    preview_url = None
    if scan["preview_path"]:
        preview_url = f"/previews/{scan['preview_path']}"

    # Build auto-ring JSON if detection confidence is sufficient.
    auto_ring_json = None
    scan_dict = dict(scan)
    if (
        scan_dict.get("auto_ring_cx_px")
        and scan_dict.get("auto_ring_confidence")
        and scan_dict["auto_ring_confidence"] >= 0.5
    ):
        auto_ring_json = {
            "cx": scan_dict["auto_ring_cx_px"],
            "cy": scan_dict["auto_ring_cy_px"],
            "radius": scan_dict["auto_ring_radius_px"],
            "confidence": scan_dict["auto_ring_confidence"],
        }

    return templates.TemplateResponse(
        request,
        "scan_review.html",
        {
            "batch": batch,
            "scan": scan,
            "circles_json": json.dumps(circles_data),
            "preview_url": preview_url,
            "ring_mm": scan["calibration_ring_mm"] or 75.0,
            "auto_ring_json": auto_ring_json,
        },
    )


@router.post("/batches/{batch_id}/scans/{scan_id}/annotate")
@require_login
async def scan_annotate(request: Request, batch_id: int, scan_id: int):
    """Save annotation: ring selection + circle states → compute calibration."""
    body = await request.json()
    ring_circle_id: int | None = body.get("ring_circle_id")
    circle_updates: list[dict] = body.get("circles", [])
    ring_mm: float = float(body.get("ring_mm", 75.0))

    with db_conn() as conn:
        scan = get_scan(conn, scan_id)
        if scan is None:
            return JSONResponse({"error": "Scan not found"}, status_code=404)

        for cu in circle_updates:
            cid = cu.get("id")
            if cid:
                update_circle(
                    conn,
                    cid,
                    cx_px=cu.get("cx"),
                    cy_px=cu.get("cy"),
                    radius_px=cu.get("radius"),
                    is_ring=1 if cu.get("is_ring") else 0,
                    is_excluded=1 if cu.get("is_excluded") else 0,
                    annotated_by="web",
                )

        if ring_circle_id:
            mark_ring_circle(conn, scan_id, ring_circle_id)

        circles_db = get_circles_for_scan(conn, scan_id)
        ring_row = next((c for c in circles_db if c["is_ring"]), None)
        apple_rows = [c for c in circles_db if not c["is_ring"] and not c["is_excluded"]]

        scale_result = None
        if ring_row:
            ring_circle = Circle(
                cx=ring_row["cx_px"], cy=ring_row["cy_px"],
                radius_px=ring_row["radius_px"], confidence=1.0,
                ellipse_major_px=ring_row["ellipse_major_px"] or 0.0,
                ellipse_minor_px=ring_row["ellipse_minor_px"] or 0.0,
                ellipse_angle_deg=ring_row["ellipse_angle_deg"] or 0.0,
            )
            apple_circles = [
                Circle(
                    cx=r["cx_px"], cy=r["cy_px"], radius_px=r["radius_px"],
                    ellipse_major_px=r["ellipse_major_px"] or 0.0,
                    ellipse_minor_px=r["ellipse_minor_px"] or 0.0,
                    ellipse_angle_deg=r["ellipse_angle_deg"] or 0.0,
                )
                for r in apple_rows
            ]
            scale_result = compute_scale_factor(
                ring_circle, ring_mm=ring_mm, apple_circles=apple_circles
            )

            for r, ac in zip(apple_rows, apple_circles):
                d_mm = ac.caliber_diameter_px * scale_result.scale_factor_mm_per_px
                update_circle(
                    conn, r["id"],
                    diameter_mm=d_mm,
                    caliber_class=classify_diameter(d_mm),
                )

            update_scan(
                conn, scan_id,
                calibration_ring_mm=ring_mm,
                scale_factor_mm_per_px=scale_result.scale_factor_mm_per_px,
                calibration_confidence=scale_result.confidence,
                calibration_warning=scale_result.warning,
                status="annotated",
            )

        create_annotation(conn, scan_id, ring_circle_id=ring_circle_id, annotated_by="web")

    return JSONResponse({
        "status": "ok",
        "scale_factor": scale_result.scale_factor_mm_per_px if scale_result else None,
        "confidence": scale_result.confidence if scale_result else "uncalibrated",
        "warning": scale_result.warning if scale_result else None,
    })


@router.post("/batches/{batch_id}/scans/{scan_id}/reingest")
@require_login
async def scan_reingest(request: Request, batch_id: int, scan_id: int):
    """Re-download from the stored Drive URL and reprocess with latest algorithms."""
    with db_conn() as conn:
        scan = get_scan(conn, scan_id)
        if scan is None:
            return HTMLResponse("Skan nie znaleziony.", status_code=404)
        drive_url = scan["drive_url"]
        fmt_hint = scan["format"] or "ply"

    if not drive_url:
        return HTMLResponse("Brak zapisanego URL Drive dla tego skanu.", status_code=400)

    with db_conn() as conn:
        delete_scan_circles(conn, scan_id)
        update_scan(conn, scan_id, status="pending", error_message=None)

    try:
        from apple_caliber_scan.services.ingest import ingest_from_drive_url

        preview_path, circles, point_count, auto_ring = ingest_from_drive_url(
            drive_url, scan_id=scan_id, batch_id=batch_id, fmt_hint=fmt_hint
        )
        _save_scan_results(
            scan_id, preview_path, circles, point_count, auto_ring, status="previewed"
        )
    except Exception as e:
        logger.error("Re-ingest failed for scan %d: %s", scan_id, e)
        with db_conn() as conn:
            update_scan(conn, scan_id, status="failed", error_message=str(e)[:500])
        with db_conn() as conn:
            batch = get_batch(conn, batch_id)
        return templates.TemplateResponse(
            request,
            "scan_drive.html",
            {"batch": batch, "error": f"Błąd ponownego przetwarzania: {e}"},
        )

    return RedirectResponse(
        url=f"/batches/{batch_id}/scans/{scan_id}/review", status_code=303
    )
