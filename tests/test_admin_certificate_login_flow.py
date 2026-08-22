from __future__ import annotations

from flask import Flask

from routes import admin_member_routes
from services.admin_auth import AdminCertificateVerification


def _app(monkeypatch):
    monkeypatch.setattr(admin_member_routes, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(admin_member_routes, "ADMIN_IP_WHITELIST", [])
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: ("event", True))
    monkeypatch.setattr(admin_member_routes, "verify_admin_password", lambda value: value == "correct-password")
    monkeypatch.setattr(
        admin_member_routes,
        "verify_admin_client_certificate_request",
        lambda: AdminCertificateVerification(True, "ok", "", {"id": 7, "device_name": "main-pc", "fingerprint_sha256": "AB" * 32}),
    )
    monkeypatch.setattr(admin_member_routes, "touch_certificate_use", lambda *args, **kwargs: True)
    app = Flask(__name__)
    app.secret_key = "s" * 64
    app.config.update(TESTING=True)
    app.register_blueprint(admin_member_routes.admin_member_bp, url_prefix="/admin")
    return app


def _load_captcha(client):
    response = client.get("/admin/captcha.png")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.headers["Cache-Control"].startswith("no-store")


def test_login_page_automatically_loads_refreshable_image_captcha(monkeypatch):
    app = _app(monkeypatch)
    body = app.test_client().get("/admin/login").get_data(as_text=True)
    assert "/admin/captcha.png" in body
    assert "刷新验证码" in body
    assert 'name="captcha"' in body
    assert 'name="otp"' not in body
    assert "Windows Hello" not in body


def test_login_requires_certificate_password_and_captcha(monkeypatch):
    app = _app(monkeypatch)
    client = app.test_client()
    codes = iter(["aB3Cd", "eF4Gh"])
    issued = {"code": ""}
    def fake_issue(session_obj):
        issued["code"] = next(codes)
        return issued["code"]
    monkeypatch.setattr(admin_member_routes, "issue_admin_captcha", fake_issue)
    monkeypatch.setattr(admin_member_routes, "verify_admin_captcha", lambda session_obj, supplied: supplied == issued["code"])
    monkeypatch.setattr(admin_member_routes, "render_admin_captcha_png", lambda code: b"\x89PNG\r\n\x1a\nimage")

    _load_captcha(client)
    invalid = client.post("/admin/login", data={"username": "admin", "password": "correct-password", "captcha": "wrong"})
    assert invalid.status_code == 401

    _load_captcha(client)
    valid = client.post("/admin/login", data={"username": "admin", "password": "correct-password", "captcha": "eF4Gh"})
    assert valid.status_code == 302
    with client.session_transaction() as session:
        assert session["admin_logged_in"] is True
        assert session["admin_certificate_id"] == 7


def test_login_rejects_invalid_certificate_before_credentials(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(
        admin_member_routes,
        "verify_admin_client_certificate_request",
        lambda: AdminCertificateVerification(False, "certificate_revoked", "证书已撤销", None),
    )
    response = app.test_client().post(
        "/admin/login", data={"username": "admin", "password": "correct-password", "captcha": "anything"}
    )
    assert response.status_code == 403
    assert "客户端证书" in response.get_data(as_text=True)
