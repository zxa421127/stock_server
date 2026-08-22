from __future__ import annotations

from types import SimpleNamespace

from services.production_readiness import collect_configuration_errors


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
        ADMIN_PASSWORD_HASH="pbkdf2_sha256$1000$YQ==$Yg==",
        ADMIN_CLIENT_CERT_REQUIRED=True,
        ADMIN_CLIENT_CERT_PROXY_SECRET="p" * 48,
        ADMIN_CLIENT_CERT_ADMIN_HOST="admin-api.example.com",
        API_TOKEN_HASH_SECRET="t" * 64,
        AUDIT_TOKEN_HMAC_SECRET="a" * 64,
        REDIS_REQUIRED=True,
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


def test_hardened_client_certificate_configuration_passes():
    assert collect_configuration_errors(_settings(), redis_getter=lambda: HealthyRedis()) == []


def test_missing_client_certificate_configuration_is_rejected():
    errors = collect_configuration_errors(
        _settings(ADMIN_CLIENT_CERT_REQUIRED=False, ADMIN_CLIENT_CERT_PROXY_SECRET="", ADMIN_CLIENT_CERT_ADMIN_HOST=""),
        redis_getter=lambda: HealthyRedis(),
    )
    joined = " ".join(errors)
    assert "ADMIN_CLIENT_CERT_REQUIRED" in joined
    assert "ADMIN_CLIENT_CERT_PROXY_SECRET" in joined
    assert "ADMIN_CLIENT_CERT_ADMIN_HOST" in joined
