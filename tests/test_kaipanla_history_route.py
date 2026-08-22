# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
from flask import Flask

from routes.market_data_routes import _query_response
from services.market_data_service import MarketDataResult


class KaipanlaHistoryRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_snapshot_response_exposes_batch_identity_and_quality(self):
        snapshot_id = "20260717_092605_auction_abcd"
        result = MarketDataResult(
            provider="kaipanla",
            data_type="morning_bidding_history",
            data=pd.DataFrame([{
                "ts_code": "000001.SZ",
                "snapshot_id": snapshot_id,
                "source_provider": "kaipanla",
                "data_quality": "complete",
            }]),
            meta={
                "source_provider": "kaipanla_snapshot",
                "requested_trade_date": "20260719",
                "actual_trade_date": "20260717",
                "fallback_used": True,
                "data_freshness": "latest_snapshot",
                "snapshot_id": snapshot_id,
                "snapshot_time": "2026-07-17 09:26:05",
                "snapshot_type": "auction",
                "payload_hash": "f" * 64,
                "data_quality": "complete",
            },
        )
        with self.app.test_request_context("/?trade_date=20260719"):
            with patch("routes.market_data_routes.query_market_data", return_value=result):
                response = _query_response("kaipanla", "morning_bidding/history")

        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["snapshot"]["snapshot_id"], snapshot_id)
        self.assertEqual(payload["snapshot"]["snapshot_type"], "auction")
        self.assertEqual(payload["source"]["snapshot_type"], "auction")
        self.assertEqual(payload["data"][0]["snapshot_id"], snapshot_id)
        self.assertEqual(payload["quality"]["data_quality"], "complete")
        self.assertIn("开盘啦历史快照", payload["msg"])

    def test_tushare_fallback_message_explicitly_says_fields_are_partial(self):
        result = MarketDataResult(
            provider="kaipanla",
            data_type="morning_bidding_history",
            data=pd.DataFrame([{"ts_code": "000001.SZ", "data_quality": "partial"}]),
            meta={
                "source_provider": "tushare",
                "requested_trade_date": "20260717",
                "actual_trade_date": "20260717",
                "fallback_used": True,
                "fallback_reason": "kaipanla_snapshot_not_found",
                "data_freshness": "tushare_historical_fallback",
                "data_quality": "partial",
                "warning": "未找到开盘啦历史快照，丰富委买与实时字段无法还原",
            },
        )
        with self.app.test_request_context("/?trade_date=20260717"):
            with patch("routes.market_data_routes.query_market_data", return_value=result):
                response = _query_response("kaipanla", "morning_bidding/history")

        payload = response.get_json()
        self.assertEqual(payload["quality"]["data_quality"], "partial")
        self.assertIn("Tushare", payload["msg"])
        self.assertIn("无法还原", payload["msg"])

    def test_invalid_query_parameters_return_http_400(self):
        with self.app.test_request_context("/?trade_date=2026-07-17"):
            with patch(
                "routes.market_data_routes.query_market_data",
                side_effect=ValueError("trade_date 必须为 YYYYMMDD"),
            ):
                response, status = _query_response("kaipanla", "morning_bidding/history")

        payload = response.get_json()
        self.assertEqual(status, 400)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], 400)
        self.assertIn("YYYYMMDD", payload["msg"])



if __name__ == "__main__":
    unittest.main()
