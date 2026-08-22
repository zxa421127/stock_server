# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from services.admin_api_test_repository import AdminApiTestRepository, create_admin_api_test_tables
from services.admin_api_test_storage import AdminApiTestStorage
from services.admin_market_test_service import AdminMarketTestService
from services.market_data_service import MarketDataResult
from services.market_interface_spec_service import MarketInterfaceSpecService


class AdminMarketTestServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.conn = sqlite3.connect(Path(self.tempdir.name) / "test.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        create_admin_api_test_tables(self.conn.cursor())
        self.conn.commit()
        self.repo = AdminApiTestRepository(connection_factory=lambda: self.conn)
        self.specs = MarketInterfaceSpecService(Path(self.tempdir.name) / "specs")
        self.specs.ensure_seed_release()
        self.storage = AdminApiTestStorage(Path(self.tempdir.name) / "results", max_result_bytes=10_000_000)
        self.repo.create_batch(batch_id="BATCH", kind="single", requested_by="admin", spec_version=self.specs.current_version(), total_count=1, retention_days=30)

    def tearDown(self):
        self.conn.close()

    def _item(self, api="daily", params=None, fields=None):
        spec = self.specs.get_effective_spec("tushare", api)
        return self.repo.create_item(
            batch_id="BATCH", provider="tushare", api_name=api, title=spec["title"],
            category=spec["category"], mode="upstream", params=params or {}, fields=fields or [],
            spec_version=self.specs.current_version(), spec_hash=spec["spec_hash"],
        )

    def test_success_ignores_stored_subset_and_requests_all_official_fields(self):
        captured = {}
        def query(provider, api, params, bypass_cache=False):
            captured.update({"provider": provider, "api": api, "params": params, "bypass": bypass_cache})
            full_row = {name: None for name in self.specs.all_output_field_names("tushare", "daily")}
            full_row.update({"ts_code": "000001.SZ", "trade_date": "20260724", "open": 10.0, "close": 10.5})
            return MarketDataResult(
                provider="tushare", data_type="daily",
                data=pd.DataFrame([full_row]),
                cache_hit=False, meta={"actual_trade_date": "20260724", "fallback_used": False},
            )
        item = self._item(params={"trade_date": "20260724"}, fields=["ts_code", "trade_date", "open", "close"])
        service = AdminMarketTestService(self.repo, self.specs, self.storage, query_func=query)
        result = service.run_item(item["id"])
        self.assertEqual(result["status"], "success_data")
        self.assertTrue(captured["bypass"])
        self.assertEqual(
            captured["params"]["fields"],
            ",".join(self.specs.all_output_field_names("tushare", "daily")),
        )
        stored = self.storage.read_response(result["result_file_path"])
        self.assertEqual(stored["count"], 1)
        self.assertEqual(stored["data"][0]["close"], 10.5)

    def test_invalid_parameter_is_classified_without_calling_provider(self):
        calls = []
        item = self._item(params={"not_defined": "x"})
        service = AdminMarketTestService(self.repo, self.specs, self.storage, query_func=lambda *a, **k: calls.append(a))
        result = service.run_item(item["id"])
        self.assertEqual(result["status"], "invalid_params")
        self.assertEqual(calls, [])
        self.assertIn("未定义参数", result["error_message"])

    def test_storage_failure_is_classified_and_does_not_escape_worker(self):
        class FailingStorage(AdminApiTestStorage):
            def store_result(self, **kwargs):
                raise OSError(22, "Invalid argument")

        item = self._item(api="etf_basic", params={"list_status": "L"})
        service = AdminMarketTestService(
            self.repo, self.specs, FailingStorage(Path(self.tempdir.name) / "bad-results"),
            query_func=lambda *a, **k: MarketDataResult(
                provider="tushare", data_type="etf_basic", error="upstream failure"
            ),
        )

        result = service.run_item(item["id"])

        self.assertEqual(result["status"], "storage_error")
        self.assertEqual(result["http_status"], 500)
        self.assertIn("OSError", result["error_message"])
        self.assertEqual(result["result_file_path"], "")

    def test_unhandled_response_conversion_error_still_writes_diagnostic_files(self):
        class InvalidFrame:
            pass

        item = self._item(api="etf_basic", params={"list_status": "L"})
        service = AdminMarketTestService(
            self.repo, self.specs, self.storage,
            query_func=lambda *a, **k: MarketDataResult(
                provider="tushare", data_type="etf_basic", data=InvalidFrame()
            ),
        )

        result = service.run_item(item["id"])

        self.assertEqual(result["status"], "internal_error")
        self.assertIn("InvalidFrame", result["error_message"])
        self.assertTrue(Path(result["result_file_path"]).is_file())
        self.assertTrue(Path(result["schema_file_path"]).is_file())

    def test_fallback_permission_and_schema_mismatch_classification(self):
        fallback_item = self._item(params={"trade_date": "20260724"}, fields=["ts_code", "trade_date"])
        fallback_row = {name: None for name in self.specs.all_output_field_names("tushare", "daily")}
        fallback_row.update({"ts_code": "000001.SZ", "trade_date": "20260723"})
        fallback_service = AdminMarketTestService(
            self.repo, self.specs, self.storage,
            query_func=lambda *a, **k: MarketDataResult(
                provider="tushare", data_type="daily", data=pd.DataFrame([fallback_row]),
                meta={"fallback_used": True, "actual_trade_date": "20260723"},
            ),
        )
        self.assertEqual(fallback_service.run_item(fallback_item["id"])["status"], "success_fallback")

        permission_item = self.repo.create_item(
            batch_id="BATCH", provider="tushare", api_name="income", title="利润表", category="财务",
            mode="upstream", params={}, fields=[], spec_version=self.specs.current_version(),
            spec_hash=self.specs.get_effective_spec("tushare", "income")["spec_hash"], attempt_no=2,
        )
        permission_service = AdminMarketTestService(
            self.repo, self.specs, self.storage,
            query_func=lambda *a, **k: MarketDataResult(provider="tushare", data_type="income", error="抱歉，您没有接口访问权限"),
        )
        self.assertEqual(permission_service.run_item(permission_item["id"])["status"], "permission_denied")

        mismatch_item = self.repo.create_item(
            batch_id="BATCH", provider="tushare", api_name="daily", title="日线", category="行情",
            mode="upstream", params={"trade_date": "20260724"}, fields=["ts_code", "close"],
            spec_version=self.specs.current_version(), spec_hash="x", attempt_no=3,
        )
        mismatch_service = AdminMarketTestService(
            self.repo, self.specs, self.storage,
            query_func=lambda *a, **k: MarketDataResult(provider="tushare", data_type="daily", data=pd.DataFrame([{"ts_code": "000001.SZ"}]), meta={}),
        )
        self.assertEqual(mismatch_service.run_item(mismatch_item["id"])["status"], "schema_mismatch")


if __name__ == "__main__":
    unittest.main()
