# -*- coding: utf-8 -*-
"""Normalization and strict size/format checks for public account inputs."""
from __future__ import annotations

from dataclasses import dataclass
import re

import config

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^\+?[0-9]{6,20}$")


@dataclass(frozen=True)
class RegistrationInput:
    username: str
    password: str
    phone: str | None
    email: str | None


def _reject_controls(value: str, label: str) -> None:
    if _CONTROL_RE.search(value):
        raise ValueError(f"{label}不能包含控制字符")


def _normalize_username(value: str) -> str:
    username = str(value or "").strip()
    _reject_controls(username, "用户名")
    min_len = int(getattr(config, "USER_USERNAME_MIN_LENGTH", 3))
    max_len = int(getattr(config, "USER_USERNAME_MAX_LENGTH", 64))
    if len(username) < min_len:
        raise ValueError(f"用户名至少 {min_len} 个字符")
    if len(username) > max_len:
        raise ValueError(f"用户名最多 {max_len} 个字符")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in username):
        raise ValueError("用户名只能包含中文、字母、数字、下划线和连字符")
    return username


def _validate_password(value: str, *, label: str = "密码") -> str:
    password = str(value or "")
    _reject_controls(password, label)
    min_len = int(getattr(config, "USER_PASSWORD_MIN_LENGTH", 12))
    max_len = int(getattr(config, "USER_PASSWORD_MAX_LENGTH", 128))
    if len(password) < min_len:
        raise ValueError(f"{label}至少 {min_len} 位")
    if len(password) > max_len:
        raise ValueError(f"{label}最多 {max_len} 位")
    return password


def _normalize_email(value: str | None) -> str | None:
    email = str(value or "").strip().lower()
    if not email:
        return None
    _reject_controls(email, "邮箱")
    max_len = int(getattr(config, "USER_EMAIL_MAX_LENGTH", 254))
    if len(email) > max_len:
        raise ValueError(f"邮箱最多 {max_len} 个字符")
    if not _EMAIL_RE.fullmatch(email):
        raise ValueError("邮箱格式不正确")
    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or len(domain) > 253 or ".." in email:
        raise ValueError("邮箱格式不正确")
    return email


def _normalize_phone(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    _reject_controls(raw, "手机号")
    compact = re.sub(r"[\s()\-]", "", raw)
    max_len = int(getattr(config, "USER_PHONE_MAX_LENGTH", 32))
    if len(compact) > max_len:
        raise ValueError(f"手机号最多 {max_len} 个字符")
    if not _PHONE_RE.fullmatch(compact):
        raise ValueError("手机号格式不正确")
    return compact


def normalize_registration_input(
    *, username: str, password: str, phone: str | None, email: str | None
) -> RegistrationInput:
    normalized = RegistrationInput(
        username=_normalize_username(username),
        password=_validate_password(password),
        phone=_normalize_phone(phone),
        email=_normalize_email(email),
    )
    if not normalized.phone and not normalized.email:
        raise ValueError("至少填写邮箱或手机号")
    return normalized


def validate_login_input(account: str, password: str) -> tuple[str, str]:
    normalized_account = str(account or "").strip()
    raw_password = str(password or "")
    _reject_controls(normalized_account, "账号")
    _reject_controls(raw_password, "密码")
    max_account = int(getattr(config, "USER_ACCOUNT_MAX_LENGTH", 254))
    max_password = int(getattr(config, "USER_PASSWORD_MAX_LENGTH", 128))
    if not normalized_account:
        raise ValueError("账号不能为空")
    if len(normalized_account) > max_account:
        raise ValueError(f"账号最多 {max_account} 个字符")
    if len(raw_password) > max_password:
        raise ValueError(f"密码最多 {max_password} 位")
    return normalized_account, raw_password


def validate_password_reset_input(account: str, contact: str) -> tuple[str, str]:
    normalized_account = str(account or "").strip()
    normalized_contact = str(contact or "").strip()
    _reject_controls(normalized_account, "账号")
    _reject_controls(normalized_contact, "联系方式")
    account_max = int(getattr(config, "USER_ACCOUNT_MAX_LENGTH", 254))
    contact_max = int(getattr(config, "PASSWORD_RESET_CONTACT_MAX_LENGTH", 254))
    if not normalized_account or not normalized_contact:
        raise ValueError("请填写账号和联系方式")
    if len(normalized_account) > account_max:
        raise ValueError(f"账号最多 {account_max} 个字符")
    if len(normalized_contact) > contact_max:
        raise ValueError(f"联系方式最多 {contact_max} 个字符")
    return normalized_account, normalized_contact


def validate_new_password(password: str, *, label: str = "密码") -> str:
    return _validate_password(password, label=label)
