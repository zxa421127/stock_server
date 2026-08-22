from __future__ import annotations

from dataclasses import dataclass

from flask import Flask

import config
import db_utils
from routes import user_routes
from services import member_service


def _app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret-" * 8
    app.register_blueprint(user_routes.user_bp, url_prefix="/user")
    return app


class AllowLimiter:
    def __init__(self):
        self.keys = []
    def check_and_record(self, key):
        self.keys.append(key)
        return True
    def clear(self, key):
        return None


def test_registration_page_uses_captcha_and_no_device_fingerprint(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", True, raising=False)
    monkeypatch.setattr(config, "REGISTRATION_EMAIL_VERIFICATION_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "REGISTRATION_SMS_VERIFICATION_ENABLED", False, raising=False)
    body = _app().test_client().get("/user/register").get_data(as_text=True)
    assert "/user/register/captcha.png" in body
    assert 'name="captcha"' in body
    assert 'name="verification_channel"' in body
    assert "device" not in body.lower()
    assert "fingerprint" not in body.lower()


def test_first_registration_step_counts_limits_and_does_not_create_user(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", True, raising=False)
    ip_limiter = AllowLimiter()
    global_limiter = AllowLimiter()
    monkeypatch.setattr(user_routes, "_registration_limiter", ip_limiter)
    monkeypatch.setattr(user_routes, "_registration_global_limiter", global_limiter)
    monkeypatch.setattr(user_routes, "verify_captcha", lambda *args, **kwargs: True)
    monkeypatch.setattr(user_routes, "get_user_by_account", lambda value: None)
    monkeypatch.setattr(user_routes, "hash_password", lambda value: "pbkdf2$hash")

    created = []

    @dataclass
    class Challenge:
        challenge_id: str = "challenge-1"
        code: str = "123456"
        channel: str = "email"
        target: str = "alice@example.com"
        expires_at_ts: int = 9999999999

    monkeypatch.setattr(user_routes, "create_challenge", lambda **kwargs: created.append(kwargs) or Challenge())
    monkeypatch.setattr(user_routes, "send_email_code", lambda address, code: None)
    monkeypatch.setattr(
        user_routes,
        "register_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("user must not exist before verification")),
    )

    client = _app().test_client()
    response = client.post(
        "/user/register",
        data={
            "username": "alice",
            "password": "A secure passphrase 123",
            "password2": "A secure passphrase 123",
            "phone": "",
            "email": "alice@example.com",
            "captcha": "ABCDE",
            "verification_channel": "email",
        },
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 202
    assert "输入验证码" in body
    assert len(ip_limiter.keys) == 1
    assert len(global_limiter.keys) == 1
    assert created[0]["payload"]["password_hash"] == "pbkdf2$hash"
    with client.session_transaction() as sess:
        assert sess["registration_challenge_id"] == "challenge-1"
        assert "password" not in repr(dict(sess)).lower()


def test_verification_completes_registration_and_establishes_versioned_session(monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", True, raising=False)
    ip_limiter = AllowLimiter()
    global_limiter = AllowLimiter()
    monkeypatch.setattr(user_routes, "_registration_limiter", ip_limiter)
    monkeypatch.setattr(user_routes, "_registration_global_limiter", global_limiter)
    monkeypatch.setattr(
        user_routes,
        "verify_and_consume_challenge",
        lambda challenge_id, code: {
            "username": "alice",
            "password_hash": "pbkdf2$hash",
            "phone": None,
            "email": "alice@example.com",
            "_verified_channel": "email",
            "_verified_target": "alice@example.com",
        },
    )
    monkeypatch.setattr(
        user_routes,
        "register_verified_user",
        lambda **kwargs: ({"id": 7, "username": "alice", "session_version": 3}, "TOKEN-ONCE"),
    )
    monkeypatch.setattr(user_routes, "record_operation", lambda **kwargs: ("event", True))
    monkeypatch.setattr(user_routes, "_sync_user_to_feishu_safely", lambda *args, **kwargs: None)

    client = _app().test_client()
    with client.session_transaction() as sess:
        sess["registration_challenge_id"] = "challenge-1"
    response = client.post("/user/register/verify", data={"code": "123456"})
    assert response.status_code == 200
    assert "TOKEN-ONCE" in response.get_data(as_text=True)
    with client.session_transaction() as sess:
        assert sess["user_id"] == 7
        assert sess["user_session_version"] == 3
        assert "registration_challenge_id" not in sess


def test_verification_is_rate_limited_before_challenge_verification(monkeypatch):
    class RecordingLimiter:
        def __init__(self, allowed):
            self.allowed = bool(allowed)
            self.keys = []

        def check_and_record(self, key):
            self.keys.append(key)
            return self.allowed

        def clear(self, key):
            return None

    verification_calls = []

    def forbidden_verification(*args, **kwargs):
        verification_calls.append((args, kwargs))
        raise AssertionError(
            "verify_and_consume_challenge must not run after registration rate limit"
        )

    monkeypatch.setattr(
        user_routes,
        "verify_and_consume_challenge",
        forbidden_verification,
    )

    client = _app().test_client()
    with client.session_transaction() as sess:
        sess["registration_challenge_id"] = "challenge-rate-limited"

    # Case 1: IP limiter denies, global limiter allows.
    ip_limiter = RecordingLimiter(False)
    global_limiter = RecordingLimiter(True)
    monkeypatch.setattr(user_routes, "_registration_limiter", ip_limiter)
    monkeypatch.setattr(
        user_routes,
        "_registration_global_limiter",
        global_limiter,
    )

    response = client.post(
        "/user/register/verify",
        data={"code": "123456"},
    )

    assert response.status_code == 429
    assert "注册请求过于频繁" in response.get_data(as_text=True)
    assert len(ip_limiter.keys) == 1
    assert global_limiter.keys == ["registration-global"]
    assert verification_calls == []

    # Case 2: IP limiter allows, global limiter denies.
    ip_limiter = RecordingLimiter(True)
    global_limiter = RecordingLimiter(False)
    monkeypatch.setattr(user_routes, "_registration_limiter", ip_limiter)
    monkeypatch.setattr(
        user_routes,
        "_registration_global_limiter",
        global_limiter,
    )

    response = client.post(
        "/user/register/verify",
        data={"code": "654321"},
    )

    assert response.status_code == 429
    assert "注册请求过于频繁" in response.get_data(as_text=True)
    assert len(ip_limiter.keys) == 1
    assert global_limiter.keys == ["registration-global"]
    assert verification_calls == []


def _use_database(monkeypatch, path):
    db_utils.close_thread_connection()
    monkeypatch.setattr(db_utils, "DB_FILE", str(path))
    monkeypatch.setattr(db_utils, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "APP_ENV", "test")
    db_utils._db_pragmas_initialized = False
    db_utils.init_db()


def test_register_verified_user_sets_only_verified_contact_timestamp(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "registered.db")
    user, token = member_service.register_verified_user(
        username="alice",
        password_hash=member_service.hash_password("A secure passphrase 123"),
        phone="+4915123456789",
        email="alice@example.com",
        verified_channel="email",
        verified_target="alice@example.com",
    )
    assert token.startswith("SK_STOCK_API_")
    assert user["email_verified_at"]
    assert user["phone_verified_at"] is None
    assert user["session_version"] == 1
    assert user["registration_status"] == "active"
