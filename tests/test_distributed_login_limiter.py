from __future__ import annotations

from services.web_security import LoginAttemptLimiter


class FakeRedis:
    def __init__(self):
        self.values = {}
    def exists(self, key):
        return 1 if key in self.values else 0
    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]
    def expire(self, key, seconds):
        return True
    def set(self, key, value, ex=None):
        self.values[key] = value
        return True
    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
        return len(keys)


def test_redis_limiter_shares_failures_between_instances():
    redis = FakeRedis()
    first = LoginAttemptLimiter(max_failures=2, window_seconds=60, lock_seconds=120, redis_getter=lambda: redis, namespace="admin")
    second = LoginAttemptLimiter(max_failures=2, window_seconds=60, lock_seconds=120, redis_getter=lambda: redis, namespace="admin")
    first.record_failure("1.2.3.4|admin")
    second.record_failure("1.2.3.4|admin")
    assert first.is_blocked("1.2.3.4|admin")
    second.clear("1.2.3.4|admin")
    assert not first.is_blocked("1.2.3.4|admin")


def test_required_redis_fails_closed_when_unavailable():
    limiter = LoginAttemptLimiter(max_failures=2, window_seconds=60, lock_seconds=120, redis_getter=lambda: None, require_redis=True)
    assert limiter.is_blocked("key")
