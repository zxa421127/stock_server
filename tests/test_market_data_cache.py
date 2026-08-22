import time
import unittest

import pandas as pd

from services.market_data_cache import TTLDataFrameCache, build_cache_key


class MarketDataCacheTests(unittest.TestCase):
    def test_returns_copy(self):
        cache = TTLDataFrameCache(max_items=10)
        source = pd.DataFrame([{"value": 1}])
        cache.set("k", source, 10)
        loaded = cache.get("k")
        loaded.loc[0, "value"] = 9
        self.assertEqual(cache.get("k").loc[0, "value"], 1)

    def test_expiry(self):
        cache = TTLDataFrameCache(max_items=10)
        cache.set("k", pd.DataFrame([{"value": 1}]), 1)
        time.sleep(1.05)
        self.assertIsNone(cache.get("k"))

    def test_key_is_order_independent(self):
        a = build_cache_key("tushare", "daily", {"a": 1, "b": 2})
        b = build_cache_key("tushare", "daily", {"b": 2, "a": 1})
        self.assertEqual(a, b)

    def test_stale_value_is_hidden_from_normal_get_but_available_for_fallback(self):
        cache = TTLDataFrameCache(max_items=10)
        now = time.time()
        cache.set(
            "k",
            pd.DataFrame([{"value": 1}]),
            1,
            stale_if_error_seconds=30,
            cached_at=now - 10,
            fresh_until=now - 1,
            stale_until=now + 20,
        )
        self.assertIsNone(cache.get("k"))
        lookup = cache.lookup("k", allow_stale=True)
        self.assertIsNotNone(lookup)
        self.assertTrue(lookup.stale)
        self.assertEqual(lookup.data.loc[0, "value"], 1)

    def test_value_is_removed_after_stale_window(self):
        cache = TTLDataFrameCache(max_items=10)
        now = time.time()
        cache.set(
            "k",
            pd.DataFrame([{"value": 1}]),
            1,
            cached_at=now - 10,
            fresh_until=now - 5,
            stale_until=now - 1,
        )
        self.assertIsNone(cache.lookup("k", allow_stale=True))


if __name__ == "__main__":
    unittest.main()
