# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from services.admin_api_test_batch_service import AdminApiTestBatchService
from services.admin_api_test_cleanup_service import AdminApiTestCleanupService
from services.admin_api_test_repository import AdminApiTestRepository, create_admin_api_test_tables
from services.admin_api_test_storage import AdminApiTestStorage
from services.market_interface_spec_service import MarketInterfaceSpecService


class FakeRunner:
    def __init__(self, repo):
        self.repo = repo
    def run_item(self, item_id):
        item = self.repo.get_item(item_id)
        self.repo.update_item(item_id, status="success_data", row_count=1, finished_at="2026-07-24 12:00:00")
        self.repo.recalculate_batch_counts(item["batch_id"])
        return self.repo.get_item(item_id)


class AdminMarketTestRouteTests(unittest.TestCase):
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
        self.storage = AdminApiTestStorage(Path(self.tempdir.name) / "results", max_result_bytes=1_000_000)
        self.cleanup = AdminApiTestCleanupService(self.repo, self.storage, critical_percent=99)
        self.batch = AdminApiTestBatchService(self.repo, self.specs, self.storage, FakeRunner(self.repo), max_workers=1)

        import routes.admin_market_test_routes as routes
        self.routes = routes
        self._old_verify_admin_confirmation = routes.verify_admin_confirmation
        routes.verify_admin_confirmation = lambda password: str(password or "") == str(__import__("config").ADMIN_PASSWORD or "")
        routes._spec_service_override = self.specs
        routes._batch_service_override = self.batch
        routes._cleanup_service_override = self.cleanup
        routes._storage_override = self.storage
        routes._repository_override = self.repo
        self.app = Flask(__name__, template_folder=str(Path.cwd() / "templates"))
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(routes.admin_market_test_bp, url_prefix="/admin")
        self.client = self.app.test_client()

    def tearDown(self):
        self.routes.verify_admin_confirmation = self._old_verify_admin_confirmation
        for name in ("_spec_service_override", "_batch_service_override", "_cleanup_service_override", "_storage_override", "_repository_override"):
            setattr(self.routes, name, None)
        self.conn.close()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_logged_in"] = True
            session["admin_csrf_token"] = "csrf"

    def test_auth_page_catalog_and_spec(self):
        response = self.client.get("/admin/interface-tester/catalog.json")
        self.assertEqual(response.status_code, 302)
        self.login()
        page = self.client.get("/admin/interface-tester")
        self.assertEqual(page.status_code, 200)
        self.assertIn("市场接口测试台", page.get_data(as_text=True))
        catalog = self.client.get("/admin/interface-tester/catalog.json").get_json()
        self.assertEqual(catalog["count"], 140)
        spec = self.client.get("/admin/interface-tester/spec/tushare/daily.json").get_json()["data"]
        self.assertTrue(spec["input_params"])
        self.assertTrue(spec["output_fields"])


    def test_interface_tester_page_uses_category_filter_and_read_only_outputs(self):
        self.login()
        html = self.client.get("/admin/interface-tester").get_data(as_text=True)
        self.assertIn('id="categoryFilter"', html)
        self.assertIn('id="outputFieldsTable"', html)
        self.assertNotIn('id="fieldsAll"', html)
        self.assertNotIn('class="out-field"', html)
        self.assertNotIn('fields: fields', html)
        self.assertIn('function itemArtifactLinks(item)', html)
        self.assertIn('本次执行未生成可下载文件', html)
        self.assertIn('错误详情', html)

    def test_catalog_supports_business_category_filter_and_counts(self):
        self.login()
        response = self.client.get(
            "/admin/interface-tester/catalog.json?provider=tushare&category=ETF%E4%B8%93%E9%A2%98&q=etf"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertTrue(payload["items"])
        self.assertTrue(all(row["provider"] == "tushare" for row in payload["items"]))
        self.assertTrue(all(row["category"] == "ETF专题" for row in payload["items"]))
        categories = payload["categories"]
        self.assertTrue(any(row["name"] == "ETF专题" and row["count"] > 0 for row in categories))
        orders = [row["sort_order"] for row in categories]
        self.assertEqual(orders, sorted(orders))
        providers = {row["name"]: row["count"] for row in payload["providers"]}
        self.assertEqual(providers["tushare"], 138)
        self.assertEqual(providers["kaipanla"], 2)



    def test_admin_can_read_and_update_default_retention_days(self):
        self.login()
        initial = self.client.get("/admin/interface-tester/settings.json")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["data"]["default_retention_days"], 30)

        updated = self.client.post(
            "/admin/interface-tester/settings/retention", json={"days": 55}
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["data"]["default_retention_days"], 55)
        self.assertEqual(self.repo.get_default_retention_days(30), 55)

        page = self.client.get("/admin/interface-tester").get_data(as_text=True)
        self.assertIn('value="55"', page)

        invalid = self.client.post(
            "/admin/interface-tester/settings/retention", json={"days": 0}
        )
        self.assertEqual(invalid.status_code, 400)

    def test_single_run_rejects_client_output_field_selection(self):
        self.login()
        response = self.client.post("/admin/interface-tester/run", json={
            "provider": "tushare", "api_name": "daily", "mode": "upstream",
            "params": {"trade_date": "20260724"},
            "fields": ["ts_code"],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("输出字段", response.get_json()["message"])

    def test_single_run_batch_controls_and_result_paging(self):
        self.login()
        single = self.client.post("/admin/interface-tester/run", json={
            "provider": "tushare", "api_name": "daily", "mode": "upstream",
            "params": {"trade_date": "20260724"},
        }).get_json()
        self.assertTrue(single["success"])
        item_id = single["data"]["item"]["id"]
        batch_id = single["data"]["batch"]["id"]
        detail = self.client.get(f"/admin/interface-tester/batches/{batch_id}.json").get_json()
        self.assertEqual(detail["data"]["batch"]["status"], "completed")
        rows = self.client.get(f"/admin/interface-tester/items/{item_id}/rows.json?page=1&page_size=10")
        # Fake runner does not create a result file; route reports a useful conflict rather than crashing.
        self.assertEqual(rows.status_code, 409)

        created = self.client.post("/admin/interface-tester/batches", json={
            "interfaces": [{"provider": "tushare", "api_name": "daily"}],
            "mode": "upstream", "start": False,
        }).get_json()["data"]
        cancelled = self.client.post(f"/admin/interface-tester/batches/{created['id']}/cancel", json={}).get_json()
        self.assertTrue(cancelled["success"])

    def test_download_without_generated_file_returns_conflict_with_execution_error(self):
        self.login()
        batch = self.batch.create_batch(
            interfaces=[("tushare", "etf_basic")], requested_by="admin", enqueue=False
        )
        item = self.repo.list_items(batch["id"])[0]
        self.repo.update_item(
            item["id"], status="storage_error", http_status=500,
            error_code="storage_error",
            error_message="OSError: [Errno 22] Invalid argument",
            finished_at="2026-07-25 12:00:00",
        )

        response = self.client.get(
            f"/admin/interface-tester/items/{item['id']}/download/json"
        )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertIn("未生成", payload["message"])
        self.assertEqual(payload["data"]["status"], "storage_error")
        self.assertIn("Invalid argument", payload["data"]["error_message"])

    def test_recorded_but_deleted_file_returns_gone(self):
        self.login()
        batch = self.batch.create_batch(
            interfaces=[("tushare", "etf_basic")], requested_by="admin", enqueue=False
        )
        item = self.repo.list_items(batch["id"])[0]
        missing = self.storage.root / "missing.json.gz"
        self.repo.update_item(
            item["id"], status="success_data", result_file_path=str(missing),
            finished_at="2026-07-25 12:00:00",
        )

        response = self.client.get(
            f"/admin/interface-tester/items/{item['id']}/download/json"
        )

        self.assertEqual(response.status_code, 410)
        self.assertIn("已不存在", response.get_json()["message"])

    def test_admin_can_save_current_and_candidate_batch_presets(self):
        self.login()
        saved = self.client.post(
            "/admin/interface-tester/spec/tushare/daily/preset",
            json={"name": "后台默认", "params": {"trade_date": "20260724"}},
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            self.specs.default_test_params("tushare", "daily"),
            {"trade_date": "20260724"},
        )

        candidate = "candidate-preset-route"
        directory = self.specs.candidates_dir / candidate
        directory.mkdir(parents=True)
        changed = dict(self.specs.get_effective_spec("tushare", "daily"))
        changed["official_verified"] = True
        changed["parse_warnings"] = []
        changed["publish_eligible"] = True
        (directory / "effective_specs.json").write_text(
            json.dumps([changed], ensure_ascii=False), encoding="utf-8"
        )
        (directory / "diffs.json").write_text("[]", encoding="utf-8")
        (directory / "manifest.json").write_text(
            json.dumps({"version": candidate}), encoding="utf-8"
        )
        updated = self.client.post(
            f"/admin/interface-tester/spec-candidates/{candidate}/tushare/daily/preset",
            json={"name": "候选默认", "params": {"ts_code": "000001.SZ"}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            updated.get_json()["data"]["presets"][0]["params"],
            {"ts_code": "000001.SZ"},
        )

    def test_admin_can_update_candidate_normalization_rules(self):
        self.login()
        candidate = "candidate-overrides-route"
        directory = self.specs.candidates_dir / candidate
        directory.mkdir(parents=True)
        changed = dict(self.specs.get_effective_spec("tushare", "daily"))
        changed["input_params"] = [dict(row) for row in changed["input_params"]]
        changed["output_fields"] = [dict(row) for row in changed["output_fields"]]
        changed["official_verified"] = True
        changed["parse_warnings"] = []
        changed["blocking_change"] = False
        changed["presets"] = [{"name": "valid", "params": {"trade_date": "20260724"}}]
        (directory / "effective_specs.json").write_text(
            json.dumps([changed], ensure_ascii=False), encoding="utf-8"
        )
        (directory / "diffs.json").write_text("[]", encoding="utf-8")
        (directory / "manifest.json").write_text(
            json.dumps({"version": candidate}), encoding="utf-8"
        )
        response = self.client.post(
            f"/admin/interface-tester/spec-candidates/{candidate}/tushare/daily/overrides",
            json={
                "input_overrides": {"ts_code": {"multiple": False}},
                "output_overrides": {"amount": {"unit": "千元"}},
                "validation_rules": [{
                    "type": "at_least_one",
                    "fields": ["ts_code", "trade_date", "start_date", "end_date"],
                    "message": "至少填写一个查询条件",
                }],
            },
        )
        self.assertEqual(response.status_code, 200)
        spec = response.get_json()["data"]
        self.assertEqual(spec["validation_rules"][0]["type"], "at_least_one")
        self.assertEqual(
            next(row for row in spec["output_fields"] if row["name"] == "amount")["unit"],
            "千元",
        )

    def test_failed_publish_audit_redacts_admin_password(self):
        self.login()
        import config
        captured = []
        old_password = config.ADMIN_PASSWORD
        old_record = self.routes.record_operation
        config.ADMIN_PASSWORD = "audit-secret-password"
        self.routes.record_operation = lambda **kwargs: captured.append(kwargs)
        try:
            response = self.client.post(
                "/admin/interface-tester/spec-candidates/publish",
                json={
                    "candidate_version": "missing-candidate",
                    "selected": [{"provider": "tushare", "api_name": "daily"}],
                    "password": "audit-secret-password",
                    "note": "must redact",
                },
            )
        finally:
            self.routes.record_operation = old_record
            config.ADMIN_PASSWORD = old_password
        self.assertEqual(response.status_code, 400)
        self.assertTrue(captured)
        serialized = json.dumps(captured, ensure_ascii=False)
        self.assertNotIn("audit-secret-password", serialized)
        self.assertIn("***REDACTED***", serialized)

    def test_lock_retention_and_candidate_subset_publish(self):
        self.login()
        batch = self.batch.create_batch(interfaces=[("tushare", "daily")], requested_by="admin")
        self.batch.run_batch_now(batch["id"])
        locked = self.client.post(f"/admin/interface-tester/batches/{batch['id']}/lock", json={"reason": "baseline"}).get_json()
        self.assertTrue(locked["data"]["is_locked"])
        self.client.post(f"/admin/interface-tester/batches/{batch['id']}/unlock", json={})
        retained = self.client.post(f"/admin/interface-tester/batches/{batch['id']}/retention", json={"days": 60}).get_json()
        self.assertEqual(retained["data"]["retention_days"], 60)

        current = self.specs.get_effective_spec("tushare", "daily")
        candidate = "candidate-route"
        directory = self.specs.candidates_dir / candidate
        directory.mkdir(parents=True)
        changed = dict(current)
        changed["title"] = "候选日线"
        changed["official_verified"] = True
        changed["parse_warnings"] = []
        changed["publish_eligible"] = True
        (directory / "effective_specs.json").write_text(json.dumps([changed], ensure_ascii=False), encoding="utf-8")
        (directory / "diffs.json").write_text("[]", encoding="utf-8")
        (directory / "manifest.json").write_text(json.dumps({"version": candidate}), encoding="utf-8")
        import config
        old_password = config.ADMIN_PASSWORD
        config.ADMIN_PASSWORD = "pass123456789"
        try:
            published = self.client.post("/admin/interface-tester/spec-candidates/publish", json={
                "candidate_version": candidate,
                "selected": [{"provider": "tushare", "api_name": "daily"}],
                "note": "route test", "password": "pass123456789", "immediate_validation": False,
            })
        finally:
            config.ADMIN_PASSWORD = old_password
        self.assertEqual(published.status_code, 200)
        self.assertEqual(self.specs.get_effective_spec("tushare", "daily")["title"], "候选日线")


if __name__ == "__main__":
    unittest.main()
