from __future__ import annotations

import json

import pytest

import config
import db_utils
from services import contact_verification, notification_delivery


def _use_database(monkeypatch, path):
    db_utils.close_thread_connection()
    monkeypatch.setattr(db_utils, "DB_FILE", str(path))
    monkeypatch.setattr(config, "DB_FILE", str(path), raising=False)
    monkeypatch.setattr(db_utils, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "API_TOKEN_HASH_SECRET", "T" * 48)
    monkeypatch.setattr(config, "CONTACT_VERIFICATION_HMAC_SECRET", "V" * 48, raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test")
    db_utils._db_pragmas_initialized = False
    db_utils.init_db()


def test_challenge_stores_digest_payload_hash_and_consumes_once(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "contact.db")
    monkeypatch.setattr(contact_verification.secrets, "randbelow", lambda n: 123456)
    challenge = contact_verification.create_challenge(
        purpose="registration",
        channel="email",
        target="user@example.com",
        payload={"username": "alice", "password_hash": "pbkdf2$secret"},
        now_ts=1_000,
    )
    row = db_utils.get_conn().execute(
        "SELECT * FROM contact_verification_challenges WHERE challenge_id=?",
        (challenge.challenge_id,),
    ).fetchone()
    assert row["code_hash"] != challenge.code
    assert challenge.code not in row["payload_json"]
    assert json.loads(row["payload_json"])["username"] == "alice"

    payload = contact_verification.verify_and_consume_challenge(
        challenge.challenge_id, challenge.code, now_ts=1_001
    )
    assert payload["username"] == "alice"
    with pytest.raises(ValueError, match="已使用"):
        contact_verification.verify_and_consume_challenge(
            challenge.challenge_id, challenge.code, now_ts=1_002
        )


def test_challenge_expires_limits_attempts_and_enforces_resend_cooldown(tmp_path, monkeypatch):
    _use_database(monkeypatch, tmp_path / "limits.db")
    monkeypatch.setattr(config, "CONTACT_CODE_MAX_ATTEMPTS", 2, raising=False)
    monkeypatch.setattr(config, "CONTACT_CODE_RESEND_SECONDS", 60, raising=False)
    challenge = contact_verification.create_challenge(
        purpose="registration",
        channel="sms",
        target="+4915123456789",
        payload={"username": "bob"},
        now_ts=1_000,
    )
    with pytest.raises(ValueError, match="发送过于频繁"):
        contact_verification.create_challenge(
            purpose="registration",
            channel="sms",
            target="+4915123456789",
            payload={"username": "bob"},
            now_ts=1_020,
        )
    with pytest.raises(ValueError, match="验证码错误"):
        contact_verification.verify_and_consume_challenge(challenge.challenge_id, "000000", now_ts=1_001)
    with pytest.raises(ValueError, match="验证码错误"):
        contact_verification.verify_and_consume_challenge(challenge.challenge_id, "000001", now_ts=1_002)
    with pytest.raises(ValueError, match="尝试次数过多"):
        contact_verification.verify_and_consume_challenge(challenge.challenge_id, challenge.code, now_ts=1_003)

    expired = contact_verification.create_challenge(
        purpose="registration",
        channel="email",
        target="expired@example.com",
        payload={"username": "eve"},
        now_ts=2_000,
        ttl_seconds=300,
    )
    with pytest.raises(ValueError, match="已过期"):
        contact_verification.verify_and_consume_challenge(expired.challenge_id, expired.code, now_ts=2_301)


def test_email_delivery_uses_smtp_tls_without_logging_code(monkeypatch):
    events = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            events.append(("connect", host, port, timeout))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def ehlo(self):
            events.append(("ehlo",))
        def starttls(self):
            events.append(("starttls",))
        def login(self, username, password):
            events.append(("login", username, password))
        def send_message(self, message):
            events.append(("send", message["To"], message.get_content()))

    monkeypatch.setattr(notification_delivery.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.com", raising=False)
    monkeypatch.setattr(config, "SMTP_PORT", 587, raising=False)
    monkeypatch.setattr(config, "SMTP_USERNAME", "mailer", raising=False)
    monkeypatch.setattr(config, "SMTP_PASSWORD", "password", raising=False)
    monkeypatch.setattr(config, "SMTP_FROM_ADDRESS", "noreply@example.com", raising=False)
    monkeypatch.setattr(config, "SMTP_USE_TLS", True, raising=False)
    monkeypatch.setattr(config, "SMTP_USE_SSL", False, raising=False)
    notification_delivery.send_email_code("user@example.com", "123456")
    assert ("starttls",) in events
    assert any(item[0] == "send" and item[1] == "user@example.com" and "123456" in item[2] for item in events)


def test_sms_delivery_signs_generic_webhook_and_disables_redirects(monkeypatch):
    captured = {}

    class Response:
        status_code = 202
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(notification_delivery.requests, "post", fake_post)
    monkeypatch.setattr(config, "SMS_VERIFY_WEBHOOK_URL", "https://sms.example/send", raising=False)
    monkeypatch.setattr(config, "SMS_VERIFY_WEBHOOK_SECRET", "S" * 48, raising=False)
    monkeypatch.setattr(notification_delivery.time, "time", lambda: 1_700_000_000)
    notification_delivery.send_sms_code("+4915123456789", "654321")
    assert captured["allow_redirects"] is False
    assert captured["timeout"] > 0
    assert captured["json"] == {"phone": "+4915123456789", "code": "654321", "purpose": "registration"}
    assert captured["headers"]["X-Stock-Timestamp"] == "1700000000"
    assert len(captured["headers"]["X-Stock-Signature"]) == 64
