# -*- coding: utf-8 -*-
"""One-way API-token storage helpers."""
from __future__ import annotations

import hashlib
import hmac


def normalize_api_token(token: str | None) -> str:
    return str(token or "").strip()


def hash_api_token(token: str | None, secret: str | None) -> str:
    normalized = normalize_api_token(token)
    key = str(secret or "").encode("utf-8")
    if not normalized or len(key) < 16:
        return ""
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def token_prefix(token: str | None, *, length: int = 20) -> str:
    value = normalize_api_token(token)
    return value[: max(4, int(length))]


def token_last4(token: str | None) -> str:
    value = normalize_api_token(token)
    return value[-4:] if len(value) >= 4 else value


def token_display(token: str | None = None, *, prefix: str | None = None, last4: str | None = None) -> str:
    shown_prefix = str(prefix or token_prefix(token)).strip()
    shown_last4 = str(last4 or token_last4(token)).strip()
    if not shown_prefix and not shown_last4:
        return "未生成"
    if shown_prefix.endswith(shown_last4) and shown_last4:
        shown_prefix = shown_prefix[: -len(shown_last4)]
    return f"{shown_prefix}…{shown_last4}" if shown_last4 else f"{shown_prefix}…"


def configured_hash_secret(settings=None) -> str:
    """Return the dedicated token secret, with a development-only app-secret fallback."""
    if settings is None:
        import config as settings
    dedicated = str(getattr(settings, "API_TOKEN_HASH_SECRET", "") or "")
    if dedicated:
        return dedicated
    if str(getattr(settings, "APP_ENV", "development")).lower() != "production":
        return str(getattr(settings, "SECRET_KEY", "") or "")
    return ""
