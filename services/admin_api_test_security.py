# -*- coding: utf-8 -*-
"""Shared sensitive-data guards for administrator interface tests."""
from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {
    "token", "api_token", "tushare_token", "kaipanla_token", "password",
    "csrf_token", "cookie", "session", "secret", "api_key", "authorization",
}


def _normalized_key(value: Any) -> str:
    return str(value or "").strip().lower()


def redact_sensitive(value: Any, *, key: str = "") -> Any:
    """Return a recursively redacted copy suitable for audit logs and files."""
    if _normalized_key(key) in SENSITIVE_KEYS:
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(k): redact_sensitive(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


def find_sensitive_keys(value: Any) -> set[str]:
    """Return every forbidden key found recursively in a request structure."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in SENSITIVE_KEYS:
                found.add(normalized)
            found.update(find_sensitive_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.update(find_sensitive_keys(item))
    return found


def assert_no_sensitive_keys(value: Any) -> None:
    """Reject sensitive request keys before they can be persisted."""
    found = find_sensitive_keys(value)
    if found:
        raise ValueError("禁止提交敏感参数：" + ",".join(sorted(found)))
