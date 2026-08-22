# -*- coding: utf-8 -*-
import unittest

from integrations.market_data.tushare.catalog import (
    TUSHARE_API_CATALOG,
    get_api_meta,
    is_allowed_tushare_api,
    list_tushare_apis,
    normalize_api_name,
)


OFFICIAL_NAME_MIGRATIONS = {
    "st_risk_warning": "st",
    "stk_surv": "stk_shock",
    "stk_surv_detail": "stk_high_shock",
    "stk_warn": "stk_alert",
    "hsgt_hold_stock": "hk_hold",
    "ths_limit": "limit_list_ths",
    "limit_list": "limit_list_d",
    "kpl_concept": "kpl_concept_cons",
    "dc_thematic": "dc_concept",
    "dc_thematic_detail": "dc_concept_cons",
    "etf_pcf": "etf_sh_cons",
    "etf_pcf_sz": "etf_sz_cons",
    "etf_ref": "rt_etf_sz_iopv",
    "index_ann": "idx_anns",
    "rt_index_k": "rt_idx_k",
    "rt_index_min": "rt_idx_min",
    "index_member": "index_member_all",
    "sw_realtime": "rt_sw_k",
    "index_market": "daily_info",
}


class TushareCatalogTests(unittest.TestCase):
    def test_existing_official_aliases(self):
        self.assertEqual(normalize_api_name("stock-basic"), "stock_basic")
        self.assertEqual(normalize_api_name("name-change"), "namechange")
        self.assertEqual(normalize_api_name("global_index"), "index_global")
        self.assertEqual(normalize_api_name("index_mins"), "idx_mins")
        self.assertEqual(normalize_api_name("index_factor_pro"), "idx_factor_pro")
        self.assertEqual(normalize_api_name("sw_min"), "sw_mins")

    def test_all_project_legacy_names_map_to_official_names(self):
        for legacy, official in OFFICIAL_NAME_MIGRATIONS.items():
            with self.subTest(legacy=legacy):
                self.assertEqual(normalize_api_name(legacy), official)
                self.assertTrue(is_allowed_tushare_api(legacy))
                self.assertIn(official, TUSHARE_API_CATALOG)

    def test_catalog_only_lists_current_official_names(self):
        names = {row["api_name"] for row in list_tushare_apis()}
        self.assertEqual(len(names), len(TUSHARE_API_CATALOG))
        self.assertIn("stk_limit", names)
        self.assertIn("limit_list_d", names)
        for legacy, official in OFFICIAL_NAME_MIGRATIONS.items():
            with self.subTest(legacy=legacy):
                self.assertIn(official, names)
                self.assertNotIn(legacy, names)

    def test_whitelist(self):
        self.assertTrue(is_allowed_tushare_api("trade_cal"))
        self.assertFalse(is_allowed_tushare_api("not_a_real_api"))

    def test_realtime_metadata_survives_aliases(self):
        self.assertTrue(get_api_meta("rt_k").realtime)
        self.assertTrue(get_api_meta("rt_index_k").realtime)
        self.assertTrue(get_api_meta("etf_ref").realtime)
        self.assertFalse(get_api_meta("stock_basic").realtime)


if __name__ == "__main__":
    unittest.main()
