# -*- coding: utf-8 -*-
"""API-key authentication, plan-scope authorization, quotas and usage logging."""
from __future__ import annotations

import json
import logging
import time
from functools import wraps
from typing import Callable

from flask import g, jsonify, request

from config import CONTACT_NOTE, CONTACT_QQ, CONTACT_WECHAT
from db_utils import get_active_subscription, get_api_key_auth_record, get_plan_by_code
from services.auth_context_cache import get_or_load_auth_context
from services.plan_catalog import scope_allowed, scope_display_name
from services.rate_limit_service import check_rate_limit
from services.usage_log_queue import enqueue_api_key_touch, enqueue_usage_log
from services.audit_service import mark_api_auth_state

ScopeResolver = Callable[..., str]


class AuthError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        audit_state: str = "invalid_token",
        error_code: str = "auth_error",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.audit_state = audit_state
        self.error_code = error_code


def _json_response(status_code: int, message: str, data=None):
    return jsonify({"code": status_code, "message": message, "data": data}), status_code


def _parse_scopes(plan: dict) -> list[str]:
    try:
        scopes = json.loads(plan.get("scopes") or "[]")
        return scopes if isinstance(scopes, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _extract_status_code(result) -> int:
    if isinstance(result, tuple) and len(result) >= 2 and isinstance(result[1], int):
        return result[1]
    if hasattr(result, "status_code"):
        return int(result.status_code)
    return 200


def _subscription_required_message() -> str:
    contacts = []
    if CONTACT_QQ:
        contacts.append(f"QQ：{CONTACT_QQ}")
    if CONTACT_WECHAT:
        contacts.append(f"微信：{CONTACT_WECHAT}")
    message = f"当前账号暂未开通接口套餐。{CONTACT_NOTE}"
    if contacts:
        message += " 联系方式：" + "，".join(contacts)
    return message


def _load_auth_context(token: str) -> dict:
    record = get_api_key_auth_record(token)
    if not record:
        raise AuthError(401, "Token无效", audit_state="invalid_token", error_code="invalid_token")
    if record.get("key_status") != "active" or record.get("user_status") != "active":
        raise AuthError(
            401,
            "Token无效或用户已停用",
            audit_state="disabled_token",
            error_code="disabled_token",
        )

    user = {
        "id": record.get("id"),
        "username": record.get("username"),
        "phone": record.get("phone"),
        "email": record.get("email"),
        "taobao_nick": record.get("taobao_nick"),
        "status": record.get("user_status"),
        "api_key_id": record.get("api_key_id"),
    }
    subscription = get_active_subscription(int(user["id"]))
    if not subscription:
        raise AuthError(
            402,
            _subscription_required_message(),
            audit_state="expired_subscription",
            error_code="expired_subscription",
        )

    plan = get_plan_by_code(subscription["plan_code"])
    if not plan or plan.get("status") not in {None, "active"}:
        raise AuthError(
            403,
            "套餐不存在或已停用，请联系管理员",
            audit_state="insufficient_scope",
            error_code="plan_unavailable",
        )

    return {
        "user": user,
        "subscription": subscription,
        "plan": plan,
        "scopes": _parse_scopes(plan),
    }


def resolve_auth_context(token: str) -> dict:
    if not token:
        raise AuthError(
            401,
            "缺少 X-API-Token",
            audit_state="missing_token",
            error_code="missing_token",
        )
    return get_or_load_auth_context(token, _load_auth_context)


def require_scope(scope: str | ScopeResolver):
    """Authorize a static scope or a scope resolved from the route arguments."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            started_at = time.monotonic()
            required_scope = scope(*args, **kwargs) if callable(scope) else scope
            required_scope = required_scope or "tushare:read"

            api_token = request.headers.get("X-API-Token", "")
            try:
                context = resolve_auth_context(api_token)
            except AuthError as exc:
                mark_api_auth_state(
                    exc.audit_state,
                    required_scope=required_scope,
                    error_code=exc.error_code,
                    error_message=exc.message,
                )
                return _json_response(exc.status_code, exc.message)

            user = context["user"]
            plan = context["plan"]
            subscription = context["subscription"]
            common_audit = {
                "principal_type": "user",
                "user_id": int(user["id"]),
                "username_snapshot": user.get("username") or "",
                "phone_snapshot": user.get("phone") or "",
                "email_snapshot": user.get("email") or "",
                "required_scope": required_scope,
                "package_code": subscription.get("plan_code") or plan.get("plan_code") or "",
            }
            provider_code = kwargs.get("provider_code")
            data_type = kwargs.get("data_type")
            if provider_code:
                common_audit["provider"] = provider_code
            if data_type:
                common_audit["api_name"] = data_type

            enqueue_api_key_touch(api_token)
            if not scope_allowed(required_scope, context["scopes"]):
                mark_api_auth_state(
                    "insufficient_scope",
                    **common_audit,
                    error_code="insufficient_scope",
                    error_message=f"当前套餐无权限访问：{scope_display_name(required_scope)}",
                )
                return _json_response(403, f"当前套餐无权限访问：{scope_display_name(required_scope)}")

            rate_limit_result = check_rate_limit(int(user["id"]), required_scope, plan)
            allowed, message = rate_limit_result
            if not allowed:
                mark_api_auth_state(
                    "rate_limited",
                    **common_audit,
                    error_code="rate_limited",
                    error_message=message,
                )
                response = _json_response(429, message)
                retry_after_seconds = getattr(
                    rate_limit_result,
                    "retry_after_seconds",
                    None,
                )
                if retry_after_seconds is not None:
                    try:
                        retry_after_value = max(1, int(retry_after_seconds))
                    except (TypeError, ValueError):
                        retry_after_value = None
                    if retry_after_value is not None:
                        response[0].headers["Retry-After"] = str(retry_after_value)
                return response

            mark_api_auth_state("valid", **common_audit)
            g.current_user = user
            g.current_subscription = subscription
            g.current_plan = plan
            g.current_scope = required_scope

            status_code = 500
            success = False
            try:
                result = view_func(*args, **kwargs)
                status_code = _extract_status_code(result)
                success = status_code < 400
                return result
            finally:
                try:
                    enqueue_usage_log(
                        user_id=int(user["id"]),
                        endpoint=request.path,
                        method=request.method,
                        scope=required_scope,
                        success=success,
                        status_code=status_code,
                        cost_ms=int((time.monotonic() - started_at) * 1000),
                        ip=request.remote_addr or "",
                    )
                except Exception as exc:
                    logging.exception("[鉴权] 写入 usage_logs 失败: %s", exc)

        return wrapper
    return decorator
