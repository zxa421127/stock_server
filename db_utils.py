# -*- coding: utf-8 -*-
"""
db_utils.py

稳定版数据库工具：
1. 管理 users/api_keys/plans/subscriptions/manual_orders 等会员数据。
2. 管理 API 文档与 usage_logs。
3. 不再创建旧 api_tokens、未落地行情表或多数据源配置表；旧表若已存在会原样保留。
4. 提供鉴权和后台页面所需的数据库函数。
"""
import os
import json
import sqlite3
import threading
import logging
import random
import time
from datetime import datetime
from typing import Any, Callable, Optional, TypeVar

from config import (
    API_KEY_TOUCH_INTERVAL_SECONDS,
    API_TOKEN_HASH_SECRET,
    DB_FILE,
    USAGE_LOG_RETAIN_FAILURES,
    USAGE_LOG_SUCCESS_SAMPLE_RATE,
)

# 确保数据库目录存在
db_dir = os.path.dirname(DB_FILE)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

_local = threading.local()
_db_pragma_lock = threading.Lock()
_db_pragmas_initialized = False
CURRENT_SCHEMA_VERSION = 5


def _ensure_database_pragmas() -> None:
    """Set database-wide WAL once per process, not once per request thread."""
    global _db_pragmas_initialized
    if _db_pragmas_initialized:
        return
    with _db_pragma_lock:
        if _db_pragmas_initialized:
            return
        conn = sqlite3.connect(DB_FILE, timeout=10)
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        finally:
            conn.close()
        _db_pragmas_initialized = True


def get_conn() -> sqlite3.Connection:
    """获取当前线程的数据库连接。"""
    if not hasattr(_local, "conn") or _local.conn is None:
        _ensure_database_pragmas()
        conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-20000")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn



_T = TypeVar("_T")
_DEFAULT_WRITE_RETRY_DELAYS = (0.2, 0.8, 2.0, 5.0)


def is_database_busy_error(exc: BaseException) -> bool:
    """Return whether an SQLite exception represents transient lock contention."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).strip().lower()
    return "locked" in message or "busy" in message


def close_thread_connection() -> None:
    """Rollback and discard the current thread-local connection safely."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        return
    try:
        conn.rollback()
    except Exception:
        pass
    try:
        conn.close()
    finally:
        _local.conn = None


def run_db_write_with_retry(
    operation: Callable[[], _T],
    *,
    attempts: int = 4,
    delays: tuple[float, ...] = _DEFAULT_WRITE_RETRY_DELAYS,
    operation_name: str = "sqlite-write",
) -> _T:
    """Run a short SQLite write transaction with bounded lock retries.

    Only ``locked``/``busy`` operational errors are retried.  The current
    thread connection is rolled back and recreated between attempts so a
    failed transaction cannot keep stale state or a reserved lock.
    """
    total_attempts = max(1, int(attempts or 1))
    retry_delays = tuple(max(0.0, float(value)) for value in (delays or (0.0,)))
    last_error: BaseException | None = None

    for attempt_index in range(total_attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not is_database_busy_error(exc):
                raise
            last_error = exc
            close_thread_connection()
            if attempt_index >= total_attempts - 1:
                raise
            delay = retry_delays[min(attempt_index, len(retry_delays) - 1)]
            logging.warning(
                "[数据库] 写入繁忙，准备重试 operation=%s attempt=%s/%s delay=%.2fs",
                operation_name,
                attempt_index + 1,
                total_attempts,
                delay,
            )
            if delay:
                time.sleep(delay)

    assert last_error is not None
    raise last_error


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def init_db() -> None:
    """Create and migrate the database. Run explicitly before production startup."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)

    init_member_tables(cursor)
    init_password_reset_tables(cursor)
    init_contact_verification_tables(cursor)
    init_api_doc_tables(cursor)
    from services.audit_schema import init_main_audit_schema
    init_main_audit_schema(cursor)
    init_indexes(cursor)
    from services.kaipanla_snapshot_repository import create_kaipanla_snapshot_tables
    create_kaipanla_snapshot_tables(cursor)
    from services.admin_api_test_repository import create_admin_api_test_tables
    create_admin_api_test_tables(cursor)
    from services.tushare_spec_monitor_repository import create_tushare_spec_monitor_tables
    create_tushare_spec_monitor_tables(cursor)
    from services.admin_client_certificate import create_admin_client_certificate_tables
    create_admin_client_certificate_tables(cursor)

    conn.commit()
    _ensure_member_columns()
    _ensure_plan_columns()
    _ensure_subscription_action_columns()
    _migrate_subscription_statuses()
    _migrate_api_doc_paths_to_unified_market_route()
    _ensure_api_key_security_columns()
    _migrate_api_key_plaintext_rows()
    ensure_default_plans(update_existing=False)
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (CURRENT_SCHEMA_VERSION, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()


def assert_schema_ready() -> None:
    """Fail fast when production starts before the explicit migration command."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        version = int((row["version"] if row else 0) or 0)
    except sqlite3.Error as exc:
        raise RuntimeError("数据库尚未迁移，请先执行 python -m tools.db.migrate") from exc
    if version < CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"数据库版本过旧: current={version}, required={CURRENT_SCHEMA_VERSION}; "
            "请先执行 python -m tools.db.migrate"
        )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    required = {"token_hash", "token_prefix", "token_last4"}
    if not required.issubset(columns):
        raise RuntimeError("api_keys安全字段缺失，请先执行 python -m tools.db.migrate")
    user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    required_user_columns = {
        "session_version", "password_changed_at", "email_verified_at",
        "phone_verified_at", "registration_status",
    }
    if not required_user_columns.issubset(user_columns):
        raise RuntimeError("users安全字段缺失，请先执行 python -m tools.db.migrate")
    challenge_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='contact_verification_challenges'"
    ).fetchone()
    if not challenge_table:
        raise RuntimeError("联系方式验证码表缺失，请先执行 python -m tools.db.migrate")
    cert_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_client_certificates'"
    ).fetchone()
    if not cert_table:
        raise RuntimeError("管理员客户端证书表缺失，请先执行 python -m tools.db.migrate")


def _ensure_member_columns() -> None:
    """兼容旧 users 表，缺字段时自动补。"""
    conn = get_conn()
    cursor = conn.cursor()

    for col, sql in [
        ("password_hash", "ALTER TABLE users ADD COLUMN password_hash TEXT"),
        ("register_source", "ALTER TABLE users ADD COLUMN register_source TEXT DEFAULT 'admin'"),
        ("last_login_at", "ALTER TABLE users ADD COLUMN last_login_at TEXT"),
        ("session_version", "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1"),
        ("password_changed_at", "ALTER TABLE users ADD COLUMN password_changed_at TEXT"),
        ("email_verified_at", "ALTER TABLE users ADD COLUMN email_verified_at TEXT"),
        ("phone_verified_at", "ALTER TABLE users ADD COLUMN phone_verified_at TEXT"),
        ("registration_status", "ALTER TABLE users ADD COLUMN registration_status TEXT NOT NULL DEFAULT 'active'"),
    ]:
        try:
            cursor.execute(f"SELECT {col} FROM users LIMIT 1")
        except Exception:
            cursor.execute(sql)
            conn.commit()
            logging.info("[数据库] users 自动添加字段: %s", col)


def _ensure_api_key_security_columns() -> None:
    """Add one-way token columns while keeping the legacy placeholder column compatible."""
    conn = get_conn()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(api_keys)").fetchall()}
    additions = [
        ("token_hash", "ALTER TABLE api_keys ADD COLUMN token_hash TEXT"),
        ("token_prefix", "ALTER TABLE api_keys ADD COLUMN token_prefix TEXT"),
        ("token_last4", "ALTER TABLE api_keys ADD COLUMN token_last4 TEXT"),
        ("rotated_at", "ALTER TABLE api_keys ADD COLUMN rotated_at TEXT"),
    ]
    for name, sql in additions:
        if name not in existing:
            conn.execute(sql)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_api_keys_token_hash ON api_keys(token_hash)")
    conn.commit()


def _migrate_api_key_plaintext_rows() -> int:
    """Hash legacy API tokens and replace plaintext with non-secret row placeholders."""
    from services.api_token_security import hash_api_token, token_last4, token_prefix

    secret = str(API_TOKEN_HASH_SECRET or "")
    if len(secret) < 16:
        # Development databases may remain legacy until a secret is configured.
        if os.getenv("APP_ENV", "development").strip().lower() == "production":
            raise RuntimeError("API_TOKEN_HASH_SECRET未配置，拒绝迁移API Token")
        return 0
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, token FROM api_keys WHERE COALESCE(token_hash,'')='' AND COALESCE(token,'')!=''"
    ).fetchall()
    changed = 0
    for row in rows:
        token = str(row["token"] or "")
        if token.startswith("hashed:"):
            continue
        digest = hash_api_token(token, secret)
        if not digest:
            continue
        conn.execute(
            "UPDATE api_keys SET token_hash=?, token_prefix=?, token_last4=?, token=? WHERE id=?",
            (digest, token_prefix(token), token_last4(token), f"hashed:{int(row['id'])}", int(row["id"])),
        )
        changed += 1
    conn.commit()
    if changed:
        logging.warning("[数据库] 已将%s条API Token迁移为不可逆哈希，明文已清除", changed)
    return changed


def _ensure_plan_columns() -> None:
    """Add performance-related columns to existing plan databases."""
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT quota_per_minute FROM plans LIMIT 1")
    except Exception:
        cursor.execute("ALTER TABLE plans ADD COLUMN quota_per_minute INTEGER DEFAULT 1000")
        conn.commit()
        logging.info("[数据库] plans 自动添加字段: quota_per_minute")




def _ensure_subscription_action_columns() -> None:
    """Add subscription-action audit columns to existing databases."""
    conn = get_conn()
    cursor = conn.cursor()
    subscription_columns = [
        ("operation_type", "ALTER TABLE subscriptions ADD COLUMN operation_type TEXT DEFAULT 'open'"),
        ("previous_subscription_id", "ALTER TABLE subscriptions ADD COLUMN previous_subscription_id INTEGER"),
        ("extra_days", "ALTER TABLE subscriptions ADD COLUMN extra_days INTEGER DEFAULT 0"),
        ("ended_at", "ALTER TABLE subscriptions ADD COLUMN ended_at TEXT"),
        ("ended_reason", "ALTER TABLE subscriptions ADD COLUMN ended_reason TEXT"),
    ]
    order_columns = [
        ("operation_type", "ALTER TABLE manual_orders ADD COLUMN operation_type TEXT DEFAULT 'open'"),
        ("subscription_id", "ALTER TABLE manual_orders ADD COLUMN subscription_id INTEGER"),
        ("previous_subscription_id", "ALTER TABLE manual_orders ADD COLUMN previous_subscription_id INTEGER"),
        ("previous_plan_code", "ALTER TABLE manual_orders ADD COLUMN previous_plan_code TEXT"),
        ("effective_time", "ALTER TABLE manual_orders ADD COLUMN effective_time TEXT"),
        ("extra_days", "ALTER TABLE manual_orders ADD COLUMN extra_days INTEGER DEFAULT 0"),
        ("operator_name", "ALTER TABLE manual_orders ADD COLUMN operator_name TEXT"),
    ]
    for table, columns in (("subscriptions", subscription_columns), ("manual_orders", order_columns)):
        existing = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        for column, sql in columns:
            if column not in existing:
                cursor.execute(sql)
                logging.info("[数据库] %s 自动添加字段: %s", table, column)
    conn.commit()


def _migrate_subscription_statuses() -> None:
    """Normalize legacy rows: future active rows become scheduled; past rows become expired."""
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE subscriptions SET status='scheduled', updated_at=? "
        "WHERE status='active' AND start_time>?",
        (now, now),
    )
    future_changed = max(int(cursor.rowcount or 0), 0)
    cursor.execute(
        "UPDATE subscriptions SET status='expired', ended_at=COALESCE(ended_at, expire_time), "
        "ended_reason=COALESCE(ended_reason, 'expired'), updated_at=? "
        "WHERE status IN ('active','scheduled') AND expire_time<?",
        (now, now),
    )
    past_changed = max(int(cursor.rowcount or 0), 0)
    conn.commit()
    if future_changed or past_changed:
        logging.info("[数据库] 订阅状态迁移: scheduled=%s expired=%s", future_changed, past_changed)


def _migrate_api_doc_paths_to_unified_market_route() -> None:
    """Rewrite stored API-document examples to the only supported market route.

    This updates existing databases once at startup. It does not register or
    preserve the removed Tushare-only HTTP blueprint.
    """
    conn = get_conn()
    cursor = conn.cursor()
    old_prefix = "/api/v1/" + "tushare"
    new_prefix = "/api/v1/market/tushare"
    cursor.execute(
        """
        UPDATE api_doc_endpoints
        SET path=REPLACE(path, ?, ?),
            request_example=CASE
                WHEN request_example IS NULL THEN NULL
                ELSE REPLACE(request_example, ?, ?)
            END,
            updated_at=?
        WHERE path LIKE ?
           OR COALESCE(request_example, '') LIKE ?
        """,
        (
            old_prefix,
            new_prefix,
            old_prefix,
            new_prefix,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"%{old_prefix}%",
            f"%{old_prefix}%",
        ),
    )
    changed = max(int(cursor.rowcount or 0), 0)
    conn.commit()
    if changed:
        logging.info("[数据库] API文档路径已统一迁移: %s 条", changed)


# =========================
# 新会员/套餐/淘宝手动开通表
# =========================
def init_member_tables(cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        phone TEXT,
        email TEXT,
        taobao_nick TEXT,
        password_hash TEXT,
        register_source TEXT DEFAULT 'admin',
        last_login_at TEXT,
        session_version INTEGER NOT NULL DEFAULT 1,
        password_changed_at TEXT,
        email_verified_at TEXT,
        phone_verified_at TEXT,
        registration_status TEXT NOT NULL DEFAULT 'active',
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        token_hash TEXT UNIQUE,
        token_prefix TEXT,
        token_last4 TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        last_used_at TEXT,
        rotated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_code TEXT UNIQUE NOT NULL,
        plan_name TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        duration_type TEXT NOT NULL,
        duration_days INTEGER NOT NULL,
        original_price_cent INTEGER NOT NULL,
        sale_price_cent INTEGER NOT NULL,
        quota_daily INTEGER DEFAULT 50000,
        quota_per_minute INTEGER DEFAULT 1000,
        max_symbols_per_request INTEGER DEFAULT 50,
        min_refresh_interval_sec INTEGER DEFAULT 1,
        scopes TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_code TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        start_time TEXT NOT NULL,
        expire_time TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        source_order_no TEXT,
        remark TEXT,
        operation_type TEXT DEFAULT 'open',
        previous_subscription_id INTEGER,
        extra_days INTEGER DEFAULT 0,
        ended_at TEXT,
        ended_reason TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS manual_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        taobao_order_no TEXT,
        plan_code TEXT NOT NULL,
        plan_type TEXT NOT NULL,
        duration_type TEXT NOT NULL,
        amount_cent INTEGER,
        promo_name TEXT,
        admin_remark TEXT,
        operation_type TEXT DEFAULT 'open',
        subscription_id INTEGER,
        previous_subscription_id INTEGER,
        previous_plan_code TEXT,
        effective_time TEXT,
        extra_days INTEGER DEFAULT 0,
        operator_name TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        promo_code TEXT UNIQUE NOT NULL,
        promo_name TEXT NOT NULL,
        plan_code TEXT NOT NULL,
        discount_type TEXT NOT NULL,
        discount_value INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        new_user_only INTEGER DEFAULT 0,
        max_total_uses INTEGER DEFAULT 0,
        max_per_user INTEGER DEFAULT 1,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        endpoint TEXT,
        method TEXT,
        scope TEXT,
        success INTEGER,
        status_code INTEGER,
        cost_ms INTEGER,
        ip TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_usage_counters (
        user_id INTEGER NOT NULL,
        usage_date TEXT NOT NULL,
        request_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        failure_count INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT,
        PRIMARY KEY (user_id, usage_date)
    )
    """)


# =========================
# 用户找回密码申请表
# =========================
def init_contact_verification_tables(cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contact_verification_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        challenge_id TEXT UNIQUE NOT NULL,
        purpose TEXT NOT NULL,
        channel TEXT NOT NULL,
        target TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 5,
        created_at_ts INTEGER NOT NULL,
        expires_at_ts INTEGER NOT NULL,
        consumed_at_ts INTEGER,
        delivery_error TEXT
    )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_challenge_target "
        "ON contact_verification_challenges(purpose,channel,target,created_at_ts)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_contact_challenge_status "
        "ON contact_verification_challenges(status,expires_at_ts)"
    )


def init_password_reset_tables(cursor) -> None:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        account TEXT,
        contact TEXT,
        status TEXT DEFAULT 'pending',
        admin_remark TEXT,
        created_at TEXT,
        handled_at TEXT
    )
    """)


# =========================
# API 文档后台管理表
# =========================
def init_api_doc_tables(cursor) -> None:
    """API 文档类目和接口说明表。

    只管理“接口说明文档”，不会自动创建真实接口。
    真实接口仍需要在 routes/*.py 中开发。
    """
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_doc_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        sort_order INTEGER DEFAULT 100,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS api_doc_endpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        method TEXT DEFAULT 'GET',
        path TEXT NOT NULL,
        scope TEXT,
        description TEXT,
        params_text TEXT,
        headers_text TEXT,
        request_example TEXT,
        response_example TEXT,
        error_codes TEXT,
        sort_order INTEGER DEFAULT 100,
        status TEXT DEFAULT 'active',
        created_at TEXT,
        updated_at TEXT
    )
    """)


def init_indexes(cursor) -> None:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_token ON api_keys(token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_user_expire ON subscriptions(user_id, expire_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_user_status_start ON subscriptions(user_id, status, start_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sub_user_status_expire ON subscriptions(user_id, status, expire_time)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_created ON manual_orders(user_id, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_taobao ON users(taobao_nick)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_day ON usage_logs(user_id, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_scope_day ON usage_logs(scope, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage_counters(usage_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_status ON password_reset_requests(status, created_at)")


# =========================
# 默认套餐初始化：统一权限中心
# =========================
def ensure_default_plans(update_existing: bool = False) -> None:
    """
    初始化内置套餐。

    update_existing=False：启动时只补缺失套餐，不覆盖线上价格/额度。
    update_existing=True ：tools/db/init_plans.py 使用，按代码中的套餐目录强制同步。
    """
    from services.plan_catalog import DEFAULT_PLANS

    for plan in DEFAULT_PLANS:
        upsert_plan_record(plan, update_existing=update_existing)


def upsert_plan_record(plan: dict[str, Any], update_existing: bool = False) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scopes_json = json.dumps(plan["scopes"], ensure_ascii=False)

    if update_existing:
        cursor.execute("""
            INSERT INTO plans (
                plan_code, plan_name, plan_type, duration_type, duration_days,
                original_price_cent, sale_price_cent, quota_daily, quota_per_minute,
                max_symbols_per_request, min_refresh_interval_sec,
                scopes, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT(plan_code) DO UPDATE SET
                plan_name=excluded.plan_name,
                plan_type=excluded.plan_type,
                duration_type=excluded.duration_type,
                duration_days=excluded.duration_days,
                original_price_cent=excluded.original_price_cent,
                sale_price_cent=excluded.sale_price_cent,
                quota_daily=excluded.quota_daily,
                quota_per_minute=excluded.quota_per_minute,
                max_symbols_per_request=excluded.max_symbols_per_request,
                min_refresh_interval_sec=excluded.min_refresh_interval_sec,
                scopes=excluded.scopes,
                status='active',
                updated_at=excluded.updated_at
        """, (
            plan["plan_code"], plan["plan_name"], plan["plan_type"], plan["duration_type"],
            plan["duration_days"], plan["original_price_cent"], plan["sale_price_cent"],
            plan["quota_daily"], plan.get("quota_per_minute", 1000), plan["max_symbols_per_request"], plan["min_refresh_interval_sec"],
            scopes_json, now, now,
        ))
    else:
        cursor.execute("""
            INSERT OR IGNORE INTO plans (
                plan_code, plan_name, plan_type, duration_type, duration_days,
                original_price_cent, sale_price_cent, quota_daily, quota_per_minute,
                max_symbols_per_request, min_refresh_interval_sec,
                scopes, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
        """, (
            plan["plan_code"], plan["plan_name"], plan["plan_type"], plan["duration_type"],
            plan["duration_days"], plan["original_price_cent"], plan["sale_price_cent"],
            plan["quota_daily"], plan.get("quota_per_minute", 1000), plan["max_symbols_per_request"], plan["min_refresh_interval_sec"],
            scopes_json, now, now,
        ))

    conn.commit()


def _api_key_lookup_clause(token: str) -> tuple[str, tuple[str, ...]]:
    """Return a hash-first lookup clause with a development legacy fallback."""
    from services.api_token_security import configured_hash_secret, hash_api_token

    digest = hash_api_token(token, configured_hash_secret())
    if digest:
        return "k.token_hash = ?", (digest,)
    return "k.token = ?", (str(token),)


def get_user_by_api_key(token: str) -> Optional[dict[str, Any]]:
    """Resolve an active API key without persisting or returning the plaintext token."""
    if not token:
        return None
    clause, params = _api_key_lookup_clause(token)
    row = get_conn().execute(
        f"""
        SELECT u.id, u.username, u.phone, u.email, u.taobao_nick, u.status
        FROM api_keys k
        JOIN users u ON k.user_id = u.id
        WHERE {clause} AND k.status='active' AND u.status='active'
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def get_api_key_auth_record(token: str) -> Optional[dict[str, Any]]:
    """Resolve an API key regardless of status without exposing the token."""
    if not token:
        return None
    clause, params = _api_key_lookup_clause(token)
    row = get_conn().execute(
        f"""
        SELECT u.id, u.username, u.phone, u.email, u.taobao_nick,
               u.status AS user_status, k.status AS key_status, k.id AS api_key_id
        FROM api_keys k
        JOIN users u ON k.user_id=u.id
        WHERE {clause}
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def touch_api_keys_batch(tokens: list[str]) -> int:
    """Update last-used timestamps using keyed token hashes."""
    from services.api_token_security import configured_hash_secret, hash_api_token

    secret = configured_hash_secret()
    digests = sorted({hash_api_token(token, secret) for token in tokens if str(token).strip()})
    digests = [value for value in digests if value]
    if not digests:
        return 0
    now = datetime.now()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    cutoff_text = datetime.fromtimestamp(
        now.timestamp() - max(int(API_KEY_TOUCH_INTERVAL_SECONDS), 0)
    ).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    if API_KEY_TOUCH_INTERVAL_SECONDS <= 0:
        conn.executemany(
            "UPDATE api_keys SET last_used_at=? WHERE token_hash=?",
            [(now_text, digest) for digest in digests],
        )
    else:
        conn.executemany(
            "UPDATE api_keys SET last_used_at=? WHERE token_hash=? "
            "AND (last_used_at IS NULL OR last_used_at < ?)",
            [(now_text, digest, cutoff_text) for digest in digests],
        )
    conn.commit()
    return len(digests)


def refresh_subscription_states(user_id: Optional[int] = None) -> None:
    """Expire old rows and promote due rows using a short retried transaction."""

    def _refresh() -> None:
        conn = get_conn()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        where_user = " AND user_id=?" if user_id is not None else ""
        params_expired = [now, now]
        if user_id is not None:
            params_expired.append(int(user_id))
        try:
            cursor.execute(
                "UPDATE subscriptions SET status='expired', ended_at=COALESCE(ended_at, expire_time), "
                "ended_reason=COALESCE(ended_reason, 'expired'), updated_at=? "
                "WHERE status IN ('active','scheduled') AND expire_time<?" + where_user,
                tuple(params_expired),
            )
            if user_id is not None:
                user_ids = [int(user_id)]
            else:
                user_ids = [int(r[0]) for r in cursor.execute(
                    "SELECT DISTINCT user_id FROM subscriptions WHERE status='scheduled' AND start_time<=? AND expire_time>=?",
                    (now, now),
                ).fetchall()]
            for uid in user_ids:
                active = cursor.execute(
                    "SELECT id FROM subscriptions WHERE user_id=? AND status='active' "
                    "AND start_time<=? AND expire_time>=? ORDER BY start_time DESC,id DESC LIMIT 1",
                    (uid, now, now),
                ).fetchone()
                if active:
                    continue
                due = cursor.execute(
                    "SELECT id FROM subscriptions WHERE user_id=? AND status='scheduled' "
                    "AND start_time<=? AND expire_time>=? ORDER BY start_time ASC,id ASC LIMIT 1",
                    (uid, now, now),
                ).fetchone()
                if due:
                    cursor.execute("UPDATE subscriptions SET status='active', updated_at=? WHERE id=?", (now, due[0]))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    run_db_write_with_retry(
        _refresh,
        operation_name=f"refresh-subscription-states:{user_id if user_id is not None else 'all'}",
    )


def get_active_subscription(user_id: int) -> Optional[dict[str, Any]]:
    refresh_subscription_states(int(user_id))
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        SELECT id, user_id, plan_code, plan_type, start_time, expire_time, status,
               source_order_no, remark, operation_type, previous_subscription_id,
               extra_days, ended_at, ended_reason, created_at, updated_at
        FROM subscriptions
        WHERE user_id=? AND status='active' AND start_time<=? AND expire_time>=?
        ORDER BY start_time DESC, id DESC LIMIT 1
        """,
        (int(user_id), now, now),
    )
    return row_to_dict(cursor.fetchone())


def get_scheduled_subscriptions(user_id: int) -> list[dict[str, Any]]:
    refresh_subscription_states(int(user_id))
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, plan_code, plan_type, start_time, expire_time, status,
               source_order_no, remark, operation_type, previous_subscription_id,
               extra_days, created_at, updated_at
        FROM subscriptions
        WHERE user_id=? AND status='scheduled'
        ORDER BY start_time ASC, id ASC
        """,
        (int(user_id),),
    )
    return rows_to_dicts(cursor.fetchall())


def list_subscription_history(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    refresh_subscription_states(int(user_id))
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, plan_code, plan_type, start_time, expire_time, status,
               source_order_no, remark, operation_type, previous_subscription_id,
               extra_days, ended_at, ended_reason, created_at, updated_at
        FROM subscriptions WHERE user_id=? ORDER BY id DESC LIMIT ?
        """,
        (int(user_id), max(1, min(int(limit), 500))),
    )
    return rows_to_dicts(cursor.fetchall())



def list_membership_actions(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Return order-level membership actions, including renewals that do not create a new subscription."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id,order_no,user_id,plan_code,plan_type,amount_cent,promo_name,admin_remark,
               operation_type,subscription_id,previous_subscription_id,previous_plan_code,
               effective_time,extra_days,operator_name,created_at
        FROM manual_orders WHERE user_id=? ORDER BY id DESC LIMIT ?
        """,
        (int(user_id), max(1, min(int(limit), 500))),
    )
    return rows_to_dicts(cursor.fetchall())

def get_plan_by_code(plan_code: str) -> Optional[dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, plan_code, plan_name, plan_type, duration_type,
               duration_days, original_price_cent, sale_price_cent,
               quota_daily, quota_per_minute, max_symbols_per_request, min_refresh_interval_sec,
               scopes, status, created_at, updated_at
        FROM plans
        WHERE plan_code = ?
          AND status = 'active'
        LIMIT 1
        """,
        (plan_code,),
    )
    return row_to_dict(cursor.fetchone())


def list_active_plans() -> list[dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, plan_code, plan_name, plan_type, duration_type,
               duration_days, sale_price_cent, quota_per_minute, max_symbols_per_request,
               min_refresh_interval_sec, status
        FROM plans
        WHERE status='active'
          AND plan_type IN ('general', 'special')
        ORDER BY
          CASE plan_type
            WHEN 'general' THEN 0
            WHEN 'special' THEN 1
            ELSE 2
          END,
          CASE duration_type
            WHEN 'month' THEN 0
            WHEN 'quarter' THEN 1
            WHEN 'year' THEN 2
            ELSE 3
          END,
          id ASC
        """
    )
    return rows_to_dicts(cursor.fetchall())


def list_members_page(*, page: int = 1, page_size: int = 50, query: str = "") -> dict[str, Any]:
    """Paginated administrator member list with safe multi-field search."""
    refresh_subscription_states()
    page = max(1, int(page or 1))
    page_size = max(10, min(int(page_size or 50), 100))
    offset = (page - 1) * page_size
    query = str(query or "").strip()
    where_sql = ""
    query_params: list[Any] = []
    if query:
        like = f"%{query}%"
        where_sql = (
            "WHERE CAST(u.id AS TEXT)=? OR u.username LIKE ? OR u.phone LIKE ? "
            "OR u.email LIKE ? OR u.taobao_nick LIKE ?"
        )
        query_params = [query, like, like, like, like]

    conn = get_conn()
    total = int(conn.execute(
        f"SELECT COUNT(*) FROM users u {where_sql}", tuple(query_params)
    ).fetchone()[0])
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        f"""
        SELECT u.id AS user_id, u.username, u.phone, u.email, u.taobao_nick,
               u.status AS user_status, u.register_source, u.last_login_at,
               k.token_prefix, k.token_last4, k.status AS key_status,
               cur.plan_code, cur.plan_type, cur.start_time, cur.expire_time, cur.status AS sub_status,
               nxt.id AS scheduled_subscription_id, nxt.plan_code AS scheduled_plan_code,
               nxt.plan_type AS scheduled_plan_type, nxt.start_time AS scheduled_start_time,
               nxt.expire_time AS scheduled_expire_time
        FROM users u
        LEFT JOIN api_keys k ON k.id=(
            SELECT k2.id FROM api_keys k2 WHERE k2.user_id=u.id
            ORDER BY CASE k2.status WHEN 'active' THEN 0 ELSE 1 END, k2.id ASC LIMIT 1
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
        {where_sql}
        ORDER BY u.id DESC LIMIT ? OFFSET ?
        """,
        (now, now, *query_params, page_size, offset),
    ).fetchall()
    items = rows_to_dicts(rows)
    from services.api_token_security import token_display
    for item in items:
        item["token_display"] = token_display(prefix=item.get("token_prefix"), last4=item.get("token_last4"))
    pages = max(1, (total + page_size - 1) // page_size)
    return {"items": items, "total": total, "page": min(page, pages), "page_size": page_size, "pages": pages, "query": query}


def list_members() -> list[dict[str, Any]]:
    """Backward-compatible first page; new UI uses ``list_members_page``."""
    return list_members_page(page=1, page_size=100)["items"]


# =========================
# 普通用户系统查询函数
# =========================
def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, phone, email, taobao_nick, password_hash,
               register_source, last_login_at, session_version, password_changed_at,
               email_verified_at, phone_verified_at, registration_status,
               status, created_at, updated_at
        FROM users
        WHERE id=?
        LIMIT 1
        """,
        (user_id,),
    )
    return row_to_dict(cursor.fetchone())


def get_user_by_account(account: str) -> Optional[dict[str, Any]]:
    """按用户名、手机号或邮箱查找用户。"""
    account = (account or "").strip()
    if not account:
        return None
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, phone, email, taobao_nick, password_hash,
               register_source, last_login_at, session_version, password_changed_at,
               email_verified_at, phone_verified_at, registration_status,
               status, created_at, updated_at
        FROM users
        WHERE username=? OR phone=? OR email=?
        LIMIT 1
        """,
        (account, account, account),
    )
    return row_to_dict(cursor.fetchone())


def get_active_api_key(user_id: int) -> Optional[str]:
    """Return only a masked API-key identifier; full tokens are shown once at creation."""
    from services.api_token_security import token_display

    row = get_conn().execute(
        "SELECT token_prefix, token_last4 FROM api_keys "
        "WHERE user_id=? AND status='active' ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return token_display(prefix=row["token_prefix"], last4=row["token_last4"])


def get_active_api_key_record(user_id: int) -> Optional[dict[str, Any]]:
    row = get_conn().execute(
        "SELECT id,user_id,token_prefix,token_last4,status,created_at,last_used_at,rotated_at "
        "FROM api_keys WHERE user_id=? AND status='active' ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    return dict(row) if row else None


def update_user_last_login(user_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET last_login_at=?, updated_at=? WHERE id=?",
        (now, now, user_id),
    )
    conn.commit()


def list_password_reset_requests(limit: int = 200) -> list[dict[str, Any]]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, r.user_id, r.account, r.contact, r.status,
               r.admin_remark, r.created_at, r.handled_at,
               u.username, u.phone, u.email
        FROM password_reset_requests r
        LEFT JOIN users u ON u.id = r.user_id
        ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END, r.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return rows_to_dicts(cursor.fetchall())


def mark_password_reset_handled(request_id: int, admin_remark: str = "") -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE password_reset_requests
        SET status='handled', admin_remark=?, handled_at=?
        WHERE id=?
        """,
        (admin_remark, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request_id),
    )
    conn.commit()


# =========================
# 统一鉴权访问日志/每日额度
# =========================
def count_usage_today(user_id: int, success_only: bool = False) -> int:
    """Legacy detail-log count, retained for migration and diagnostics."""
    conn = get_conn()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    sql = "SELECT COUNT(*) AS cnt FROM usage_logs WHERE user_id=? AND created_at LIKE ?"
    params: list[Any] = [user_id, f"{today}%"]
    if success_only:
        sql += " AND success=1"
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return int(row["cnt"] if row else 0)


def get_daily_usage_count(user_id: int, usage_date: str | None = None) -> int:
    """Return exact durable daily usage, seeding older databases from detail logs once."""
    usage_date = usage_date or datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT request_count FROM daily_usage_counters WHERE user_id=? AND usage_date=?",
        (int(user_id), usage_date),
    )
    row = cursor.fetchone()
    if row is not None:
        return int(row["request_count"] or 0)

    cursor.execute(
        "SELECT COUNT(*) AS cnt, SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok "
        "FROM usage_logs WHERE user_id=? AND created_at LIKE ?",
        (int(user_id), f"{usage_date}%"),
    )
    legacy = cursor.fetchone()
    total = int(legacy["cnt"] or 0) if legacy else 0
    success = int(legacy["ok"] or 0) if legacy else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO daily_usage_counters
            (user_id, usage_date, request_count, success_count, failure_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, usage_date) DO NOTHING
        """,
        (int(user_id), usage_date, total, success, max(total - success, 0), now),
    )
    conn.commit()
    cursor.execute(
        "SELECT request_count FROM daily_usage_counters WHERE user_id=? AND usage_date=?",
        (int(user_id), usage_date),
    )
    seeded = cursor.fetchone()
    return int(seeded["request_count"] or 0) if seeded else total


def _should_keep_usage_detail(item: dict[str, Any]) -> bool:
    if not item.get("success") and USAGE_LOG_RETAIN_FAILURES:
        return True
    sample_rate = float(USAGE_LOG_SUCCESS_SAMPLE_RATE)
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    return random.random() < sample_rate


def record_usage_log(
    user_id: int,
    endpoint: str,
    method: str,
    scope: str,
    success: bool,
    status_code: int,
    cost_ms: int,
    ip: str,
) -> None:
    record_usage_logs_batch([{
        "user_id": user_id,
        "endpoint": endpoint,
        "method": method,
        "scope": scope,
        "success": success,
        "status_code": status_code,
        "cost_ms": cost_ms,
        "ip": ip,
    }])


def record_usage_logs_batch(payloads: list[dict[str, Any]]) -> int:
    """Persist exact daily totals and sampled detail rows in one transaction."""
    if not payloads:
        return 0
    default_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows: list[tuple[Any, ...]] = []
    detail_rows: list[tuple[Any, ...]] = []
    counters: dict[tuple[int, str], list[int]] = {}

    for item in payloads:
        created_at = str(item.get("created_at") or default_now)
        user_id = int(item["user_id"])
        success = 1 if item.get("success") else 0
        row = (
            user_id,
            str(item.get("endpoint", "")),
            str(item.get("method", "")),
            str(item.get("scope", "")),
            success,
            int(item.get("status_code", 0)),
            int(item.get("cost_ms", 0)),
            str(item.get("ip", "")),
            created_at,
        )
        all_rows.append(row)
        if _should_keep_usage_detail(item):
            detail_rows.append(row)
        usage_date = created_at[:10]
        bucket = counters.setdefault((user_id, usage_date), [0, 0, 0])
        bucket[0] += 1
        bucket[1] += success
        bucket[2] += 1 - success

    conn = get_conn()
    cursor = conn.cursor()
    if detail_rows:
        cursor.executemany(
            """
            INSERT INTO usage_logs
                (user_id, endpoint, method, scope, success, status_code, cost_ms, ip, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            detail_rows,
        )

    counter_rows = [
        (user_id, usage_date, values[0], values[1], values[2], default_now)
        for (user_id, usage_date), values in counters.items()
    ]
    cursor.executemany(
        """
        INSERT INTO daily_usage_counters
            (user_id, usage_date, request_count, success_count, failure_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, usage_date) DO UPDATE SET
            request_count=request_count + excluded.request_count,
            success_count=success_count + excluded.success_count,
            failure_count=failure_count + excluded.failure_count,
            updated_at=excluded.updated_at
        """,
        counter_rows,
    )
    conn.commit()
    return len(all_rows)


if __name__ == "__main__":
    init_db()
    logging.info("数据库初始化成功: %s", DB_FILE)
