# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
import pandas as pd

from integrations.market_data.kaipanla.adapter import normalize_kaipanla_bidding


class KaipanlaBiddingAdapterTests(unittest.TestCase):
    def test_output_contains_final_business_fields_and_hides_raw_positions(self):
        raw = pd.DataFrame([[
            "000001", "平安银行", 12.35, 3.15, 86_000_000, 3.21,
            -12_000_000, 1.25, 36_000_000, 72_000_000,
            36_000_001, "银行", 1_800_000_000,
            -12_000_000, 24_000_000, -36_000_000, "2连板",
        ]])
        row = normalize_kaipanla_bidding(raw, trade_date="20260717").iloc[0]
        self.assertEqual(row["auction_net_amount"], -12_000_000)
        self.assertEqual(row["auction_match_amount"], 36_000_001)
        self.assertEqual(row["auction_amount"], 36_000_000)
        self.assertEqual(row["main_net_amount"], -12_000_000)
        self.assertEqual(row["main_buy_amount"], 24_000_000)
        self.assertEqual(row["main_sell_amount"], 36_000_000)
        self.assertEqual(row["limit_up_days"], 2)
        for removed in ("10", "13", "14", "15", "主力卖出", "main_sell_amount_signed", "main_amount_relation_valid", "field_validation_warning"):
            self.assertNotIn(removed, row.index)

    def test_tushare_industry_is_separate_from_kaipanla_sector(self):
        raw = pd.DataFrame([{0: "920001", 1: "", 11: ""}])
        stock_basic = pd.DataFrame([{"symbol": "920001", "ts_code": "920001.BJ", "name": "北交测试", "industry": "机械"}])
        row = normalize_kaipanla_bidding(raw, trade_date="20260717", stock_basic_df=stock_basic).iloc[0]
        self.assertEqual(row["ts_code"], "920001.BJ")
        self.assertEqual(row["name"], "北交测试")
        self.assertTrue(pd.isna(row["sector"]))
        self.assertEqual(row["行业"], "机械")

    def test_nullable_reference_fields_do_not_break_code_matching(self):
        raw = pd.DataFrame([{0: "920002", 1: None, 11: None}])
        stock_basic = pd.DataFrame([{"symbol": pd.NA, "ts_code": "920002.BJ", "name": "北交可空字段", "industry": pd.NA}])
        row = normalize_kaipanla_bidding(raw, trade_date="20260717", stock_basic_df=stock_basic).iloc[0]
        self.assertEqual(row["ts_code"], "920002.BJ")
        self.assertEqual(row["name"], "北交可空字段")
        self.assertTrue(pd.isna(row["sector"]))

    def test_legacy_auction_buy_sell_columns_are_ignored(self):
        raw = pd.DataFrame([{0: "300001", 6: 110.0, "auction_buy_amount": 150.0, "auction_sell_amount": 40.0, 13: 1.0, 14: 100.0, 15: -40.0}])
        row = normalize_kaipanla_bidding(raw, trade_date="20260717").iloc[0]
        self.assertEqual(row["auction_net_amount"], 110)
        self.assertEqual(row["main_net_amount"], 1)
        self.assertEqual(row["main_buy_amount"], 100)
        self.assertEqual(row["main_sell_amount"], 40)
        self.assertNotIn("auction_buy_amount", row.index)
        self.assertNotIn("auction_sell_amount", row.index)

    def test_raw_10_maps_only_to_match_amount(self):
        row = normalize_kaipanla_bidding(pd.DataFrame([{0: "600000", 1: "浦发银行", 10: 88_000_000}]), trade_date="20260717").iloc[0]
        self.assertEqual(row["auction_match_amount"], 88_000_000)
        self.assertTrue(pd.isna(row["auction_amount"]))
        self.assertNotIn("10", row.index)


if __name__ == "__main__":
    unittest.main()
