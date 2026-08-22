# -*- coding: utf-8 -*-
"""Pre-upstream market query validation and resource leases.

The module deliberately uses only broadly available request attributes (user,
API key and IP-independent Redis counters).  It does not use device or browser
fingerprinting.
"""
from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import config
from services.redis_backend import get_redis, redis_key

_SYMBOL_KEYS = {"ts_code", "symbol", "symbols", "codes", "stock_code", "stock_codes"}
_DATE_PAIRS = (
    ("start_date", "end_date"),
    ("begin_date", "end_date"),
    ("start", "end"),
    ("start_time", "end_time"),
)
_FINANCIAL_HINTS = {
    "income", "balancesheet", "cashflow", "forecast", "express", "fina_indicator",
    "dividend", "audit", "disclosure_date", "mainbz", "balancesheet_vip",
    "income_vip", "cashflow_vip",
}
_INTRADAY_HINTS = {"minute", "min", "tick", "realtime", "rt_", "intraday"}
_SPLIT_RE = re.compile(r"[,;\s|]+")

_lock = threading.RLock()
_refresh_seen: dict[str, float] = {}
_active_user: dict[int, int] = {}
_active_token: dict[int, int] = {}
_active_global = 0


class QuerySecurityError(ValueError):
    """Safe, client-displayable request policy error."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        status_code: int = 400,
        retry_after: int | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.status_code = int(status_code)
        self.retry_after = (
            max(1, int(retry_after))
            if retry_after is not None and int(retry_after) > 0
            else None
        )


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _value_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _split_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for part in value:
            items.extend(_split_items(part))
        return items
    return [item for item in _SPLIT_RE.split(str(value).strip()) if item]


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    # Tushare commonly uses YYYYMMDD; ISO dates are accepted as well.
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise QuerySecurityError("日期参数格式不正确", reason="date_format")


def _date_span_limit(data_type: str) -> int:
    normalized = str(data_type or "").strip().lower().replace("-", "_").replace("/", "_")
    overrides = dict(getattr(config, "MARKET_QUERY_DATE_SPAN_OVERRIDES", {}) or {})
    if normalized in overrides:
        return max(1, _as_int(overrides[normalized], 1))
    if normalized in _FINANCIAL_HINTS or any(hint in normalized for hint in _FINANCIAL_HINTS):
        return max(1, _as_int(getattr(config, "MARKET_QUERY_FINANCIAL_MAX_DATE_SPAN_DAYS", 3650), 3650))
    if any(hint in normalized for hint in _INTRADAY_HINTS):
        return max(1, _as_int(getattr(config, "MARKET_QUERY_INTRADAY_MAX_DATE_SPAN_DAYS", 31), 31))
    return max(1, _as_int(getattr(config, "MARKET_QUERY_DEFAULT_MAX_DATE_SPAN_DAYS", 3660), 3660))


def validate_market_query(
    provider: str,
    data_type: str,
    params: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate request complexity and active-plan constraints.

    Returns a shallow copy so downstream providers cannot mutate the Flask
    request data structure.
    """
    del provider  # Reserved for provider-specific policy overrides.
    normalized = dict(params or {})
    max_params = _as_int(getattr(config, "MARKET_QUERY_MAX_PARAMS", 50), 50)
    if len(normalized) > max_params:
        raise QuerySecurityError(f"查询参数过多，最多允许{max_params}个", reason="parameter_count")

    max_key = _as_int(getattr(config, "MARKET_QUERY_MAX_PARAM_KEY_LENGTH", 64), 64)
    max_value = _as_int(getattr(config, "MARKET_QUERY_MAX_PARAM_VALUE_LENGTH", 4096), 4096)
    for raw_key, value in normalized.items():
        key = str(raw_key)
        if not key or len(key) > max_key or any(ord(ch) < 32 for ch in key):
            raise QuerySecurityError("查询参数名称无效或过长", reason="parameter_key")
        if len(_value_text(value).encode("utf-8")) > max_value:
            raise QuerySecurityError(f"参数 {key} 内容过长", reason="parameter_value")

    symbol_set: set[str] = set()
    for key, value in normalized.items():
        if str(key).strip().lower() in _SYMBOL_KEYS:
            symbol_set.update(_split_items(value))
    symbol_limit = max(0, _as_int((plan or {}).get("max_symbols_per_request"), 0))
    if symbol_limit and len(symbol_set) > symbol_limit:
        raise QuerySecurityError(
            f"单次最多查询{symbol_limit}个证券代码，当前为{len(symbol_set)}个",
            reason="symbols",
        )

    fields = _split_items(normalized.get("fields"))
    field_limit = max(1, _as_int(getattr(config, "MARKET_QUERY_MAX_FIELDS", 120), 120))
    if len(fields) > field_limit:
        raise QuerySecurityError(f"输出字段最多允许{field_limit}个", reason="fields")

    span_limit = _date_span_limit(data_type)
    for start_key, end_key in _DATE_PAIRS:
        if start_key not in normalized or end_key not in normalized:
            continue
        start = _parse_date(normalized.get(start_key))
        end = _parse_date(normalized.get(end_key))
        if start is None or end is None:
            continue
        if end < start:
            raise QuerySecurityError("结束日期不能早于开始日期", reason="date_order")
        span_days = (end - start).days
        if span_days > span_limit:
            raise QuerySecurityError(
                f"该接口单次日期跨度最多{span_limit}天，当前为{span_days}天；请按日期分段查询并合并结果",
                reason="date_span",
            )
    return normalized


def _refresh_key(user_id: int, token_id: int, provider: str, data_type: str) -> str:
    return f"{int(user_id)}:{int(token_id)}:{provider.strip().lower()}:{data_type.strip().lower()}"


def enforce_refresh_interval(
    user_id: int,
    token_id: int,
    provider: str,
    data_type: str,
    plan: dict[str, Any] | None,
) -> None:
    interval = max(0, _as_int((plan or {}).get("min_refresh_interval_sec"), 0))
    if interval <= 0 or str((plan or {}).get("plan_type", "")).lower() == "admin":
        return
    key = _refresh_key(user_id, token_id, provider, data_type)
    client = get_redis()
    if client is not None:
        try:
            allowed = client.set(redis_key("market", "refresh", key), "1", nx=True, ex=max(1, interval))
            if not allowed:
                raise QuerySecurityError(
                    f"该套餐同一接口最短刷新间隔为{interval}秒",
                    reason="refresh_interval",
                    status_code=429,
                    retry_after=max(1, interval),
                )
            return
        except QuerySecurityError:
            raise
        except Exception:
            if bool(getattr(config, "REDIS_REQUIRED", False)):
                raise QuerySecurityError("请求控制服务暂不可用", reason="limiter_unavailable", status_code=503)

    if bool(getattr(config, "REDIS_REQUIRED", False)):
        raise QuerySecurityError("请求控制服务暂不可用", reason="limiter_unavailable", status_code=503)
    now = time.time()
    with _lock:
        last = _refresh_seen.get(key)
        if last is not None and now - last < interval:
            retry_after = max(1, int(interval - (now - last)))
            raise QuerySecurityError(
                f"该套餐同一接口最短刷新间隔为{interval}秒，请在{retry_after}秒后重试",
                reason="refresh_interval",
                status_code=429,
                retry_after=retry_after,
            )
        _refresh_seen[key] = now
        if len(_refresh_seen) > 100_000:
            cutoff = now - max(interval, 3600)
            for old_key in [item for item, seen in _refresh_seen.items() if seen < cutoff]:
                _refresh_seen.pop(old_key, None)


_ACQUIRE_LUA = """
local user_key = KEYS[1]
local token_key = KEYS[2]
local global_key = KEYS[3]
local user_limit = tonumber(ARGV[1])
local token_limit = tonumber(ARGV[2])
local global_limit = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local u = tonumber(redis.call('GET', user_key) or '0')
local t = tonumber(redis.call('GET', token_key) or '0')
local g = tonumber(redis.call('GET', global_key) or '0')
if user_limit > 0 and u >= user_limit then return {0, 'user'} end
if token_limit > 0 and t >= token_limit then return {0, 'token'} end
if global_limit > 0 and g >= global_limit then return {0, 'global'} end
redis.call('INCR', user_key); redis.call('EXPIRE', user_key, ttl)
redis.call('INCR', token_key); redis.call('EXPIRE', token_key, ttl)
redis.call('INCR', global_key); redis.call('EXPIRE', global_key, ttl)
return {1, 'ok'}
"""

_RELEASE_LUA = """
for i=1,3 do
  local current = tonumber(redis.call('GET', KEYS[i]) or '0')
  if current <= 1 then redis.call('DEL', KEYS[i]) else redis.call('DECR', KEYS[i]) end
end
return 1
"""


def concurrency_limits_for_plan(
    plan: dict[str, Any] | None = None,
) -> tuple[int, int, int, int]:
    """Return user/token/global/TTL limits for the active plan.

    General and Special use explicit tier limits. Admin, legacy and unknown
    plan types deliberately retain the legacy per-user/per-token settings so
    this change does not silently widen internal access.
    """
    plan_type = str((plan or {}).get("plan_type", "")).strip().lower()
    if plan_type == "general":
        user_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER", 2), 2),
        )
        token_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN", 2), 2),
        )
    elif plan_type == "special":
        user_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER", 4), 4),
        )
        token_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN", 4), 4),
        )
    else:
        user_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_MAX_CONCURRENT_PER_USER", 4), 4),
        )
        token_limit = max(
            0,
            _as_int(getattr(config, "MARKET_QUERY_MAX_CONCURRENT_PER_TOKEN", 2), 2),
        )

    global_limit = max(
        0,
        _as_int(getattr(config, "MARKET_QUERY_MAX_CONCURRENT_GLOBAL", 12), 12),
    )
    ttl = max(
        5,
        _as_int(getattr(config, "MARKET_QUERY_LEASE_TTL_SECONDS", 180), 180),
    )
    return user_limit, token_limit, global_limit, ttl


def _concurrency_retry_after() -> int:
    return max(
        1,
        _as_int(
            getattr(config, "MARKET_QUERY_CONCURRENCY_RETRY_AFTER_SECONDS", 2),
            2,
        ),
    )


def _concurrency_error(blocked: str) -> QuerySecurityError:
    messages = {
        "user": "该用户并发请求已达上限",
        "token": "该 Token 并发请求已达上限",
        "global": "服务器重查询并发已达上限",
    }
    return QuerySecurityError(
        messages.get(blocked, "并发请求已达上限"),
        reason="concurrency",
        status_code=429,
        retry_after=_concurrency_retry_after(),
    )


def _acquire_local(
    user_id: int,
    token_id: int,
    plan: dict[str, Any] | None = None,
) -> None:
    global _active_global
    user_limit, token_limit, global_limit, _ = concurrency_limits_for_plan(plan)
    with _lock:
        if user_limit and _active_user.get(user_id, 0) >= user_limit:
            raise _concurrency_error("user")
        if token_limit and _active_token.get(token_id, 0) >= token_limit:
            raise _concurrency_error("token")
        if global_limit and _active_global >= global_limit:
            raise _concurrency_error("global")
        _active_user[user_id] = _active_user.get(user_id, 0) + 1
        _active_token[token_id] = _active_token.get(token_id, 0) + 1
        _active_global += 1


def _release_local(user_id: int, token_id: int) -> None:
    global _active_global
    with _lock:
        if _active_user.get(user_id, 0) <= 1:
            _active_user.pop(user_id, None)
        else:
            _active_user[user_id] -= 1
        if _active_token.get(token_id, 0) <= 1:
            _active_token.pop(token_id, None)
        else:
            _active_token[token_id] -= 1
        _active_global = max(0, _active_global - 1)


@contextmanager
def request_lease(
    user_id: int,
    token_id: int,
    plan: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Acquire bounded plan-aware user/token/global concurrency and release it."""
    user_id = int(user_id)
    token_id = int(token_id or 0)
    user_limit, token_limit, global_limit, ttl = concurrency_limits_for_plan(plan)
    client = get_redis()
    redis_keys = (
        redis_key("market", "concurrent", "user", user_id),
        redis_key("market", "concurrent", "token", token_id),
        redis_key("market", "concurrent", "global"),
    )
    acquired_redis = False
    acquired_local = False
    if client is not None:
        try:
            result = client.eval(
                _ACQUIRE_LUA,
                3,
                *redis_keys,
                user_limit,
                token_limit,
                global_limit,
                ttl,
            )
            if int(result[0]) != 1:
                blocked = result[1] if len(result) > 1 else "unknown"
                if isinstance(blocked, bytes):
                    blocked = blocked.decode("utf-8", errors="replace")
                raise _concurrency_error(str(blocked))
            acquired_redis = True
        except QuerySecurityError:
            raise
        except Exception:
            if bool(getattr(config, "REDIS_REQUIRED", False)):
                raise QuerySecurityError(
                    "请求控制服务暂不可用",
                    reason="limiter_unavailable",
                    status_code=503,
                )
    if not acquired_redis:
        if bool(getattr(config, "REDIS_REQUIRED", False)):
            raise QuerySecurityError(
                "请求控制服务暂不可用",
                reason="limiter_unavailable",
                status_code=503,
            )
        _acquire_local(user_id, token_id, plan)
        acquired_local = True
    try:
        yield
    finally:
        if acquired_redis:
            try:
                client.eval(_RELEASE_LUA, 3, *redis_keys)
            except Exception:
                # The keys have a bounded TTL, so a failed release cannot leak
                # capacity forever.
                pass
        elif acquired_local:
            _release_local(user_id, token_id)


def reset_query_security_state() -> None:
    global _active_global
    with _lock:
        _refresh_seen.clear()
        _active_user.clear()
        _active_token.clear()
        _active_global = 0
