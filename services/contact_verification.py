# -*- coding: utf-8 -*-
"""Database-backed, one-time contact verification challenges."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import config
from db_utils import get_conn


@dataclass(frozen=True)
class ContactChallenge:
    challenge_id: str
    code: str
    channel: str
    target: str
    expires_at_ts: int


def _secret() -> bytes:
    value = str(getattr(config, "CONTACT_VERIFICATION_HMAC_SECRET", "") or "")
    if len(value) < 16:
        if str(getattr(config, "APP_ENV", "development")).lower() == "production":
            raise RuntimeError("CONTACT_VERIFICATION_HMAC_SECRET未配置或长度不足")
        value = str(getattr(config, "SECRET_KEY", "development-contact-secret") or "")
    return hashlib.sha256(("contact-verification:" + value).encode("utf-8")).digest()


def _hash_code(challenge_id: str, target: str, code: str) -> str:
    return hmac.new(
        _secret(),
        f"{challenge_id}:{target}:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_challenge(
    *,
    purpose: str,
    channel: str,
    target: str,
    payload: dict[str, Any],
    now_ts: int | None = None,
    ttl_seconds: int | None = None,
) -> ContactChallenge:
    purpose = str(purpose or "").strip().lower()
    channel = str(channel or "").strip().lower()
    target = str(target or "").strip()
    if purpose not in {"registration"}:
        raise ValueError("不支持的验证码用途")
    if channel not in {"email", "sms"}:
        raise ValueError("不支持的验证渠道")
    if not target:
        raise ValueError("验证目标不能为空")
    now = int(time.time() if now_ts is None else now_ts)
    ttl = int(ttl_seconds or getattr(config, "CONTACT_CODE_TTL_SECONDS", 300))
    resend = int(getattr(config, "CONTACT_CODE_RESEND_SECONDS", 60))
    max_attempts = int(getattr(config, "CONTACT_CODE_MAX_ATTEMPTS", 5))
    conn = get_conn()
    recent = conn.execute(
        "SELECT created_at_ts FROM contact_verification_challenges "
        "WHERE purpose=? AND channel=? AND target=? AND status='active' "
        "ORDER BY id DESC LIMIT 1",
        (purpose, channel, target),
    ).fetchone()
    if recent and now - int(recent["created_at_ts"]) < resend:
        raise ValueError("验证码发送过于频繁，请稍后再试")

    challenge_id = secrets.token_urlsafe(24)
    code = f"{100000 + secrets.randbelow(900000):06d}"
    expires = now + max(60, min(1800, ttl))
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    conn.execute(
        "INSERT INTO contact_verification_challenges "
        "(challenge_id,purpose,channel,target,code_hash,payload_json,status,attempts,max_attempts,created_at_ts,expires_at_ts) "
        "VALUES (?,?,?,?,?,?,'active',0,?,?,?)",
        (
            challenge_id,
            purpose,
            channel,
            target,
            _hash_code(challenge_id, target, code),
            payload_json,
            max(1, min(20, max_attempts)),
            now,
            expires,
        ),
    )
    conn.commit()
    return ContactChallenge(challenge_id, code, channel, target, expires)


def mark_delivery_failed(challenge_id: str, error: str) -> None:
    conn = get_conn()
    conn.execute(
        "UPDATE contact_verification_challenges SET status='delivery_failed',delivery_error=? "
        "WHERE challenge_id=? AND status='active'",
        (str(error or "delivery failed")[:500], challenge_id),
    )
    conn.commit()


def verify_and_consume_challenge(
    challenge_id: str,
    supplied_code: str,
    *,
    now_ts: int | None = None,
) -> dict[str, Any]:
    now = int(time.time() if now_ts is None else now_ts)
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM contact_verification_challenges WHERE challenge_id=? LIMIT 1",
        (str(challenge_id or ""),),
    ).fetchone()
    if not row:
        raise ValueError("验证码请求不存在")
    status = str(row["status"] or "")
    if status == "consumed":
        raise ValueError("验证码已使用")
    if status == "locked":
        raise ValueError("验证码尝试次数过多")
    if status == "expired":
        raise ValueError("验证码已过期")
    if status != "active":
        raise ValueError("验证码不可用")
    if now > int(row["expires_at_ts"]):
        conn.execute(
            "UPDATE contact_verification_challenges SET status='expired' WHERE id=?",
            (int(row["id"]),),
        )
        conn.commit()
        raise ValueError("验证码已过期")
    attempts = int(row["attempts"] or 0)
    max_attempts = int(row["max_attempts"] or 0)
    if attempts >= max_attempts:
        conn.execute(
            "UPDATE contact_verification_challenges SET status='locked' WHERE id=?",
            (int(row["id"]),),
        )
        conn.commit()
        raise ValueError("验证码尝试次数过多")

    supplied = str(supplied_code or "").strip()
    expected = str(row["code_hash"] or "")
    actual = _hash_code(str(row["challenge_id"]), str(row["target"]), supplied)
    if not supplied or not hmac.compare_digest(actual, expected):
        attempts += 1
        new_status = "locked" if attempts >= max_attempts else "active"
        conn.execute(
            "UPDATE contact_verification_challenges SET attempts=?,status=? WHERE id=?",
            (attempts, new_status, int(row["id"])),
        )
        conn.commit()
        raise ValueError("验证码错误")

    conn.execute(
        "UPDATE contact_verification_challenges SET status='consumed',consumed_at_ts=? WHERE id=?",
        (now, int(row["id"])),
    )
    conn.commit()
    payload = json.loads(str(row["payload_json"] or "{}"))
    payload["_verified_channel"] = str(row["channel"])
    payload["_verified_target"] = str(row["target"])
    return payload
