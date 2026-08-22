from __future__ import annotations

from flask import Flask

from routes import admin_member_routes, user_routes


def _user_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(user_routes.user_bp, url_prefix="/user")
    return app


def _admin_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(admin_member_routes.admin_member_bp, url_prefix="/admin")
    return app


def test_user_login_success_is_audited_without_password(monkeypatch):
    user = {"id": 7, "username": "alice", "phone": "13800138000", "email": "alice@example.com", "status": "active"}
    events = []
    monkeypatch.setattr(user_routes, "get_user_by_account", lambda account: user, raising=False)
    monkeypatch.setattr(user_routes, "authenticate_user", lambda account, password: user)
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    response = _user_app().test_client().post("/user/login", data={"account": "alice", "password": "secret-value"})
    assert response.status_code == 302
    event = events[-1]
    assert event["action_code"] == "user.auth.login_success"
    assert event["actor_type"] == "user"
    assert event["target_user"]["id"] == 7
    assert "secret-value" not in str(event)
    assert "password" not in str(event.get("request_data", {})).lower()


def test_existing_user_wrong_password_is_attributed_to_target_user(monkeypatch):
    user = {"id": 8, "username": "bob", "phone": "", "email": "bob@example.com", "status": "active"}
    events = []
    monkeypatch.setattr(user_routes, "get_user_by_account", lambda account: user, raising=False)
    monkeypatch.setattr(user_routes, "authenticate_user", lambda account, password: None)
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    response = _user_app().test_client().post("/user/login", data={"account": "bob", "password": "wrong-secret"})
    assert response.status_code == 401
    event = events[-1]
    assert event["action_code"] == "user.auth.login_failed"
    assert event["actor_type"] == "anonymous"
    assert event["target_user"]["id"] == 8
    assert event["error_code"] == "invalid_credentials"
    assert "wrong-secret" not in str(event)


def test_unknown_and_disabled_user_login_failures_are_distinguished_only_in_audit(monkeypatch):
    events = []
    monkeypatch.setattr(user_routes, "authenticate_user", lambda account, password: None)
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))

    monkeypatch.setattr(user_routes, "get_user_by_account", lambda account: None, raising=False)
    unknown = _user_app().test_client().post("/user/login", data={"account": "missing", "password": "x"})
    assert unknown.status_code == 401
    assert "账号或密码错误" in unknown.get_data(as_text=True)
    assert events[-1]["error_code"] == "invalid_credentials"
    assert events[-1]["target_user"].get("id") is None

    disabled_user = {"id": 9, "username": "disabled", "status": "disabled"}
    monkeypatch.setattr(user_routes, "get_user_by_account", lambda account: disabled_user, raising=False)
    disabled = _user_app().test_client().post("/user/login", data={"account": "disabled", "password": "x"})
    assert disabled.status_code == 401
    assert "账号或密码错误" in disabled.get_data(as_text=True)
    assert events[-1]["error_code"] == "account_disabled"
    assert events[-1]["target_user"]["id"] == 9


def test_user_logout_and_disabled_session_rejection_are_audited(monkeypatch):
    active = {"id": 10, "username": "carol", "status": "active"}
    disabled = {"id": 10, "username": "carol", "status": "disabled"}
    events = []
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))

    monkeypatch.setattr(user_routes, "get_user_by_id", lambda user_id: active)
    client = _user_app().test_client()
    with client.session_transaction() as session:
        session["user_id"] = 10
        session["stale_sensitive_value"] = "must-be-cleared"
    response = client.post("/user/logout")
    assert response.status_code == 302
    assert events[-1]["action_code"] == "user.auth.logout"
    assert events[-1]["target_user"]["id"] == 10
    with client.session_transaction() as session:
        assert not session

    monkeypatch.setattr(user_routes, "get_user_by_id", lambda user_id: disabled)
    client = _user_app().test_client()
    with client.session_transaction() as session:
        session["user_id"] = 10
    rejected = client.get("/user/dashboard")
    assert rejected.status_code == 302
    assert "/user/login" in rejected.headers["Location"]
    assert events[-1]["action_code"] == "user.auth.session_rejected"
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_admin_login_success_failure_and_logout_are_audited(monkeypatch):
    events = []
    monkeypatch.setattr(admin_member_routes, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(admin_member_routes, "verify_admin_password", lambda password: password == "admin-pass")
    from services.admin_auth import AdminCertificateVerification
    monkeypatch.setattr(
        admin_member_routes,
        "verify_admin_client_certificate_request",
        lambda: AdminCertificateVerification(True, "ok", "", {"id": 1, "device_name": "test", "fingerprint_sha256": "AB" * 32}),
    )
    monkeypatch.setattr(admin_member_routes, "verify_admin_captcha", lambda session_obj, supplied: supplied == "aB3Cd")
    monkeypatch.setattr(admin_member_routes, "touch_certificate_use", lambda *args, **kwargs: True)
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    client = _admin_app().test_client()

    failed = client.post("/admin/login", data={"username": "admin", "password": "wrong-secret", "captcha": "aB3Cd"})
    assert failed.status_code == 401
    assert events[-1]["action_code"] == "admin.auth.login_failed"
    assert events[-1]["actor_type"] == "anonymous"
    assert "wrong-secret" not in str(events[-1])

    success = client.post("/admin/login", data={"username": "admin", "password": "admin-pass", "captcha": "aB3Cd"})
    assert success.status_code == 302
    assert events[-1]["action_code"] == "admin.auth.login_success"
    assert events[-1]["actor_type"] == "admin"
    with client.session_transaction() as session:
        assert session["admin_logged_in"] is True
        assert session.get("admin_csrf_token")

    logout = client.post("/admin/logout")
    assert logout.status_code == 302
    assert events[-1]["action_code"] == "admin.auth.logout"
    with client.session_transaction() as session:
        assert "admin_logged_in" not in session

def test_user_login_rejects_oversized_input_before_authentication(monkeypatch):
    auth_calls = []
    monkeypatch.setattr(
        user_routes,
        "authenticate_user",
        lambda account, password: auth_calls.append((account, password)) or None,
    )

    response = _user_app().test_client().post(
        "/user/login",
        data={"account": "x" * 255, "password": "secret"},
    )

    assert response.status_code == 400
    assert "登录请求无效" in response.get_data(as_text=True)
    assert auth_calls == []

