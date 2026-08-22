# -*- coding: utf-8 -*-
"""Namespaced, digest-only, one-time CAPTCHA challenge storage."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any, MutableMapping

import config

CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"


def session_key(namespace: str) -> str:
    normalized = "".join(ch for ch in str(namespace or "default").lower() if ch.isalnum() or ch in "_-")
    return f"_captcha_v1_{normalized or 'default'}"


def _session(session_obj: MutableMapping[str, Any] | None):
    if session_obj is not None:
        return session_obj
    from flask import session
    return session


def _secret_bytes(namespace: str) -> bytes:
    secret = str(getattr(config, "SECRET_KEY", "") or "")
    if len(secret) < 16:
        secret = "development-captcha-secret-please-change"
    context = f"captcha:{namespace}:" + secret
    return hashlib.sha256(context.encode("utf-8")).digest()


def _digest(namespace: str, nonce: str, code: str) -> str:
    return hmac.new(
        _secret_bytes(namespace),
        f"{nonce}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_captcha(
    session_obj: MutableMapping[str, Any] | None,
    namespace: str,
    *,
    length: int = 5,
    now: float | None = None,
) -> str:
    target = _session(session_obj)
    size = max(4, min(8, int(length)))
    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(size))
    nonce = secrets.token_urlsafe(18)
    target[session_key(namespace)] = {
        "nonce": nonce,
        "digest": _digest(namespace, nonce, code),
        "issued_at": float(time.time() if now is None else now),
    }
    try:
        target.modified = True
    except Exception:
        pass
    return code


def verify_captcha(
    session_obj: MutableMapping[str, Any] | None,
    namespace: str,
    supplied: str | None,
    *,
    now: float | None = None,
    ttl_seconds: int = 300,
    consume: bool = True,
) -> bool:
    target = _session(session_obj)
    key = session_key(namespace)
    state = target.pop(key, None) if consume else target.get(key)
    try:
        target.modified = True
    except Exception:
        pass
    if not isinstance(state, dict):
        return False
    nonce = str(state.get("nonce") or "")
    expected = str(state.get("digest") or "")
    try:
        issued_at = float(state.get("issued_at") or 0)
    except (TypeError, ValueError):
        return False
    current = float(time.time() if now is None else now)
    ttl = max(30, min(1800, int(ttl_seconds)))
    if not nonce or not expected or issued_at <= 0 or current < issued_at - 5 or current - issued_at > ttl:
        return False
    value = str(supplied or "").strip()
    if not value:
        return False
    return hmac.compare_digest(_digest(namespace, nonce, value), expected)
