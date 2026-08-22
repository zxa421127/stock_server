# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import pandas as pd

from integrations.market_data.base import MarketDataProvider, ProviderResponse
from integrations.market_data.registry import ProviderRegistry
from services.market_data_cache import clear_cache
from services.market_data_service import query_market_data


class FlakyProvider(MarketDataProvider):
    code = "fake"
    display_name = "Fake"

    def __init__(self):
        self.mode = "success"
        self.calls = 0

    def health_check(self):
        return {"available": True}

    def catalog(self):
        return [{"api_name": "stock_company"}]

    def query(self, data_type, params):
        self.calls += 1
        if self.mode == "error":
            return ProviderResponse(error="RuntimeError: upstream timeout")
        if self.mode == "empty":
            return ProviderResponse(pd.DataFrame())
        return ProviderResponse(pd.DataFrame([{"value": 1}]))


class MarketDataResilienceTests(unittest.TestCase):
    def setUp(self):
        clear_cache()
        self.registry = ProviderRegistry()
        self.provider = FlakyProvider()
        self.registry.register(self.provider)

    def _patches(self):
        return (
            patch("services.market_data_service.get_provider_registry", return_value=self.registry),
            patch("services.market_data_cache.get_redis", return_value=None),
            patch("services.market_data_service.config.MARKET_DATA_CACHE_TTL_OVERRIDES", {"stock_company": 1}),
            patch("services.market_data_service.config.MARKET_DATA_STALE_IF_ERROR_APIS", ["stock_company"]),
            patch("services.market_data_service.config.MARKET_DATA_STALE_IF_ERROR_SECONDS", 30),
            patch("services.market_data_service.config.MARKET_DATA_BACKGROUND_REFRESH_APIS", []),
        )

    def test_upstream_error_uses_last_good_static_value(self):
        patches = self._patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            first = query_market_data("fake", "stock_company", {"exchange": "SZSE"})
            self.assertIsNone(first.error)
            time.sleep(1.05)
            self.provider.mode = "error"
            second = query_market_data("fake", "stock_company", {"exchange": "SZSE"})
        self.assertIsNone(second.error)
        self.assertTrue(second.cache_hit)
        self.assertTrue(second.meta.get("cache_stale"))
        self.assertEqual(second.meta.get("stale_reason"), "upstream_error")
        self.assertEqual(len(second.data), 1)

    def test_empty_refresh_does_not_destroy_last_good_static_value(self):
        patches = self._patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            query_market_data("fake", "stock_company", {"exchange": "SZSE"})
            time.sleep(1.05)
            self.provider.mode = "empty"
            second = query_market_data("fake", "stock_company", {"exchange": "SZSE"})
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.meta.get("stale_reason"), "upstream_empty")
        self.assertEqual(len(second.data), 1)


if __name__ == "__main__":
    unittest.main()
