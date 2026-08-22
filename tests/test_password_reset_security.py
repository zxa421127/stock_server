from __future__ import annotations

from flask import Flask

from routes import user_routes


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(user_routes.user_bp, url_prefix="/user")
    return app


def test_forgot_password_no_longer_accepts_a_new_password():
    response = _app().test_client().get("/user/forgot-password")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="contact"' in body
    assert 'name="new_password"' not in body
    assert 'name="new_password2"' not in body


def test_forgot_password_creates_review_request_and_returns_generic_message(monkeypatch):
    calls = []
    events = []
    monkeypatch.setattr(
        user_routes,
        "submit_password_reset_request",
        lambda account, contact: calls.append((account, contact)) or 42,
        raising=False,
    )
    monkeypatch.setattr(
        user_routes,
        "record_operation",
        lambda **kwargs: events.append(kwargs) or ("event", True),
    )
    user_routes._password_reset_limiter.clear("127.0.0.1|alice")

    response = _app().test_client().post(
        "/user/forgot-password",
        data={"account": "alice", "contact": "alice@example.com"},
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 202
    assert calls == [("alice", "alice@example.com")]
    assert "申请已接收" in body
    assert "用户ID" not in body
    assert events[-1]["action_code"] == "user.password_reset_request"
    assert events[-1]["request_data"] == {"account_supplied": True, "contact_supplied": True}
