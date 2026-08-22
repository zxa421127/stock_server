from __future__ import annotations

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

import services.audit_service as audit


def _app(monkeypatch):
    events = []
    monkeypatch.setattr(audit, "enqueue_event", lambda event_type, event, strict=False: events.append((event_type, event)) or True)
    monkeypatch.setattr(audit.config, "AUDIT_ENABLED", True)
    monkeypatch.setattr(audit.config, "AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000)
    monkeypatch.setattr(audit.config, "AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000)
    monkeypatch.setattr(audit.config, "AUDIT_TOKEN_HMAC_SECRET", "test-secret")

    app = Flask(__name__)
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False)

    @app.before_request
    def before():
        audit.begin_api_audit()

    @app.after_request
    def after(response):
        audit.finish_api_audit(response)
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify({"error": exc.description}), exc.code
        audit.mark_api_auth_state("internal_error", error_code="internal_error", error_message=str(exc))
        return jsonify({"error": "internal"}), 500

    @app.get("/api/ok")
    def ok():
        audit.mark_api_auth_state(
            "valid",
            principal_type="user",
            user_id=7,
            username_snapshot="alice",
            phone_snapshot="13812345678",
            email_snapshot="alice@example.com",
            required_scope="tushare:read",
            package_code="general_month",
            provider="tushare",
            api_name="daily",
        )
        return jsonify({"ok": True})

    @app.get("/api/missing")
    def missing():
        audit.mark_api_auth_state("missing_token", error_code="missing_token", error_message="缺少 X-API-Token")
        return jsonify({"error": "missing"}), 401

    @app.get("/api/fail")
    def fail():
        raise RuntimeError("boom")

    @app.get("/api/business-error")
    def business_error():
        audit.mark_api_auth_state("valid", principal_type="user", user_id=7, error_code="", error_message="")
        return jsonify({"success": False, "code": 400, "msg": "业务参数错误"}), 400

    @app.get("/html")
    def html():
        return "html"

    return app, events


def test_api_success_is_recorded_once_with_user_context_and_sanitized_params(monkeypatch):
    app, events = _app(monkeypatch)
    client = app.test_client()
    response = client.get(
        "/api/ok?trade_date=20260718&password=secret-value",
        headers={"X-API-Token": "raw-token", "User-Agent": "pytest-agent"},
    )
    assert response.status_code == 200
    assert len(events) == 1
    event_type, event = events[0]
    assert event_type == "api_access"
    assert event["auth_state"] == "valid"
    assert event["user_id"] == 7
    assert event["provider"] == "tushare"
    assert event["api_name"] == "daily"
    assert event["request_path"] == "/api/ok"
    assert event["status_code"] == 200
    assert event["success"] is True
    assert event["duration_ms"] >= 0
    assert event["request_params"]["query"]["password"] == "[REDACTED]"
    serialized = str(event)
    assert "secret-value" not in serialized
    assert "raw-token" not in serialized
    assert len(event["token_fingerprint"]) == 64


def test_missing_token_404_and_500_are_each_recorded_once(monkeypatch):
    app, events = _app(monkeypatch)
    client = app.test_client()
    assert client.get("/api/missing").status_code == 401
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/api/fail").status_code == 500
    assert len(events) == 3
    assert [item[1]["status_code"] for item in events] == [401, 404, 500]
    assert events[0][1]["auth_state"] == "missing_token"
    assert events[1][1]["auth_state"] == "missing_token"
    assert events[2][1]["auth_state"] == "internal_error"


def test_non_api_page_is_not_recorded(monkeypatch):
    app, events = _app(monkeypatch)
    assert app.test_client().get("/html").status_code == 200
    assert events == []


def test_record_operation_sanitizes_passwords_and_uses_request_metadata(monkeypatch):
    app, events = _app(monkeypatch)
    with app.test_request_context(
        "/admin/members/open",
        method="POST",
        data={"new_password": "do-not-store", "plan_code": "general_year"},
        headers={"User-Agent": "pytest-agent"},
    ):
        event_id, durable = audit.record_operation(
            actor_type="admin",
            actor_id=None,
            actor_name="admin",
            target_user={"id": 9, "username": "bob", "phone": "13912345678", "email": "bob@example.com"},
            action_category="membership",
            action_code="admin.subscription_renew",
            action_name="套餐续费",
            success=True,
            status_code=200,
            before_data={"plan": "general_month"},
            after_data={"plan": "general_year"},
            request_data={"new_password": "do-not-store", "plan_code": "general_year"},
        )
    assert durable is True
    assert event_id
    event = events[0][1]
    assert event["request_data"]["new_password"] == "[REDACTED]"
    assert "do-not-store" not in str(event)
    assert event["target_user_id"] == 9
    assert event["request_path"] == "/admin/members/open"


def test_require_scope_publishes_auth_states(monkeypatch):
    from middleware import auth

    states = []
    monkeypatch.setattr(auth, "mark_api_auth_state", lambda state, **ctx: states.append((state, ctx)))
    monkeypatch.setattr(auth, "enqueue_api_key_touch", lambda token: None)
    monkeypatch.setattr(auth, "enqueue_usage_log", lambda **payload: None)

    app = Flask(__name__)

    @app.get("/missing")
    @auth.require_scope("tushare:read")
    def missing_route():
        return jsonify({"ok": True})

    response = app.test_client().get("/missing")
    assert response.status_code == 401
    assert states[-1][0] == "missing_token"

    states.clear()
    monkeypatch.setattr(
        auth,
        "resolve_auth_context",
        lambda token: (_ for _ in ()).throw(auth.AuthError(401, "bad", audit_state="invalid_token", error_code="invalid_token")),
    )
    response = app.test_client().get("/missing", headers={"X-API-Token": "bad"})
    assert response.status_code == 401
    assert states[-1][0] == "invalid_token"

    states.clear()
    context = {
        "user": {"id": 3, "username": "alice", "phone": "13812345678", "email": "a@example.com"},
        "subscription": {"plan_code": "general_month"},
        "plan": {"plan_code": "general_month", "scopes": '["tushare:read"]'},
        "scopes": ["tushare:read"],
    }
    monkeypatch.setattr(auth, "resolve_auth_context", lambda token: context)
    monkeypatch.setattr(auth, "scope_allowed", lambda required, scopes: False)
    response = app.test_client().get("/missing", headers={"X-API-Token": "valid"})
    assert response.status_code == 403
    assert states[-1][0] == "insufficient_scope"

    states.clear()
    monkeypatch.setattr(auth, "scope_allowed", lambda required, scopes: True)
    monkeypatch.setattr(auth, "check_rate_limit", lambda *args: (False, "slow down"))
    response = app.test_client().get("/missing", headers={"X-API-Token": "valid"})
    assert response.status_code == 429
    assert states[-1][0] == "rate_limited"


def test_api_failure_extracts_only_short_error_summary(monkeypatch):
    app, events = _app(monkeypatch)
    response = app.test_client().get("/api/business-error")
    assert response.status_code == 400
    assert events[-1][1]["error_code"] == "http_400"
    assert events[-1][1]["error_message"] == "业务参数错误"
    assert "success" not in events[-1][1]["error_message"]

def test_require_scope_generic_429_sets_retry_after_from_structured_result(monkeypatch):
    from middleware import auth

    monkeypatch.setattr(auth, "mark_api_auth_state", lambda state, **ctx: None)
    monkeypatch.setattr(auth, "enqueue_api_key_touch", lambda token: None)
    monkeypatch.setattr(auth, "enqueue_usage_log", lambda **payload: None)

    context = {
        "user": {
            "id": 3,
            "username": "alice",
            "phone": "13812345678",
            "email": "a@example.com",
        },
        "subscription": {"plan_code": "general_month"},
        "plan": {
            "plan_code": "general_month",
            "scopes": '["tushare:read"]',
        },
        "scopes": ["tushare:read"],
    }

    class _StructuredDecision:
        allowed = False
        message = "slow down"
        reason_code = "minute_limit"
        retry_after_seconds = 7

        def __iter__(self):
            yield self.allowed
            yield self.message

    monkeypatch.setattr(auth, "resolve_auth_context", lambda token: context)
    monkeypatch.setattr(auth, "scope_allowed", lambda required, scopes: True)
    monkeypatch.setattr(auth, "check_rate_limit", lambda *args: _StructuredDecision())

    app = Flask(__name__)

    @app.get("/rate-limited")
    @auth.require_scope("tushare:read")
    def rate_limited_route():
        return jsonify({"ok": True})

    response = app.test_client().get(
        "/rate-limited",
        headers={"X-API-Token": "valid"},
    )
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
