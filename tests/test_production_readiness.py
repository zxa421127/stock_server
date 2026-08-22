from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.production_readiness import (
    assert_production_ready,
    collect_configuration_errors,
)


class HealthyRedis:
    def ping(self):
        return True


def _settings(**overrides):
    values = dict(
        APP_ENV="production",
        SERVER_HOST="127.0.0.1",
        ALLOW_DIRECT_PUBLIC_BIND=False,
        TRUST_PROXY_HEADERS=True,
        PROXY_FIX_X_FOR=1,
        PROXY_FIX_X_PROTO=1,
        SECRET_KEY="s" * 64,
        ADMIN_PASSWORD="please-change-password",
        ADMIN_CLIENT_CERT_REQUIRED=True,
        ADMIN_CLIENT_CERT_PROXY_SECRET="p" * 48,
        ADMIN_CLIENT_CERT_ADMIN_HOST="admin-api.example.com",
        REDIS_REQUIRED=True,
        ADMIN_PASSWORD_HASH="pbkdf2_sha256$1000$YQ==$Yg==",
        API_TOKEN_HASH_SECRET="t" * 64,
        AUDIT_TOKEN_HMAC_SECRET="a" * 64,
        REDIS_URL="redis://127.0.0.1:6379/0",
        SESSION_COOKIE_SECURE=True,
        ALLOW_INSECURE_DEFAULTS=False,
        DB_AUTO_MIGRATE=False,
        REQUIRE_EXTERNAL_WORKERS=True,
        ADMIN_API_TEST_IN_PROCESS_WORKER=False,
        ENABLE_IN_PROCESS_FEISHU_WORKER=False,
        API_DOC_STATUS_IN_PROCESS=False,
        KAIPANLA_SNAPSHOT_IN_PROCESS=False,
        TUSHARE_SPEC_MONITOR_IN_PROCESS=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_production_configuration_accepts_hardened_settings():
    assert collect_configuration_errors(_settings(), redis_getter=lambda: HealthyRedis()) == []


def test_production_configuration_rejects_plaintext_and_missing_redis():
    errors = collect_configuration_errors(
        _settings(ADMIN_PASSWORD_HASH="", REDIS_URL="", DB_AUTO_MIGRATE=True),
        redis_getter=lambda: None,
    )
    joined = " ".join(errors)
    assert "ADMIN_PASSWORD_HASH" in joined
    assert "REDIS_URL" in joined
    assert "DB_AUTO_MIGRATE" in joined


def test_production_configuration_rejects_in_process_workers():
    errors = collect_configuration_errors(
        _settings(ADMIN_API_TEST_IN_PROCESS_WORKER=True),
        redis_getter=lambda: HealthyRedis(),
    )
    assert any("ADMIN_API_TEST_IN_PROCESS_WORKER" in item for item in errors)


def test_production_configuration_rejects_plaintext_and_disabled_client_certificate_auth():
    errors = collect_configuration_errors(
        _settings(ADMIN_PASSWORD="still-plaintext", ADMIN_CLIENT_CERT_REQUIRED=False),
        redis_getter=lambda: HealthyRedis(),
    )
    joined = " ".join(errors)
    assert "ADMIN_PASSWORD明文" in joined
    assert "ADMIN_CLIENT_CERT_REQUIRED" in joined


def test_production_configuration_rejects_public_placeholder_secrets():
    errors = collect_configuration_errors(
        _settings(
            API_TOKEN_HASH_SECRET="CHANGE_ME_TO_A_RANDOM_SECRET_AT_LEAST_32_CHARS",
            AUDIT_TOKEN_HMAC_SECRET="REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARS",
            REGISTRATION_CONTACT_VERIFICATION_REQUIRED=True,
            REGISTRATION_EMAIL_VERIFICATION_ENABLED=True,
            REGISTRATION_SMS_VERIFICATION_ENABLED=False,
            CONTACT_VERIFICATION_HMAC_SECRET="CHANGE_ME_TO_AN_INDEPENDENT_RANDOM_SECRET_AT_LEAST_32_CHARS",
            SMTP_HOST="smtp.example.com",
            SMTP_FROM_ADDRESS="noreply@example.com",
        ),
        redis_getter=lambda: HealthyRedis(),
    )
    joined = " ".join(errors)
    assert "API_TOKEN_HASH_SECRET" in joined
    assert "AUDIT_TOKEN_HMAC_SECRET" in joined
    assert "CONTACT_VERIFICATION_HMAC_SECRET" in joined


def test_production_configuration_rejects_placeholder_sms_webhook_secret():
    errors = collect_configuration_errors(
        _settings(
            REGISTRATION_CONTACT_VERIFICATION_REQUIRED=True,
            REGISTRATION_EMAIL_VERIFICATION_ENABLED=False,
            REGISTRATION_SMS_VERIFICATION_ENABLED=True,
            CONTACT_VERIFICATION_HMAC_SECRET="v" * 64,
            SMS_VERIFY_WEBHOOK_URL="https://sms.example.com/send",
            SMS_VERIFY_WEBHOOK_SECRET="CHANGE_ME_TO_A_RANDOM_SMS_SECRET_AT_LEAST_32_CHARS",
        ),
        redis_getter=lambda: HealthyRedis(),
    )
    assert any("SMS_VERIFY_WEBHOOK_SECRET" in item for item in errors)

def test_assert_production_ready_fails_closed_on_public_placeholder_secrets():
    settings = _settings(
        API_TOKEN_HASH_SECRET="CHANGE_ME_TO_A_RANDOM_SECRET_AT_LEAST_32_CHARS",
        AUDIT_TOKEN_HMAC_SECRET="REPLACE_WITH_A_RANDOM_SECRET_AT_LEAST_32_CHARS",
        REGISTRATION_CONTACT_VERIFICATION_REQUIRED=True,
        REGISTRATION_EMAIL_VERIFICATION_ENABLED=True,
        REGISTRATION_SMS_VERIFICATION_ENABLED=False,
        CONTACT_VERIFICATION_HMAC_SECRET="CHANGE_ME_TO_AN_INDEPENDENT_RANDOM_SECRET_AT_LEAST_32_CHARS",
        SMTP_HOST="smtp.example.com",
        SMTP_FROM_ADDRESS="noreply@example.com",
    )

    with pytest.raises(RuntimeError) as exc_info:
        assert_production_ready(
            settings,
            redis_getter=lambda: HealthyRedis(),
        )

    message = str(exc_info.value)
    assert "API_TOKEN_HASH_SECRET" in message
    assert "AUDIT_TOKEN_HMAC_SECRET" in message
    assert "CONTACT_VERIFICATION_HMAC_SECRET" in message

