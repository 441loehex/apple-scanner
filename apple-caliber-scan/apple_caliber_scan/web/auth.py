"""Session-based authentication for the web UI."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps

from fastapi import Request
from fastapi.responses import RedirectResponse

from apple_caliber_scan import config

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "acs_session"
SESSION_MAX_AGE = 8 * 60 * 60  # 8 hours


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def require_login(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not is_authenticated(request):
            return RedirectResponse(url="/login", status_code=302)
        return await func(request, *args, **kwargs)
    return wrapper


def login_user(request: Request) -> None:
    request.session["authenticated"] = True


def logout_user(request: Request) -> None:
    request.session.clear()


def check_credentials(username: str, password: str) -> bool:
    expected_user = config.WEB_USERNAME
    try:
        expected_pass = config.get_web_password()
    except RuntimeError:
        return False
    return username == expected_user and password == expected_pass
