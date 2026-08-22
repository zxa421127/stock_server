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


def test_registration_success_and_validation_failure_are_audited_without_passwords(monkeypatch):
    events = []
    monkeypatch.setattr(user_routes.config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", False)
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(user_routes, "register_user", lambda **kwargs: (
        {"id": 5, "username": kwargs["username"], "phone": kwargs["phone"], "email": kwargs["email"]},
        "TOKEN",
    ))
    monkeypatch.setattr(user_routes, "_sync_user_to_feishu_safely", lambda *args, **kwargs: None)
    client = _user_app().test_client()

    response = client.post("/user/register", data={
        "username": "alice",
        "password": "secret-one-2026",
        "password2": "secret-one-2026",
        "phone": "13812345678",
        "email": "alice@example.com",
    })
    assert response.status_code == 200
    assert events[-1]["action_code"] == "user.register"
    assert events[-1]["success"] is True
    assert events[-1]["target_user"]["id"] == 5
    assert "password" not in str(events[-1]["request_data"]).lower()
    assert "secret-one-2026" not in str(events[-1])

    response = client.post("/user/register", data={
        "username": "alice",
        "password": "pwd-one-secret-781",
        "password2": "pwd-two-secret-992",
        "phone": "13812345678",
    })
    assert response.status_code == 400
    assert events[-1]["action_code"] == "user.register"
    assert events[-1]["success"] is False
    assert "pwd-one-secret-781" not in str(events[-1])
    assert "pwd-two-secret-992" not in str(events[-1])


def test_user_password_change_success_and_failure_are_audited_without_secret_values(monkeypatch):
    events = []
    user = {"id": 7, "username": "alice", "phone": "13812345678", "email": "a@example.com"}
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(user_routes, "_current_user", lambda: user)
    monkeypatch.setattr(user_routes, "change_user_password", lambda user_id, current, new: user)
    client = _user_app().test_client()

    response = client.post("/user/change-password", data={
        "current_password": "old-secret",
        "new_password": "new-secret",
        "new_password2": "new-secret",
    })
    assert response.status_code == 200
    assert events[-1]["action_code"] == "user.password_change"
    assert events[-1]["success"] is True
    assert events[-1]["request_data"] == {"password_changed": True}
    assert "old-secret" not in str(events[-1])
    assert "new-secret" not in str(events[-1])

    response = client.post("/user/change-password", data={
        "current_password": "old-secret",
        "new_password": "new-secret",
        "new_password2": "different",
    })
    assert response.status_code == 400
    assert events[-1]["success"] is False
    assert events[-1]["request_data"] == {"password_changed": False}
    assert "different" not in str(events[-1])


def test_admin_subscription_success_maps_action_code_and_captures_before_after(monkeypatch):
    events = []
    user = {"id": 9, "username": "bob", "phone": "13912345678", "email": "b@example.com"}
    before = {"id": 1, "plan_code": "general_month", "expire_time": "2026-08-01 00:00:00"}
    after = {
        "action_type": "renew", "action_label": "续费当前套餐", "plan_code": "general_month",
        "plan_name": "通用月卡", "start_time": "2026-07-01 00:00:00", "expire_time": "2026-09-01 00:00:00",
        "extra_days": 0,
    }
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(admin_member_routes, "get_user_by_id", lambda user_id: user)
    monkeypatch.setattr(admin_member_routes, "get_active_subscription", lambda user_id: before)
    monkeypatch.setattr(admin_member_routes, "get_scheduled_subscriptions", lambda user_id: [])
    monkeypatch.setattr(admin_member_routes, "get_or_create_api_key", lambda user_id: "TOKEN")
    monkeypatch.setattr(admin_member_routes, "apply_subscription_action", lambda **kwargs: after)
    monkeypatch.setattr(admin_member_routes, "_sync_user_to_feishu_safely", lambda *args, **kwargs: None)
    app = _admin_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post("/admin/members/open", data={
        "user_id": "9", "plan_code": "general_month", "action_type": "renew",
        "extra_days": "0", "amount_cent": "4900", "remark": "续费",
    })
    assert response.status_code == 200
    event = events[-1]
    assert event["action_code"] == "admin.subscription_renew"
    assert event["success"] is True
    assert event["before_data"]["current_subscription"]["plan_code"] == "general_month"
    assert event["after_data"]["plan_code"] == "general_month"
    assert "TOKEN" not in str(event)


def test_admin_subscription_validation_failure_and_password_reset_are_audited(monkeypatch):
    events = []
    user = {"id": 9, "username": "bob", "phone": "13912345678", "email": "b@example.com"}
    monkeypatch.setattr(admin_member_routes, "record_operation", lambda **kwargs: events.append(kwargs) or ("e", True))
    monkeypatch.setattr(admin_member_routes, "get_user_by_id", lambda user_id: user)
    monkeypatch.setattr(admin_member_routes, "admin_reset_user_password", lambda user_id, new_password: user)
    monkeypatch.setattr(
        admin_member_routes,
        "verify_admin_high_risk_confirmation",
        lambda *args: type("Confirmation", (), {"ok": True, "code": "ok", "message": ""})(),
    )
    app = _admin_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post("/admin/members/open", data={"user_id": "9", "action_type": "renew"})
    assert response.status_code == 400
    assert events[-1]["success"] is False
    assert events[-1]["action_category"] == "membership"

    response = client.post("/admin/users/reset-password", data={
        "user_id": "9", "new_password": "admin-secret", "new_password2": "admin-secret",
    })
    assert response.status_code == 200
    assert events[-1]["action_code"] == "admin.user_password_reset"
    assert events[-1]["request_data"] == {"password_changed": True}
    assert "admin-secret" not in str(events[-1])

def test_admin_password_reset_requires_high_risk_confirmation(monkeypatch):
    events = []
    reset_calls = []
    user = {"id": 9, "username": "bob", "phone": "13912345678", "email": "b@example.com"}

    monkeypatch.setattr(
        admin_member_routes,
        "record_operation",
        lambda **kwargs: events.append(kwargs) or ("e", True),
    )
    monkeypatch.setattr(admin_member_routes, "get_user_by_id", lambda user_id: user)
    monkeypatch.setattr(
        admin_member_routes,
        "admin_reset_user_password",
        lambda user_id, new_password: reset_calls.append((user_id, new_password)) or user,
    )
    monkeypatch.setattr(
        admin_member_routes,
        "verify_admin_high_risk_confirmation",
        lambda *args: type(
            "Confirmation",
            (),
            {
                "ok": False,
                "code": "confirmation_text_invalid",
                "message": "高风险操作确认文字不匹配",
            },
        )(),
    )

    app = _admin_app()
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_logged_in"] = True

    response = client.post(
        "/admin/users/reset-password",
        data={
            "user_id": "9",
            "new_password": "admin-secret",
            "new_password2": "admin-secret",
            "admin_password": "admin-current-password",
            "confirmation_text": "WRONG PHRASE",
        },
    )

    assert response.status_code == 403
    assert reset_calls == []
    assert events[-1]["action_code"] == "admin.user_password_reset"
    assert events[-1]["error_code"] == "confirmation_text_invalid"
    assert "admin-current-password" not in str(events[-1])
    assert "WRONG PHRASE" not in str(events[-1])

