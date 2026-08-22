from __future__ import annotations

from flask import Flask

import config
from services import admin_auth


VALID_FP = "AB" * 32


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "s" * 64
    return app


def _cert(fingerprint: str = VALID_FP) -> dict:
    return {
        "id": 1,
        "admin_username": "admin",
        "device_name": "main-pc",
        "serial_number": "01AB",
        "fingerprint_sha256": fingerprint,
        "subject_dn": "CN=admin-main-pc",
        "not_before": "2026-01-01T00:00:00Z",
        "not_after": "2099-01-01T00:00:00Z",
        "status": "active",
    }


def _forwarded() -> dict:
    from datetime import datetime

    return {
        "fingerprint_sha256": VALID_FP,
        "serial_number": "01AB",
        "subject_dn": "CN=admin-main-pc",
        "issuer_dn": "CN=Test CA",
        "not_before": datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        "not_after": datetime.fromisoformat("2099-01-01T00:00:00+00:00"),
    }


def _configure(monkeypatch) -> None:
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_REQUIRED", True, raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_PROXY_SECRET", "p" * 48, raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "admin.example.com", raising=False)
    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin")


def _headers() -> dict[str, str]:
    return {
        "X-Admin-Proxy-Auth": "p" * 48,
        "X-Admin-Client-Cert-Verify": "SUCCESS",
        "X-Admin-Client-Cert": "dummy",
    }


def test_admin_certificate_request_rejects_wrong_host(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded())
    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert())

    with _app().test_request_context(
        "/admin/login",
        base_url="https://api.example.com",
        headers=_headers(),
    ):
        result = admin_auth.verify_admin_client_certificate_request()

    assert result.ok is False
    assert result.code == "admin_host_mismatch"


def test_admin_certificate_request_accepts_configured_host_with_port(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded())
    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert())

    with _app().test_request_context(
        "/admin/login",
        base_url="https://admin.example.com:443",
        headers=_headers(),
    ):
        result = admin_auth.verify_admin_client_certificate_request()

    assert result.ok is True


def test_admin_session_is_bound_to_original_certificate_fingerprint():
    assert admin_auth.admin_session_certificate_matches(VALID_FP, _cert()) is True
    assert admin_auth.admin_session_certificate_matches("CD" * 32, _cert()) is False
    assert admin_auth.admin_session_certificate_matches("", _cert()) is False
    assert admin_auth.admin_session_certificate_matches(VALID_FP, None) is False
