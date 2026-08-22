from __future__ import annotations

from flask import Flask, request, session
import hmac

from routes import admin_audit_routes


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_audit_routes.admin_audit_bp, url_prefix="/admin")
    return app


def _csrf_app() -> Flask:
    app = _app()

    @app.before_request
    def enforce_admin_csrf():
        if (
            request.method == "POST"
            and request.path.startswith("/admin")
            and session.get("admin_logged_in") is True
        ):
            expected = str(session.get("admin_csrf_token") or "")
            supplied = str(
                request.form.get("csrf_token")
                or request.headers.get("X-CSRF-Token")
                or ""
            )
            if expected and not (supplied and hmac.compare_digest(expected, supplied)):
                return {"success": False, "msg": "CSRF校验失败"}, 403
        return None

    return app


def _operation_result():
    return {
        "items": [{
            "event_id": "op-1", "created_at": "2026-07-19 12:00:00",
            "success": True, "action_name": "管理员续费套餐", "action_code": "admin.subscription_renew",
            "actor_type": "admin", "actor_name": "admin", "target_user_id": 7,
            "target_username": "alice", "target_phone": "13812345678",
            "target_email": "alice@example.com", "client_ip": "1.2.3.4",
            "before_data": {"plan": "month", "phone": "13712345678", "email": "nested@example.com"}, "after_data": {"plan": "year"},
            "request_data": {}, "status_code": 200, "error_message": "",
        }],
        "total": 1, "page": 1, "page_size": 50, "pages": 1,
        "stats": {"total": 1, "success_count": 1, "failure_count": 0,
                  "target_user_count": 1, "admin_count": 1, "user_count": 0},
    }


def _api_result():
    return {
        "items": [{
            "event_id": "api-1", "created_at": "2026-07-19 12:00:00",
            "success": False, "user_id": None, "username_snapshot": "",
            "phone_snapshot": "", "email_snapshot": "", "provider": "tushare",
            "api_name": "daily", "request_method": "GET", "status_code": 401,
            "duration_ms": 12, "auth_state": "missing_token", "client_ip": "1.2.3.4",
            "request_path": "/api/v1/market/tushare/daily", "request_params": {"query": {"trade_date": ["20260719"]}},
        }],
        "total": 1, "page": 1, "page_size": 50, "pages": 1,
        "stats": {"total": 1, "success_count": 0, "failure_count": 1, "user_count": 0,
                  "anonymous_count": 1, "average_duration_ms": 12, "unauthorized_count": 1,
                  "subscription_required_count": 0, "forbidden_count": 0,
                  "rate_limited_count": 0, "server_error_count": 0, "slowest_api": {"provider": "tushare", "api_name": "daily", "duration_ms": 12}},
    }


def test_audit_pages_require_admin_session(monkeypatch):
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs", lambda *a, **k: _operation_result())
    monkeypatch.setattr(admin_audit_routes, "query_api_access_logs", lambda *a, **k: _api_result())
    client = _app().test_client()

    assert client.get("/admin/operation-history").status_code == 302
    assert client.get("/admin/data-access-history").status_code == 302
    assert "/admin/login" in client.get("/admin/operation-history").headers["Location"]


def test_operation_page_masks_sensitive_values(monkeypatch):
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs", lambda *a, **k: _operation_result())
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.get("/admin/operation-history")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "138****5678" in body
    assert "ali***@example.com" in body
    assert "13812345678" not in body
    assert "alice@example.com" not in body
    assert "13712345678" not in body
    assert "nested@example.com" not in body
    assert "查看完整信息" in body
    assert "element.hidden = false" in body
    assert "/admin/audit/reveal-sensitive" in body


def test_access_page_lists_anonymous_failed_request(monkeypatch):
    monkeypatch.setattr(admin_audit_routes, "query_api_access_logs", lambda *a, **k: _api_result())
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.get("/admin/data-access-history")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "匿名" in body
    assert "missing_token" in body
    assert "daily" in body
    assert "查看完整信息" in body


def test_sensitive_reveal_requires_password_and_strict_durable_audit(monkeypatch):
    record = _operation_result()["items"][0]
    events = []
    monkeypatch.setattr(admin_audit_routes, "get_operation_log", lambda event_id: record)
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("audit-id", kwargs.get("strict") is True))
    monkeypatch.setattr(admin_audit_routes, "verify_admin_confirmation", lambda password, otp=None: password == "admin-pass")
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    wrong = client.post("/admin/audit/reveal-sensitive", json={
        "table": "operation", "event_id": "op-1", "fields": ["target_phone"], "password": "bad",
    })
    assert wrong.status_code == 403
    assert events[-1]["success"] is False

    ok = client.post("/admin/audit/reveal-sensitive", json={
        "table": "operation", "event_id": "op-1", "fields": ["target_phone", "target_email"], "password": "admin-pass",
    })
    assert ok.status_code == 200
    assert ok.get_json()["data"] == {"target_phone": "13812345678", "target_email": "alice@example.com"}
    assert events[-1]["strict"] is True
    assert events[-1]["action_code"] == "admin.sensitive_reveal"
    assert ok.headers["Cache-Control"] == "no-store"


def test_sensitive_reveal_is_denied_when_strict_audit_is_not_durable(monkeypatch):
    record = _operation_result()["items"][0]
    monkeypatch.setattr(admin_audit_routes, "get_operation_log", lambda event_id: record)
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: ("audit-id", False))
    monkeypatch.setattr(admin_audit_routes, "verify_admin_confirmation", lambda password, otp=None: password == "admin-pass")
    client = _app().test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post("/admin/audit/reveal-sensitive", json={
        "table": "operation", "event_id": "op-1", "fields": ["target_phone"], "password": "admin-pass",
    })
    assert response.status_code == 503
    assert "审计系统暂不可用" in response.get_json()["message"]


def test_browser_reveal_sends_csrf_header_and_succeeds_under_global_guard(monkeypatch):
    record = _operation_result()["items"][0]
    monkeypatch.setattr(admin_audit_routes, "query_operation_logs", lambda *a, **k: _operation_result())
    monkeypatch.setattr(admin_audit_routes, "get_operation_log", lambda event_id: record)
    monkeypatch.setattr(admin_audit_routes, "record_operation", lambda **kwargs: ("audit-id", True))
    monkeypatch.setattr(admin_audit_routes, "verify_admin_confirmation", lambda password, otp=None: password == "admin-pass")

    client = _csrf_app().test_client()
    with client.session_transaction() as admin_session:
        admin_session["admin_logged_in"] = True
        admin_session["admin_csrf_token"] = "csrf-test-token"

    page = client.get("/admin/operation-history")
    body = page.get_data(as_text=True)
    assert 'meta name="admin-csrf-token" content="csrf-test-token"' in body
    assert "'X-CSRF-Token': csrfToken" in body

    denied = client.post("/admin/audit/reveal-sensitive", json={
        "table": "operation", "event_id": "op-1",
        "fields": ["target_phone"], "password": "admin-pass",
    })
    assert denied.status_code == 403

    allowed = client.post(
        "/admin/audit/reveal-sensitive",
        headers={"X-CSRF-Token": "csrf-test-token"},
        json={
            "table": "operation", "event_id": "op-1",
            "fields": ["target_phone", "target_email"],
            "password": "admin-pass",
        },
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["data"] == {
        "target_phone": "13812345678",
        "target_email": "alice@example.com",
    }
