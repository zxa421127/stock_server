# -*- coding: utf-8 -*-
"""High-throughput fixed-window limits with Redis and in-process fallback."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any

import config
from services.redis_backend import get_redis, redis_key

_lock = threading.RLock()
_minute_windows: dict[tuple[int, int], int] = {}
_daily_windows: dict[tuple[int, str], int] = {}
_global_windows: dict[int, int] = {}
_daily_seed_cache: dict[tuple[int, str], int] = {}

_RATE_LUA = """
local minute_key = KEYS[1]
local daily_key = KEYS[2]
local global_key = KEYS[3]
local minute_limit = tonumber(ARGV[1])
local daily_limit = tonumber(ARGV[2])
local global_limit = tonumber(ARGV[3])
local daily_ttl = tonumber(ARGV[4])
local initial_daily = tonumber(ARGV[5])

local g = tonumber(redis.call('GET', global_key) or '0')
if global_limit > 0 and g >= global_limit then
  return {-2, g, 0, 0}
end
local m = tonumber(redis.call('GET', minute_key) or '0')
if minute_limit > 0 and m >= minute_limit then
  return {0, g, m, 0}
end
local raw_daily = redis.call('GET', daily_key)
if not raw_daily and daily_limit > 0 then
  redis.call('SET', daily_key, initial_daily, 'EX', daily_ttl, 'NX')
end
local d = tonumber(redis.call('GET', daily_key) or '0')
if daily_limit > 0 and d >= daily_limit then
  return {-1, g, m, d}
end

g = redis.call('INCR', global_key)
if g == 1 then redis.call('EXPIRE', global_key, 2) end
m = redis.call('INCR', minute_key)
if m == 1 then redis.call('EXPIRE', minute_key, 120) end
if daily_limit > 0 then
  d = redis.call('INCR', daily_key)
  if d == 1 then redis.call('EXPIRE', daily_key, daily_ttl) end
end
return {1, g, m, d}
"""


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _daily_ttl_seconds() -> int:
    now = datetime.now()
    tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return max(60, int((tomorrow - now).total_seconds()) + 3600)


def _initial_daily_usage(user_id: int, day_bucket: str) -> int:
    """Read durable usage only once per user/day, then count in memory or Redis."""
    key = (int(user_id), day_bucket)
    with _lock:
        cached = _daily_seed_cache.get(key)
    if cached is not None:
        return cached
    try:
        from db_utils import get_daily_usage_count
        usage_date = day_bucket if "-" in day_bucket else f"{day_bucket[:4]}-{day_bucket[4:6]}-{day_bucket[6:8]}"
        value = max(int(get_daily_usage_count(int(user_id), usage_date)), 0)
    except Exception:
        value = 0
    with _lock:
        _daily_seed_cache[key] = value
        if len(_daily_seed_cache) > 100000:
            for old_key in [item for item in _daily_seed_cache if item[1] != day_bucket]:
                _daily_seed_cache.pop(old_key, None)
    return value


def effective_per_minute_limit(plan: dict) -> int:
    if str((plan or {}).get("plan_type", "")).lower() == "admin":
        return 0
    configured = _to_int((plan or {}).get("quota_per_minute"), 0)
    if configured <= 0:
        configured = int(getattr(config, "DEFAULT_REQUESTS_PER_MINUTE", 1000) or 1000)
    return max(configured, int(getattr(config, "MIN_REQUESTS_PER_MINUTE", 1) or 1))


class RateLimitDecision(tuple):
    # Structured limiter result that remains a real two-item tuple.

    def __new__(
        cls,
        allowed: bool,
        message: str,
        reason_code: str,
        retry_after_seconds: int | None,
    ):
        obj = super().__new__(
            cls,
            (
                bool(allowed),
                str(message),
            ),
        )
        obj.reason_code = str(reason_code)
        obj.retry_after_seconds = (
            None
            if retry_after_seconds is None
            else max(1, int(retry_after_seconds))
        )
        return obj

    @property
    def allowed(self) -> bool:
        return bool(self[0])

    @property
    def message(self) -> str:
        return str(self[1])

    def __repr__(self) -> str:
        return (
            "RateLimitDecision("
            f"allowed={self.allowed!r}, "
            f"message={self.message!r}, "
            f"reason_code={self.reason_code!r}, "
            f"retry_after_seconds={self.retry_after_seconds!r}"
            ")"
        )


def _ceil_positive_seconds(seconds: float) -> int:
    whole = int(seconds)
    if seconds > float(whole):
        whole += 1
    return max(1, whole)


def _seconds_until_next_minute(now: datetime | None = None) -> int:
    current = now or datetime.now()
    next_minute = current.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return _ceil_positive_seconds((next_minute - current).total_seconds())


def _seconds_until_next_local_midnight(now: datetime | None = None) -> int:
    current = now or datetime.now()
    midnight = datetime.combine(
        current.date() + timedelta(days=1),
        datetime.min.time(),
    )
    return _ceil_positive_seconds((midnight - current).total_seconds())

def _check_redis(
    user_id: int,
    minute_limit: int,
    daily_limit: int,
) -> RateLimitDecision | None:
    client = get_redis()
    if client is None:
        return None
    now = datetime.now()
    minute_bucket = now.strftime("%Y%m%d%H%M")
    day_bucket = now.strftime("%Y%m%d")
    second_bucket = int(time.time())
    global_limit = int(getattr(config, "GLOBAL_REQUESTS_PER_SECOND", 600) or 0)
    try:
        result = client.eval(
            _RATE_LUA,
            3,
            redis_key("rate", "minute", user_id, minute_bucket),
            redis_key("rate", "day", user_id, day_bucket),
            redis_key("rate", "global", second_bucket),
            minute_limit,
            daily_limit,
            global_limit,
            _daily_ttl_seconds(),
            _initial_daily_usage(user_id, day_bucket) if daily_limit > 0 else 0,
        )
        code = int(result[0])
        if code == 1:
            return RateLimitDecision(True, "ok", "allowed", None)
        if code == 0:
            return RateLimitDecision(
                False,
                f"每分钟调用次数已达上限：{minute_limit}",
                "minute_limit",
                _seconds_until_next_minute(now),
            )
        if code == -1:
            return RateLimitDecision(
                False,
                f"今日调用额度已用完：{daily_limit}",
                "daily_limit",
                _seconds_until_next_local_midnight(now),
            )
        return RateLimitDecision(
            False,
            "服务器当前请求过多，请稍后重试",
            "global_rps",
            1,
        )
    except Exception:
        return None


def _check_local(
    user_id: int,
    minute_limit: int,
    daily_limit: int,
) -> RateLimitDecision:
    now_ts = int(time.time())
    minute_bucket = now_ts // 60
    now = datetime.now()
    day_bucket = now.strftime("%Y-%m-%d")
    global_limit = int(getattr(config, "GLOBAL_REQUESTS_PER_SECOND", 600) or 0)
    day_seed = _initial_daily_usage(user_id, day_bucket) if daily_limit > 0 else 0
    with _lock:
        global_count = _global_windows.get(now_ts, 0)
        if global_limit > 0 and global_count >= global_limit:
            return RateLimitDecision(
                False,
                "服务器当前请求过多，请稍后重试",
                "global_rps",
                1,
            )
        minute_key = (user_id, minute_bucket)
        minute_count = _minute_windows.get(minute_key, 0)
        if minute_limit > 0 and minute_count >= minute_limit:
            return RateLimitDecision(
                False,
                f"每分钟调用次数已达上限：{minute_limit}",
                "minute_limit",
                max(1, 60 - (now_ts % 60)),
            )
        day_key = (user_id, day_bucket)
        if day_key not in _daily_windows:
            _daily_windows[day_key] = day_seed
        day_count = _daily_windows.get(day_key, 0)
        if daily_limit > 0 and day_count >= daily_limit:
            return RateLimitDecision(
                False,
                f"今日调用额度已用完：{daily_limit}",
                "daily_limit",
                _seconds_until_next_local_midnight(now),
            )

        _global_windows[now_ts] = global_count + 1
        _minute_windows[minute_key] = minute_count + 1
        if daily_limit > 0:
            _daily_windows[day_key] = day_count + 1

        if len(_global_windows) > 10:
            for key in [key for key in _global_windows if key < now_ts - 2]:
                _global_windows.pop(key, None)
        if len(_minute_windows) > 100000:
            for key in [key for key in _minute_windows if key[1] < minute_bucket - 2]:
                _minute_windows.pop(key, None)
        if len(_daily_windows) > 100000:
            for key in [key for key in _daily_windows if key[1] != day_bucket]:
                _daily_windows.pop(key, None)
    return RateLimitDecision(True, "ok", "allowed", None)


def check_rate_limit(
    user_id: int,
    scope: str,
    plan: dict,
) -> RateLimitDecision:
    del scope  # All authenticated API calls share the same per-user minute window.
    user_id = int(user_id)
    minute_limit = effective_per_minute_limit(plan or {})
    daily_limit = max(_to_int((plan or {}).get("quota_daily"), 0), 0)
    redis_result = _check_redis(user_id, minute_limit, daily_limit)
    if redis_result is not None:
        return redis_result
    if bool(getattr(config, "REDIS_REQUIRED", False)):
        return RateLimitDecision(
            False,
            "限流服务暂不可用，请稍后重试",
            "limiter_unavailable",
            5,
        )
    return _check_local(user_id, minute_limit, daily_limit)


def reset_local_rate_limits() -> None:
    with _lock:
        _minute_windows.clear()
        _daily_windows.clear()
        _global_windows.clear()
        _daily_seed_cache.clear()
