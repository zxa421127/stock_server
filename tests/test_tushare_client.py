# -*- coding: utf-8 -*-
"""Tests for official SDK mode and explicit relay URL behavior."""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch

import pandas as pd


class FakePro:
    def __init__(self):
        self.calls = []

    def query(self, api_name, fields="", **params):
        self.calls.append((api_name, fields, params))
        return pd.DataFrame([{"ok": 1}])


class TushareClientTests(unittest.TestCase):
    def setUp(self):
        self.fake_pro = FakePro()
        self.pro_api_calls = []

        tushare = types.ModuleType("tushare")
        tushare.set_token = lambda token: None

        def pro_api(token, timeout=30):
            self.pro_api_calls.append((token, timeout))
            return self.fake_pro

        tushare.pro_api = pro_api
        tushare.pro_bar = lambda api=None, **params: pd.DataFrame([{"bar": 1}])

        pro_module = types.ModuleType("tushare.pro")
        client_module = types.ModuleType("tushare.pro.client")

        class DataApi:
            _DataApi__http_url = "https://sdk-current.example/dataapi"

        self.data_api = DataApi
        client_module.DataApi = DataApi

        self.saved_modules = {
            name: sys.modules.get(name)
            for name in ("tushare", "tushare.pro", "tushare.pro.client", "integrations.market_data.tushare.client")
        }
        sys.modules["tushare"] = tushare
        sys.modules["tushare.pro"] = pro_module
        sys.modules["tushare.pro.client"] = client_module
        sys.modules.pop("integrations.market_data.tushare.client", None)
        self.module = importlib.import_module("integrations.market_data.tushare.client")

    def tearDown(self):
        for name, module in self.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_empty_url_keeps_sdk_current_endpoint(self):
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", ""), \
             patch.object(self.module.config, "TUSHARE_TIMEOUT_SECONDS", 15):
            self.module.TushareClient.reset()
            self.module.TushareClient.get_pro()
            self.assertEqual(self.module.TushareClient.mode(), "sdk_default")

        self.assertEqual(self.data_api._DataApi__http_url, "https://sdk-current.example/dataapi")
        self.assertEqual(self.pro_api_calls, [("abc", 15)])

    def test_explicit_relay_url_and_parameter_cleaning(self):
        relay = "http://47.116.63.181:8000/dataapi"
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 0,
            "data": {"fields": ["ok"], "items": [[1]]},
            "msg": "",
        }
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", relay), \
             patch.object(self.module.config, "TUSHARE_TIMEOUT_SECONDS", 30), \
             patch.object(self.module.requests, "post", return_value=response) as post:
            df, error = self.module.call_tushare_api(
                "trade_cal",
                fields="exchange,cal_date",
                exchange="SSE",
                token="must-not-forward",
                source_code="must-not-forward",
            )

        self.assertIsNone(error)
        self.assertEqual(len(df), 1)
        body = post.call_args.kwargs["json"]
        self.assertEqual(post.call_args.args[0], relay + "/trade_cal")
        self.assertEqual(body["fields"], "exchange,cal_date")
        self.assertEqual(body["params"]["exchange"], "SSE")
        self.assertEqual(body["params"]["ts_type_name"], relay)
        self.assertNotIn("token", body["params"])
        self.assertNotIn("source_code", body["params"])

    def test_relay_http_403_is_not_silently_treated_as_empty(self):
        relay = "http://47.116.63.181:8000/dataapi"
        response = Mock()
        response.status_code = 403
        response.json.return_value = {"detail": "api not allowed"}
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", relay), \
             patch.object(self.module.config, "TUSHARE_TIMEOUT_SECONDS", 30), \
             patch.object(self.module.requests, "post", return_value=response):
            df, error = self.module.call_tushare_api("stk_mins", ts_code="000001.SZ")

        self.assertTrue(df.empty)
        self.assertIn("无接口权限", error)
        self.assertIn("HTTP 403", error)

    def test_old_direct_api_name_maps_to_current_upstream_name(self):
        relay = "http://47.116.63.181:8000/dataapi"
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 0, "data": {"fields": [], "items": []}, "msg": ""}
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", relay), \
             patch.object(self.module.config, "TUSHARE_TIMEOUT_SECONDS", 30), \
             patch.object(self.module.requests, "post", return_value=response) as post:
            self.module.call_tushare_api("global_index")
        self.assertEqual(post.call_args.args[0], relay + "/index_global")

    def test_all_project_legacy_names_map_to_official_upstream_paths(self):
        relay = "http://47.116.63.181:8000/dataapi"
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"code": 0, "data": {"fields": [], "items": []}, "msg": ""}
        migrations = {
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
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", relay), \
             patch.object(self.module.config, "TUSHARE_TIMEOUT_SECONDS", 30), \
             patch.object(self.module.requests, "post", return_value=response) as post:
            for legacy, official in migrations.items():
                with self.subTest(legacy=legacy):
                    self.module.call_tushare_api(legacy)
                    self.assertEqual(post.call_args.args[0], relay + "/" + official)

    def test_invalid_relay_url_is_rejected(self):
        with patch.object(self.module.config, "TUSHARE_TOKEN", "abc"), \
             patch.object(self.module.config, "TUSHARE_API_URL", "not-a-url"):
            self.module.TushareClient.reset()
            with self.assertRaises(RuntimeError):
                self.module.TushareClient.get_pro()


if __name__ == "__main__":
    unittest.main()
