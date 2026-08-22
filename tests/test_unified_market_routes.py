# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

from integrations.market_data.tushare.catalog import list_tushare_apis


ROOT = Path(__file__).resolve().parents[1]


class UnifiedMarketRouteTests(unittest.TestCase):
    def test_removed_blueprint_file_is_absent(self):
        self.assertFalse((ROOT / "routes" / "tushare_routes.py").exists())

    def test_app_only_registers_unified_market_blueprint(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('app.register_blueprint(market_data_bp, url_prefix="/api/v1/market")', source)
        self.assertNotIn("tushare_bp", source)

    def test_unified_route_and_cache_endpoints_exist(self):
        source = (ROOT / "routes" / "market_data_routes.py").read_text(encoding="utf-8")
        self.assertIn('@market_data_bp.route("/<provider_code>/<path:data_type>"', source)
        self.assertIn('@market_data_bp.get("/cache/stats")', source)
        self.assertIn('@market_data_bp.post("/cache/clear")', source)
        self.assertIn('@market_data_bp.route("/cache/query/<provider_code>/<path:data_type>"', source)

    def test_catalog_only_emits_unified_urls(self):
        rows = list_tushare_apis()
        self.assertGreater(len(rows), 0)
        self.assertTrue(all(row["url"].startswith("/api/v1/market/tushare/") for row in rows))
        self.assertTrue(all("market_url" not in row for row in rows))


if __name__ == "__main__":
    unittest.main()
