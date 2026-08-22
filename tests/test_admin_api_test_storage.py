# -*- coding: utf-8 -*-
from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.admin_api_test_storage import AdminApiTestStorage, ResultTooLargeError


class AdminApiTestStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name) / "results"
        self.storage = AdminApiTestStorage(self.root, max_result_bytes=2_000_000)

    def test_full_result_round_trip_paging_csv_and_checksum(self):
        rows = [{"ts_code": f"{index:06d}.SZ", "close": index + 0.5} for index in range(250)]
        result = self.storage.store_result(
            batch_id="BATCH-1", item_id=1, provider="tushare", api_name="daily",
            request_payload={"params": {"trade_date": "20260724"}},
            response_payload={"success": True, "count": 250, "data": rows},
            schema_report={"status": "matched"},
        )
        self.assertEqual(result["row_count"], 250)
        self.assertTrue(Path(result["result_file_path"]).exists())
        self.assertEqual(len(result["result_sha256"]), 64)
        page = self.storage.read_rows(result["result_file_path"], page=2, page_size=100)
        self.assertEqual(page["total"], 250)
        self.assertEqual(page["rows"][0]["ts_code"], "000100.SZ")
        self.assertTrue(Path(result["csv_file_path"]).exists())
        with gzip.open(result["result_file_path"], "rt", encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["data"][-1]["ts_code"], "000249.SZ")

    def test_gzip_fsync_uses_writable_handle_for_windows_compatibility(self):
        real_open = open
        open_modes = {}

        def tracked_open(file, mode="r", *args, **kwargs):
            handle = real_open(file, mode, *args, **kwargs)
            open_modes[handle.fileno()] = mode
            return handle

        def windows_compatible_fsync(fd):
            mode = open_modes.get(fd, "")
            if mode and "w" not in mode and "a" not in mode and "+" not in mode:
                raise OSError(22, "Invalid argument")

        with patch("services.admin_api_test_storage.open", side_effect=tracked_open), patch(
            "services.admin_api_test_storage.os.fsync", side_effect=windows_compatible_fsync
        ):
            stored = self.storage.store_result(
                batch_id="WINDOWS", item_id=1, provider="tushare", api_name="etf_basic",
                request_payload={"params": {"list_status": "L"}},
                response_payload={"success": False, "data": [], "msg": "upstream error"},
                schema_report={"expected_fields": ["ts_code", "csname"]},
            )

        self.assertTrue(Path(stored["result_file_path"]).is_file())

    def test_empty_result_writes_header_only_csv_instead_of_dot_path(self):
        stored = self.storage.store_result(
            batch_id="EMPTY", item_id=1, provider="tushare", api_name="etf_basic",
            request_payload={},
            response_payload={"success": False, "data": [], "msg": "no data"},
            schema_report={"expected_fields": ["ts_code", "csname"]},
        )

        self.assertNotEqual(stored["csv_file_path"], ".")
        self.assertEqual(stored["column_count"], 2)
        self.assertTrue(Path(stored["csv_file_path"]).is_file())
        with gzip.open(stored["csv_file_path"], "rt", encoding="utf-8-sig") as handle:
            self.assertEqual(handle.read().strip(), "ts_code,csname")

    def test_size_limit_never_silently_truncates(self):
        small = AdminApiTestStorage(self.root, max_result_bytes=100)
        with self.assertRaises(ResultTooLargeError):
            small.store_result(
                batch_id="B", item_id=1, provider="tushare", api_name="daily",
                request_payload={}, response_payload={"data": [{"x": "a" * 500}]}, schema_report={},
            )

    def test_batch_zip_and_safe_delete(self):
        stored = self.storage.store_result(
            batch_id="BATCH-2", item_id=1, provider="tushare", api_name="daily",
            request_payload={}, response_payload={"data": [{"x": 1}]}, schema_report={},
        )
        manifest = self.storage.write_batch_manifest("BATCH-2", {"status": "completed", "items": [stored]})
        archive = self.storage.build_batch_zip("BATCH-2")
        self.assertTrue(Path(manifest).exists())
        self.assertTrue(Path(archive).exists())
        with self.assertRaises(ValueError):
            self.storage.safe_resolve("../../etc/passwd")
        self.storage.delete_batch("BATCH-2")
        self.assertFalse(Path(stored["result_dir"]).parents[2].exists())


if __name__ == "__main__":
    unittest.main()
