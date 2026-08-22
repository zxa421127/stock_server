# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import sys
from collections import Counter
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import db_utils
from services import api_doc_service
from services.api_doc_catalog import FULL_API_DOCS, FULL_API_DOCS_TOTAL
from tools import sync_full_api_docs as sync_tool


class FullApiDocsTests(unittest.TestCase):
    def _run_with_temp_db(self, callback):
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
                    callback(conn)
                    conn.close()
                finally:
                    db_utils._local = old_local
                    db_utils._db_pragmas_initialized = old_pragmas

    def test_static_catalog_total_is_derived_and_interfaces_are_unique(self):
        self.assertEqual(FULL_API_DOCS_TOTAL, len(FULL_API_DOCS))
        keys = {(item["provider"], item["api_name"]) for item in FULL_API_DOCS}
        self.assertEqual(len(keys), FULL_API_DOCS_TOTAL)
        provider_counts = Counter(item["provider"] for item in FULL_API_DOCS)
        self.assertEqual(sum(provider_counts.values()), FULL_API_DOCS_TOTAL)
        self.assertGreater(provider_counts["tushare"], 0)
        self.assertGreater(provider_counts["kaipanla"], 0)

    def test_sync_installs_generated_documents_and_is_idempotent(self):
        def assertions(conn):
            first = api_doc_service.sync_full_api_docs(force=True)
            self.assertTrue(first["changed"])
            self.assertEqual(first["endpoint_count"], FULL_API_DOCS_TOTAL)

            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints "
                "WHERE path LIKE '/api/v1/market/tushare/%' "
                "OR path LIKE '/api/v1/market/kaipanla/%'"
            ).fetchone()["cnt"]
            self.assertEqual(count, FULL_API_DOCS_TOTAL)

            second = api_doc_service.sync_full_api_docs(force=False)
            self.assertFalse(second["changed"])
            count_after = conn.execute("SELECT COUNT(*) AS cnt FROM api_doc_endpoints").fetchone()["cnt"]
            self.assertEqual(count_after, FULL_API_DOCS_TOTAL)

        self._run_with_temp_db(assertions)

    def test_permission_scope_counts_match_two_tier_catalog(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            points = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints WHERE scope='tushare:points15000:read'"
            ).fetchone()["cnt"]
            independent = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints WHERE scope LIKE 'tushare:independent:%'"
            ).fetchone()["cnt"]
            kaipanla = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints WHERE scope='market:kaipanla:read'"
            ).fetchone()["cnt"]
            expected_scopes = Counter(item["scope"] for item in api_doc_service.FULL_API_DOCS)
            self.assertEqual(points, expected_scopes["tushare:points15000:read"])
            self.assertEqual(
                independent,
                sum(count for scope, count in expected_scopes.items() if scope.startswith("tushare:independent:")),
            )
            self.assertEqual(kaipanla, expected_scopes["market:kaipanla:read"])

        self._run_with_temp_db(assertions)

    def test_custom_unrelated_document_is_preserved(self):
        def assertions(conn):
            now = "2026-07-13 00:00:00"
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('自定义接口','',999,'active',?,?)",
                (now, now),
            )
            category_id = cur.lastrowid
            cur.execute(
                "INSERT INTO api_doc_endpoints "
                "(category_id,title,method,path,scope,status,created_at,updated_at) "
                "VALUES (?,'自定义健康检查','GET','/api/v1/custom/health','custom:read','active',?,?)",
                (category_id, now, now),
            )
            conn.commit()

            api_doc_service.sync_full_api_docs(force=True)
            custom_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints WHERE path='/api/v1/custom/health'"
            ).fetchone()["cnt"]
            self.assertEqual(custom_count, 1)
            total = conn.execute("SELECT COUNT(*) AS cnt FROM api_doc_endpoints").fetchone()["cnt"]
            self.assertEqual(total, FULL_API_DOCS_TOTAL + 1)

        self._run_with_temp_db(assertions)

    def test_sync_check_rejects_same_count_with_stale_fingerprint(self):
        status = {
            "expected_version": "v2",
            "installed_version": "v2",
            "expected_count": 140,
            "installed_count": 140,
            "expected_fingerprint": "new",
            "installed_fingerprint": "old",
        }
        with patch.object(sync_tool.db_utils, "init_db", return_value=None), \
             patch.object(sync_tool, "full_api_docs_status", return_value=status), \
             patch.object(sys, "argv", ["sync_full_api_docs", "--check"]):
            self.assertEqual(sync_tool.main(), 1)

    def test_public_docs_expose_all_generated_endpoints(self):
        def assertions(_conn):
            api_doc_service.sync_full_api_docs(force=True)
            docs = api_doc_service.list_public_docs()
            endpoint_count = sum(len(category["endpoints"]) for category in docs)
            self.assertEqual(endpoint_count, FULL_API_DOCS_TOTAL)
            self.assertTrue(all(category["endpoints"] for category in docs))

        self._run_with_temp_db(assertions)


if __name__ == "__main__":
    unittest.main()
