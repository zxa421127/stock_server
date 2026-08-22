# -*- coding: utf-8 -*-
"""Security helpers for audit logging and export."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_TERMS = (
    "password",
    "old_password",
    "new_password",
    "confirm_password",
    "token",
    "api_token",
    "x-api-token",
    "authorization",
    "cookie",
    "session",
    "secret",
    "access_key",
    "private_key",
)


def _normalized_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return any(term.replace("-", "_") in normalized for term in _SENSITIVE_TERMS)


def _sanitize(value: Any, key: Any = None) -> Any:
    if key is not None and _is_sensitive_key(key):
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return sanitize_error_message(value, max_chars=max(len(value), 1))
    if isinstance(value, dict):
        return {str(k): _sanitize(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(item) for item in value]
    return str(value)


def sanitize_mapping(value: Any, *, max_chars: int | None = None) -> Any:
    cleaned = _sanitize(value)
    if max_chars is None or max_chars <= 0:
        return cleaned
    serialized = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(serialized) <= max_chars:
        return cleaned
    return {"truncated": True, "preview": serialized[:max_chars]}


def sanitize_value(value: Any, *, max_chars: int | None = None) -> Any:
    return sanitize_mapping(value, max_chars=max_chars)


def sanitize_request_payload(request, *, max_chars: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "query": request.args.to_dict(flat=False) if getattr(request, "args", None) else {},
        "json": {},
        "form": request.form.to_dict(flat=False) if getattr(request, "form", None) else {},
        "files": [],
    }
    if getattr(request, "is_json", False):
        body = request.get_json(silent=True)
        payload["json"] = body if body is not None else {}
    files = getattr(request, "files", None)
    if files:
        payload["files"] = [
            {
                "field": field,
                "filename": storage.filename or "",
                "content_type": storage.content_type or "",
                "content_length": getattr(storage, "content_length", None),
            }
            for field, storage in files.items()
        ]
    return sanitize_mapping(payload, max_chars=max_chars)


def mask_phone(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) >= 7:
        return f"{text[:3]}{'*' * max(4, len(text) - 7)}{text[-4:]}"
    if len(text) == 1:
        return "*"
    return f"{text[0]}{'*' * max(1, len(text) - 2)}{text[-1]}"


def mask_email(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if "@" not in text:
        return mask_text(text)
    local, domain = text.split("@", 1)
    prefix = local[:3] if local else ""
    return f"{prefix}***@{domain}"


def mask_text(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) == 1:
        return "*"
    if len(text) == 2:
        return f"{text[0]}*"
    return f"{text[0]}{'*' * max(1, len(text) - 2)}{text[-1]}"


def mask_record(record: dict[str, Any], fields: set[str] | None = None) -> dict[str, Any]:
    target_fields = {field.lower() for field in fields} if fields else None
    result: dict[str, Any] = {}
    for key, value in record.items():
        lower = key.lower()
        should_mask = target_fields is None or lower in target_fields
        if should_mask and "phone" in lower:
            result[key] = mask_phone(str(value or ""))
        elif should_mask and "email" in lower:
            result[key] = mask_email(str(value or ""))
        elif should_mask and lower in {"name", "real_name", "taobao_nick"}:
            result[key] = mask_text(str(value or ""))
        else:
            result[key] = value
    return result


def mask_sensitive_structure(value: Any, key: str = "") -> Any:
    """Recursively mask business contact fields for default UI/CSV output."""
    normalized = _normalized_key(key)
    if isinstance(value, dict):
        return {str(k): mask_sensitive_structure(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [mask_sensitive_structure(item) for item in value]
    if value is None:
        return value
    if "email" in normalized:
        return mask_email(str(value))
    if "phone" in normalized or "mobile" in normalized:
        return mask_phone(str(value))
    return value


def token_fingerprint(token: str, secret: str) -> str:
    raw = str(token or "")
    if not raw:
        return ""
    key = str(secret or "").encode("utf-8")
    return hmac.new(key, raw.encode("utf-8"), hashlib.sha256).hexdigest()


_LABELED_CREDENTIAL_RE = re.compile(
    r"(?i)\b(authorization|x[-_]api[-_]token|api[-_]token|password|old[-_]password|new[-_]password|confirm[-_]password|access[-_]key|private[-_]key|secret|token|cookie|session)\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def sanitize_error_message(value: Any, *, max_chars: int = 2000) -> str:
    text = str(value or "")
    text = _LABELED_CREDENTIAL_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED]", text)
    return text[: max(0, int(max_chars))] if max_chars is not None else text


def safe_csv_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    stripped = text.lstrip()
    if stripped[:1] in {"=", "+", "-", "@"}:
        return "'" + text
    return text
