from __future__ import annotations

from flask import Flask

import config
from services import admin_auth


VALID_FP = "AB" * 32


def _app():
    app = Flask(__name__)
    app.secret_key = "s" * 64
    return app


def _headers(**overrides):
    values = {
        "X-Admin-Proxy-Auth": "p" * 48,
        "X-Admin-Client-Cert-Verify": "SUCCESS",
        "X-Admin-Client-Cert-Fingerprint": VALID_FP,
        "X-Admin-Client-Cert-Serial": "01AB",
        "X-Admin-Client-Cert-Subject": "CN=admin-main-pc",
    }
    values.update(overrides)
    return values


def _cert(status="active", not_before="2026-01-01T00:00:00Z", not_after="2099-01-01T00:00:00Z"):
    return {
        "id": 1,
        "admin_username": "admin",
        "device_name": "main-pc",
        "serial_number": "01AB",
        "fingerprint_sha256": VALID_FP,
        "subject_dn": "CN=admin-main-pc",
        "not_before": not_before,
        "not_after": not_after,
        "status": status,
    }




def _forwarded(serial="01AB", not_before="2026-01-01T00:00:00Z", not_after="2099-01-01T00:00:00Z"):
    from datetime import datetime
    def parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return {
        "fingerprint_sha256": VALID_FP,
        "serial_number": serial,
        "subject_dn": "CN=admin-main-pc",
        "issuer_dn": "CN=Test CA",
        "not_before": parse(not_before),
        "not_after": parse(not_after),
    }

def _configure(monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_REQUIRED", True, raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "admin.example.com", raising=False)
    monkeypatch.setattr(config, "ADMIN_CLIENT_CERT_PROXY_SECRET", "p" * 48, raising=False)
    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin")


def test_valid_client_certificate_is_accepted(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded())
    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert())
    with _app().test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers()):
        result = admin_auth.verify_admin_client_certificate_request()
    assert result.ok
    assert result.certificate["device_name"] == "main-pc"


def test_missing_or_forged_proxy_headers_fail_closed(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded())
    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert())
    app = _app()
    with app.test_request_context("/admin/login", base_url="https://admin.example.com"):
        assert admin_auth.verify_admin_client_certificate_request().code == "proxy_auth_missing"
    with app.test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers(**{"X-Admin-Proxy-Auth": "wrong"})):
        assert admin_auth.verify_admin_client_certificate_request().code == "proxy_auth_invalid"


def test_unknown_revoked_expired_and_serial_mismatch_fail(monkeypatch):
    _configure(monkeypatch)
    app = _app()
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded())
    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: None)
    with app.test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers()):
        assert admin_auth.verify_admin_client_certificate_request().code == "certificate_unknown"

    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert(status="revoked"))
    with app.test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers()):
        assert admin_auth.verify_admin_client_certificate_request().code == "certificate_revoked"

    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert(not_after="2020-01-01T00:00:00Z"))
    with app.test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers()):
        assert admin_auth.verify_admin_client_certificate_request().code == "certificate_expired"

    monkeypatch.setattr(admin_auth, "get_certificate_by_fingerprint", lambda value: _cert())
    monkeypatch.setattr(admin_auth, "_forwarded_certificate_details", lambda: _forwarded(serial="DEADBEEF"))
    with app.test_request_context("/admin/login", base_url="https://admin.example.com", headers=_headers()):
        assert admin_auth.verify_admin_client_certificate_request().code == "certificate_serial_mismatch"
