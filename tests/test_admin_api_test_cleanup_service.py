# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.admin_api_test_cleanup_service import AdminApiTestCleanupService
from services.admin_api_test_repository import AdminApiTestRepository, create_admin_api_test_tables
from services.admin_api_test_storage import AdminApiTestStorage


class AdminApiTestCleanupServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.conn = sqlite3.connect(Path(self.tempdir.name) / "test.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        create_admin_api_test_tables(self.conn.cursor())
        self.conn.commit()
        self.repo = AdminApiTestRepository(connection_factory=lambda: self.conn)
        self.storage = AdminApiTestStorage(Path(self.tempdir.name) / "results", max_result_bytes=1_000_000)
        self.service = AdminApiTestCleanupService(self.repo, self.storage, retention_days=30, critical_percent=90)

    def tearDown(self):
        self.conn.close()

    def _batch(self, batch_id, status="completed", expires_at="2026-01-01 00:00:00", locked=False):
        path = self.storage._batch_dir(batch_id, create=True)
        (path / "marker.txt").write_text("x", encoding="utf-8")
        self.repo.create_batch(batch_id=batch_id, kind="batch", requested_by="admin", spec_version="v1", total_count=0, retention_days=30, result_dir=str(path))
        self.repo.update_batch(batch_id, status=status, finished_at="2025-12-01 00:00:00", expires_at=expires_at)
        if locked:
            self.repo.lock_batch(batch_id, locked_by="admin", reason="baseline")
        return path

    def test_cleanup_deletes_only_expired_unlocked_terminal_batches(self):
        expired = self._batch("EXPIRED")
        locked = self._batch("LOCKED", locked=True)
        running = self._batch("RUNNING", status="running")
        result = self.service.cleanup_once(now="2026-07-24 00:00:00")
        self.assertEqual(result["deleted"], ["EXPIRED"])
        self.assertFalse(expired.exists())
        self.assertIsNone(self.repo.get_batch("EXPIRED"))
        self.assertTrue(locked.exists())
        self.assertTrue(running.exists())

    def test_delete_failure_is_recorded_and_metadata_is_kept(self):
        self._batch("FAIL")
        class BrokenStorage:
            def delete_batch(self, batch_id):
                raise OSError("disk busy")
            def disk_status(self):
                return {"used_percent": 10}
        service = AdminApiTestCleanupService(self.repo, BrokenStorage(), retention_days=30, critical_percent=90)
        result = service.cleanup_once(now="2026-07-24 00:00:00")
        self.assertEqual(result["failed"], ["FAIL"])
        self.assertEqual(self.repo.get_batch("FAIL")["cleanup_status"], "delete_failed")

    def test_disk_guard_blocks_at_critical_threshold(self):
        class FullStorage:
            def disk_status(self):
                return {"used_percent": 92.5, "free_bytes": 1}
        service = AdminApiTestCleanupService(self.repo, FullStorage(), critical_percent=90)
        with self.assertRaisesRegex(RuntimeError, "磁盘使用率"):
            service.assert_can_start_batch()

    def test_manual_delete_rejects_locked_batch(self):
        self._batch("LOCKED2", locked=True)
        with self.assertRaisesRegex(ValueError, "永久保留"):
            self.service.delete_batch("LOCKED2")


if __name__ == "__main__":
    unittest.main()
