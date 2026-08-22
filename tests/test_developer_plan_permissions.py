# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from integrations.market_data.tushare.catalog import list_tushare_apis
from integrations.market_data.tushare.permissions import (
    INDEPENDENT_PERMISSION_APIS,
    permission_class_for_api,
    required_scope_for_api,
)
from services.plan_catalog import (
    GENERAL_SCOPES,
    SPECIAL_SCOPES,
    plan_by_code,
    public_plan_codes,
    scope_allowed,
)


class TwoTierPlanTests(unittest.TestCase):
    def test_official_permission_split_covers_all_tushare_apis(self):
        rows = list_tushare_apis()
        points = [row for row in rows if row["permission_class"] == "15000积分权限"]
        independent = [row for row in rows if row["permission_class"] == "单独权限"]
        self.assertEqual(len(points) + len(independent), len(rows))
        self.assertTrue(points)
        self.assertTrue(independent)
        self.assertEqual({row["api_name"] for row in independent}, set(INDEPENDENT_PERMISSION_APIS))

    def test_catalog_exposes_permission_metadata(self):
        row_map = {row["api_name"]: row for row in list_tushare_apis()}
        self.assertEqual(row_map["stock_basic"]["permission_class"], "15000积分权限")
        self.assertEqual(row_map["rt_k"]["permission_class"], "单独权限")
        self.assertIn("required_scope", row_map["rt_k"])

    def test_general_plan_allows_points_only(self):
        self.assertTrue(scope_allowed(required_scope_for_api("stock_basic"), GENERAL_SCOPES))
        self.assertFalse(scope_allowed(required_scope_for_api("etf_mins"), GENERAL_SCOPES))
        self.assertFalse(scope_allowed(required_scope_for_api("rt_k"), GENERAL_SCOPES))
        self.assertFalse(scope_allowed(required_scope_for_api("stk_auction_o"), GENERAL_SCOPES))
        self.assertFalse(scope_allowed("market:kaipanla:read", GENERAL_SCOPES))

    def test_special_plan_allows_general_independent_and_kaipanla(self):
        for api_name in ("stock_basic", "etf_mins", "rt_k", "stk_auction_o"):
            with self.subTest(api_name=api_name):
                self.assertTrue(scope_allowed(required_scope_for_api(api_name), SPECIAL_SCOPES))
        self.assertTrue(scope_allowed("market:kaipanla:read", SPECIAL_SCOPES))
        self.assertFalse(scope_allowed("market:miniqmt:read", SPECIAL_SCOPES))
        self.assertFalse(scope_allowed("admin:sync", SPECIAL_SCOPES))

    def test_six_plan_codes_prices_and_durations(self):
        expected = {
            "general_month": (4900, 30, "general"),
            "general_quarter": (14700, 90, "general"),
            "general_year": (58800, 365, "general"),
            "special_month": (8900, 30, "special"),
            "special_quarter": (26700, 90, "special"),
            "special_year": (106800, 365, "special"),
        }
        self.assertEqual(public_plan_codes(), set(expected))
        for code, (price, days, plan_type) in expected.items():
            with self.subTest(code=code):
                plan = plan_by_code(code)
                self.assertEqual(plan["sale_price_cent"], price)
                self.assertEqual(plan["duration_days"], days)
                self.assertEqual(plan["plan_type"], plan_type)

    def test_permission_class_function(self):
        self.assertEqual(permission_class_for_api("daily"), "15000积分权限")
        self.assertEqual(permission_class_for_api("rt_min"), "单独权限")


if __name__ == "__main__":
    unittest.main()
