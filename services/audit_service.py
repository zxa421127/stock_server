# -*- coding: utf-8 -*-
"""Audit event construction and Flask request lifecycle integration."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any

from flask import g, has_request_context, request, session

import config
from services.audit_security import sanitize_error_message, sanitize_mapping, sanitize_request_payload, token_fingerprint
from services.audit_spool import enqueue_event
from services.web_security import client_ip


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_api_path(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _client_ip() -> str:
    if not has_request_context():
        return ""
    return client_ip()


def _infer_provider_api(path: str) -> tuple[str, str]:
    parts = [part for part in path.split("/") if part]
    # /api/v1/market/<provider>/<data_type...>
    if len(parts) >= 5 and parts[:3] == ["api", "v1", "market"]:
        return parts[3], "/".join(parts[4:])
    # /api/admin/<operation...>
    if len(parts) >= 2 and parts[0] == "api":
        provider = parts[1]
        return provider, "/".join(parts[2:])
    return "system", "/".join(parts[1:]) if parts and parts[0] == "api" else ""


def current_request_metadata() -> dict[str, Any]:
    if not has_request_context():
        return {
            "request_method": "",
            "request_path": "",
            "client_ip": "",
            "forwarded_for": "",
            "user_agent": "",
        }
    return {
        "request_method": request.method,
        "request_path": request.path,
        "client_ip": _client_ip(),
        "forwarded_for": request.headers.get("X-Forwarded-For", ""),
        "user_agent": request.headers.get("User-Agent", ""),
    }


def begin_api_audit() -> None:
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return
    if not has_request_context() or not _is_api_path(request.path):
        return
    if getattr(g, "audit_context", None):
        return
    token = request.headers.get("X-API-Token", "") or ""
    provider, api_name = _infer_provider_api(request.path)
    g.audit_context = {
        "event_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "principal_type": "anonymous",
        "user_id": None,
        "username_snapshot": "",
        "phone_snapshot": "",
        "email_snapshot": "",
        "auth_state": "unresolved" if token else "missing_token",
        "token_fingerprint": token_fingerprint(
            token, str(getattr(config, "AUDIT_TOKEN_HMAC_SECRET", config.SECRET_KEY))
        ),
        "provider": provider,
        "api_name": api_name,
        "route_rule": "",
        "request_path": request.path,
        "request_method": request.method,
        "required_scope": "",
        "package_code": "",
        "request_params": sanitize_request_payload(
            request,
            max_chars=int(getattr(config, "AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000)),
        ),
        "content_type": request.content_type or "",
        "status_code": 0,
        "success": False,
        "duration_ms": 0,
        "error_code": "missing_token" if not token else "",
        "error_message": "",
        "client_ip": _client_ip(),
        "forwarded_for": request.headers.get("X-Forwarded-For", ""),
        "user_agent": request.headers.get("User-Agent", ""),
        "created_at": _now_text(),
        "started_monotonic": time.monotonic(),
        "finalized": False,
    }


def mark_api_auth_state(state: str, **context: Any) -> None:
    if not has_request_context():
        return
    audit_context = getattr(g, "audit_context", None)
    if not audit_context:
        return
    audit_context["auth_state"] = str(state or audit_context.get("auth_state") or "unresolved")
    allowed = {
        "principal_type",
        "user_id",
        "username_snapshot",
        "phone_snapshot",
        "email_snapshot",
        "required_scope",
        "package_code",
        "provider",
        "api_name",
        "error_code",
        "error_message",
    }
    for key in allowed:
        if key in context and context[key] is not None:
            value = context[key]
            if key == "error_message":
                value = sanitize_error_message(value, max_chars=int(getattr(config, "AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000)))
            audit_context[key] = value


def finish_api_audit(response=None, exception: Exception | None = None) -> bool:
    if not has_request_context():
        return False
    audit_context = getattr(g, "audit_context", None)
    if not audit_context or audit_context.get("finalized"):
        return False
    status_code = int(getattr(response, "status_code", 500 if exception else 200))
    audit_context["route_rule"] = str(getattr(getattr(request, "url_rule", None), "rule", "") or "")
    audit_context["status_code"] = status_code
    audit_context["success"] = status_code < 400
    audit_context["duration_ms"] = max(
        0,
        int((time.monotonic() - float(audit_context.get("started_monotonic") or time.monotonic())) * 1000),
    )
    if exception is not None:
        audit_context["auth_state"] = "internal_error"
        audit_context["error_code"] = "internal_error"
        audit_context["error_message"] = sanitize_error_message(exception, max_chars=int(getattr(config, "AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000)))
    elif status_code >= 400 and not audit_context.get("error_code"):
        audit_context["error_code"] = f"http_{status_code}"
    if status_code >= 400 and not audit_context.get("error_message") and response is not None:
        try:
            payload = response.get_json(silent=True)
            if isinstance(payload, dict):
                summary = payload.get("message") or payload.get("msg") or payload.get("error")
                if isinstance(summary, (str, int, float)):
                    audit_context["error_message"] = sanitize_error_message(summary, max_chars=int(getattr(config, "AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000)))
        except Exception:
            pass
    if audit_context.get("auth_state") == "unresolved":
        audit_context["auth_state"] = "public_endpoint" if status_code < 400 else "invalid_token"
    event = {
        key: value
        for key, value in audit_context.items()
        if key not in {"started_monotonic", "finalized"}
    }
    audit_context["finalized"] = True
    try:
        return enqueue_event("api_access", event, strict=False)
    except Exception:
        logging.exception("[audit] 提交API访问审计失败")
        return False


def record_operation(
    *,
    actor_type: str,
    actor_id: int | None,
    actor_name: str,
    target_user: dict[str, Any] | None,
    action_category: str,
    action_code: str,
    action_name: str,
    success: bool,
    status_code: int,
    error_code: str = "",
    error_message: str = "",
    before_data: Any = None,
    after_data: Any = None,
    request_data: Any = None,
    related_event_id: str = "",
    strict: bool = False,
) -> tuple[str, bool]:
    event_id = str(uuid.uuid4())
    target = target_user or {}
    metadata = current_request_metadata()
    event = {
        "event_id": event_id,
        "actor_type": str(actor_type or "system"),
        "actor_id": actor_id,
        "actor_name": str(actor_name or ""),
        "target_user_id": target.get("id"),
        "target_username": str(target.get("username") or ""),
        "target_phone": str(target.get("phone") or ""),
        "target_email": str(target.get("email") or ""),
        "action_category": str(action_category or "other"),
        "action_code": str(action_code or "unknown"),
        "action_name": str(action_name or action_code or "未知操作"),
        "request_method": metadata["request_method"],
        "request_path": metadata["request_path"],
        "success": bool(success),
        "status_code": int(status_code),
        "error_code": str(error_code or ""),
        "error_message": sanitize_error_message(error_message, max_chars=int(getattr(config, "AUDIT_ERROR_MESSAGE_MAX_CHARS", 2000))),
        "before_data": sanitize_mapping(
            before_data or {}, max_chars=int(getattr(config, "AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000))
        ),
        "after_data": sanitize_mapping(
            after_data or {}, max_chars=int(getattr(config, "AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000))
        ),
        "request_data": sanitize_mapping(
            request_data or {}, max_chars=int(getattr(config, "AUDIT_REQUEST_PARAMS_MAX_CHARS", 12000))
        ),
        "related_event_id": str(related_event_id or ""),
        "client_ip": metadata["client_ip"],
        "forwarded_for": metadata["forwarded_for"],
        "user_agent": metadata["user_agent"],
        "created_at": _now_text(),
    }
    try:
        durable = enqueue_event("operation", event, strict=strict)
    except Exception:
        logging.exception("[audit] 提交操作审计失败 action=%s", action_code)
        durable = False
    return event_id, bool(durable)
