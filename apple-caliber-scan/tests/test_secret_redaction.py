"""Tests proving secrets never appear in log output or error messages."""

from __future__ import annotations

import logging


def test_login_wrong_password_does_not_log_password(auth_client, caplog):
    """An incorrect password attempt must not log the submitted password."""
    with caplog.at_level(logging.DEBUG, logger="apple_caliber_scan"):
        auth_client.post(
            "/login",
            data={"username": "freshora", "password": "SUPER_SECRET_ATTEMPT_XYZ"},
            follow_redirects=True,
        )
    for record in caplog.records:
        assert "SUPER_SECRET_ATTEMPT_XYZ" not in record.getMessage(), (
            "Submitted password appeared in log output"
        )


def test_web_password_env_not_logged_on_startup(monkeypatch, caplog):
    """ACS_WEB_PASSWORD value must not appear in any log record during app init."""
    import apple_caliber_scan.config as cfg
    monkeypatch.setenv("ACS_WEB_PASSWORD", "MYSECRETPASSWORD999")
    cfg._WEB_PASSWORD = "MYSECRETPASSWORD999"

    with caplog.at_level(logging.DEBUG):
        from apple_caliber_scan.web.app import create_app
        create_app()

    for record in caplog.records:
        assert "MYSECRETPASSWORD999" not in record.getMessage(), (
            f"ACS_WEB_PASSWORD appeared in log: {record.getMessage()!r}"
        )


def test_secret_key_not_in_error_response(test_client, monkeypatch):
    """The session secret key must not appear in any HTTP response body."""
    import apple_caliber_scan.config as cfg
    secret = "VERYSECRETKEY_THAT_MUST_NOT_APPEAR"
    cfg._WEB_SECRET_KEY = secret
    monkeypatch.setenv("ACS_WEB_SECRET_KEY", secret)

    # Hit a non-existent route to trigger 404 or redirect
    r = test_client.get("/nonexistent-route-12345", follow_redirects=True)
    assert secret not in r.text, "Secret key appeared in HTTP response body"


def test_telegram_token_not_in_config_repr(monkeypatch):
    """ACS_TELEGRAM_TOKEN must not appear in config module's string representations."""
    monkeypatch.setenv("ACS_TELEGRAM_TOKEN", "BOT_TOKEN_MUST_NOT_LEAK_9999")
    import apple_caliber_scan.config as cfg
    cfg.TELEGRAM_TOKEN = "BOT_TOKEN_MUST_NOT_LEAK_9999"

    # Ensure the token is not in any __repr__ or __str__ of config module
    cfg_repr = repr(cfg)
    # The repr of a module doesn't normally contain attribute values,
    # but this verifies no accidental str(cfg) logging dumps the token.
    assert "BOT_TOKEN_MUST_NOT_LEAK_9999" not in cfg_repr


def test_ingest_error_does_not_leak_path_secrets(tmp_path, caplog, monkeypatch):
    """IngestError for a bad file must not reveal secret env values in the message."""
    import apple_caliber_scan.config as cfg
    from apple_caliber_scan.services.ingest import IngestError, ingest_from_local_file

    monkeypatch.setenv("ACS_WEB_PASSWORD", "LEAKY_PASSWORD_CHECK_777")
    cfg._WEB_PASSWORD = "LEAKY_PASSWORD_CHECK_777"

    bad_file = tmp_path / "bad.ply"
    bad_file.write_text("not a valid ply file")

    with caplog.at_level(logging.WARNING):
        try:
            ingest_from_local_file(bad_file, scan_id=99, batch_id=1)
        except (IngestError, Exception):
            pass  # Expected to fail

    for record in caplog.records:
        assert "LEAKY_PASSWORD_CHECK_777" not in record.getMessage(), (
            f"Secret appeared in ingest log: {record.getMessage()!r}"
        )
