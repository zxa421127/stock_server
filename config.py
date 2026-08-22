# -*- coding: utf-8 -*-
"""Application configuration loaded from the project-level .env file."""
from __future__ import annotations

import calendar
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _get_float(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _get_list(name: str, default: str = "") -> list[str]:
    return [part.strip() for part in os.getenv(name, default).split(",") if part.strip()]


def _get_int_map(
    name: str,
    default: str = "",
    *,
    minimum: int = 0,
    maximum: int = 604800,
) -> dict[str, int]:
    """Parse comma-separated ``name=seconds`` settings safely.

    Invalid items are ignored instead of preventing the service from starting.
    API names are normalized to lower-case underscore form.
    """
    result: dict[str, int] = {}
    raw = os.getenv(name, default)
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip().lower().replace("-", "_")
        if not key:
            continue
        try:
            seconds = int(value.strip())
        except (TypeError, ValueError):
            continue
        result[key] = max(minimum, min(seconds, maximum))
    return result


# Database
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR
# Keep the code default aligned with the deployed database name.  This also
# prevents an empty stock_server.db being created if .env is temporarily absent.
DB_FILE = Path(os.getenv("DB_FILE", str(DATA_DIR / "tokens.db")))
if not DB_FILE.is_absolute():
    DB_FILE = BASE_DIR / DB_FILE
DB_FILE = str(DB_FILE.resolve())

# HTTP server
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1").strip() or "127.0.0.1"
ALLOW_DIRECT_PUBLIC_BIND = _get_bool("ALLOW_DIRECT_PUBLIC_BIND", False)
SERVER_PORT = _get_int("SERVER_PORT", 8899, 1, 65535)
ENABLE_HTTP_ACCESS_LOG = _get_bool("ENABLE_HTTP_ACCESS_LOG", False)

# Flask/admin
APP_ENV = os.getenv("APP_ENV", "development").strip().lower() or "development"

# Deployment-slot identity guard. Local ad-hoc development can leave it off,
# but production and any explicit deployment slot fail closed unless enabled.
DEPLOYMENT_SLOT = os.getenv("DEPLOYMENT_SLOT", "").strip().lower()
ENVIRONMENT_GUARD_ENABLED = _get_bool("ENVIRONMENT_GUARD_ENABLED", False)
EXPECTED_PROJECT_ROOT = os.getenv("EXPECTED_PROJECT_ROOT", "").strip()
EXPECTED_RUNTIME_ROOT = os.getenv("EXPECTED_RUNTIME_ROOT", "").strip()
EXPECTED_SERVER_PORT = _get_int("EXPECTED_SERVER_PORT", 0, 0, 65535)
EXPECTED_REDIS_DB = _get_int("EXPECTED_REDIS_DB", -1, -1, 65535)
EXPECTED_REDIS_KEY_PREFIX = os.getenv("EXPECTED_REDIS_KEY_PREFIX", "").strip()
EXPECTED_ADMIN_HOST = os.getenv("EXPECTED_ADMIN_HOST", "").strip().lower()
SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-secret")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "please-change-password")  # development-only legacy fallback
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
# Legacy TOTP values remain readable for rollback compatibility, but production
# administrator authentication now uses project-managed mTLS client certificates.
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "").strip()
ADMIN_REQUIRE_MFA = _get_bool("ADMIN_REQUIRE_MFA", False)
ADMIN_CLIENT_CERT_REQUIRED = _get_bool("ADMIN_CLIENT_CERT_REQUIRED", APP_ENV == "production")
ADMIN_CLIENT_CERT_PROXY_SECRET = os.getenv("ADMIN_CLIENT_CERT_PROXY_SECRET", "").strip()
ADMIN_CLIENT_CERT_ADMIN_HOST = os.getenv("ADMIN_CLIENT_CERT_ADMIN_HOST", "").strip().lower()
ADMIN_CLIENT_CERT_VERIFY_HEADER = os.getenv("ADMIN_CLIENT_CERT_VERIFY_HEADER", "X-Admin-Client-Cert-Verify").strip()
ADMIN_CLIENT_CERT_PEM_HEADER = os.getenv("ADMIN_CLIENT_CERT_PEM_HEADER", "X-Admin-Client-Cert").strip()
ADMIN_CLIENT_CERT_DER_HEADER = os.getenv("ADMIN_CLIENT_CERT_DER_HEADER", "X-Admin-Client-Cert-DER").strip()
ADMIN_CLIENT_CERT_FINGERPRINT_HEADER = os.getenv("ADMIN_CLIENT_CERT_FINGERPRINT_HEADER", "X-Admin-Client-Cert-Fingerprint").strip()
ADMIN_CLIENT_CERT_SERIAL_HEADER = os.getenv("ADMIN_CLIENT_CERT_SERIAL_HEADER", "X-Admin-Client-Cert-Serial").strip()
ADMIN_CLIENT_CERT_SUBJECT_HEADER = os.getenv("ADMIN_CLIENT_CERT_SUBJECT_HEADER", "X-Admin-Client-Cert-Subject").strip()
ADMIN_CLIENT_CERT_PROXY_HEADER = os.getenv("ADMIN_CLIENT_CERT_PROXY_HEADER", "X-Admin-Proxy-Auth").strip()
ADMIN_CAPTCHA_LENGTH = _get_int("ADMIN_CAPTCHA_LENGTH", 5, 4, 8)
ADMIN_CAPTCHA_WIDTH = _get_int("ADMIN_CAPTCHA_WIDTH", 180, 120, 320)
ADMIN_CAPTCHA_HEIGHT = _get_int("ADMIN_CAPTCHA_HEIGHT", 58, 42, 120)
API_TOKEN_HASH_SECRET = os.getenv("API_TOKEN_HASH_SECRET", "").strip()
DB_AUTO_MIGRATE = _get_bool("DB_AUTO_MIGRATE", APP_ENV != "production")
REQUIRE_EXTERNAL_WORKERS = _get_bool("REQUIRE_EXTERNAL_WORKERS", APP_ENV == "production")
ADMIN_IP_WHITELIST = _get_list("ADMIN_IP_WHITELIST")
SESSION_COOKIE_SECURE = _get_bool("SESSION_COOKIE_SECURE", APP_ENV == "production")
SESSION_LIFETIME_MINUTES = _get_int("SESSION_LIFETIME_MINUTES", 480, 5, 10080)
ALLOW_INSECURE_DEFAULTS = _get_bool("ALLOW_INSECURE_DEFAULTS", False)
TRUST_PROXY_HEADERS = _get_bool("TRUST_PROXY_HEADERS", False)
PROXY_FIX_X_FOR = _get_int("PROXY_FIX_X_FOR", 1, 0, 5)
PROXY_FIX_X_PROTO = _get_int("PROXY_FIX_X_PROTO", 1, 0, 5)
PROXY_FIX_X_HOST = _get_int("PROXY_FIX_X_HOST", 0, 0, 5)
ADMIN_LOGIN_MAX_FAILURES = _get_int("ADMIN_LOGIN_MAX_FAILURES", 5, 1, 100)
ADMIN_LOGIN_WINDOW_SECONDS = _get_int("ADMIN_LOGIN_WINDOW_SECONDS", 900, 10, 86400)
ADMIN_LOGIN_LOCK_SECONDS = _get_int("ADMIN_LOGIN_LOCK_SECONDS", 900, 10, 86400)
USER_USERNAME_MIN_LENGTH = _get_int("USER_USERNAME_MIN_LENGTH", 3, 1, 64)
USER_USERNAME_MAX_LENGTH = _get_int("USER_USERNAME_MAX_LENGTH", 64, 3, 256)
USER_PASSWORD_MAX_LENGTH = _get_int("USER_PASSWORD_MAX_LENGTH", 128, 12, 1024)
USER_EMAIL_MAX_LENGTH = _get_int("USER_EMAIL_MAX_LENGTH", 254, 64, 1024)
USER_PHONE_MAX_LENGTH = _get_int("USER_PHONE_MAX_LENGTH", 32, 8, 128)
USER_ACCOUNT_MAX_LENGTH = _get_int("USER_ACCOUNT_MAX_LENGTH", 254, 64, 1024)
PASSWORD_RESET_CONTACT_MAX_LENGTH = _get_int("PASSWORD_RESET_CONTACT_MAX_LENGTH", 254, 32, 1024)
REGISTRATION_GLOBAL_MAX_REQUESTS = _get_int("REGISTRATION_GLOBAL_MAX_REQUESTS", 30, 1, 10000)
REGISTRATION_GLOBAL_WINDOW_SECONDS = _get_int("REGISTRATION_GLOBAL_WINDOW_SECONDS", 60, 10, 86400)
REGISTRATION_GLOBAL_LOCK_SECONDS = _get_int("REGISTRATION_GLOBAL_LOCK_SECONDS", 60, 10, 86400)
REGISTRATION_CAPTCHA_LENGTH = _get_int("REGISTRATION_CAPTCHA_LENGTH", 5, 4, 8)
REGISTRATION_CONTACT_VERIFICATION_REQUIRED = _get_bool("REGISTRATION_CONTACT_VERIFICATION_REQUIRED", APP_ENV == "production")
REGISTRATION_EMAIL_VERIFICATION_ENABLED = _get_bool("REGISTRATION_EMAIL_VERIFICATION_ENABLED", True)
REGISTRATION_SMS_VERIFICATION_ENABLED = _get_bool("REGISTRATION_SMS_VERIFICATION_ENABLED", False)
CONTACT_VERIFICATION_HMAC_SECRET = os.getenv("CONTACT_VERIFICATION_HMAC_SECRET", "").strip()
CONTACT_CODE_MAX_ATTEMPTS = _get_int("CONTACT_CODE_MAX_ATTEMPTS", 5, 1, 20)
CONTACT_CODE_RESEND_SECONDS = _get_int("CONTACT_CODE_RESEND_SECONDS", 60, 10, 3600)
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = _get_int("SMTP_PORT", 587, 1, 65535)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_FROM_ADDRESS = os.getenv("SMTP_FROM_ADDRESS", "").strip()
SMTP_USE_TLS = _get_bool("SMTP_USE_TLS", True)
SMTP_USE_SSL = _get_bool("SMTP_USE_SSL", False)
SMTP_TIMEOUT_SECONDS = _get_int("SMTP_TIMEOUT_SECONDS", 10, 1, 60)
SMS_VERIFY_WEBHOOK_URL = os.getenv("SMS_VERIFY_WEBHOOK_URL", "").strip()
SMS_VERIFY_WEBHOOK_SECRET = os.getenv("SMS_VERIFY_WEBHOOK_SECRET", "").strip()
SMS_VERIFY_TIMEOUT_SECONDS = _get_int("SMS_VERIFY_TIMEOUT_SECONDS", 10, 1, 60)
USER_REGISTRATION_MAX_REQUESTS = _get_int("USER_REGISTRATION_MAX_REQUESTS", 5, 1, 100)
USER_REGISTRATION_WINDOW_SECONDS = _get_int("USER_REGISTRATION_WINDOW_SECONDS", 3600, 60, 86400)
USER_REGISTRATION_LOCK_SECONDS = _get_int("USER_REGISTRATION_LOCK_SECONDS", 3600, 60, 86400)
USER_LOGIN_MAX_FAILURES = _get_int("USER_LOGIN_MAX_FAILURES", 8, 1, 100)
USER_LOGIN_WINDOW_SECONDS = _get_int("USER_LOGIN_WINDOW_SECONDS", 900, 10, 86400)
USER_LOGIN_LOCK_SECONDS = _get_int("USER_LOGIN_LOCK_SECONDS", 900, 10, 86400)
PASSWORD_RESET_MAX_REQUESTS = _get_int("PASSWORD_RESET_MAX_REQUESTS", 3, 1, 20)
PASSWORD_RESET_WINDOW_SECONDS = _get_int("PASSWORD_RESET_WINDOW_SECONDS", 3600, 60, 86400)
PASSWORD_RESET_LOCK_SECONDS = _get_int("PASSWORD_RESET_LOCK_SECONDS", 3600, 60, 86400)
CORS_ORIGINS = _get_list("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")


# Shared cache/rate-limit backend. Leave REDIS_URL empty for single-process fallback.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "stock_server").strip() or "stock_server"
REDIS_CONNECT_TIMEOUT_SECONDS = float(os.getenv("REDIS_CONNECT_TIMEOUT_SECONDS", "1.0") or 1.0)
REDIS_SOCKET_TIMEOUT_SECONDS = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "1.0") or 1.0)
REDIS_REQUIRED = _get_bool("REDIS_REQUIRED", APP_ENV == "production")

# Public plan RPM is defined by the active plan. DEFAULT is fallback-only.
# MIN is a compatibility floor; keep it at 1 so explicit 120/300 RPM plans are not lifted.
AUTH_CONTEXT_CACHE_TTL_SECONDS = _get_int("AUTH_CONTEXT_CACHE_TTL_SECONDS", 30, 0, 3600)

# User contact text
CONTACT_QQ = os.getenv("CONTACT_QQ", "").strip()
CONTACT_WECHAT = os.getenv("CONTACT_WECHAT", "").strip()
CONTACT_NOTE = os.getenv(
    "CONTACT_NOTE",
    "如需开通接口套餐，请联系管理员开通对应权限和有效期。",
).strip()

# Tushare
# Empty URL means: use the SDK's current default. This supports both the official SDK
# and relay scheme 1, because the relay installer patches the SDK itself.
# Set the URL for relay scheme 2, e.g. http://47.116.63.181:8000/dataapi.
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "").strip()
TUSHARE_API_URL = os.getenv("TUSHARE_API_URL", "").strip()
TUSHARE_ALLOWED_RELAY_HOSTS = [host.lower() for host in _get_list("TUSHARE_ALLOWED_RELAY_HOSTS", "")]
TUSHARE_ALLOW_INSECURE_HTTP_RELAY = _get_bool("TUSHARE_ALLOW_INSECURE_HTTP_RELAY", False)
TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL = os.getenv("TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL", "").strip()
TUSHARE_TIMEOUT_SECONDS = _get_int("TUSHARE_TIMEOUT_SECONDS", 30, 1, 300)
TUSHARE_CONNECT_TIMEOUT_SECONDS = _get_int("TUSHARE_CONNECT_TIMEOUT_SECONDS", 5, 1, 60)
TUSHARE_MAX_RESPONSE_BYTES = _get_int("TUSHARE_MAX_RESPONSE_BYTES", 32 * 1024 * 1024, 1024, 512 * 1024 * 1024)

# Tushare response cache (in-process)

# Per-interface TTL keeps frequently changing data fresh while avoiding repeated
# large/static upstream calls.  .env can override any item with api=seconds.

# Empty data is cached only briefly.  This avoids repeatedly hammering the
# upstream while ensuring a temporary empty result does not linger for 5 min.

# Safe, slow-changing interfaces may serve the last good value when refresh
# fails.  This protects website latency without serving stale real-time prices.

# For selected slow/static interfaces, return cached data immediately and
# refresh it in a bounded background pool near/after expiry.
MARKET_DATA_BACKGROUND_REFRESH_ENABLED = _get_bool(
    "MARKET_DATA_BACKGROUND_REFRESH_ENABLED", True
)

# Optional non-blocking cache warm-up after the web process starts.  It is safe
# for the project's default single-process Waitress deployment.  Disable it in
# multi-worker deployments unless Redis is shared.
MARKET_DATA_PREWARM_ENABLED = _get_bool("MARKET_DATA_PREWARM_ENABLED", False)

REALTIME_CACHE_TTL_SECONDS = _get_int("REALTIME_CACHE_TTL_SECONDS", 1, 0, 60)
LOCAL_CACHE_PROMOTION_TTL_SECONDS = _get_int("LOCAL_CACHE_PROMOTION_TTL_SECONDS", 15, 1, 300)

# Usage-log queue
ASYNC_USAGE_LOG_ENABLED = _get_bool("ASYNC_USAGE_LOG_ENABLED", True)
USAGE_LOG_FLUSH_INTERVAL_SECONDS = _get_int("USAGE_LOG_FLUSH_INTERVAL_SECONDS", 1, 1, 60)

USAGE_LOG_BATCH_SIZE = _get_int("USAGE_LOG_BATCH_SIZE", 500, 1, 5000)
USAGE_LOG_DROP_ON_FULL = _get_bool("USAGE_LOG_DROP_ON_FULL", True)
# Exact daily counters are always persisted; successful detail rows are sampled to control DB growth.
USAGE_LOG_SUCCESS_SAMPLE_RATE = _get_float("USAGE_LOG_SUCCESS_SAMPLE_RATE", 0.10, 0.0, 1.0)
USAGE_LOG_RETAIN_FAILURES = _get_bool("USAGE_LOG_RETAIN_FAILURES", True)
USAGE_LOG_RETENTION_DAYS = _get_int("USAGE_LOG_RETENTION_DAYS", 30, 1, 3650)

# Durable audit history
AUDIT_ENABLED = _get_bool("AUDIT_ENABLED", True)
OPERATION_LOG_RETENTION_DAYS = _get_int("OPERATION_LOG_RETENTION_DAYS", 365, 0, 36500)
AUDIT_CLEANUP_INTERVAL_HOURS = _get_int("AUDIT_CLEANUP_INTERVAL_HOURS", 24, 1, 720)
AUDIT_SPOOL_DB_FILE = Path(os.getenv("AUDIT_SPOOL_DB_FILE", str(DATA_DIR / "audit_spool.db")))
if not AUDIT_SPOOL_DB_FILE.is_absolute():
    AUDIT_SPOOL_DB_FILE = BASE_DIR / AUDIT_SPOOL_DB_FILE
AUDIT_SPOOL_DB_FILE = str(AUDIT_SPOOL_DB_FILE.resolve())
AUDIT_REQUEST_PARAMS_MAX_CHARS = _get_int("AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000, 100, 1000000)
AUDIT_ERROR_MESSAGE_MAX_CHARS = _get_int("AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000, 100, 100000)
AUDIT_TOKEN_HMAC_SECRET = os.getenv("AUDIT_TOKEN_HMAC_SECRET", "").strip() or SECRET_KEY
AUDIT_EMERGENCY_DIR = Path(os.getenv("AUDIT_EMERGENCY_DIR", str(DATA_DIR / "audit_emergency")))
if not AUDIT_EMERGENCY_DIR.is_absolute():
    AUDIT_EMERGENCY_DIR = BASE_DIR / AUDIT_EMERGENCY_DIR
AUDIT_EMERGENCY_DIR = AUDIT_EMERGENCY_DIR.resolve()

# Logging
LOG_DIR = Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs")))
if not LOG_DIR.is_absolute():
    LOG_DIR = BASE_DIR / LOG_DIR
LOG_RETENTION_DAYS = _get_int("LOG_RETENTION_DAYS", 30, 1, 3650)


# API-document runtime health refresh.  The page always reads the newest valid
# report; enabling the worker additionally runs the full 140-interface test
# every 12 hours.  Keep it disabled in multi-worker web deployments and run
# tools.api_doc_status_worker as one dedicated process instead.
API_DOC_STATUS_AUTO_REFRESH_ENABLED = _get_bool(
    "API_DOC_STATUS_AUTO_REFRESH_ENABLED", False
)
API_DOC_STATUS_IN_PROCESS = _get_bool("API_DOC_STATUS_IN_PROCESS", True)
API_DOC_STATUS_BASE_URL = os.getenv(
    "API_DOC_STATUS_BASE_URL", f"http://127.0.0.1:{SERVER_PORT}"
).strip().rstrip("/")

# MiniQMT / XtQuant (optional; xtquant is supplied by the QMT installation)
MINIQMT_ENABLED = _get_bool("MINIQMT_ENABLED", False)
MINIQMT_MAX_SYMBOLS_PER_REQUEST = _get_int("MINIQMT_MAX_SYMBOLS_PER_REQUEST", 200, 1, 5000)

# Feishu (optional)
ENABLE_FEISHU_SYNC = _get_bool("ENABLE_FEISHU_SYNC", False)
# True for a single Waitress process. Set False for multi-worker Gunicorn and run tools.feishu_worker once.
ENABLE_IN_PROCESS_FEISHU_WORKER = _get_bool("ENABLE_IN_PROCESS_FEISHU_WORKER", True)
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "").strip()
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "").strip()
FEISHU_BTABLE_APP_TOKEN = os.getenv("FEISHU_BTABLE_APP_TOKEN", "").strip()
FEISHU_BTABLE_TABLE_ID = os.getenv("FEISHU_BTABLE_TABLE_ID", "").strip()
FEISHU_BIDDING_APP_TOKEN = os.getenv("FEISHU_BIDDING_APP_TOKEN", "").strip()
FEISHU_BIDDING_TABLE_ID = os.getenv("FEISHU_BIDDING_TABLE_ID", "").strip()
FEISHU_UNOPENED_STATUS_TEXT = os.getenv("FEISHU_UNOPENED_STATUS_TEXT", "").strip()
# Enable only after the six extended membership fields have been added to the Feishu table.
FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED = _get_bool("FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED", False)
BIDDING_SYNC_HOUR = _get_int("BIDDING_SYNC_HOUR", 18, 0, 23)
BIDDING_SYNC_MINUTE = _get_int("BIDDING_SYNC_MINUTE", 0, 0, 59)
# Add only missing bidding fields; never mutate incompatible existing field types.
FEISHU_BIDDING_AUTO_CREATE_FIELDS = _get_bool("FEISHU_BIDDING_AUTO_CREATE_FIELDS", True)
# Disabled by default: a Tushare partial fallback must not silently enter the Kaipanla table.
FEISHU_BIDDING_ALLOW_TUSHARE_FALLBACK = _get_bool("FEISHU_BIDDING_ALLOW_TUSHARE_FALLBACK", False)
FEISHU_SYNC_INTERVAL_MINUTES = _get_int("FEISHU_SYNC_INTERVAL_MINUTES", 5, 1, 1440)
FEISHU_SYNC_LOCK_FILE = Path(os.getenv("FEISHU_SYNC_LOCK_FILE", str(DATA_DIR / "feishu_sync.lock")))
if not FEISHU_SYNC_LOCK_FILE.is_absolute():
    FEISHU_SYNC_LOCK_FILE = BASE_DIR / FEISHU_SYNC_LOCK_FILE
FEISHU_SYNC_LOCK_FILE = str(FEISHU_SYNC_LOCK_FILE.resolve())
# 0 means fail fast when another sync task is active.
FEISHU_SYNC_LOCK_TIMEOUT_SECONDS = _get_float("FEISHU_SYNC_LOCK_TIMEOUT_SECONDS", 0.0, 0.0, 300.0)

# Kaipanla (optional, used only by Feishu bidding sync)
KAIPANLA_USER_ID = os.getenv("KAIPANLA_USER_ID", "").strip()
KAIPANLA_TOKEN = os.getenv("KAIPANLA_TOKEN", "").strip()
KAIPANLA_DEVICE_ID = os.getenv("KAIPANLA_DEVICE_ID", "").strip()

# Daily Kaipanla morning-bidding snapshots (Asia/Shanghai).
KAIPANLA_SNAPSHOT_ENABLED = _get_bool("KAIPANLA_SNAPSHOT_ENABLED", False)
KAIPANLA_SNAPSHOT_IN_PROCESS = _get_bool("KAIPANLA_SNAPSHOT_IN_PROCESS", True)
KAIPANLA_AUCTION_SNAPSHOT_HOUR = _get_int("KAIPANLA_AUCTION_SNAPSHOT_HOUR", 9, 0, 23)
KAIPANLA_AUCTION_SNAPSHOT_MINUTE = _get_int("KAIPANLA_AUCTION_SNAPSHOT_MINUTE", 26, 0, 59)
KAIPANLA_AUCTION_SNAPSHOT_SECOND = _get_int("KAIPANLA_AUCTION_SNAPSHOT_SECOND", 5, 0, 59)
KAIPANLA_POST_OPEN_SNAPSHOT_HOUR = _get_int("KAIPANLA_POST_OPEN_SNAPSHOT_HOUR", 9, 0, 23)
KAIPANLA_POST_OPEN_SNAPSHOT_MINUTE = _get_int("KAIPANLA_POST_OPEN_SNAPSHOT_MINUTE", 31, 0, 59)
KAIPANLA_POST_OPEN_SNAPSHOT_SECOND = _get_int("KAIPANLA_POST_OPEN_SNAPSHOT_SECOND", 0, 0, 59)
KAIPANLA_CLOSE_SNAPSHOT_HOUR = _get_int("KAIPANLA_CLOSE_SNAPSHOT_HOUR", 15, 0, 23)
KAIPANLA_CLOSE_SNAPSHOT_MINUTE = _get_int("KAIPANLA_CLOSE_SNAPSHOT_MINUTE", 1, 0, 59)
KAIPANLA_CLOSE_SNAPSHOT_SECOND = _get_int("KAIPANLA_CLOSE_SNAPSHOT_SECOND", 0, 0, 59)
KAIPANLA_SNAPSHOT_POLL_SECONDS = _get_int("KAIPANLA_SNAPSHOT_POLL_SECONDS", 5, 1, 60)
KAIPANLA_SNAPSHOT_PAGE_SIZE = _get_int("KAIPANLA_SNAPSHOT_PAGE_SIZE", 1000, 1, 1000)
KAIPANLA_SNAPSHOT_MAX_PAGES = _get_int("KAIPANLA_SNAPSHOT_MAX_PAGES", 10, 1, 100)
KAIPANLA_SNAPSHOT_RETENTION_DAYS = _get_int("KAIPANLA_SNAPSHOT_RETENTION_DAYS", 1095, 30, 3650)


def add_months(n: int) -> str:
    """Return the end of the day N calendar months from now."""
    today = datetime.now()
    month_index = today.month - 1 + n
    year = today.year + month_index // 12
    month = month_index % 12 + 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return today.replace(year=year, month=month, day=day, hour=23, minute=59, second=59).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

# Administrator market-interface tester
ADMIN_API_TEST_RESULT_DIR = Path(os.getenv("ADMIN_API_TEST_RESULT_DIR", str(DATA_DIR / "admin_api_test_results")))
if not ADMIN_API_TEST_RESULT_DIR.is_absolute():
    ADMIN_API_TEST_RESULT_DIR = BASE_DIR / ADMIN_API_TEST_RESULT_DIR
ADMIN_API_TEST_RESULT_DIR = ADMIN_API_TEST_RESULT_DIR.resolve()
ADMIN_API_TEST_SPEC_DIR = Path(os.getenv("ADMIN_API_TEST_SPEC_DIR", str(BASE_DIR / "interface_specs")))
if not ADMIN_API_TEST_SPEC_DIR.is_absolute():
    ADMIN_API_TEST_SPEC_DIR = BASE_DIR / ADMIN_API_TEST_SPEC_DIR
ADMIN_API_TEST_SPEC_DIR = ADMIN_API_TEST_SPEC_DIR.resolve()
ADMIN_API_TEST_CLEANUP_ENABLED = _get_bool("ADMIN_API_TEST_CLEANUP_ENABLED", True)
ADMIN_API_TEST_IN_PROCESS_WORKER = _get_bool("ADMIN_API_TEST_IN_PROCESS_WORKER", True)

# Tushare official-spec monitoring.  Scheduled scans never publish releases;
# they only persist snapshots and administrator-facing change alerts.
TUSHARE_SPEC_MONITOR_ENABLED = _get_bool("TUSHARE_SPEC_MONITOR_ENABLED", True)
TUSHARE_SPEC_MONITOR_IN_PROCESS = _get_bool("TUSHARE_SPEC_MONITOR_IN_PROCESS", True)


# ================================================================
# PLATFORM_POLICY_RUNTIME_OVERLAY_V1
#
# Shared platform/business/risk/performance tuning comes from the
# checked-in settings/platform_policy.json.
#
# Environment identity, paths, ports, Redis endpoints and secrets
# continue to come from .env / process environment.
# ================================================================

from services.platform_policy import (
    managed_config as _managed_platform_config,
    waitress_backlog as _platform_waitress_backlog,
)

_PLATFORM_POLICY_VALUES = (
    _managed_platform_config()
)

for (
    _platform_policy_name,
    _platform_policy_value,
) in _PLATFORM_POLICY_VALUES.items():

    globals()[
        _platform_policy_name
    ] = _platform_policy_value


WAITRESS_BACKLOG = (
    _platform_waitress_backlog()
)


del _platform_policy_name
del _platform_policy_value

