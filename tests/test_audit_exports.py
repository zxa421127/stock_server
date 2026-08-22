from __future__ import annotations

from flask import Flask

from routes import admin_audit_routes


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_audit_routes.admin_audit_bp, url_prefix="/admin")
    return app


def _rows():
    return [{
        "event_id": "op-1", "created_at": "2026-07-19 12:00:00", "success": True,
        "actor_type": "admin", "actor_name": "admin", "target_user_id": 7,
        "target_username": "=alice", "target_phone": "13812345678",
        "target_email": "alice@example.com", "action_category": "membership",
        "action_code": "admin.subscription_renew", "action_name": "续费",
        "status_code": 200, "error_code": "", "error_message": "",
        "client_ip": "1.2.3.4", "before_data": {"phone": "13712345678", "email": "nested@example.com"}, "after_data": {}, "request_data": {},
    }]


def test_masked_operation_export_masks_sensitive_values_and_escapes_formula(monkeypatch):
    events = []
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs_for_export", lambda filters, limit: _rows())
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("audit", True))
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.get("/admin/operation-history/export.csv?action_code=admin.subscription_renew")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "138****5678" in text
    assert "ali***@example.com" in text
    assert "13812345678" not in text
    assert "13712345678" not in text
    assert "nested@example.com" not in text
    assert "137****5678" in text
    assert "'=alice" in text
    assert events[-1]["action_code"] == "admin.audit_export_masked"


def test_full_export_requires_password_and_strict_audit(monkeypatch):
    events = []
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs_for_export", lambda filters, limit: _rows())
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("audit", kwargs.get("strict") is True))
    monkeypatch.setattr(admin_audit_routes, "verify_admin_confirmation", lambda password, otp=None: password == "admin-pass")
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    denied = client.post("/admin/operation-history/export-full.csv", data={"password": "wrong"})
    assert denied.status_code == 403

    response = client.post("/admin/operation-history/export-full.csv", data={"password": "admin-pass"})
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "13812345678" in text
    assert "alice@example.com" in text
    assert events[-1]["strict"] is True
    assert events[-1]["action_code"] == "admin.audit_export_full"
    assert response.headers["Cache-Control"] == "no-store"


def test_full_export_is_denied_when_audit_cannot_be_persisted(monkeypatch):
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs_for_export", lambda filters, limit: _rows())
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: ("audit", False))
    monkeypatch.setattr(admin_audit_routes, "verify_admin_confirmation", lambda password, otp=None: password == "admin-pass")
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post("/admin/operation-history/export-full.csv", data={"password": "admin-pass"})
    assert response.status_code == 503

def test_full_api_export_requires_password_and_strict_audit(monkeypatch):
    events = []

    monkeypatch.setattr(
        admin_audit_routes,
        "query_api_access_logs_for_export",
        lambda filters, limit: [{}],
    )
    monkeypatch.setattr(
        admin_audit_routes,
        "_api_csv_rows",
        lambda records, full: (["result"], [["ok"]]),
    )
    monkeypatch.setattr(
        admin_audit_routes,
        "record_operation",
        lambda **kwargs: events.append(kwargs)
        or ("audit", kwargs.get("strict") is True),
    )
    monkeypatch.setattr(
        admin_audit_routes,
        "verify_admin_confirmation",
        lambda password, otp=None: password == "admin-pass",
    )

    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    denied = client.post(
        "/admin/data-access-history/export-full.csv",
        data={"password": "wrong"},
    )
    assert denied.status_code == 403

    response = client.post(
        "/admin/data-access-history/export-full.csv",
        data={"password": "admin-pass"},
    )

    assert response.status_code == 200
    assert events[-1]["strict"] is True
    assert events[-1]["action_code"] == "admin.audit_export_full"
    assert events[-1]["request_data"]["history_type"] == "api"
    assert response.headers["Cache-Control"] == "no-store"


def test_full_api_export_is_denied_when_audit_cannot_be_persisted(monkeypatch):
    monkeypatch.setattr(
        admin_audit_routes,
        "query_api_access_logs_for_export",
        lambda filters, limit: [{}],
    )
    monkeypatch.setattr(
        admin_audit_routes,
        "record_operation",
        lambda **kwargs: ("audit", False),
    )
    monkeypatch.setattr(
        admin_audit_routes,
        "verify_admin_confirmation",
        lambda password, otp=None: password == "admin-pass",
    )

    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post(
        "/admin/data-access-history/export-full.csv",
        data={"password": "admin-pass"},
    )

    assert response.status_code == 503

