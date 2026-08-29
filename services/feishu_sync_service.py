# -*- coding: utf-8 -*-
"""
services/feishu_sync_service.py

飞书多维表格双向同步服务。

当前版本适配单 Token 新会员体系：
users + api_keys + subscriptions + plans

同步规则：
1. 本地数据库是会员、Token、套餐、权限和审计信息的唯一权威源。
2. 本地 → 飞书：按“用户ID”发布会员展示信息，完整 Token 不进入飞书。
3. 飞书 → 本地：只导入新用户登记或关联已有用户，不覆盖既有本地资料/权限。
4. 开盘啦竞价表：只做本地不可变快照 → 飞书。
"""
import logging
import sqlite3
import threading
import time
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

import config
from db_utils import (
    get_conn,
    is_database_busy_error,
    refresh_subscription_states,
    run_db_write_with_retry,
)
from integrations.feishu.bitable import get_bitable_manager
from services.member_service import get_or_create_api_key
from services.plan_catalog import LEGACY_PUBLIC_PLAN_MIGRATION
from services.audit_security import token_fingerprint
from services.process_lock import process_lock
from services.sync_result import SyncResult

SYNC_INTERVAL_MINUTES = config.FEISHU_SYNC_INTERVAL_MINUTES
_sync_running = False
_sync_thread = None
_last_bidding_sync_date = None
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_RUNTIME_MEMBER_TABLES = ("users", "api_keys", "subscriptions", "plans")
_RUNTIME_BIDDING_TABLES = ("kaipanla_bidding_snapshots",)


class RuntimeSchemaNotReadyError(RuntimeError):
    """Raised when a standalone sync command runs before startup initialization."""


def _sync_lock_settings() -> tuple[str, float]:
    return (
        str(getattr(config, "FEISHU_SYNC_LOCK_FILE", "data/feishu_sync.lock")),
        float(getattr(config, "FEISHU_SYNC_LOCK_TIMEOUT_SECONDS", 0.0) or 0.0),
    )


def _ensure_runtime_db_ready(required_tables: tuple[str, ...] = _RUNTIME_MEMBER_TABLES) -> None:
    """Read-only schema guard; runtime syncs must never rerun migrations."""
    conn = get_conn()
    placeholders = ",".join("?" for _ in required_tables)
    rows = conn.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
        required_tables,
    ).fetchall()
    existing = {str(row[0]) for row in rows}
    missing = [name for name in required_tables if name not in existing]
    if missing:
        raise RuntimeSchemaNotReadyError(
            "数据库尚未完成启动初始化，缺少表: " + ", ".join(missing)
        )


def _busy_result(counts: tuple[int, ...], task_name: str) -> SyncResult:
    message = f"{task_name}正在运行，当前任务未启动，请稍后重试"
    logging.warning("[同步] %s", message)
    return SyncResult(counts, status="busy", message=message)


def _database_busy_result(counts: tuple[int, ...], task_name: str, exc: BaseException) -> SyncResult:
    message = f"SQLite数据库正被其他任务写入，{task_name}未完成，请稍后重试"
    logging.error("[同步] %s: %s", message, exc)
    return SyncResult(counts, status="database_busy", message=message)


def _schema_not_ready_result(counts: tuple[int, ...], exc: BaseException) -> SyncResult:
    message = str(exc)
    logging.error("[同步] %s", message)
    return SyncResult(counts, status="schema_not_ready", message=message)


def _china_now() -> datetime:
    return datetime.now(_SHANGHAI_TZ)


# ==================== 通用转换工具 ====================
def feishu_time_to_str(value: Any) -> str:
    """把飞书日期字段返回值转成本地字符串。"""
    if not value:
        return ""
    if isinstance(value, (int, float)):
        num = float(value)
        if num > 1e12:
            num = num / 1000
        return datetime.fromtimestamp(num).strftime("%Y-%m-%d %H:%M:%S")

    text = str(value).strip()
    if not text:
        return ""
    try:
        num = float(text)
        if num > 1e12:
            num = num / 1000
        return datetime.fromtimestamp(num).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

    return text


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_token_expire_status(expire_time: str) -> str:
    try:
        expire_dt = datetime.strptime(expire_time, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return "时间格式错误"
    return "有效" if datetime.now() <= expire_dt else "已过期"


def role_from_plan_type(plan_type: Optional[str]) -> str:
    """本地套餐类型映射到飞书“账号权限”。"""
    plan_type = (plan_type or "").strip().lower()
    if plan_type == "admin":
        return "admin"
    if plan_type in ("special", "realtime"):
        return "vip"
    return "member"


def plan_code_from_feishu(fields: dict) -> str:
    """
    从飞书字段推断套餐代码。

    注意：
    - “套餐代码”为空时，不再默认写成 general_month；
    - 只有旧飞书记录带了授权时间或状态为“有效”时，才按“账号权限”兜底映射；
    - 普通注册用户 / 未开通用户应保持 plan_code 为空，避免被误开通。
    """
    plan_code = safe_text(fields.get("套餐代码")).strip()
    if plan_code:
        # 飞书表可能仍保存六套餐迁移前的 history_*/realtime_* 代码。
        # 在飞书→本地阶段先映射为当前代码，避免出现“套餐代码不存在”，
        # 随后的本地→飞书同步会把新代码回写到多维表格。
        return LEGACY_PUBLIC_PLAN_MIGRATION.get(plan_code, plan_code)

    status_text = safe_text(fields.get("状态")).strip()
    has_auth_time = bool(fields.get("授权截止时间") or fields.get("开始授权时间"))

    if status_text == "有效" or has_auth_time:
        role = safe_text(fields.get("账号权限") or "member").strip().lower()
        if role == "admin":
            return "admin_internal"
        if role in ("vip", "realtime", "实时"):
            return "special_month"
        return "general_month"

    return ""


def local_status_from_feishu(status_text: str) -> tuple[str, str, str]:
    """
    飞书“状态”映射成本地 users/api_keys/subscriptions 状态。
    返回：(user_status, key_status, subscription_status)
    """
    status_text = (status_text or "有效").strip()
    if status_text in ("已禁用", "禁用", "disabled", "停用"):
        return "disabled", "disabled", "disabled"
    return "active", "active", "active"


def feishu_status_from_local(user_status: str, key_status: str, sub_status: str, expire_time: str, has_plan: bool = True) -> str:
    """
    本地状态映射到飞书“状态”。

    飞书旧表常见选项是：有效 / 已过期 / 已禁用。
    未开通用户默认写“已过期”，并在备注里写明“普通注册用户，暂未开通套餐”，避免飞书单选字段没有“未开通”选项时同步失败。
    如果你已经在飞书“状态”字段增加了“未开通”选项，可以在 .env 增加：
    FEISHU_UNOPENED_STATUS_TEXT=未开通
    """
    if user_status != "active" or key_status != "active" or sub_status == "disabled":
        return "已禁用"

    if not has_plan:
        return getattr(config, "FEISHU_UNOPENED_STATUS_TEXT", None) or "已过期"

    try:
        if datetime.strptime(expire_time, "%Y-%m-%d %H:%M:%S") < datetime.now():
            return "已过期"
    except Exception:
        return "时间格式错误"
    return "有效"


def safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def _token_log_fingerprint(token: str) -> str:
    """Return a stable short HMAC fingerprint without exposing Token text."""
    digest = token_fingerprint(
        safe_text(token).strip(),
        safe_text(getattr(config, "AUDIT_TOKEN_HMAC_SECRET", config.SECRET_KEY)),
    )
    return digest[:12]


def _merge_remark_parts(*values: Any) -> str:
    """Merge semicolon-separated remark fragments without repeated feedback-loop entries."""
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = safe_text(value).strip()
        if not text:
            continue
        for raw_part in text.replace("；", ";").split(";"):
            part = raw_part.strip()
            if part and part not in seen:
                seen.add(part)
                parts.append(part)
    return "; ".join(parts)


def _feishu_config_ready() -> bool:
    return bool(
        getattr(config, "FEISHU_APP_ID", "")
        and getattr(config, "FEISHU_APP_SECRET", "")
        and getattr(config, "FEISHU_BTABLE_APP_TOKEN", "")
        and getattr(config, "FEISHU_BTABLE_TABLE_ID", "")
    )


def _get_local_member_rows(user_id: Optional[int] = None) -> list[dict]:
    """Read one row per user with the current plan, next scheduled plan and latest action."""
    refresh_subscription_states(int(user_id) if user_id is not None else None)
    conn = get_conn()
    cursor = conn.cursor()
    params = []
    where_sql = ""
    if user_id is not None:
        where_sql = "WHERE u.id=?"
        params.append(int(user_id))
    now = now_str()
    cursor.execute(
        f"""
        SELECT u.id AS user_id,u.username,u.phone,u.email,u.taobao_nick,
               u.status AS user_status,u.register_source,u.created_at AS user_created_at,
               k.id AS api_key_id,k.token_prefix,k.token_last4,k.status AS key_status,k.created_at AS token_create_time,
               cur.id AS subscription_id,cur.plan_code,cur.plan_type,cur.start_time,cur.expire_time,
               cur.status AS subscription_status,cur.source_order_no,cur.remark,
               cur.operation_type,cur.extra_days,
               nxt.id AS scheduled_subscription_id,nxt.plan_code AS scheduled_plan_code,
               nxt.plan_type AS scheduled_plan_type,nxt.start_time AS scheduled_start_time,
               nxt.expire_time AS scheduled_expire_time,nxt.extra_days AS scheduled_extra_days,
               ord.operation_type AS latest_operation_type,ord.extra_days AS latest_extra_days
        FROM users u
        LEFT JOIN api_keys k ON k.id=(
            SELECT k2.id FROM api_keys k2 WHERE k2.user_id=u.id
            ORDER BY CASE k2.status WHEN 'active' THEN 0 ELSE 1 END,k2.id ASC LIMIT 1
        )
        LEFT JOIN subscriptions cur ON cur.id=(
            SELECT s1.id FROM subscriptions s1 WHERE s1.user_id=u.id AND s1.status='active'
              AND s1.start_time<=? AND s1.expire_time>=?
            ORDER BY s1.start_time DESC,s1.id DESC LIMIT 1
        )
        LEFT JOIN subscriptions nxt ON nxt.id=(
            SELECT s2.id FROM subscriptions s2 WHERE s2.user_id=u.id AND s2.status='scheduled'
            ORDER BY s2.start_time ASC,s2.id ASC LIMIT 1
        )
        LEFT JOIN manual_orders ord ON ord.id=(
            SELECT o2.id FROM manual_orders o2 WHERE o2.user_id=u.id ORDER BY o2.id DESC LIMIT 1
        )
        {where_sql}
        ORDER BY u.id DESC
        """,
        (now, now, *params),
    )
    return [dict(r) for r in cursor.fetchall()]

def _build_feishu_member_fields(row: dict, bitable) -> dict:
    """Convert one authoritative local membership row to Feishu display fields."""
    user_id = row.get("user_id")
    username = row.get("username") or row.get("taobao_nick") or row.get("phone") or row.get("email") or f"user_{user_id}"
    has_plan = bool(row.get("plan_code"))
    plan_code = safe_text(row.get("plan_code")).strip()
    plan_type = safe_text(row.get("plan_type")).strip()
    key_status = row.get("key_status") or "active"
    user_status = row.get("user_status") or "active"
    sub_status = row.get("subscription_status") or ("active" if has_plan else "")
    expire_time = safe_text(row.get("expire_time")).strip()
    start_time = safe_text(row.get("start_time")).strip()
    token_create_time = row.get("token_create_time") or row.get("user_created_at") or now_str()
    role = role_from_plan_type(plan_type if has_plan else None)
    status_text = feishu_status_from_local(user_status, key_status, sub_status, expire_time, has_plan=has_plan)

    order_remark = (
        f"订单:{safe_text(row.get('source_order_no')).strip()}"
        if row.get("source_order_no")
        else ""
    )
    unopened_remark = "普通注册用户，暂未开通套餐" if not has_plan else ""
    remark = _merge_remark_parts(row.get("remark"), order_remark, unopened_remark)

    fields = {
        "用户ID": str(user_id),
        # 主动清空旧飞书表中的完整Token；Token只保存在本地数据库/用户中心。
        "授权码": "",
        "用户名称": username,
        "账号权限": role,
        "套餐代码": plan_code,
        "套餐类型": plan_type,
        "手机号": safe_text(row.get("phone")),
        "邮箱": safe_text(row.get("email")),
        "淘宝昵称": safe_text(row.get("taobao_nick")),
        "用户状态": user_status,
        "Token状态": key_status,
        "来源订单号": safe_text(row.get("source_order_no")),
        "记录时间": bitable._str_to_ms(token_create_time or now_str()),
        "状态": status_text,
        "备注": remark,
    }
    if has_plan:
        fields["开始授权时间"] = bitable._str_to_ms(start_time or now_str())
        fields["授权截止时间"] = bitable._str_to_ms(expire_time or start_time or now_str())
    else:
        fields["开始授权时间"] = None
        fields["授权截止时间"] = None

    if getattr(config, "FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED", False):
        action_labels = {
            "open": "首次开通",
            "renew": "续费当前套餐",
            "switch_now": "立即换套餐",
            "switch_scheduled": "到期后换套餐",
            "feishu_sync": "飞书同步",
        }
        fields.update({
            "待生效套餐代码": safe_text(row.get("scheduled_plan_code")),
            "待生效套餐类型": safe_text(row.get("scheduled_plan_type")),
            "最近操作类型": action_labels.get(
                safe_text(row.get("latest_operation_type")),
                safe_text(row.get("latest_operation_type")),
            ),
            "额外补偿天数": int(row.get("latest_extra_days") or 0),
        })
        fields["待生效开始时间"] = (
            bitable._str_to_ms(row.get("scheduled_start_time")) if row.get("scheduled_start_time") else None
        )
        fields["待生效截止时间"] = (
            bitable._str_to_ms(row.get("scheduled_expire_time")) if row.get("scheduled_expire_time") else None
        )
    return fields

def _sync_single_user_to_feishu_impl(user_id: int) -> str:
    _ensure_runtime_db_ready()
    run_db_write_with_retry(
        lambda: get_or_create_api_key(int(user_id)),
        operation_name=f"feishu-single-user-token:{int(user_id)}",
    )
    rows = _get_local_member_rows(int(user_id))
    if not rows:
        logging.warning("[同步] 单用户同步飞书失败，本地用户不存在: user_id=%s", user_id)
        return "not_found"

    row = rows[0]
    if _is_reserved_membership_test_account(row.get("phone")):
        logging.info("[同步] 跳过本地测试账号(单用户本地→飞书): user_id=%s", user_id)
        return "skipped_test_account"
    bitable = get_bitable_manager()
    fields = _build_feishu_member_fields(row, bitable)
    result = bitable.upsert_member_record(fields, user_id=row.get("user_id"))
    logging.info("[同步] 单用户本地→飞书完成: user_id=%s result=%s", user_id, result)
    return result


def sync_single_user_to_feishu(user_id: int) -> str:
    """Immediately publish one authoritative local user to Feishu."""
    if not _feishu_config_ready():
        logging.warning("[同步] 飞书配置不完整，跳过单用户同步: user_id=%s", user_id)
        return "skipped"
    lock_path, timeout = _sync_lock_settings()
    with process_lock(lock_path, timeout=timeout) as acquired:
        if not acquired:
            logging.warning("[同步] 另一个飞书同步任务正在运行，单用户发布未启动: user_id=%s", user_id)
            return "busy"
        try:
            return _sync_single_user_to_feishu_impl(int(user_id))
        except RuntimeSchemaNotReadyError as exc:
            logging.error("[同步] 单用户发布失败: %s", exc)
            return "schema_not_ready"
        except sqlite3.OperationalError as exc:
            if is_database_busy_error(exc):
                logging.error("[同步] 单用户发布数据库繁忙 user_id=%s: %s", user_id, exc)
                return "database_busy"
            logging.exception("[同步] 单用户本地→飞书失败: user_id=%s err=%s", user_id, exc)
            return "failed"
        except Exception as exc:
            logging.exception("[同步] 单用户本地→飞书失败: user_id=%s err=%s", user_id, exc)
            return "failed"


# ==================== 会员表：飞书 → 本地 ====================
def _is_reserved_membership_test_account(phone) -> bool:
    """Keep local automated-test accounts out of two-way Feishu sync."""
    return safe_text(phone).strip().startswith("__MEMBERSHIP_TEST_")


def _is_reserved_local_user(cursor, user_id: int | None) -> bool:
    """Check the already-matched local user, not only fields supplied by Feishu.

    Old/stale Feishu rows may omit the phone field but still identify a local
    test user by user ID or token.  Checking only the incoming phone lets such
    rows overwrite the disposable admin fixture's subscription.
    """
    if user_id is None:
        return False
    row = cursor.execute(
        "SELECT phone FROM users WHERE id=? LIMIT 1",
        (int(user_id),),
    ).fetchone()
    return bool(row and _is_reserved_membership_test_account(row["phone"]))


def _find_unique_local_user_by_identity(cursor, *, phone=None, email=None, taobao_nick=None):
    """Return one local user ID or a conflict reason for Feishu registration linking."""
    matches: set[int] = set()
    for column, value in (("phone", phone), ("email", email), ("taobao_nick", taobao_nick)):
        value = safe_text(value).strip()
        if not value:
            continue
        rows = cursor.execute(
            f"SELECT id FROM users WHERE {column}=? ORDER BY id",
            (value,),
        ).fetchall()
        ids = {int(row["id"]) for row in rows}
        if len(ids) > 1:
            return None, f"duplicate_{column}"
        matches.update(ids)

    if len(matches) > 1:
        return None, "cross_field_conflict"
    if len(matches) == 1:
        return next(iter(matches)), "matched"
    return None, "not_found"


def _writeback_authoritative_member_record(bitable, record_id: str, user_id: int) -> bool:
    """Write local authoritative display fields back to the same Feishu row."""
    rows = _get_local_member_rows(int(user_id))
    if not rows:
        logging.warning(
            "[同步] 飞书登记回写失败，本地用户不存在: record_id=%s user_id=%s",
            record_id,
            user_id,
        )
        return False
    fields = _build_feishu_member_fields(rows[0], bitable)
    return bool(bitable.update_record(record_id, fields))


def _create_feishu_user_atomic(
    *,
    username: str,
    phone: str | None,
    email: str | None,
    taobao_nick: str | None,
) -> int:
    """Create a disabled review record; Feishu input never activates credentials."""

    def _create() -> int:
        conn = get_conn()
        if conn.in_transaction:
            conn.rollback()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            now = now_str()
            cursor.execute(
                """
                INSERT INTO users (
                    username, phone, email, taobao_nick,
                    register_source, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'feishu_pending', 'disabled', ?, ?)
                """,
                (username or taobao_nick or phone or email, phone, email, taobao_nick, now, now),
            )
            user_id = int(cursor.lastrowid)
            conn.commit()
            return user_id
        except Exception:
            conn.rollback()
            raise

    return run_db_write_with_retry(
        _create,
        operation_name="feishu-register-user",
    )


def _sync_feishu_to_local_impl() -> SyncResult:
    _ensure_runtime_db_ready()
    bitable = get_bitable_manager()
    feishu_records = bitable.list_all_records()
    if not feishu_records:
        logging.warning("[同步] 飞书会员表没有记录")
        return SyncResult((0, 0), status="empty", message="飞书会员表没有记录")

    added_count = 0
    linked_count = 0

    for record_id, fields in feishu_records:
        cursor = get_conn().cursor()
        feishu_user_id_text = safe_text(fields.get("用户ID")).strip()
        username = safe_text(fields.get("用户名称")).strip()
        phone = safe_text(fields.get("手机号")).strip() or None
        email = safe_text(fields.get("邮箱")).strip() or None
        taobao_nick = safe_text(fields.get("淘宝昵称")).strip() or None

        if _is_reserved_membership_test_account(phone):
            logging.info("[同步] 跳过本地测试账号(飞书登记): record_id=%s", record_id)
            continue

        identity_user_id, identity_reason = _find_unique_local_user_by_identity(
            cursor, phone=phone, email=email, taobao_nick=taobao_nick
        )
        if identity_reason in (
            "duplicate_phone", "duplicate_email", "duplicate_taobao_nick", "cross_field_conflict"
        ):
            logging.warning(
                "[同步] 飞书登记身份冲突，跳过: record_id=%s reason=%s",
                record_id, identity_reason,
            )
            continue

        user_id = None
        if feishu_user_id_text.isdigit():
            row = cursor.execute(
                "SELECT id FROM users WHERE id=? LIMIT 1", (int(feishu_user_id_text),)
            ).fetchone()
            if row:
                user_id = int(row["id"])
                if identity_user_id is not None and identity_user_id != user_id:
                    logging.warning(
                        "[同步] 飞书登记用户ID与联系方式指向不同用户，跳过: "
                        "record_id=%s user_id=%s identity_user_id=%s",
                        record_id, user_id, identity_user_id,
                    )
                    continue

        if user_id is None and identity_user_id is not None:
            user_id = int(identity_user_id)

        if user_id is not None:
            if _is_reserved_local_user(cursor, user_id):
                logging.info(
                    "[同步] 跳过本地测试账号(飞书登记二次校验): record_id=%s user_id=%s",
                    record_id, user_id,
                )
                continue
            linked_count += 1
            if not _writeback_authoritative_member_record(bitable, record_id, user_id):
                logging.warning(
                    "[同步] 飞书登记关联成功但回写失败: record_id=%s user_id=%s",
                    record_id, user_id,
                )
            else:
                logging.info(
                    "[同步] 飞书登记关联已有用户: record_id=%s user_id=%s",
                    record_id, user_id,
                )
            continue

        if not any((phone, email, taobao_nick)):
            logging.warning("[同步] 飞书登记缺少手机号/邮箱/淘宝昵称，跳过: record_id=%s", record_id)
            continue

        user_id = _create_feishu_user_atomic(
            username=username, phone=phone, email=email, taobao_nick=taobao_nick
        )
        added_count += 1
        if not _writeback_authoritative_member_record(bitable, record_id, user_id):
            logging.warning(
                "[同步] 飞书新用户已创建但回写失败: record_id=%s user_id=%s",
                record_id, user_id,
            )
        else:
            logging.info("[同步] 飞书登记创建新用户: record_id=%s user_id=%s", record_id, user_id)

    logging.info("[同步] 飞书登记导入完成: 新增%d条, 关联%d条", added_count, linked_count)
    return SyncResult((added_count, linked_count), status="ok", message="飞书登记导入完成")


def sync_feishu_to_local() -> SyncResult:
    """Import only new/uniquely linked member registrations from Feishu."""
    logging.info("[同步] 飞书登记 → 本地（仅新用户/关联，不覆盖本地权限）")
    if not _feishu_config_ready():
        message = "飞书配置不完整，跳过飞书登记导入"
        logging.warning("[同步] %s", message)
        return SyncResult((0, 0), status="skipped", message=message)

    lock_path, timeout = _sync_lock_settings()
    with process_lock(lock_path, timeout=timeout) as acquired:
        if not acquired:
            return _busy_result((0, 0), "飞书同步任务")
        try:
            return _sync_feishu_to_local_impl()
        except RuntimeSchemaNotReadyError as exc:
            return _schema_not_ready_result((0, 0), exc)
        except sqlite3.OperationalError as exc:
            if is_database_busy_error(exc):
                return _database_busy_result((0, 0), "飞书登记导入", exc)
            logging.exception("[同步] 飞书登记导入失败: %s", exc)
            return SyncResult((0, 0), status="error", message=str(exc))
        except Exception as exc:
            logging.exception("[同步] 飞书登记导入失败: %s", exc)
            return SyncResult((0, 0), status="error", message=str(exc))


# ==================== 会员表：本地 → 飞书 ====================
def _sync_local_to_feishu_impl(user_id: Optional[int] = None) -> SyncResult:
    _ensure_runtime_db_ready()
    if user_id is not None:
        run_db_write_with_retry(
            lambda: get_or_create_api_key(int(user_id)),
            operation_name=f"feishu-local-token:{int(user_id)}",
        )

    rows = _get_local_member_rows(int(user_id) if user_id is not None else None)
    if not rows:
        return SyncResult((0, 0, 0), status="empty", message="没有可发布的本地用户")
    bitable = get_bitable_manager()
    added_count = 0
    updated_count = 0
    failed_count = 0

    for row in rows:
        if _is_reserved_membership_test_account(row.get("phone")):
            logging.info("[同步] 跳过本地测试账号(本地→飞书): user_id=%s", row.get("user_id"))
            continue
        if not row.get("api_key_id"):
            run_db_write_with_retry(
                lambda uid=int(row["user_id"]): get_or_create_api_key(uid),
                operation_name=f"feishu-local-token:{int(row['user_id'])}",
            )
            refreshed = _get_local_member_rows(int(row["user_id"]))
            row = refreshed[0] if refreshed else row

        fields = _build_feishu_member_fields(row, bitable)
        result = bitable.upsert_member_record(fields, user_id=row.get("user_id"))
        username = fields.get("用户名称") or f"user_{row.get('user_id')}"
        plan_code = fields.get("套餐代码") or "未开通"

        if result == "added":
            added_count += 1
            logging.info("[同步] 本地→飞书 新增: user_id=%s %s | %s", row.get("user_id"), username, plan_code)
        elif result == "updated":
            updated_count += 1
            logging.info("[同步] 本地→飞书 更新: user_id=%s %s | %s", row.get("user_id"), username, plan_code)
        else:
            failed_count += 1
            logging.warning("[同步] 本地→飞书 失败: user_id=%s %s | %s", row.get("user_id"), username, plan_code)

    logging.info("[同步] 本地→飞书完成: 新增%d条, 更新%d条, 失败%d条", added_count, updated_count, failed_count)
    return SyncResult((added_count, updated_count, failed_count), status="ok", message="本地→飞书发布完成")


def sync_local_to_feishu(user_id: Optional[int] = None) -> SyncResult:
    """Publish authoritative local membership data to Feishu."""
    logging.info("[同步] 本地 → 飞书，新会员体系 user_id=%s", user_id or "ALL")
    if not _feishu_config_ready():
        message = "飞书配置不完整，跳过本地→飞书"
        logging.warning("[同步] %s", message)
        return SyncResult((0, 0, 0), status="skipped", message=message)

    lock_path, timeout = _sync_lock_settings()
    with process_lock(lock_path, timeout=timeout) as acquired:
        if not acquired:
            return _busy_result((0, 0, 0), "飞书同步任务")
        try:
            return _sync_local_to_feishu_impl(user_id)
        except RuntimeSchemaNotReadyError as exc:
            return _schema_not_ready_result((0, 0, 0), exc)
        except sqlite3.OperationalError as exc:
            if is_database_busy_error(exc):
                return _database_busy_result((0, 0, 0), "本地→飞书发布", exc)
            logging.exception("[同步] 本地→飞书失败: %s", exc)
            return SyncResult((0, 0, 0), status="error", message=str(exc))
        except Exception as exc:
            logging.exception("[同步] 本地→飞书失败: %s", exc)
            return SyncResult((0, 0, 0), status="error", message=str(exc))


# ==================== 竞价数据同步 ====================
def _sync_bidding_to_feishu_impl() -> SyncResult:
    _ensure_runtime_db_ready(_RUNTIME_BIDDING_TABLES)
    logging.info("=" * 60)
    logging.info("[竞价同步] 从本地完整三时点快照同步到飞书")
    logging.info("=" * 60)

    from integrations.market_data.kaipanla.schema import SNAPSHOT_TYPES
    from services.kaipanla_bidding_service import get_kaipanla_bidding_service
    from utils.common import df_to_list

    now = _china_now()
    trade_date = now.strftime("%Y%m%d")
    service = get_kaipanla_bidding_service()
    data_list = []
    errors = []
    for snapshot_type in SNAPSHOT_TYPES:
        result = run_db_write_with_retry(
            lambda snapshot_type=snapshot_type: service.query_history({
                "trade_date": trade_date,
                "snapshot_type": snapshot_type,
                "limit": config.BIDDING_SYNC_COUNT,
            }),
            operation_name=f"feishu-bidding-history-{snapshot_type}",
        )
        if result.error:
            errors.append(f"{snapshot_type}: {result.error}")
            continue
        meta = result.meta or {}
        source_provider = str(meta.get("source_provider") or "")
        data_quality = str(meta.get("data_quality") or "")
        fallback_used = bool(meta.get("fallback_used"))
        actual_type = str(meta.get("snapshot_type") or "")
        if source_provider != "kaipanla_snapshot" or data_quality != "complete" or fallback_used or actual_type != snapshot_type:
            errors.append(
                f"{snapshot_type}: 拒绝非完整本地快照 source={source_provider} "
                f"quality={data_quality} fallback={fallback_used} actual_type={actual_type}"
            )
            continue
        if result.data is None or result.data.empty:
            errors.append(f"{snapshot_type}: 快照为空")
            continue
        data_list.extend(df_to_list(result.data))

    if not data_list:
        message = "；".join(errors) or "竞价快照为空"
        logging.error("[竞价同步] %s", message)
        return SyncResult((0, 0), status="error", message=message)
    if errors:
        logging.warning("[竞价同步] 部分快照未同步: %s", "；".join(errors))

    bitable = get_bitable_manager()
    bitable.ensure_bidding_schema(
        create_missing=bool(getattr(config, "FEISHU_BIDDING_AUTO_CREATE_FIELDS", True))
    )
    success_count, fail_count = bitable.batch_add_bidding_records(data_list)
    message = "竞价三时点快照写入完成"
    if errors:
        message += "；" + "；".join(errors)
    logging.info("[竞价同步] 写入完成：成功 %d 条，失败 %d 条", success_count, fail_count)
    return SyncResult(
        (success_count, fail_count),
        status="partial" if errors else "ok",
        message=message,
    )


def sync_bidding_to_feishu() -> SyncResult:
    """Sync the immutable Kaipanla snapshot to Feishu under the global sync lock."""
    lock_path, timeout = _sync_lock_settings()
    with process_lock(lock_path, timeout=timeout) as acquired:
        if not acquired:
            return _busy_result((0, 0), "飞书同步任务")
        try:
            return _sync_bidding_to_feishu_impl()
        except RuntimeSchemaNotReadyError as exc:
            return _schema_not_ready_result((0, 0), exc)
        except sqlite3.OperationalError as exc:
            if is_database_busy_error(exc):
                return _database_busy_result((0, 0), "竞价同步", exc)
            logging.exception("[竞价同步] 同步异常: %s", exc)
            return SyncResult((0, 0), status="error", message=str(exc))
        except Exception as exc:
            logging.exception("[竞价同步] 同步异常: %s", exc)
            return SyncResult((0, 0), status="error", message=str(exc))


def _check_and_sync_bidding():
    """检查是否到了每日竞价同步时间。"""
    global _last_bidding_sync_date
    now = _china_now()
    today_str = now.strftime("%Y-%m-%d")
    if _last_bidding_sync_date == today_str:
        return

    sync_hour = config.BIDDING_SYNC_HOUR
    sync_minute = config.BIDDING_SYNC_MINUTE
    if now.hour == sync_hour and now.minute >= sync_minute:
        logging.info("[竞价同步] 到达同步时间 %s:%02d，开始同步", sync_hour, sync_minute)
        result = sync_bidding_to_feishu()
        success_count, _fail_count = result
        if success_count > 0 and result.status == "ok":
            _last_bidding_sync_date = today_str
        elif result.status == "partial":
            logging.warning("[竞价同步] 三时点快照尚未齐全，本日稍后继续重试: %s", result.message)


# ==================== 同步服务线程 ====================
def run_full_sync():
    """执行一次本地权威发布；不自动从飞书覆盖本地。"""
    logging.info("=" * 50)
    logging.info("[同步] 开始本地→飞书发布同步")
    logging.info("=" * 50)

    # 本地数据库是会员、Token、套餐和权限的唯一权威源。
    sync_local_to_feishu()
    # 同步循环里顺便检查竞价数据。
    _check_and_sync_bidding()

    logging.info("[同步] 本地→飞书发布同步完成")


def _sync_worker():
    logging.info("[同步服务] 后台同步服务已启动，间隔 %d 分钟", SYNC_INTERVAL_MINUTES)

    try:
        run_full_sync()
        logging.info("[同步服务] 下次同步: %d 分钟后\n", SYNC_INTERVAL_MINUTES)
    except Exception as e:
        logging.exception("[同步服务] 首次同步出错: %s", e)

    while _sync_running:
        for _ in range(SYNC_INTERVAL_MINUTES * 60):
            if not _sync_running:
                break
            time.sleep(1)
        if not _sync_running:
            break
        try:
            run_full_sync()
            logging.info("[同步服务] 下次同步: %d 分钟后\n", SYNC_INTERVAL_MINUTES)
        except Exception as e:
            logging.exception("[同步服务] 同步出错: %s", e)

    logging.info("[同步服务] 同步服务已停止")


def start_sync_service():
    global _sync_running, _sync_thread
    if _sync_running:
        logging.warning("[同步服务] 同步服务已经在运行")
        return
    _sync_running = True
    _sync_thread = threading.Thread(target=_sync_worker, daemon=True)
    _sync_thread.start()


def stop_sync_service():
    global _sync_running
    _sync_running = False
    logging.info("[同步服务] 正在停止同步服务...")


def trigger_sync_now():
    threading.Thread(target=run_full_sync, daemon=True).start()
    logging.info("[同步服务] 已触发本地→飞书立即发布")


def trigger_bidding_sync_now():
    threading.Thread(target=sync_bidding_to_feishu, daemon=True).start()
    logging.info("[竞价同步] 已触发立即同步")
