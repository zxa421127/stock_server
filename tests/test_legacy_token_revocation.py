from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from services.production_readiness import collect_configuration_errors
from tools.db.migrate_legacy_tokens import count_active_legacy_tokens, revoke_legacy_tokens


def _legacy_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE api_tokens (
            id INTEGER PRIMARY KEY,
            token TEXT,
            expire_time TEXT,
            status TEXT
        );
        INSERT INTO api_tokens VALUES (1,'ACTIVE1','2039-01-01 00:00:00','有效');
        INSERT INTO api_tokens VALUES (2,'ACTIVE2','2039-01-01 00:00:00','active');
        INSERT INTO api_tokens VALUES (3,'DISABLED','2039-01-01 00:00:00','disabled');
        """
    )
    conn.commit()
    return conn


def test_legacy_tokens_are_revoked_not_promoted(tmp_path):
    conn = _legacy_db(tmp_path / "legacy.db")
    assert count_active_legacy_tokens(conn) == 2
    assert revoke_legacy_tokens(conn, dry_run=True) == 2
    assert count_active_legacy_tokens(conn) == 2
    assert revoke_legacy_tokens(conn) == 2
    assert count_active_legacy_tokens(conn) == 0
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'"
    ).fetchone() is None
    statuses = [row[0] for row in conn.execute("SELECT status FROM api_tokens ORDER BY id")]
    assert statuses == ["revoked", "revoked", "disabled"]


def test_production_readiness_rejects_active_legacy_tokens(tmp_path):
    path = tmp_path / "legacy.db"
    conn = _legacy_db(path)
    conn.close()
    settings = SimpleNamespace(
        APP_ENV="production",
        SECRET_KEY="S" * 64,
        ADMIN_PASSWORD_HASH="pbkdf2_sha256$600000$salt$digest",
        ADMIN_PASSWORD="please-change-password",
        ADMIN_CLIENT_CERT_REQUIRED=True,
        ADMIN_CLIENT_CERT_PROXY_SECRET="P" * 64,
        ADMIN_CLIENT_CERT_ADMIN_HOST="admin.example.com",
        API_TOKEN_HASH_SECRET="T" * 64,
        CONTACT_VERIFICATION_HMAC_SECRET="V" * 64,
        SESSION_COOKIE_SECURE=True,
        ALLOW_INSECURE_DEFAULTS=False,
        DB_AUTO_MIGRATE=False,
        REDIS_REQUIRED=True,
        REDIS_URL="redis://localhost/0",
        SERVER_HOST="127.0.0.1",
        TRUST_PROXY_HEADERS=True,
        PROXY_FIX_X_FOR=1,
        PROXY_FIX_X_PROTO=1,
        REQUIRE_EXTERNAL_WORKERS=False,
        REGISTRATION_CONTACT_VERIFICATION_REQUIRED=True,
        REGISTRATION_EMAIL_VERIFICATION_ENABLED=True,
        SMTP_HOST="smtp.example.com",
        SMTP_FROM_ADDRESS="noreply@example.com",
        REGISTRATION_SMS_VERIFICATION_ENABLED=False,
        TUSHARE_API_URL="https://relay.example.com/dataapi",
        TUSHARE_ALLOWED_RELAY_HOSTS=["relay.example.com"],
        DB_FILE=str(path),
    )

    class Redis:
        def ping(self):
            return True

    errors = collect_configuration_errors(settings, redis_getter=lambda: Redis())
    assert any("旧api_tokens" in item for item in errors)
