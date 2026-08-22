# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd

from integrations.market_data.base import MarketDataProvider, ProviderResponse
from integrations.market_data.registry import ProviderRegistry
from services.market_data_cache import clear_cache
from services.market_data_service import query_market_data


class FakeProvider(MarketDataProvider):
    code = "fake"
    display_name = "Fake"

    def __init__(self):
        self.calls = 0

    def health_check(self):
        return {"available": True}

    def catalog(self):
        return [{"api_name": "daily"}]

    def query(self, data_type, params):
        self.calls += 1
        time.sleep(0.02)
        return ProviderResponse(pd.DataFrame([{"value": 1}]))


class ProviderRegistryTests(unittest.TestCase):
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = FakeProvider()
        registry.register(provider)
        self.assertIs(registry.get("fake"), provider)
        self.assertEqual(registry.codes(), ["fake"])

    def test_duplicate_registration_is_rejected(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider())
        with self.assertRaises(ValueError):
            registry.register(FakeProvider())

    def test_market_service_uses_cache(self):
        clear_cache()
        registry = ProviderRegistry()
        provider = FakeProvider()
        registry.register(provider)
        with patch("services.market_data_service.get_provider_registry", return_value=registry), \
             patch("services.market_data_cache.get_redis", return_value=None):
            first = query_market_data("fake", "daily", {"symbol": "A"})
            second = query_market_data("fake", "daily", {"symbol": "A"})
        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(provider.calls, 1)

    def test_thirty_identical_requests_are_coalesced(self):
        clear_cache()
        registry = ProviderRegistry()
        provider = FakeProvider()
        registry.register(provider)
        with patch("services.market_data_service.get_provider_registry", return_value=registry), \
             patch("services.market_data_cache.get_redis", return_value=None):
            with ThreadPoolExecutor(max_workers=30) as pool:
                results = list(pool.map(lambda _: query_market_data("fake", "daily", {"symbol": "A"}), range(30)))
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(results), 30)
        self.assertTrue(all(len(result.data) == 1 for result in results))


if __name__ == "__main__":
    unittest.main()
