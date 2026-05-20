"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from apple_caliber_scan import config
from apple_caliber_scan.web.auth import (
    SESSION_MAX_AGE,
    check_credentials,
    is_authenticated,
    login_user,
    logout_user,
)

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app() -> FastAPI:
    # Validate required config on startup
    config.get_web_password()
    config.get_web_secret_key()
    config.ensure_data_dirs()

    from apple_caliber_scan.database.connection import initialize_schema
    initialize_schema()

    app = FastAPI(
        title="Apple Caliber Scan — Freshora Sp. Z. o. o.",
        docs_url=None,
        redoc_url=None,
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=config.get_web_secret_key(),
        session_cookie="acs_session",
        max_age=SESSION_MAX_AGE,
        https_only=False,
        same_site="lax",
    )

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve scan preview images
    previews_dir = config.DATA_DIR / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/previews", StaticFiles(directory=str(previews_dir)), name="previews")

    # Mount report files
    reports_dir = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/reports-files", StaticFiles(directory=str(reports_dir)), name="reports-files")

    # Auth routes
    @app.get("/login", response_class=HTMLResponse)
    async def login_get(request: Request):
        if is_authenticated(request):
            return RedirectResponse(url="/", status_code=302)
        return templates.TemplateResponse(request, "login.html", {"error": None})

    @app.post("/login", response_class=HTMLResponse)
    async def login_post(request: Request):
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        if check_credentials(username, password):
            login_user(request)
            return RedirectResponse(url="/", status_code=303)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Nieprawidłowy login lub hasło."},
        )

    @app.get("/logout")
    async def logout(request: Request):
        logout_user(request)
        return RedirectResponse(url="/login", status_code=302)

    # Register routers
    from apple_caliber_scan.web.routes.batches import router as batches_router
    from apple_caliber_scan.web.routes.reports import router as reports_router
    from apple_caliber_scan.web.routes.scans import router as scans_router

    app.include_router(batches_router)
    app.include_router(scans_router)
    app.include_router(reports_router)

    return app
