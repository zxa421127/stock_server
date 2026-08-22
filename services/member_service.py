# -*- coding: utf-8 -*-
"""
会员/用户服务。

保留原来的管理员手动开通逻辑，同时新增普通用户注册、登录、自助找回密码、管理员重置密码。
"""
import secrets
import string
from datetime import datetime, timedelta

import config
from services.api_token_security import configured_hash_secret, hash_api_token, token_display, token_last4, token_prefix
from services.security_credentials import hash_secret, verify_secret
from services.user_input_security import validate_new_password

from db_utils import (
    get_conn,
    row_to_dict,
    get_user_by_account,
    get_user_by_id,
    update_user_last_login,
)


def generate_api_token() -> str:
    """Generate a high-entropy credential without predictable timestamp material."""
    return "SK_STOCK_API_" + secrets.token_urlsafe(36)


def _generate_manual_order_no(user_id: int) -> str:
    """Generate a collision-resistant internal order number.

    Windows clocks may return the same ``datetime.now()`` value for several
    operations executed within one scheduler tick.  A timestamp plus user id
    is therefore not sufficient for a UNIQUE database column.  The random
    suffix also makes concurrent administrator submissions safe.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    random_suffix = secrets.token_hex(8).upper()
    return f"MANUAL_{timestamp}_{int(user_id)}_{random_suffix}"


def hash_password(password: str) -> str:
    """Use the shared adaptive PBKDF2 credential format for new user passwords."""
    return hash_secret(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify both legacy and newly generated PBKDF2 records."""
    return verify_secret(password, password_hash)


def create_or_get_user(username=None, phone=None, email=None, taobao_nick=None):
    """
    管理员开通/续费时使用。
    优先按手机号、淘宝昵称、邮箱查重；不存在则创建用户。
    """
    conn = get_conn()
    cursor = conn.cursor()

    if phone:
        cursor.execute("SELECT * FROM users WHERE phone=? LIMIT 1", (phone,))
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)

    if taobao_nick:
        cursor.execute("SELECT * FROM users WHERE taobao_nick=? LIMIT 1", (taobao_nick,))
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)

    if email:
        cursor.execute("SELECT * FROM users WHERE email=? LIMIT 1", (email,))
        row = cursor.fetchone()
        if row:
            return row_to_dict(row)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO users (
            username, phone, email, taobao_nick,
            register_source, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'admin', 'active', ?, ?)
        """,
        (username, phone, email, taobao_nick, now, now),
    )
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,))
    return row_to_dict(cursor.fetchone())


def register_user(username: str, password: str, phone: str | None = None, email: str | None = None):
    """
    普通用户自助注册。
    注册后只创建 users + api_keys，不创建 subscription，因此接口仍不可用。
    """
    username = (username or "").strip()
    password = password or ""
    phone = (phone or "").strip() or None
    email = (email or "").strip() or None

    if not username:
        raise ValueError("用户名不能为空")
    if len(username) < 3:
        raise ValueError("用户名至少 3 个字符")
    min_length = int(getattr(config, "USER_PASSWORD_MIN_LENGTH", 12))
    if len(password) < min_length:
        raise ValueError(f"密码至少 {min_length} 位")
    if not phone and not email:
        raise ValueError("手机号或邮箱至少填写一个，方便找回密码和管理员开通")

    if get_user_by_account(username):
        raise ValueError("用户名已存在")
    if phone and get_user_by_account(phone):
        raise ValueError("手机号已被注册")
    if email and get_user_by_account(email):
        raise ValueError("邮箱已被注册")

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO users (
            username, phone, email, taobao_nick, password_hash,
            register_source, status, created_at, updated_at
        ) VALUES (?, ?, ?, NULL, ?, 'self', 'active', ?, ?)
        """,
        (username, phone, email, hash_password(password), now, now),
    )
    user_id = cursor.lastrowid
    conn.commit()

    token = get_or_create_api_key(user_id)
    user = get_user_by_id(user_id)
    return user, token


def register_verified_user(
    *,
    username: str,
    password_hash: str,
    phone: str | None,
    email: str | None,
    verified_channel: str,
    verified_target: str,
):
    """Create a self-service user only after a contact challenge was consumed."""
    username = str(username or "").strip()
    phone = str(phone or "").strip() or None
    email = str(email or "").strip().lower() or None
    channel = str(verified_channel or "").strip().lower()
    target = str(verified_target or "").strip().lower() if channel == "email" else str(verified_target or "").strip()
    if channel == "email" and (not email or target != email):
        raise ValueError("邮箱验证结果与注册信息不一致")
    if channel == "sms" and (not phone or target != phone):
        raise ValueError("手机号验证结果与注册信息不一致")
    if channel not in {"email", "sms"}:
        raise ValueError("注册联系方式尚未验证")
    if not str(password_hash or "").startswith("pbkdf2_sha256$"):
        raise ValueError("密码摘要格式无效")
    if get_user_by_account(username):
        raise ValueError("用户名已存在")
    if phone and get_user_by_account(phone):
        raise ValueError("手机号已被注册")
    if email and get_user_by_account(email):
        raise ValueError("邮箱已被注册")

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email_verified_at = now if channel == "email" else None
    phone_verified_at = now if channel == "sms" else None
    try:
        cursor.execute(
            """
            INSERT INTO users (
                username,phone,email,taobao_nick,password_hash,register_source,
                status,session_version,password_changed_at,email_verified_at,
                phone_verified_at,registration_status,created_at,updated_at
            ) VALUES (?,?,?,NULL,?,'self','active',1,?,?,?,?,?,?)
            """,
            (
                username, phone, email, password_hash, now,
                email_verified_at, phone_verified_at, "active", now, now,
            ),
        )
        user_id = int(cursor.lastrowid)
        token = generate_api_token()
        _store_api_token(cursor, user_id=user_id, token=token)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return get_user_by_id(user_id), token


def authenticate_user(account: str, password: str):
    """普通用户登录。account 可以是用户名、手机号或邮箱。"""
    user = get_user_by_account(account)
    if not user:
        return None
    if user.get("status") != "active":
        return None
    if not verify_password(password, user.get("password_hash")):
        return None
    update_user_last_login(int(user["id"]))
    return get_user_by_id(int(user["id"]))


def bump_user_session_version(user_id: int, *, password_changed: bool = False) -> int:
    """Invalidate all existing signed browser sessions for one user."""
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if password_changed:
        conn.execute(
            "UPDATE users SET session_version=COALESCE(session_version,1)+1,"
            "password_changed_at=?,updated_at=? WHERE id=?",
            (now, now, int(user_id)),
        )
    else:
        conn.execute(
            "UPDATE users SET session_version=COALESCE(session_version,1)+1,updated_at=? WHERE id=?",
            (now, int(user_id)),
        )
    conn.commit()
    row = conn.execute("SELECT session_version FROM users WHERE id=?", (int(user_id),)).fetchone()
    if not row:
        raise ValueError("用户不存在")
    _clear_user_auth_cache(int(user_id))
    return int(row["session_version"] or 1)


def change_user_password(user_id: int, current_password: str, new_password: str) -> dict:
    """Change a logged-in user's password and revoke every prior session."""
    validate_new_password(new_password, label="新密码")
    if len(str(current_password or "")) > int(getattr(config, "USER_PASSWORD_MAX_LENGTH", 128)):
        raise ValueError("当前密码长度无效")
    user = get_user_by_id(int(user_id))
    if not user:
        raise ValueError("用户不存在")
    if not verify_password(current_password, user.get("password_hash")):
        raise ValueError("当前密码错误")
    conn = get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE users SET password_hash=?,session_version=COALESCE(session_version,1)+1,"
        "password_changed_at=?,updated_at=? WHERE id=?",
        (hash_password(new_password), now, now, int(user_id)),
    )
    conn.commit()
    _clear_user_auth_cache(int(user_id))
    return get_user_by_id(int(user_id))


def _store_api_token(cursor, *, user_id: int, token: str, key_id: int | None = None) -> int:
    secret = configured_hash_secret(config)
    digest = hash_api_token(token, secret)
    if not digest:
        raise RuntimeError("API_TOKEN_HASH_SECRET未配置或长度不足")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    placeholder = f"hashed:{secrets.token_hex(16)}"
    if key_id is None:
        cursor.execute(
            "INSERT INTO api_keys "
            "(user_id,token,token_hash,token_prefix,token_last4,status,created_at,rotated_at) "
            "VALUES (?,?,?,?,?,'active',?,?)",
            (user_id, placeholder, digest, token_prefix(token), token_last4(token), now, now),
        )
        return int(cursor.lastrowid)
    cursor.execute(
        "UPDATE api_keys SET token=?,token_hash=?,token_prefix=?,token_last4=?,"
        "status='active',rotated_at=? WHERE id=?",
        (placeholder, digest, token_prefix(token), token_last4(token), now, int(key_id)),
    )
    return int(key_id)


def get_or_create_api_key(user_id: int) -> str:
    """Create a token once; existing tokens are returned only as a masked identifier."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id,token_hash,token_prefix,token_last4,token FROM api_keys "
        "WHERE user_id=? AND status='active' ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        if row["token_hash"]:
            return token_display(prefix=row["token_prefix"], last4=row["token_last4"])
        # Development-only compatibility before the explicit migration command.
        return str(row["token"] or "")

    token = generate_api_token()
    cursor = conn.cursor()
    _store_api_token(cursor, user_id=int(user_id), token=token)
    conn.commit()
    return token


def rotate_api_key(user_id: int) -> str:
    """Replace the active key and return the new plaintext exactly once."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM api_keys WHERE user_id=? AND status='active' ORDER BY id ASC LIMIT 1",
        (int(user_id),),
    ).fetchone()
    token = generate_api_token()
    cursor = conn.cursor()
    _store_api_token(cursor, user_id=int(user_id), token=token, key_id=int(row["id"]) if row else None)
    conn.commit()
    try:
        from services.auth_context_cache import clear_user_auth_context_cache
        clear_user_auth_context_cache(int(user_id))
    except Exception:
        pass
    return token


ACTION_LABELS = {
    "open": "首次开通",
    "renew": "续费当前套餐",
    "switch_now": "立即换套餐",
    "switch_scheduled": "到期后换套餐",
}


def _parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _current_subscription_row(cursor, user_id: int, now_text: str):
    cursor.execute(
        """
        SELECT * FROM subscriptions
        WHERE user_id=? AND status='active' AND start_time<=? AND expire_time>=?
        ORDER BY start_time DESC,id DESC LIMIT 1
        """,
        (int(user_id), now_text, now_text),
    )
    return cursor.fetchone()


def _scheduled_subscription_rows(cursor, user_id: int):
    cursor.execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='scheduled' ORDER BY start_time ASC,id ASC",
        (int(user_id),),
    )
    return cursor.fetchall()


def _insert_manual_order(
    cursor,
    *,
    order_no: str,
    user_id: int,
    plan: dict,
    action_type: str,
    taobao_order_no: str | None,
    amount_cent: int | None,
    promo_name: str | None,
    remark: str | None,
    previous_subscription_id: int | None,
    previous_plan_code: str | None,
    effective_time: str,
    extra_days: int,
    operator_name: str | None,
    created_at: str,
) -> int:
    cursor.execute(
        """
        INSERT INTO manual_orders (
            order_no,user_id,taobao_order_no,plan_code,plan_type,duration_type,
            amount_cent,promo_name,admin_remark,operation_type,subscription_id,
            previous_subscription_id,previous_plan_code,effective_time,extra_days,
            operator_name,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?,?)
        """,
        (
            order_no,
            int(user_id),
            taobao_order_no,
            plan["plan_code"],
            plan["plan_type"],
            plan["duration_type"],
            amount_cent,
            promo_name,
            remark,
            action_type,
            previous_subscription_id,
            previous_plan_code,
            effective_time,
            int(extra_days),
            operator_name,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _shift_scheduled_subscriptions(cursor, user_id: int, delta: timedelta, now_text: str) -> None:
    for row in _scheduled_subscription_rows(cursor, int(user_id)):
        start_dt = _parse_dt(row["start_time"]) + delta
        expire_dt = _parse_dt(row["expire_time"]) + delta
        cursor.execute(
            "UPDATE subscriptions SET start_time=?,expire_time=?,updated_at=? WHERE id=?",
            (
                start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                expire_dt.strftime("%Y-%m-%d %H:%M:%S"),
                now_text,
                int(row["id"]),
            ),
        )


def _rebase_scheduled_subscriptions(cursor, user_id: int, start_dt: datetime, now_text: str) -> None:
    """Preserve scheduled rows after an immediate switch by moving the queue behind the new plan."""
    next_start = start_dt
    for row in _scheduled_subscription_rows(cursor, int(user_id)):
        duration = _parse_dt(row["expire_time"]) - _parse_dt(row["start_time"])
        next_expire = next_start + duration
        cursor.execute(
            "UPDATE subscriptions SET start_time=?,expire_time=?,updated_at=? WHERE id=?",
            (
                next_start.strftime("%Y-%m-%d %H:%M:%S"),
                next_expire.strftime("%Y-%m-%d %H:%M:%S"),
                now_text,
                int(row["id"]),
            ),
        )
        next_start = next_expire


def apply_subscription_action(
    user_id: int,
    plan_code: str,
    action_type: str,
    taobao_order_no: str | None = None,
    amount_cent: int | None = None,
    promo_name: str | None = None,
    remark: str | None = None,
    extra_days: int = 0,
    cancel_scheduled: bool = True,
    operator_name: str | None = None,
) -> dict:
    """Apply one explicit membership action atomically.

    action_type:
      open             - only when no active/scheduled subscription exists;
      renew            - extend the current subscription; target plan must be identical;
      switch_now       - end current plan now and activate the new plan immediately;
      switch_scheduled - queue the new plan after all current/scheduled rights.
    """
    action_type = (action_type or "").strip()
    if action_type not in ACTION_LABELS:
        raise ValueError("操作类型无效，请选择首次开通、续费、立即换套餐或到期后换套餐")
    try:
        extra_days = int(extra_days or 0)
    except (TypeError, ValueError):
        raise ValueError("额外补偿天数必须是整数")
    if extra_days < 0 or extra_days > 3650:
        raise ValueError("额外补偿天数必须在0到3650天之间")
    if amount_cent is not None and int(amount_cent) < 0:
        raise ValueError("实际收款金额不能小于0")

    conn = get_conn()
    cursor = conn.cursor()
    if conn.in_transaction:
        conn.commit()
    cursor.execute("BEGIN IMMEDIATE")
    try:
        cursor.execute("SELECT * FROM plans WHERE plan_code=? AND status='active' LIMIT 1", (plan_code,))
        plan_row = cursor.fetchone()
        plan = row_to_dict(plan_row)
        if not plan:
            raise ValueError("套餐不存在或未启用，请先运行 python -m tools.db.init_plans")

        now_dt = datetime.now()
        now_text = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        # Normalize this user's legacy rows inside the same transaction.
        cursor.execute(
            "UPDATE subscriptions SET status='scheduled',updated_at=? WHERE user_id=? AND status='active' AND start_time>?",
            (now_text, int(user_id), now_text),
        )
        cursor.execute(
            "UPDATE subscriptions SET status='expired',ended_at=COALESCE(ended_at,expire_time),"
            "ended_reason=COALESCE(ended_reason,'expired'),updated_at=? "
            "WHERE user_id=? AND status IN ('active','scheduled') AND expire_time<?",
            (now_text, int(user_id), now_text),
        )
        current = _current_subscription_row(cursor, int(user_id), now_text)
        scheduled = _scheduled_subscription_rows(cursor, int(user_id))
        previous_id = int(current["id"]) if current else None
        previous_plan_code = current["plan_code"] if current else None
        base_days = int(plan["duration_days"])
        total_days = base_days + extra_days
        order_no = _generate_manual_order_no(int(user_id))

        if action_type == "open":
            if current or scheduled:
                raise ValueError("该用户已有当前或待生效套餐，请选择续费或换套餐")
            start_dt = now_dt
            expire_dt = start_dt + timedelta(days=total_days)
            effective_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")

        elif action_type == "renew":
            if not current:
                raise ValueError("当前没有有效套餐，不能续费，请选择首次开通")
            if current["plan_code"] != plan["plan_code"]:
                raise ValueError("续费只能选择当前相同套餐；更换套餐请选择立即换套餐或到期后换套餐")
            delta = timedelta(days=total_days)
            old_expire = _parse_dt(current["expire_time"])
            new_expire = old_expire + delta
            cursor.execute(
                "UPDATE subscriptions SET expire_time=?,extra_days=COALESCE(extra_days,0)+?,updated_at=? WHERE id=?",
                (new_expire.strftime("%Y-%m-%d %H:%M:%S"), extra_days, now_text, int(current["id"])),
            )
            _shift_scheduled_subscriptions(cursor, int(user_id), delta, now_text)
            effective_time = old_expire.strftime("%Y-%m-%d %H:%M:%S")
            order_id = _insert_manual_order(
                cursor, order_no=order_no, user_id=int(user_id), plan=plan, action_type=action_type,
                taobao_order_no=taobao_order_no, amount_cent=amount_cent, promo_name=promo_name,
                remark=remark, previous_subscription_id=previous_id, previous_plan_code=previous_plan_code,
                effective_time=effective_time, extra_days=extra_days, operator_name=operator_name,
                created_at=now_text,
            )
            cursor.execute("UPDATE manual_orders SET subscription_id=? WHERE id=?", (int(current["id"]), order_id))
            conn.commit()
            _clear_user_auth_cache(int(user_id))
            return {
                "action_type": action_type,
                "action_label": ACTION_LABELS[action_type],
                "subscription_id": int(current["id"]),
                "plan_code": plan["plan_code"],
                "plan_name": plan["plan_name"],
                "plan_type": plan["plan_type"],
                "start_time": current["start_time"],
                "expire_time": new_expire.strftime("%Y-%m-%d %H:%M:%S"),
                "order_no": order_no,
                "extra_days": extra_days,
            }

        elif action_type == "switch_now":
            if not current:
                raise ValueError("当前没有有效套餐，请选择首次开通")
            if current["plan_code"] == plan["plan_code"]:
                raise ValueError("目标套餐与当前套餐相同，请选择续费当前套餐")
            cursor.execute(
                "UPDATE subscriptions SET status='replaced',expire_time=?,ended_at=?,ended_reason='switch_now',updated_at=? WHERE id=?",
                (now_text, now_text, now_text, int(current["id"])),
            )
            if cancel_scheduled:
                cursor.execute(
                    "UPDATE subscriptions SET status='cancelled',ended_at=?,ended_reason='switch_now_cancel_queue',updated_at=? "
                    "WHERE user_id=? AND status='scheduled'",
                    (now_text, now_text, int(user_id)),
                )
            start_dt = now_dt
            expire_dt = start_dt + timedelta(days=total_days)
            effective_time = now_text

        else:  # switch_scheduled
            if not current and not scheduled:
                raise ValueError("当前没有套餐，请选择首次开通")
            if current and not scheduled and current["plan_code"] == plan["plan_code"]:
                raise ValueError("目标套餐与当前套餐相同，请选择续费当前套餐")
            rights_end = now_dt
            if current:
                rights_end = max(rights_end, _parse_dt(current["expire_time"]))
            for item in scheduled:
                rights_end = max(rights_end, _parse_dt(item["expire_time"]))
            start_dt = rights_end
            expire_dt = start_dt + timedelta(days=total_days)
            effective_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")

        order_id = _insert_manual_order(
            cursor, order_no=order_no, user_id=int(user_id), plan=plan, action_type=action_type,
            taobao_order_no=taobao_order_no, amount_cent=amount_cent, promo_name=promo_name,
            remark=remark, previous_subscription_id=previous_id, previous_plan_code=previous_plan_code,
            effective_time=effective_time, extra_days=extra_days, operator_name=operator_name,
            created_at=now_text,
        )
        status = "scheduled" if action_type == "switch_scheduled" else "active"
        cursor.execute(
            """
            INSERT INTO subscriptions (
                user_id,plan_code,plan_type,start_time,expire_time,status,source_order_no,remark,
                operation_type,previous_subscription_id,extra_days,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                int(user_id), plan["plan_code"], plan["plan_type"],
                start_dt.strftime("%Y-%m-%d %H:%M:%S"), expire_dt.strftime("%Y-%m-%d %H:%M:%S"),
                status, order_no, remark, action_type, previous_id, extra_days, now_text, now_text,
            ),
        )
        subscription_id = int(cursor.lastrowid)
        cursor.execute("UPDATE manual_orders SET subscription_id=? WHERE id=?", (subscription_id, order_id))
        if action_type == "switch_now" and not cancel_scheduled:
            _rebase_scheduled_subscriptions(cursor, int(user_id), expire_dt, now_text)
        conn.commit()
        _clear_user_auth_cache(int(user_id))
        return {
            "action_type": action_type,
            "action_label": ACTION_LABELS[action_type],
            "subscription_id": subscription_id,
            "plan_code": plan["plan_code"],
            "plan_name": plan["plan_name"],
            "plan_type": plan["plan_type"],
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "expire_time": expire_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "order_no": order_no,
            "extra_days": extra_days,
        }
    except Exception:
        conn.rollback()
        raise


def cancel_scheduled_subscription(user_id: int, subscription_id: int, operator_name: str | None = None) -> dict:
    conn = get_conn()
    cursor = conn.cursor()
    if conn.in_transaction:
        conn.commit()
    cursor.execute("BEGIN IMMEDIATE")
    try:
        row = cursor.execute(
            "SELECT * FROM subscriptions WHERE id=? AND user_id=? LIMIT 1",
            (int(subscription_id), int(user_id)),
        ).fetchone()
        if not row:
            raise ValueError("待生效套餐不存在")
        if row["status"] != "scheduled":
            raise ValueError("只能取消待生效套餐")
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE subscriptions SET status='cancelled',ended_at=?,ended_reason='admin_cancel_scheduled',"
            "remark=TRIM(COALESCE(remark,'') || ?),updated_at=? WHERE id=?",
            (now_text, f"; 取消人:{operator_name or 'admin'}", now_text, int(subscription_id)),
        )
        conn.commit()
        _clear_user_auth_cache(int(user_id))
        return dict(row)
    except Exception:
        conn.rollback()
        raise


def _clear_user_auth_cache(user_id: int) -> None:
    try:
        from services.auth_context_cache import clear_user_auth_context_cache
        clear_user_auth_context_cache(int(user_id))
    except Exception:
        # The database change is authoritative; cache expiration is a performance detail.
        pass


def open_subscription(user_id, plan_code, taobao_order_no=None, amount_cent=None, promo_name=None, remark=None):
    """Backward-compatible wrapper for old tools.

    New admin code must use apply_subscription_action explicitly. This wrapper opens a new
    subscription when none exists, renews the same plan, and otherwise schedules a switch.
    """
    conn = get_conn()
    cursor = conn.cursor()
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current = _current_subscription_row(cursor, int(user_id), now_text)
    if not current:
        action = "open"
    elif current["plan_code"] == plan_code:
        action = "renew"
    else:
        action = "switch_scheduled"
    return apply_subscription_action(
        user_id=int(user_id), plan_code=plan_code, action_type=action,
        taobao_order_no=taobao_order_no, amount_cent=amount_cent,
        promo_name=promo_name, remark=remark, operator_name="legacy_wrapper",
    )

def submit_password_reset_request(account: str, contact: str):
    """用户提交找回密码申请；第一版由管理员人工处理。"""
    account = (account or "").strip()
    contact = (contact or "").strip()
    if not account:
        raise ValueError("账号不能为空")
    if not contact:
        raise ValueError("联系方式不能为空")

    user = get_user_by_account(account)
    user_id = user["id"] if user else None

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO password_reset_requests (user_id, account, contact, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (user_id, account, contact, now),
    )
    conn.commit()
    return cursor.lastrowid



def admin_reset_user_password(user_id: int, new_password: str):
    validate_new_password(new_password, label="新密码")
    user = get_user_by_id(int(user_id))
    if not user:
        raise ValueError("用户不存在")

    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE users SET password_hash=?,session_version=COALESCE(session_version,1)+1,"
        "password_changed_at=?,updated_at=? WHERE id=?",
        (hash_password(new_password), now, now, int(user_id)),
    )
    conn.commit()
    _clear_user_auth_cache(int(user_id))
    return get_user_by_id(int(user_id))
