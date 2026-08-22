# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd

from integrations.market_data.kaipanla.client import KaipanlaClient
from services.kaipanla_bidding_service import KaipanlaBiddingService
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


class KaipanlaBiddingServiceTests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.repo = KaipanlaSnapshotRepository(connection_factory=lambda: self.conn)

    def tearDown(self):
        self.conn.close()
        os.remove(self.db_path)

    @staticmethod
    def _result(data=None, error=None, meta=None):
        return SimpleNamespace(data=data if data is not None else pd.DataFrame(), error=error, meta=meta or {})

    @staticmethod
    def _raw_fetch(data):
        def fetch_page(**kwargs):
            return data, {"ret": 0, "info": data.values.tolist()}, None, kwargs
        return fetch_page

    def test_live_query_marks_trade_date_only_inside_verified_auction_window(self):
        raw = pd.DataFrame([{0: "000001", 1: "平安银行", 6: 1, 10: 2, 13: 3, 14: 5, 15: -2}])

        def market_query(provider, api_name, params, **kwargs):
            if api_name == "trade_cal":
                return self._result(pd.DataFrame([{"cal_date": "20260717", "is_open": 1}]))
            return self._result(pd.DataFrame())

        service = KaipanlaBiddingService(
            repository=self.repo,
            client=KaipanlaClient(fetch_page=self._raw_fetch(raw)),
            market_query=market_query,
            china_now=lambda: datetime(2026, 7, 17, 9, 25, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        response = service.query_live({"st": 20})
        self.assertEqual(response.meta["actual_trade_date"], "20260717")
        self.assertEqual(response.meta["data_freshness"], "verified_live")
        self.assertEqual(response.data.iloc[0]["trade_date"], "20260717")

    def test_live_query_outside_window_is_explicitly_unverified(self):
        raw = pd.DataFrame([{0: "000001", 1: "平安银行"}])

        def market_query(provider, api_name, params, **kwargs):
            if api_name == "trade_cal":
                return self._result(pd.DataFrame([{"cal_date": "20260717", "is_open": 1}]))
            return self._result(pd.DataFrame())

        service = KaipanlaBiddingService(
            repository=self.repo,
            client=KaipanlaClient(fetch_page=self._raw_fetch(raw)),
            market_query=market_query,
            china_now=lambda: datetime(2026, 7, 17, 15, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        response = service.query_live({"st": 20})
        self.assertIsNone(response.meta["actual_trade_date"])
        self.assertEqual(response.meta["data_freshness"], "unverified_realtime")
        self.assertIn("未标注交易日", response.meta["warning"])
        self.assertTrue(pd.isna(response.data.iloc[0]["trade_date"]))

    def test_capture_rejects_empty_upstream_payload(self):
        service = KaipanlaBiddingService(
            repository=self.repo,
            client=KaipanlaClient(fetch_page=self._raw_fetch(pd.DataFrame())),
            market_query=lambda *args, **kwargs: self._result(pd.DataFrame()),
        )
        response = service.capture_snapshot(
            trade_date="20260717", snapshot_time="2026-07-17 09:26:05"
        )
        self.assertIsNotNone(response.error)
        self.assertIn("空", response.error)
        self.assertFalse(self.repo.has_snapshot("20260717"))

    def test_history_can_read_exact_typed_snapshot_id_when_same_day_has_two_types(self):
        first = self.repo.save_snapshot(
            trade_date="20260717", snapshot_time="2026-07-17 09:26:05", snapshot_type="auction", source_params={},
            raw_payload={"version": 1}, normalized_data=[{"ts_code": "000001.SZ", "name": "竞价批次"}],
        )
        second = self.repo.save_snapshot(
            trade_date="20260717", snapshot_time="2026-07-17 09:31:00", snapshot_type="post_open", source_params={},
            raw_payload={"version": 2}, normalized_data=[{"ts_code": "000001.SZ", "name": "开盘后批次"}],
        )
        self.assertNotEqual(first.snapshot.snapshot_id, second.snapshot.snapshot_id)
        service = KaipanlaBiddingService(repository=self.repo, market_query=lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
        response = service.query_history({"snapshot_id": second.snapshot.snapshot_id, "snapshot_type": "post_open"})
        self.assertEqual(response.data.iloc[0]["name"], "开盘后批次")
        self.assertEqual(response.meta["snapshot_type"], "post_open")
        self.assertEqual(response.meta["data_freshness"], "exact_snapshot_id")

    def test_requested_non_trading_date_uses_canonical_snapshot_on_or_before(self):
        self.repo.save_snapshot(
            trade_date="20260717", snapshot_time="2026-07-17 09:26:05", source_params={}, raw_payload={},
            normalized_data=[{"ts_code": "000001.SZ"}],
        )
        service = KaipanlaBiddingService(repository=self.repo, market_query=lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
        response = service.query_history({"trade_date": "20260719"})
        self.assertEqual(response.meta["actual_trade_date"], "20260717")
        self.assertEqual(response.meta["data_freshness"], "latest_snapshot_on_or_before")

    def test_no_snapshot_resolves_latest_open_date_before_tushare_fallback(self):
        calls = []
        def market_query(provider, api_name, params, **kwargs):
            calls.append((api_name, dict(params)))
            if api_name == "trade_cal":
                return self._result(pd.DataFrame([
                    {"cal_date": "20260717", "is_open": 1},
                    {"cal_date": "20260718", "is_open": 0},
                    {"cal_date": "20260719", "is_open": 0},
                ]))
            if api_name == "stk_auction_o":
                self.assertEqual(params["trade_date"], "20260717")
                return self._result(pd.DataFrame([{"ts_code": "000001.SZ", "trade_date": "20260717", "price": 12.35}]), meta={"actual_trade_date": "20260717"})
            return self._result(pd.DataFrame())
        service = KaipanlaBiddingService(repository=self.repo, market_query=market_query)
        response = service.query_history({"trade_date": "20260719"})
        self.assertIsNone(response.error)
        self.assertEqual(response.meta["fallback_reason"], "kaipanla_snapshot_not_found")
        self.assertEqual(response.meta["data_freshness"], "tushare_historical_fallback")
        self.assertEqual(response.meta["actual_trade_date"], "20260717")
        self.assertIn("无法还原", response.meta["warning"])

    def test_no_snapshot_stops_when_trade_calendar_is_unknown(self):
        calls = []
        def market_query(provider, api_name, params, **kwargs):
            calls.append(api_name)
            if api_name == "trade_cal":
                return self._result(error="trade calendar unavailable")
            raise AssertionError("unverified date must not be queried")
        response = KaipanlaBiddingService(repository=self.repo, market_query=market_query).query_history({"trade_date": "20260719"})
        self.assertIn("无法确认最近交易日", response.error)
        self.assertNotIn("stk_auction_o", calls)
        self.assertIsNone(response.meta["actual_trade_date"])


if __name__ == "__main__":
    unittest.main()
