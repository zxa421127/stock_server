# -*- coding: utf-8 -*-
"""Business rules for the administrator user detail/edit center."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import config
import db_utils

REGISTER_SOURCE_OPTIONS: dict[str, str] = {
    "self": "用户自助注册",
    "admin": "管理员创建",
    "feishu": "飞书同步",
    "legacy_migration": "历史迁移",
    "other": "其他",
}
_ALLOWED_STATUSES = {"active", "disabled"}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PROFILE_FIELDS = ("phone", "email", "taobao_nick", "register_source")


class UserProfileError(ValueError):
    """Base class carrying a stable error code for HTTP and audit layers."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class UserProfileValidationError(UserProfileError):
    pass


class UserProfileConflictError(UserProfileError):
    pass


class UserNotFoundError(UserProfileError):
    def __init__(self, message: str = "用户不存在"):
        super().__init__(message, "user_not_found")


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_profile_input(current_user: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    """Normalize and validate administrator-editable profile fields."""
    phone = _text(payload.get("phone"))
    email = _text(payload.get("email")).lower()
    taobao_nick = _text(payload.get("taobao_nick"))
    register_source = _text(payload.get("register_source")) or _text(current_user.get("register_source")) or "other"

    if len(phone) > 64:
        raise UserProfileValidationError("手机号不能超过64个字符", "phone_too_long")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in phone):
        raise UserProfileValidationError("手机号不能包含控制字符", "invalid_phone")
    if len(email) > 254:
        raise UserProfileValidationError("邮箱不能超过254个字符", "email_too_long")
    if email and not _EMAIL_RE.fullmatch(email):
        raise UserProfileValidationError("邮箱格式不正确", "invalid_email")
    if len(taobao_nick) > 128:
        raise UserProfileValidationError("淘宝昵称不能超过128个字符", "taobao_nick_too_long")

    current_source = _text(current_user.get("register_source"))
    if register_source not in REGISTER_SOURCE_OPTIONS and register_source != current_source:
        raise UserProfileValidationError("注册来源不在允许范围内", "invalid_register_source")

    return {
        "phone": phone,
        "email": email,
        "taobao_nick": taobao_nick,
        "register_source": register_source,
    }


def _public_profile(user: dict[str, Any]) -> dict[str, Any]:
    return {field: user.get(field) or "" for field in _PROFILE_FIELDS} | {
        "id": user.get("id"),
        "username": user.get("username") or "",
        "status": user.get("status") or "",
    }


def _clear_user_auth_cache(user_id: int) -> None:
    try:
        from services.auth_context_cache import clear_user_auth_context_cache
        clear_user_auth_context_cache(int(user_id))
    except Exception:
        logging.exception("[管理员用户中心] 清理用户鉴权缓存失败: user_id=%s", user_id)


def update_user_profile(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Update editable fields atomically and return before/after snapshots."""
    conn = db_utils.get_conn()
    current = db_utils.get_user_by_id(int(user_id))
    if not current:
        raise UserNotFoundError()
    normalized = normalize_profile_input(current, payload)

    try:
        if normalized["phone"]:
            row = conn.execute(
                "SELECT id FROM users WHERE phone=? AND id<>? LIMIT 1",
                (normalized["phone"], int(user_id)),
            ).fetchone()
            if row:
                raise UserProfileConflictError("手机号已被其他用户使用", "duplicate_phone")
        if normalized["email"]:
            row = conn.execute(
                "SELECT id FROM users WHERE LOWER(email)=LOWER(?) AND id<>? LIMIT 1",
                (normalized["email"], int(user_id)),
            ).fetchone()
            if row:
                raise UserProfileConflictError("邮箱已被其他用户使用", "duplicate_email")

        before = _public_profile(current)
        changed_fields = [field for field in _PROFILE_FIELDS if str(before.get(field) or "") != normalized[field]]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET phone=?,email=?,taobao_nick=?,register_source=?,updated_at=? WHERE id=?",
            (
                normalized["phone"] or None,
                normalized["email"] or None,
                normalized["taobao_nick"] or None,
                normalized["register_source"],
                now,
                int(user_id),
            ),
        )
        conn.commit()
    except UserProfileError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise

    after_user = db_utils.get_user_by_id(int(user_id))
    _clear_user_auth_cache(int(user_id))
    return {
        "user": after_user,
        "before": before,
        "after": _public_profile(after_user or {}),
        "changed_fields": changed_fields,
    }


def set_user_status(user_id: int, new_status: str) -> dict[str, Any]:
    """Enable or disable only the user record; tokens and subscriptions remain unchanged."""
    status = _text(new_status).lower()
    if status not in _ALLOWED_STATUSES:
        raise UserProfileValidationError("账号状态只能是active或disabled", "invalid_user_status")
    conn = db_utils.get_conn()
    current = db_utils.get_user_by_id(int(user_id))
    if not current:
        raise UserNotFoundError()
    before = _public_profile(current)
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE users SET status=?,session_version=CASE WHEN ?='disabled' "
            "THEN COALESCE(session_version,1)+1 ELSE session_version END,updated_at=? WHERE id=?",
            (status, status, now, int(user_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    after_user = db_utils.get_user_by_id(int(user_id))
    _clear_user_auth_cache(int(user_id))
    return {
        "user": after_user,
        "before": before,
        "after": _public_profile(after_user or {}),
        "changed": before.get("status") != status,
    }


def get_admin_user_detail(user_id: int) -> dict[str, Any] | None:
    """Aggregate one user's profile, plans and API-key status for the detail page."""
    user = db_utils.get_user_by_id(int(user_id))
    if not user:
        return None
    conn = db_utils.get_conn()
    token_row = conn.execute(
        "SELECT COUNT(*) AS total,"
        "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active,"
        "SUM(CASE WHEN status='disabled' THEN 1 ELSE 0 END) AS disabled "
        "FROM api_keys WHERE user_id=?",
        (int(user_id),),
    ).fetchone()
    token_summary = {
        "total": int(token_row["total"] or 0),
        "active": int(token_row["active"] or 0),
        "disabled": int(token_row["disabled"] or 0),
    }
    return {
        "user": user,
        "current_subscription": db_utils.get_active_subscription(int(user_id)),
        "scheduled_subscriptions": db_utils.get_scheduled_subscriptions(int(user_id)),
        "token_summary": token_summary,
    }


def sync_user_profile_to_feishu(user_id: int) -> dict[str, str]:
    """Synchronize one user after a local update without rolling back local state."""
    if not config.ENABLE_FEISHU_SYNC:
        return {"status": "disabled", "result": "", "error": ""}
    try:
        from services.feishu_sync_service import sync_single_user_to_feishu
        result = sync_single_user_to_feishu(int(user_id))
        return {"status": "success", "result": str(result or ""), "error": ""}
    except Exception as exc:
        logging.exception("[管理员用户中心] 飞书单用户同步失败: user_id=%s", user_id)
        return {"status": "failed", "result": "", "error": str(exc)}
