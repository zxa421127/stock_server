# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch

from services import rate_limit_service as limiter


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        limiter.reset_local_rate_limits()

        # These unit tests exercise the in-process fallback counters.  They must
        # not inherit deployment-specific Redis fail-closed settings or seed the
        # daily quota from the machine's real usage database.  Otherwise a user
        # id that has already consumed quota in the active test database can make
        # an otherwise deterministic unit test fail depending on test order/time.
        self.redis_required_patch = patch.object(limiter.config, "REDIS_REQUIRED", False)
        self.redis_required_patch.start()
        self.addCleanup(self.redis_required_patch.stop)

        self.daily_usage_seed_patch = patch.object(
            limiter,
            "_initial_daily_usage",
            return_value=0,
        )
        self.daily_usage_seed_patch.start()
        self.addCleanup(self.daily_usage_seed_patch.stop)

    def test_general_plan_uses_120_per_minute_when_floor_is_one(self):
        plan = {"plan_type": "general", "quota_per_minute": 120, "quota_daily": 0}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "MIN_REQUESTS_PER_MINUTE", 1), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            for _ in range(120):
                self.assertTrue(limiter.check_rate_limit(1, "tushare:read", plan)[0])
            allowed, message = limiter.check_rate_limit(1, "tushare:read", plan)
        self.assertFalse(allowed)
        self.assertIn("120", message)

    def test_special_plan_uses_300_per_minute_when_floor_is_one(self):
        plan = {"plan_type": "special", "quota_per_minute": 300, "quota_daily": 0}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "MIN_REQUESTS_PER_MINUTE", 1), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            for _ in range(300):
                self.assertTrue(limiter.check_rate_limit(101, "market:read", plan)[0])
            allowed, message = limiter.check_rate_limit(101, "market:read", plan)
        self.assertFalse(allowed)
        self.assertIn("300", message)

    def test_default_plan_supports_1000_per_minute(self):
        plan = {"plan_type": "realtime", "quota_per_minute": 1000, "quota_daily": 0}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            for _ in range(1000):
                self.assertTrue(limiter.check_rate_limit(2, "tushare:read", plan)[0])
            self.assertFalse(limiter.check_rate_limit(2, "tushare:read", plan)[0])

    def test_daily_quota_is_independent_from_usage_log_flush(self):
        plan = {"plan_type": "history", "quota_per_minute": 1000, "quota_daily": 2}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            self.assertTrue(limiter.check_rate_limit(3, "tushare:read", plan)[0])
            self.assertTrue(limiter.check_rate_limit(3, "tushare:read", plan)[0])
            allowed, message = limiter.check_rate_limit(3, "tushare:read", plan)
        self.assertFalse(allowed)
        self.assertIn("今日调用额度", message)

        # Keep the production safety contract covered without adding a separate
        # test count: when Redis is required and unavailable, rate limiting must
        # fail closed instead of silently falling back to process-local counters.
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "REDIS_REQUIRED", True):
            allowed, message = limiter.check_rate_limit(303, "tushare:read", plan)
        self.assertFalse(allowed)
        self.assertIn("限流服务暂不可用", message)

    def test_thirty_users_have_independent_general_plan_windows(self):
        plan = {"plan_type": "general", "quota_per_minute": 120, "quota_daily": 0}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "MIN_REQUESTS_PER_MINUTE", 1), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            for user_id in range(1, 31):
                for _ in range(120):
                    self.assertTrue(limiter.check_rate_limit(user_id, "tushare:read", plan)[0])
                self.assertFalse(limiter.check_rate_limit(user_id, "tushare:read", plan)[0])

    def test_admin_has_no_per_user_minute_limit(self):
        plan = {"plan_type": "admin", "quota_per_minute": 0, "quota_daily": 0}
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 0):
            for _ in range(1500):
                self.assertTrue(limiter.check_rate_limit(4, "admin:sync", plan)[0])

    def test_admin_minute_exemption_still_obeys_global_rps(self):
        plan = {"plan_type": "admin", "quota_per_minute": 0, "quota_daily": 0}

        # Admin intentionally has no per-user minute quota, but the server-wide
        # RPS guard must remain active. Pin time so all calls share one second.
        with patch.object(limiter, "get_redis", return_value=None), \
             patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 2), \
             patch.object(limiter.time, "time", return_value=1_700_000_000):
            self.assertEqual(limiter.effective_per_minute_limit(plan), 0)
            self.assertTrue(limiter.check_rate_limit(404, "admin:sync", plan)[0])
            self.assertTrue(limiter.check_rate_limit(404, "admin:sync", plan)[0])
            allowed, message = limiter.check_rate_limit(
                404,
                "admin:sync",
                plan,
            )

        self.assertFalse(allowed)
        self.assertIn("服务器当前请求过多", message)


if __name__ == "__main__":
    unittest.main()

def test_rate_limit_decision_preserves_legacy_sequence_contract():
    decision = limiter.RateLimitDecision(
        False,
        "slow down",
        "minute_limit",
        7,
    )
    allowed, message = decision
    assert isinstance(decision, tuple)
    assert allowed is False
    assert message == "slow down"
    assert len(decision) == 2
    assert decision[0] is False
    assert decision[1] == "slow down"
    assert decision[-1] == "slow down"
    assert tuple(decision) == (False, "slow down")
    assert decision == (False, "slow down")
    assert bool(decision) is True
    assert decision.reason_code == "minute_limit"
    assert decision.retry_after_seconds == 7


def test_local_rate_limit_decision_metadata_is_structured():
    limiter.reset_local_rate_limits()
    with patch.object(limiter, "get_redis", return_value=None), \
         patch.object(limiter.config, "REDIS_REQUIRED", False), \
         patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 1), \
         patch.object(limiter.time, "time", return_value=1000):
        first = limiter.check_rate_limit(
            9101,
            "tushare:read",
            {"quota_per_minute": 100, "quota_daily": 0},
        )
        second = limiter.check_rate_limit(
            9102,
            "tushare:read",
            {"quota_per_minute": 100, "quota_daily": 0},
        )
    assert first.allowed is True
    assert first.reason_code == "allowed"
    assert first.retry_after_seconds is None
    assert second.allowed is False
    assert second.reason_code == "global_rps"
    assert second.retry_after_seconds == 1

    limiter.reset_local_rate_limits()
    with patch.object(limiter, "get_redis", return_value=None), \
         patch.object(limiter.config, "REDIS_REQUIRED", False), \
         patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 100), \
         patch.object(limiter.time, "time", return_value=1000):
        first = limiter.check_rate_limit(
            9201,
            "tushare:read",
            {"quota_per_minute": 1, "quota_daily": 0},
        )
        second = limiter.check_rate_limit(
            9201,
            "tushare:read",
            {"quota_per_minute": 1, "quota_daily": 0},
        )
    assert first.allowed is True
    assert second.allowed is False
    assert second.reason_code == "minute_limit"
    assert 1 <= second.retry_after_seconds <= 60


def test_daily_and_unavailable_retry_metadata_are_explicit():
    limiter.reset_local_rate_limits()
    with patch.object(limiter, "get_redis", return_value=None), \
         patch.object(limiter.config, "REDIS_REQUIRED", False), \
         patch.object(limiter, "_initial_daily_usage", return_value=1), \
         patch.object(limiter.config, "GLOBAL_REQUESTS_PER_SECOND", 100):
        daily = limiter.check_rate_limit(
            9301,
            "tushare:read",
            {"quota_per_minute": 100, "quota_daily": 1},
        )
    assert daily.allowed is False
    assert daily.reason_code == "daily_limit"
    assert 1 <= daily.retry_after_seconds <= 86400

    with patch.object(limiter, "get_redis", return_value=None), \
         patch.object(limiter.config, "REDIS_REQUIRED", True):
        unavailable = limiter.check_rate_limit(
            9401,
            "tushare:read",
            {"quota_per_minute": 100, "quota_daily": 0},
        )
    assert unavailable.allowed is False
    assert unavailable.reason_code == "limiter_unavailable"
    assert unavailable.retry_after_seconds == 5
