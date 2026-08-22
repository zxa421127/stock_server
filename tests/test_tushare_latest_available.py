# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
import unittest

import pandas as pd

from integrations.market_data.tushare.latest_available import (
    LATEST_AVAILABLE_POLICIES,
    is_latest_available_api,
    latest_cache_ttl_cap,
    query_with_latest_available,
)
from services.market_data_service import cache_policy_for


NOW = datetime(2026, 7, 13, 20, 0, 0)


class LatestAvailableDataTests(unittest.TestCase):
    def test_current_empty_falls_back_to_previous_weekday(self):
        calls = []

        def raw_query(api_name, params):
            calls.append((api_name, dict(params)))
            if params.get("trade_date") == "20260710":
                return pd.DataFrame([{"trade_date": "20260710", "value": 1}]), None
            return pd.DataFrame(), None

        df, error, meta = query_with_latest_available(
            "etf_share_size",
            {"trade_date": "20260713", "latest": True},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertEqual(len(df), 1)
        self.assertTrue(meta["fallback_used"])
        self.assertEqual(meta["requested_trade_date"], "20260713")
        self.assertEqual(meta["actual_trade_date"], "20260710")
        self.assertEqual(meta["data_freshness"], "latest_available")
        self.assertEqual([item[1]["trade_date"] for item in calls], ["20260713", "20260710"])

    def test_current_available_wins_without_fallback(self):
        calls = []

        def raw_query(api_name, params):
            calls.append(dict(params))
            return pd.DataFrame([{"trade_date": "20260713", "value": 1}]), None

        df, error, meta = query_with_latest_available(
            "margin",
            {"trade_date": "20260713"},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertEqual(len(df), 1)
        self.assertFalse(meta["fallback_used"])
        self.assertEqual(meta["actual_trade_date"], "20260713")
        self.assertEqual(len(calls), 1)

    def test_explicit_old_date_keeps_exact_semantics(self):
        calls = []

        def raw_query(api_name, params):
            calls.append(dict(params))
            return pd.DataFrame(), None

        _, error, meta = query_with_latest_available(
            "margin_detail",
            {"trade_date": "20260710"},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertFalse(meta["latest_available_enabled"])
        self.assertEqual(calls, [{"trade_date": "20260710"}])

    def test_latest_false_disables_current_date_fallback(self):
        calls = []

        def raw_query(api_name, params):
            calls.append(dict(params))
            return pd.DataFrame(), None

        _, error, meta = query_with_latest_available(
            "dc_hot",
            {"trade_date": "20260713", "latest": False},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertFalse(meta["latest_available_enabled"])
        self.assertEqual(calls, [{"trade_date": "20260713"}])

    def test_ccass_detail_uses_latest_nonempty_summary_identity(self):
        calls = []

        def raw_query(api_name, params):
            calls.append((api_name, dict(params)))
            date = params.get("trade_date")
            if api_name == "ccass_hold" and date == "20260710":
                return pd.DataFrame([
                    {"trade_date": "20260710", "ts_code": "08017.HK", "name": "sample"}
                ]), None
            if api_name == "ccass_hold_detail" and date == "20260710":
                return pd.DataFrame([
                    {"trade_date": "20260710", "ts_code": "08017.HK", "participant": "A"}
                ]), None
            return pd.DataFrame(), None

        df, error, meta = query_with_latest_available(
            "ccass_hold_detail",
            {"trade_date": "20260713", "latest": True},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertEqual(len(df), 1)
        self.assertTrue(meta["fallback_used"])
        self.assertEqual(meta["reference_api"], "ccass_hold")
        self.assertEqual(meta["reference_ts_code"], "08017.HK")
        self.assertEqual(meta["actual_trade_date"], "20260710")
        self.assertIn(
            ("ccass_hold_detail", {"trade_date": "20260710", "ts_code": "08017.HK"}),
            calls,
        )


    def test_hk_hold_northbound_uses_range_and_keeps_latest_quarter(self):
        calls = []

        def raw_query(api_name, params):
            calls.append((api_name, dict(params)))
            return pd.DataFrame([
                {"trade_date": "20260331", "exchange": "SH", "value": 1},
                {"trade_date": "20260630", "exchange": "SH", "value": 2},
            ]), None

        df, error, meta = query_with_latest_available(
            "hk_hold",
            {"trade_date": "20260713", "exchange": "SH", "latest": True},
            raw_query,
            now=NOW,
        )
        self.assertIsNone(error)
        self.assertEqual(len(calls), 1)
        self.assertIn("start_date", calls[0][1])
        self.assertNotIn("trade_date", calls[0][1])
        self.assertEqual(meta["actual_trade_date"], "20260630")
        self.assertTrue(meta["fallback_used"])
        self.assertEqual(df["trade_date"].tolist(), ["20260630"])

    def test_upstream_error_is_not_hidden_by_date_fallback(self):
        calls = []

        def raw_query(api_name, params):
            calls.append(dict(params))
            return pd.DataFrame(), "PermissionError: api not allowed"

        _, error, meta = query_with_latest_available(
            "hk_hold",
            {"trade_date": "20260713", "exchange": "HK", "latest": True},
            raw_query,
            now=NOW,
        )
        self.assertIn("api not allowed", error)
        self.assertEqual(len(calls), 1)
        self.assertEqual(meta["fallback_attempt_count"], 1)



    def test_service_cache_ttl_is_capped_for_fast_refresh(self):
        self.assertEqual(cache_policy_for("tushare", "dc_hot", realtime=False).ttl_seconds, 60)
        self.assertLessEqual(
            cache_policy_for("tushare", "etf_share_size", realtime=False).ttl_seconds,
            300,
        )

    def test_target_set_and_ttl_caps_are_complete(self):
        expected = {
            "etf_share_size", "margin", "margin_detail", "dc_hot", "kpl_list",
            "ths_hot", "ccass_hold", "ccass_hold_detail", "hk_hold",
        }
        self.assertEqual(set(LATEST_AVAILABLE_POLICIES), expected)
        self.assertTrue(all(is_latest_available_api(api) for api in expected))
        self.assertEqual(latest_cache_ttl_cap("dc_hot"), 60)
        self.assertEqual(latest_cache_ttl_cap("ccass_hold"), 600)


if __name__ == "__main__":
    unittest.main()
