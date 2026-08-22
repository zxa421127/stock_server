# -*- coding: utf-8 -*-
"""Small web-security primitives shared by HTML administrator routes."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from flask import request


def client_ip() -> str:
    """Return the WSGI peer address; ProxyFix may replace it only when explicitly enabled."""
    return str(request.remote_addr or "").strip()


class LoginAttemptLimiter:
    """Failed-login limiter backed by Redis when available, with local fallback.

    In production ``require_redis=True`` makes the limiter fail closed during a
    Redis outage so authentication cannot bypass the shared limit by switching
    workers.
    """
    def __init__(
        self,
        *,
        max_failures: int,
        window_seconds: int,
        lock_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        redis_getter: Callable[[], object | None] | None = None,
        namespace: str = "login",
        require_redis: bool = False,
    ) -> None:
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self.lock_seconds = max(1, int(lock_seconds))
        self.clock = clock
        self.namespace = str(namespace or "login").strip()
        self.require_redis = bool(require_redis)
        if redis_getter is None:
            from services.redis_backend import get_redis
            redis_getter = get_redis
        self.redis_getter = redis_getter
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.RLock()

    def _redis_keys(self, key: str) -> tuple[str, str]:
        from services.redis_backend import redis_key
        digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
        base = redis_key("security", "login", self.namespace, digest)
        return f"{base}:failures", f"{base}:locked"

    def _redis(self):
        try:
            return self.redis_getter()
        except Exception as exc:
            logging.warning("[登录限流] Redis访问失败: %s", exc)
            return None

    def _prune(self, key: str, now: float) -> deque[float]:
        failures = self._failures[key]
        cutoff = now - self.window_seconds
        while failures and failures[0] < cutoff:
            failures.popleft()
        return failures

    def is_blocked(self, key: str) -> bool:
        client = self._redis()
        if client is not None:
            try:
                _, lock_key = self._redis_keys(key)
                return bool(client.exists(lock_key))
            except Exception as exc:
                logging.warning("[登录限流] Redis检查失败: %s", exc)
                if self.require_redis:
                    return True
        elif self.require_redis:
            return True

        now = self.clock()
        with self._lock:
            until = self._blocked_until.get(key, 0.0)
            if until > now:
                return True
            self._blocked_until.pop(key, None)
            self._prune(key, now)
            return False

    def record_failure(self, key: str) -> None:
        client = self._redis()
        if client is not None:
            try:
                failure_key, lock_key = self._redis_keys(key)
                count = int(client.incr(failure_key))
                if count == 1:
                    client.expire(failure_key, self.window_seconds)
                if count >= self.max_failures:
                    client.set(lock_key, b"1", ex=self.lock_seconds)
                    client.delete(failure_key)
                return
            except Exception as exc:
                logging.warning("[登录限流] Redis写入失败: %s", exc)
                if self.require_redis:
                    return
        elif self.require_redis:
            return

        now = self.clock()
        with self._lock:
            failures = self._prune(key, now)
            failures.append(now)
            if len(failures) >= self.max_failures:
                self._blocked_until[key] = now + self.lock_seconds
                failures.clear()

    def clear(self, key: str) -> None:
        client = self._redis()
        if client is not None:
            try:
                failure_key, lock_key = self._redis_keys(key)
                client.delete(failure_key, lock_key)
            except Exception as exc:
                logging.warning("[登录限流] Redis清理失败: %s", exc)
        with self._lock:
            self._failures.pop(key, None)
            self._blocked_until.pop(key, None)



class AttemptLimiter(LoginAttemptLimiter):
    """Generic request-attempt limiter.

    Unlike login failure limiting, callers invoke :meth:`check_and_record` for
    every request attempt, including successful attempts. The Nth allowed
    request consumes the final slot; subsequent requests are rejected until
    the lock expires.
    """

    def __init__(
        self,
        *,
        max_attempts: int,
        window_seconds: int,
        lock_seconds: int,
        clock: Callable[[], float] = time.monotonic,
        redis_getter: Callable[[], object | None] | None = None,
        namespace: str = "attempt",
        require_redis: bool = False,
    ) -> None:
        super().__init__(
            max_failures=max_attempts,
            window_seconds=window_seconds,
            lock_seconds=lock_seconds,
            clock=clock,
            redis_getter=redis_getter,
            namespace=namespace,
            require_redis=require_redis,
        )

    def check_and_record(self, key: str) -> bool:
        if self.is_blocked(key):
            return False
        self.record_failure(key)
        return True
