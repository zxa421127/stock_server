# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.admin_api_test_repository import AdminApiTestRepository, create_admin_api_test_tables
import db_utils


class AdminApiTestRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "test.db"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        create_admin_api_test_tables(self.conn.cursor())
        self.conn.commit()
        self.repo = AdminApiTestRepository(connection_factory=lambda: self.conn)

    def tearDown(self):
        db_utils.close_thread_connection()
        self.conn.close()

    def test_batch_item_and_event_round_trip(self):
        batch = self.repo.create_batch(
            batch_id="BATCH-1",
            kind="batch",
            requested_by="admin",
            spec_version="seed-v1",
            total_count=2,
            retention_days=30,
        )
        self.assertEqual(batch["status"], "queued")
        item = self.repo.create_item(
            batch_id="BATCH-1", provider="tushare", api_name="daily",
            title="A股日线行情", category="行情数据", mode="upstream",
            params={"trade_date": "20260724"}, fields=["ts_code", "close"],
            spec_version="seed-v1", spec_hash="abc",
        )
        self.repo.add_event("BATCH-1", "created", {"item_id": item["id"]})
        self.assertEqual(self.repo.get_batch("BATCH-1")["total_count"], 2)
        self.assertEqual(self.repo.list_items("BATCH-1")[0]["params"]["trade_date"], "20260724")
        self.assertEqual(self.repo.list_events("BATCH-1")[0]["event_type"], "created")

    def test_cancel_and_failed_item_selection(self):
        self.repo.create_batch(batch_id="BATCH-2", kind="batch", requested_by="admin", spec_version="v1", total_count=3, retention_days=30)
        for api, status in [("daily", "success_data"), ("income", "upstream_error"), ("moneyflow", "permission_denied")]:
            item = self.repo.create_item(
                batch_id="BATCH-2", provider="tushare", api_name=api,
                title=api, category="x", mode="upstream", params={}, fields=[],
                spec_version="v1", spec_hash=api,
            )
            self.repo.update_item(item["id"], status=status)
        self.repo.request_cancel("BATCH-2")
        self.assertTrue(self.repo.get_batch("BATCH-2")["cancel_requested"])
        failed = self.repo.list_failed_items("BATCH-2")
        self.assertEqual({row["api_name"] for row in failed}, {"income", "moneyflow"})

    def test_lock_and_retention_updates(self):
        self.repo.create_batch(batch_id="BATCH-3", kind="batch", requested_by="admin", spec_version="v1", total_count=0, retention_days=30)
        self.repo.lock_batch("BATCH-3", locked_by="admin", reason="baseline")
        locked = self.repo.get_batch("BATCH-3")
        self.assertTrue(locked["is_locked"])
        self.assertEqual(locked["lock_reason"], "baseline")
        self.repo.unlock_batch("BATCH-3")
        self.repo.set_retention_days("BATCH-3", 90)
        unlocked = self.repo.get_batch("BATCH-3")
        self.assertFalse(unlocked["is_locked"])
        self.assertEqual(unlocked["retention_days"], 90)
        with self.assertRaisesRegex(ValueError, "1到36500"):
            self.repo.set_retention_days("BATCH-3", 0)
        with self.assertRaisesRegex(ValueError, "1到36500"):
            self.repo.set_retention_days("BATCH-3", 36501)

    def test_default_retention_setting_persists_and_validates_range(self):
        self.assertEqual(self.repo.get_default_retention_days(30), 30)
        saved = self.repo.set_default_retention_days(45, updated_by="admin")
        self.assertEqual(saved["days"], 45)
        self.assertEqual(saved["updated_by"], "admin")
        self.assertEqual(self.repo.get_default_retention_days(30), 45)
        with self.assertRaisesRegex(ValueError, "1到36500"):
            self.repo.set_default_retention_days(0, updated_by="admin")
        with self.assertRaisesRegex(ValueError, "1到36500"):
            self.repo.set_default_retention_days(36501, updated_by="admin")



if __name__ == "__main__":
    unittest.main()
