# -*- coding: utf-8 -*-
"""Fail-closed production configuration validation."""
from __future__ import annotations

from typing import Callable, Any


_PLACEHOLDER_SECRET_PREFIXES = (
    "please", "change", "replace", "example", "your_", "your-",
    "changeme", "change_me", "请", "填写", "修改",
)


def _is_insecure_secret(value: object, *, minimum_length: int = 32) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return len(text) < minimum_length or lowered.startswith(_PLACEHOLDER_SECRET_PREFIXES)


def collect_configuration_errors(settings: Any, *, redis_getter: Callable[[], Any]) -> list[str]:
    errors: list[str] = []
    if str(getattr(settings, "APP_ENV", "")).lower() != "production":
        return errors

    secret_key = str(getattr(settings, "SECRET_KEY", "") or "")
    if _is_insecure_secret(secret_key):
        errors.append("SECRET_KEY 必须是至少32位的随机值")

    admin_hash = str(getattr(settings, "ADMIN_PASSWORD_HASH", "") or "")
    if not admin_hash.startswith("pbkdf2_sha256$"):
        errors.append("ADMIN_PASSWORD_HASH 必须配置为PBKDF2哈希，生产环境禁止明文管理员密码")
    legacy_admin_password = str(getattr(settings, "ADMIN_PASSWORD", "") or "").strip()
    if legacy_admin_password and legacy_admin_password != "please-change-password":
        errors.append("生产环境必须删除ADMIN_PASSWORD明文配置，只保留ADMIN_PASSWORD_HASH")

    if not bool(getattr(settings, "ADMIN_CLIENT_CERT_REQUIRED", False)):
        errors.append("ADMIN_CLIENT_CERT_REQUIRED 在生产环境必须为true")
    proxy_secret = str(getattr(settings, "ADMIN_CLIENT_CERT_PROXY_SECRET", "") or "").strip()
    if _is_insecure_secret(proxy_secret):
        errors.append("ADMIN_CLIENT_CERT_PROXY_SECRET 必须是至少32位的随机值")
    admin_host = str(getattr(settings, "ADMIN_CLIENT_CERT_ADMIN_HOST", "") or "").strip().lower()
    if not admin_host or admin_host in {"localhost", "127.0.0.1", "api.example.com"}:
        errors.append("ADMIN_CLIENT_CERT_ADMIN_HOST 必须配置为独立的管理员HTTPS域名")

    token_secret = str(getattr(settings, "API_TOKEN_HASH_SECRET", "") or "")
    if _is_insecure_secret(token_secret):
        errors.append("API_TOKEN_HASH_SECRET 必须是至少32位的随机值，不能使用公开占位内容")

    audit_secret = str(getattr(settings, "AUDIT_TOKEN_HMAC_SECRET", "") or "")
    if _is_insecure_secret(audit_secret):
        errors.append("AUDIT_TOKEN_HMAC_SECRET 必须是至少32位的独立随机值，不能使用公开占位内容")

    verification_required = bool(getattr(settings, "REGISTRATION_CONTACT_VERIFICATION_REQUIRED", False))
    contact_secret = str(getattr(settings, "CONTACT_VERIFICATION_HMAC_SECRET", "") or "")
    if verification_required and _is_insecure_secret(contact_secret):
        errors.append("CONTACT_VERIFICATION_HMAC_SECRET 必须是至少32位的独立随机值，不能使用公开占位内容")
    if verification_required:
        email_enabled = bool(getattr(settings, "REGISTRATION_EMAIL_VERIFICATION_ENABLED", False))
        sms_enabled = bool(getattr(settings, "REGISTRATION_SMS_VERIFICATION_ENABLED", False))
        if not email_enabled and not sms_enabled:
            errors.append("生产注册必须至少启用邮箱SMTP或短信Webhook验证渠道")
        if email_enabled:
            if not str(getattr(settings, "SMTP_HOST", "") or "").strip():
                errors.append("启用邮箱验证时必须配置SMTP_HOST")
            if not str(getattr(settings, "SMTP_FROM_ADDRESS", "") or "").strip():
                errors.append("启用邮箱验证时必须配置SMTP_FROM_ADDRESS")
        if sms_enabled:
            sms_url = str(getattr(settings, "SMS_VERIFY_WEBHOOK_URL", "") or "").strip()
            sms_secret = str(getattr(settings, "SMS_VERIFY_WEBHOOK_SECRET", "") or "")
            if not sms_url.lower().startswith("https://"):
                errors.append("SMS_VERIFY_WEBHOOK_URL 在生产环境必须使用HTTPS")
            if _is_insecure_secret(sms_secret):
                errors.append("SMS_VERIFY_WEBHOOK_SECRET 必须是至少32位的随机值，不能使用公开占位内容")

    tushare_url = str(getattr(settings, "TUSHARE_API_URL", "") or "").strip()
    if tushare_url:
        try:
            from integrations.market_data.tushare.client import validate_tushare_endpoint
            validate_tushare_endpoint(
                tushare_url, production=True,
                allowed_hosts=getattr(settings, "TUSHARE_ALLOWED_RELAY_HOSTS", []) or [],
                allow_insecure_http_relay=bool(getattr(settings, "TUSHARE_ALLOW_INSECURE_HTTP_RELAY", False)),
                insecure_http_relay_exact_url=str(getattr(settings, "TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL", "") or "").strip(),
            )
        except Exception as exc:
            errors.append(f"Tushare中转配置不安全: {exc}")

    db_file = str(getattr(settings, "DB_FILE", "") or "").strip()
    if db_file:
        try:
            import sqlite3
            from tools.db.migrate_legacy_tokens import count_active_legacy_tokens
            conn = sqlite3.connect(db_file)
            try:
                if count_active_legacy_tokens(conn) > 0:
                    errors.append("数据库仍存在有效旧api_tokens明文凭证，请先执行吊销工具")
            finally:
                conn.close()
        except sqlite3.Error as exc:
            errors.append(f"数据库旧Token检查失败: {type(exc).__name__}")

    if not bool(getattr(settings, "SESSION_COOKIE_SECURE", False)):
        errors.append("SESSION_COOKIE_SECURE 必须为true")
    if bool(getattr(settings, "ALLOW_INSECURE_DEFAULTS", False)):
        errors.append("ALLOW_INSECURE_DEFAULTS 在生产环境必须为false")
    if bool(getattr(settings, "DB_AUTO_MIGRATE", True)):
        errors.append("DB_AUTO_MIGRATE 在生产环境必须为false，请在发布阶段单独执行迁移")

    if not bool(getattr(settings, "REDIS_REQUIRED", False)):
        errors.append("REDIS_REQUIRED 在生产环境必须为true")
    redis_url = str(getattr(settings, "REDIS_URL", "") or "").strip()
    if not redis_url:
        errors.append("REDIS_URL 必须配置，生产环境禁止进程内限流/缓存降级")
    else:
        try:
            client = redis_getter()
            if client is None or not client.ping():
                errors.append("Redis连接或PING失败")
        except Exception as exc:
            errors.append(f"Redis连接失败: {type(exc).__name__}")


    host = str(getattr(settings, "SERVER_HOST", "127.0.0.1") or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"} and not bool(getattr(settings, "ALLOW_DIRECT_PUBLIC_BIND", False)):
        errors.append("SERVER_HOST必须绑定回环地址，由受信任反向代理对外提供HTTPS；如确需直连请显式设置ALLOW_DIRECT_PUBLIC_BIND")
    if not bool(getattr(settings, "TRUST_PROXY_HEADERS", False)):
        errors.append("生产环境必须启用TRUST_PROXY_HEADERS，并仅允许可信反向代理访问Waitress或Gunicorn")
    elif int(getattr(settings, "PROXY_FIX_X_FOR", 0) or 0) != 1 or int(getattr(settings, "PROXY_FIX_X_PROTO", 0) or 0) != 1:
        errors.append("单层反向代理部署必须将PROXY_FIX_X_FOR和PROXY_FIX_X_PROTO精确设置为1")

    if bool(getattr(settings, "REQUIRE_EXTERNAL_WORKERS", True)):
        for name in (
            "ADMIN_API_TEST_IN_PROCESS_WORKER",
            "ENABLE_IN_PROCESS_FEISHU_WORKER",
            "API_DOC_STATUS_IN_PROCESS",
            "KAIPANLA_SNAPSHOT_IN_PROCESS",
            "TUSHARE_SPEC_MONITOR_IN_PROCESS",
        ):
            if bool(getattr(settings, name, False)):
                errors.append(f"{name} 在生产环境必须为false，使用独立Worker")
    return errors


def assert_production_ready(settings: Any, *, redis_getter: Callable[[], Any]) -> None:
    errors = collect_configuration_errors(settings, redis_getter=redis_getter)
    if errors:
        raise RuntimeError("生产配置检查失败: " + "; ".join(errors))
