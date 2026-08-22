# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import db_utils


class ApiDocPathMigrationTests(unittest.TestCase):
    def test_existing_document_paths_are_migrated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = str(Path(temp_dir) / "test.db")
            with patch.object(db_utils, "DB_FILE", db_file):
                old_local = db_utils._local
                old_pragmas = db_utils._db_pragmas_initialized
                try:
                    db_utils._local = threading.local()
                    db_utils._db_pragmas_initialized = False
                    conn = db_utils.get_conn()
                    db_utils.init_api_doc_tables(conn.cursor())
                    conn.commit()
                    now = "2026-07-11 00:00:00"
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO api_doc_categories
                        (name, description, sort_order, status, created_at, updated_at)
                        VALUES ('test', '', 1, 'active', ?, ?)
                        """,
                        (now, now),
                    )
                    category_id = cur.lastrowid
                    removed_prefix = "/api/v1/" + "tushare/"
                    cur.execute(
                        """
                        INSERT INTO api_doc_endpoints
                        (category_id, title, method, path, request_example, status, created_at, updated_at)
                        VALUES (?, 'daily', 'GET', ?, ?, 'active', ?, ?)
                        """,
                        (
                            category_id,
                            removed_prefix + "daily",
                            "GET " + removed_prefix + "daily",
                            now,
                            now,
                        ),
                    )
                    conn.commit()

                    db_utils._migrate_api_doc_paths_to_unified_market_route()
                    row = conn.execute(
                        "SELECT path, request_example FROM api_doc_endpoints WHERE title='daily'"
                    ).fetchone()
                    self.assertEqual(row["path"], "/api/v1/market/tushare/daily")
                    self.assertEqual(row["request_example"], "GET /api/v1/market/tushare/daily")
                    conn.close()
                finally:
                    db_utils._local = old_local
                    db_utils._db_pragmas_initialized = old_pragmas


if __name__ == "__main__":
    unittest.main()
