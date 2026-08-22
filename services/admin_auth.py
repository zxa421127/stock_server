# -*- coding: utf-8 -*-
"""Central administrator password and client-certificate verification."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import ipaddress
from typing import Any
from urllib.parse import unquote, urlsplit

import config
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from services.admin_client_certificate import (
    get_certificate_by_fingerprint,
    normalize_fingerprint,
    normalize_serial,
)
from services.security_credentials import is_valid_totp_secret, verify_secret, verify_totp

try:
    from flask import has_request_context, request
except Exception:  # pragma: no cover
    has_request_context = lambda: False  # type: ignore[assignment]
    request = None  # type: ignore[assignment]

_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class AdminCertificateVerification:
    ok: bool
    code: str
    message: str
    certificate: dict[str, Any] | None = None


@dataclass(frozen=True)
class AdminHighRiskConfirmation:
    """Server-side result for destructive administrator action confirmation."""

    ok: bool
    code: str
    message: str


def verify_admin_password(password: str) -> bool:
    encoded = str(getattr(config, "ADMIN_PASSWORD_HASH", "") or "")
    if encoded:
        return verify_secret(password, encoded)
    # Legacy plaintext is accepted only outside production for migration/testing.
    if str(getattr(config, "APP_ENV", "development")).lower() == "production":
        return False
    legacy = str(getattr(config, "ADMIN_PASSWORD", "") or "")
    return bool(legacy and hmac.compare_digest(str(password or ""), legacy))


def _is_loopback_address(value: str | None) -> bool:
    raw = str(value or "").strip().strip("[]").split("%", 1)[0].lower()
    if not raw:
        return False
    if raw in _LOOPBACK_HOSTS or raw.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(raw).is_loopback
    except ValueError:
        return False


def _external_request_context() -> bool:
    """Return True unless both request host and apparent peer are loopback."""
    try:
        if not has_request_context():
            return False
        host_value = str(getattr(request, "host", "") or "")
        hostname = urlsplit(f"//{host_value}").hostname or host_value
        remote_addr = str(getattr(request, "remote_addr", "") or "")
        return not (_is_loopback_address(hostname) and _is_loopback_address(remote_addr))
    except Exception:
        return bool(has_request_context())


def admin_client_certificate_required() -> bool:
    return bool(
        getattr(config, "ADMIN_CLIENT_CERT_REQUIRED", False)
        or str(getattr(config, "APP_ENV", "development")).lower() == "production"
        or _external_request_context()
    )


def _header(setting_name: str, default_name: str) -> str:
    configured = str(getattr(config, setting_name, default_name) or default_name).strip()
    return str(request.headers.get(configured) or "") if has_request_context() else ""


def _request_hostname() -> str:
    if not has_request_context():
        return ""
    host_value = str(getattr(request, "host", "") or "")
    return str(urlsplit(f"//{host_value}").hostname or "").strip().lower()


def admin_session_certificate_matches(
    session_fingerprint: str | None,
    certificate: dict[str, Any] | None,
) -> bool:
    """Bind an authenticated administrator session to one certificate."""
    expected = normalize_fingerprint(session_fingerprint)
    actual = normalize_fingerprint(str((certificate or {}).get("fingerprint_sha256") or ""))
    return bool(expected and actual and hmac.compare_digest(expected, actual))


def _certificate_details(certificate: x509.Certificate) -> dict[str, Any]:
    return {
        "fingerprint_sha256": certificate.fingerprint(hashes.SHA256()).hex().upper(),
        "serial_number": format(certificate.serial_number, "X"),
        "subject_dn": certificate.subject.rfc4514_string(),
        "issuer_dn": certificate.issuer.rfc4514_string(),
        "not_before": certificate.not_valid_before_utc,
        "not_after": certificate.not_valid_after_utc,
    }


def _forwarded_certificate_details() -> dict[str, Any] | None:
    pem_raw = _header("ADMIN_CLIENT_CERT_PEM_HEADER", "X-Admin-Client-Cert")
    if pem_raw:
        try:
            decoded = unquote(pem_raw).strip()
            return _certificate_details(
                x509.load_pem_x509_certificate(decoded.encode("utf-8"))
            )
        except Exception:
            pass

    der_raw = _header("ADMIN_CLIENT_CERT_DER_HEADER", "X-Admin-Client-Cert-DER")
    if der_raw:
        try:
            der_bytes = base64.b64decode(der_raw.strip(), validate=True)
            return _certificate_details(x509.load_der_x509_certificate(der_bytes))
        except Exception:
            pass

    return None

def _parse_utc(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def verify_admin_client_certificate_request(
    *,
    admin_username: str | None = None,
    now: datetime | None = None,
) -> AdminCertificateVerification:
    """Verify trusted reverse-proxy mTLS headers against the local registry.

    Nginx or Caddy must overwrite every certificate header and add a long shared
    proxy secret. The application backend must listen only on loopback; this
    prevents clients from supplying trusted-looking headers directly.
    """
    if not admin_client_certificate_required():
        return AdminCertificateVerification(True, "development_bypass", "本机开发模式未启用客户端证书", None)
    if not has_request_context():
        return AdminCertificateVerification(False, "request_context_missing", "缺少请求上下文")

    configured_admin_host = str(
        getattr(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "") or ""
    ).strip().lower().rstrip(".")
    request_hostname = _request_hostname().rstrip(".")
    if configured_admin_host and request_hostname != configured_admin_host:
        return AdminCertificateVerification(
            False,
            "admin_host_mismatch",
            "管理员请求未使用配置的专用后台域名",
        )

    configured_proxy_secret = str(getattr(config, "ADMIN_CLIENT_CERT_PROXY_SECRET", "") or "")
    supplied_proxy_secret = _header("ADMIN_CLIENT_CERT_PROXY_HEADER", "X-Admin-Proxy-Auth")
    if not configured_proxy_secret:
        return AdminCertificateVerification(False, "proxy_auth_missing", "服务器未配置管理员证书代理密钥")
    if not supplied_proxy_secret:
        return AdminCertificateVerification(False, "proxy_auth_missing", "请求未经过可信管理员代理")
    if not hmac.compare_digest(configured_proxy_secret, supplied_proxy_secret):
        return AdminCertificateVerification(False, "proxy_auth_invalid", "管理员代理认证失败")

    verify_status = _header("ADMIN_CLIENT_CERT_VERIFY_HEADER", "X-Admin-Client-Cert-Verify").strip().upper()
    if verify_status != "SUCCESS":
        return AdminCertificateVerification(False, "certificate_not_verified", "客户端证书未通过TLS验证")

    forwarded = _forwarded_certificate_details()
    if not forwarded:
        return AdminCertificateVerification(False, "certificate_pem_missing", "客户端证书原文缺失或无法解析")
    fingerprint = normalize_fingerprint(str(forwarded.get("fingerprint_sha256") or ""))
    if not fingerprint:
        return AdminCertificateVerification(False, "certificate_fingerprint_missing", "客户端证书SHA-256指纹无效")
    try:
        certificate = get_certificate_by_fingerprint(fingerprint)
    except Exception:
        return AdminCertificateVerification(False, "certificate_registry_unavailable", "客户端证书登记表不可用")
    if not certificate:
        return AdminCertificateVerification(False, "certificate_unknown", "客户端证书未登记")

    status = str(certificate.get("status") or "").lower()
    if status != "active":
        return AdminCertificateVerification(False, "certificate_revoked", "客户端证书已撤销或停用", certificate)

    expected_admin = str(admin_username or getattr(config, "ADMIN_USERNAME", "admin") or "admin")
    if not hmac.compare_digest(str(certificate.get("admin_username") or ""), expected_admin):
        return AdminCertificateVerification(False, "certificate_admin_mismatch", "客户端证书未绑定当前管理员", certificate)

    header_serial = normalize_serial(str(forwarded.get("serial_number") or ""))
    registered_serial = normalize_serial(str(certificate.get("serial_number") or ""))
    if not header_serial or not registered_serial or not hmac.compare_digest(header_serial, registered_serial):
        return AdminCertificateVerification(False, "certificate_serial_mismatch", "客户端证书序列号不匹配", certificate)

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    forwarded_not_before = forwarded.get("not_before")
    forwarded_not_after = forwarded.get("not_after")
    if not isinstance(forwarded_not_before, datetime) or current < forwarded_not_before.astimezone(timezone.utc):
        return AdminCertificateVerification(False, "certificate_not_yet_valid", "客户端证书尚未生效", certificate)
    if not isinstance(forwarded_not_after, datetime) or current >= forwarded_not_after.astimezone(timezone.utc):
        return AdminCertificateVerification(False, "certificate_expired", "客户端证书已过期", certificate)
    not_before = _parse_utc(str(certificate.get("not_before") or ""))
    not_after = _parse_utc(str(certificate.get("not_after") or ""))
    if not not_before or current < not_before:
        return AdminCertificateVerification(False, "certificate_not_yet_valid", "客户端证书尚未生效", certificate)
    if not not_after or current >= not_after:
        return AdminCertificateVerification(False, "certificate_expired", "客户端证书已过期", certificate)

    return AdminCertificateVerification(True, "ok", "", certificate)


# Legacy TOTP helpers remain for rollback compatibility and old maintenance tools.
def admin_mfa_required() -> bool:
    return bool(getattr(config, "ADMIN_REQUIRE_MFA", False))


def admin_mfa_configured() -> bool:
    return is_valid_totp_secret(str(getattr(config, "ADMIN_TOTP_SECRET", "") or ""))


def verify_admin_mfa(code: str | None) -> bool:
    if not admin_mfa_required():
        return True
    secret = str(getattr(config, "ADMIN_TOTP_SECRET", "") or "")
    return bool(admin_mfa_configured() and verify_totp(secret, code))


def verify_admin_confirmation(password: str, _legacy_otp: str | None = None) -> bool:
    verification = verify_admin_client_certificate_request()
    return bool(verification.ok and verify_admin_password(password))


def verify_admin_high_risk_confirmation(
    password: str,
    confirmation_text: str,
    expected_text: str,
) -> AdminHighRiskConfirmation:
    """Require both administrator re-authentication and an exact typed phrase.

    This is intentionally independent from browser-side ``confirm()`` dialogs.
    A destructive operation is authorized only when the current request still
    has a valid administrator client certificate, the administrator password is
    re-entered correctly, and the operator types the exact server-provided
    confirmation phrase.
    """
    if not verify_admin_confirmation(str(password or "")):
        return AdminHighRiskConfirmation(
            False,
            "admin_reauthentication_failed",
            "管理员密码或客户端证书二次验证失败",
        )

    expected = str(expected_text or "").strip()
    supplied = str(confirmation_text or "").strip()
    if not expected or not supplied or not hmac.compare_digest(supplied, expected):
        return AdminHighRiskConfirmation(
            False,
            "confirmation_text_invalid",
            "高风险操作确认文字不匹配",
        )

    return AdminHighRiskConfirmation(True, "ok", "")
