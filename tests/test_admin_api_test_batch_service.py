# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from services.admin_api_test_repository import AdminApiTestRepository, create_admin_api_test_tables
from services.admin_api_test_storage import AdminApiTestStorage
from services.admin_api_test_batch_service import AdminApiTestBatchService
from services.market_interface_spec_service import MarketInterfaceSpecService


class FakeRunner:
    def __init__(self, repo, fail_names=(), cancel_after_first=None):
        self.repo = repo
        self.fail_names = set(fail_names)
        self.calls = []
        self.cancel_after_first = cancel_after_first

    def run_item(self, item_id):
        item = self.repo.get_item(item_id)
        self.calls.append(item["api_name"])
        status = "upstream_error" if item["api_name"] in self.fail_names else "success_data"
        self.repo.update_item(item_id, status=status, row_count=1, finished_at="2026-07-24 12:00:00")
        self.repo.recalculate_batch_counts(item["batch_id"])
        if self.cancel_after_first and len(self.calls) == 1:
            self.repo.request_cancel(item["batch_id"])
        return self.repo.get_item(item_id)


class AdminApiTestBatchServiceTests(unittest.TestCase):
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
        # Batch baselines require officially confirmed Tushare specs. Mark the
        # isolated test release as reviewed so these tests exercise execution,
        # cancellation, and retry rather than the specification gate.
        import json
        rows = self.specs._load_specs()
        for row in rows:
            if row.get("provider") == "tushare":
                row["official_verified"] = True
        version = "official-test"
        release_dir = self.specs.releases_dir / version
        release_dir.mkdir(parents=True)
        (release_dir / "effective_specs.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        (release_dir / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs.current_file.write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs._cache_version = ""
        self.storage = AdminApiTestStorage(Path(self.tempdir.name) / "results", max_result_bytes=1_000_000)

    def tearDown(self):
        self.conn.close()

    @staticmethod
    def selection(*names):
        return [{"provider": "tushare", "api_name": name} for name in names]

    def service(self, runner):
        return AdminApiTestBatchService(
            repository=self.repo, spec_service=self.specs, storage=self.storage,
            test_service=runner, max_workers=1, retention_days=30,
        )

    def test_external_worker_mode_leaves_enqueued_batch_persisted_without_starting_thread(self):
        runner = FakeRunner(self.repo)
        service = AdminApiTestBatchService(
            repository=self.repo, spec_service=self.specs, storage=self.storage,
            test_service=runner, max_workers=1, retention_days=30,
            auto_start_worker=False,
        )
        batch = service.create_batch(
            interfaces=self.selection("daily"), requested_by="admin", enqueue=True
        )
        persisted = self.repo.get_batch(batch["id"])
        self.assertEqual(persisted["status"], "queued")
        self.assertIsNone(service._thread)
        events = self.repo.list_events(batch["id"])
        self.assertIn("queued_for_external_worker", [row["event_type"] for row in events])

    def test_external_worker_polls_batches_created_after_worker_start(self):
        import time
        db_path = Path(self.tempdir.name) / "thread-worker.db"
        setup = sqlite3.connect(db_path)
        create_admin_api_test_tables(setup.cursor())
        setup.commit()
        setup.close()

        opened_connections = []

        def connection_factory():
            connection = sqlite3.connect(db_path, check_same_thread=False, timeout=5)
            connection.row_factory = sqlite3.Row
            opened_connections.append(connection)
            return connection

        thread_repo = AdminApiTestRepository(connection_factory=connection_factory)
        runner = FakeRunner(thread_repo)
        service = AdminApiTestBatchService(
            repository=thread_repo, spec_service=self.specs, storage=self.storage,
            test_service=runner, max_workers=1, retention_days=30,
            auto_start_worker=False, persisted_poll_seconds=0.05,
        )
        service.start_worker()
        try:
            batch = service.create_batch(
                interfaces=self.selection("daily"), requested_by="admin", enqueue=True
            )
            deadline = time.time() + 2
            while time.time() < deadline:
                current = thread_repo.get_batch(batch["id"])
                if current and current["status"] == "completed":
                    break
                time.sleep(0.02)
            self.assertEqual(thread_repo.get_batch(batch["id"])["status"], "completed")
            self.assertEqual(runner.calls, ["daily"])
        finally:
            service.stop_worker()
            for connection in opened_connections:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass

    def test_sensitive_parameters_are_rejected_before_persistence(self):
        runner = FakeRunner(self.repo)
        service = self.service(runner)
        with self.assertRaisesRegex(ValueError, "禁止提交敏感参数"):
            service.create_batch(
                interfaces=[{
                    "provider": "tushare",
                    "api_name": "daily",
                    "params": {"trade_date": "20260724", "token": "must-not-persist"},
                }],
                requested_by="admin",
            )
        self.assertEqual(self.repo.list_batches(), [])


    def test_batch_always_persists_complete_official_output_field_list(self):
        runner = FakeRunner(self.repo)
        service = self.service(runner)
        batch = service.create_batch(
            interfaces=[{
                "provider": "tushare", "api_name": "daily",
                "params": {"trade_date": "20260724"},
                "fields": ["ts_code"],
            }],
            requested_by="admin",
        )
        item = self.repo.list_items(batch["id"])[0]
        self.assertEqual(
            item["fields"],
            self.specs.all_output_field_names("tushare", "daily"),
        )


    def test_new_batch_uses_latest_persisted_default_retention(self):
        self.repo.set_default_retention_days(75, updated_by="admin")
        runner = FakeRunner(self.repo)
        service = self.service(runner)
        batch = service.create_batch(
            interfaces=self.selection("daily"), requested_by="admin"
        )
        self.assertEqual(batch["retention_days"], 75)

    def test_batch_runs_to_completed_and_writes_manifest(self):
        runner = FakeRunner(self.repo)
        service = self.service(runner)
        batch = service.create_batch(interfaces=self.selection("daily", "stock_basic"), requested_by="admin")
        completed = service.run_batch_now(batch["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["success_count"], 2)
        self.assertEqual(runner.calls, ["daily", "stock_basic"])
        self.assertTrue((Path(completed["result_dir"]) / "manifest.json").exists())
        self.assertIsNotNone(completed["expires_at"])

    def test_safe_cancel_keeps_completed_and_marks_remaining_cancelled(self):
        runner = FakeRunner(self.repo, cancel_after_first=True)
        service = self.service(runner)
        batch = service.create_batch(interfaces=self.selection("daily", "stock_basic", "income"), requested_by="admin")
        completed = service.run_batch_now(batch["id"])
        statuses = [row["status"] for row in self.repo.list_items(batch["id"])]
        self.assertEqual(completed["status"], "cancelled")
        self.assertEqual(statuses[0], "success_data")
        self.assertEqual(statuses[1:], ["cancelled", "cancelled"])

    def test_retry_failed_creates_child_with_only_failed_interfaces(self):
        runner = FakeRunner(self.repo, fail_names={"income"})
        service = self.service(runner)
        batch = service.create_batch(interfaces=self.selection("daily", "income"), requested_by="admin")
        service.run_batch_now(batch["id"])
        child = service.retry_failed(batch["id"], requested_by="admin", enqueue=False)
        child_items = self.repo.list_items(child["id"])
        self.assertEqual(child["parent_batch_id"], batch["id"])
        self.assertEqual([row["api_name"] for row in child_items], ["income"])

    def test_blocking_spec_is_skipped_and_selected_validation_is_supported(self):
        current = self.specs.get_effective_spec("tushare", "daily")
        release = self.specs._load_specs()
        for row in release:
            if row["provider"] == "tushare" and row["api_name"] == "daily":
                row["blocking_change"] = True
                row["change_status"] = "pending_confirmation"
        # Test-only release replacement through internal atomic helper path.
        version = "blocking-test"
        release_dir = self.specs.releases_dir / version
        release_dir.mkdir(parents=True)
        import json
        (release_dir / "effective_specs.json").write_text(json.dumps(release, ensure_ascii=False), encoding="utf-8")
        (release_dir / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs.current_file.write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs._cache_version = ""
        runner = FakeRunner(self.repo)
        service = self.service(runner)
        batch = service.create_validation_batch([("tushare", "daily"), ("tushare", "stock_basic")], release_id="R1", requested_by="admin", enqueue=False)
        service.run_batch_now(batch["id"])
        statuses = {row["api_name"]: row["status"] for row in self.repo.list_items(batch["id"])}
        self.assertEqual(statuses["daily"], "spec_change_pending")
        self.assertEqual(statuses["stock_basic"], "success_data")
        self.assertEqual(runner.calls, ["stock_basic"])


if __name__ == "__main__":
    unittest.main()
