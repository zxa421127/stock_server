# -*- coding: utf-8 -*-
"""Optional Redis connection shared by cache and distributed rate limiting."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import config

_lock = threading.RLock()
_client: Any = None
_last_failure_at = 0.0
_failure_cooldown = 10.0


def get_redis():
    global _client, _last_failure_at
    redis_url = (getattr(config, "REDIS_URL", "") or "").strip()
    if not redis_url:
        return None

    now = time.monotonic()
    with _lock:
        if _client is not None:
            return _client
        if now - _last_failure_at < _failure_cooldown:
            return None
        try:
            import redis

            client = redis.Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_connect_timeout=float(getattr(config, "REDIS_CONNECT_TIMEOUT_SECONDS", 1.0)),
                socket_timeout=float(getattr(config, "REDIS_SOCKET_TIMEOUT_SECONDS", 1.0)),
                health_check_interval=30,
            )
            client.ping()
            _client = client
            logging.info("[Redis] 连接成功")
            return _client
        except Exception as exc:
            _last_failure_at = now
            if bool(getattr(config, "REDIS_REQUIRED", False)):
                logging.error("[Redis] 生产必需连接不可用，拒绝静默降级: %s", exc)
            else:
                logging.warning("[Redis] 不可用，使用进程内降级方案: %s", exc)
            return None


def redis_key(*parts: object) -> str:
    prefix = (getattr(config, "REDIS_KEY_PREFIX", "stock_server") or "stock_server").strip(":")
    normalized = [str(part).strip(":") for part in parts if str(part)]
    return ":".join([prefix, *normalized])


def reset_redis_backend() -> None:
    global _client, _last_failure_at
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
        _client = None
        _last_failure_at = 0.0
