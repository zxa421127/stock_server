# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import db_utils
from flask import Flask
from services import api_doc_service
from services.api_doc_catalog import FULL_API_DOCS, FULL_API_DOCS_TOTAL


class ApiDocServiceStatisticsTests(unittest.TestCase):
    def _run_with_temp_db(self, callback):
        """Initialize only tables used by API-document service tests."""
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

    def _run_with_api_doc_only_db(self, callback):
        self._run_with_temp_db(callback)

    def test_catalog_total_is_derived_from_catalog_length(self):
        self.assertEqual(FULL_API_DOCS_TOTAL, len(FULL_API_DOCS))

    def test_sync_removes_only_two_approved_obsolete_documents(self):
        def assertions(conn):
            now = "2026-07-20 00:00:00"
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('旧接口','',1,'active',?,?)",
                (now, now),
            )
            obsolete_category_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('自定义接口','',2,'active',?,?)",
                (now, now),
            )
            custom_category_id = int(cur.lastrowid)
            rows = [
                (
                    obsolete_category_id,
                    "股票基础信息",
                    "/api/data/stock/basic?list_status=L",
                    "stock_basic:read",
                ),
                (
                    obsolete_category_id,
                    "交易日历",
                    "/api/data/trade/cal?exchange=SSE&start_date=20260701&end_date=20260731",
                    "trade_cal:read",
                ),
                (
                    custom_category_id,
                    "自定义健康检查",
                    "/api/v1/custom/health",
                    "custom:read",
                ),
            ]
            cur.executemany(
                "INSERT INTO api_doc_endpoints "
                "(category_id,title,method,path,scope,status,created_at,updated_at) "
                "VALUES (?,?,'GET',?,?,'active',?,?)",
                [(category_id, title, path, scope, now, now) for category_id, title, path, scope in rows],
            )
            conn.commit()

            result = api_doc_service.sync_full_api_docs(force=True)

            remaining_paths = {
                row["path"]
                for row in conn.execute("SELECT path FROM api_doc_endpoints").fetchall()
            }
            self.assertNotIn("/api/data/stock/basic?list_status=L", remaining_paths)
            self.assertNotIn(
                "/api/data/trade/cal?exchange=SSE&start_date=20260701&end_date=20260731",
                remaining_paths,
            )
            self.assertIn("/api/v1/custom/health", remaining_paths)
            self.assertEqual(result["obsolete_docs_deleted"], 2)
            self.assertEqual(result["empty_categories_deleted"], 1)

            category_names = {
                row["name"] for row in conn.execute("SELECT name FROM api_doc_categories").fetchall()
            }
            self.assertNotIn("旧接口", category_names)
            self.assertIn("自定义接口", category_names)

        self._run_with_temp_db(assertions)

    def test_non_force_sync_still_cleans_obsolete_documents(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            now = "2026-07-20 00:00:00"
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('旧接口','',999,'active',?,?)",
                (now, now),
            )
            category_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO api_doc_endpoints "
                "(category_id,title,method,path,scope,status,created_at,updated_at) "
                "VALUES (?,'股票基础信息','GET','/api/data/stock/basic?list_status=L','stock_basic:read','active',?,?)",
                (category_id, now, now),
            )
            conn.commit()

            result = api_doc_service.sync_full_api_docs(force=False)

            self.assertFalse(result["changed"])
            self.assertEqual(result["obsolete_docs_deleted"], 1)
            count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM api_doc_endpoints "
                "WHERE path='/api/data/stock/basic?list_status=L'"
            ).fetchone()["cnt"]
            self.assertEqual(count, 0)

        self._run_with_temp_db(assertions)

    def test_idempotent_sync_releases_write_transaction(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)

            result = api_doc_service.sync_full_api_docs(force=False)

            self.assertFalse(result["changed"])
            self.assertFalse(conn.in_transaction)

        self._run_with_temp_db(assertions)

    def test_idempotent_sync_allows_second_connection_writer(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            api_doc_service.sync_full_api_docs(force=False)

            second = sqlite3.connect(db_utils.DB_FILE, timeout=0.1)
            try:
                second.execute("BEGIN IMMEDIATE")
                second.rollback()
            finally:
                second.close()

        self._run_with_temp_db(assertions)

    def test_ensure_default_docs_skips_sync_when_catalog_is_current(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)

            with patch.object(api_doc_service, "sync_full_api_docs") as sync_mock:
                api_doc_service.ensure_default_api_docs()

            sync_mock.assert_not_called()
            self.assertFalse(conn.in_transaction)

        self._run_with_temp_db(assertions)

    def test_legacy_catalog_shape_is_replaced_without_duplicate_rows(self):
        def assertions(conn):
            now = "2026-07-23 00:00:00"
            category_ids = {}
            for doc in FULL_API_DOCS:
                name = doc["category"]
                if name not in category_ids:
                    cur = conn.execute(
                        "INSERT INTO api_doc_categories "
                        "(name,description,sort_order,status,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,?)",
                        (name, doc.get("category_description", ""), 100, "legacy", now, now),
                    )
                    category_ids[name] = int(cur.lastrowid)
            for index, doc in enumerate(FULL_API_DOCS):
                conn.execute(
                    "INSERT INTO api_doc_endpoints "
                    "(category_id,title,method,path,scope,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        category_ids[doc["category"]], doc["title"], "GET",
                        f"/legacy/api-doc/{index}", doc.get("scope", ""),
                        "legacy", now, now,
                    ),
                )
            conn.commit()

            before = conn.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN path LIKE '/api/v1/market/tushare/%' "
                "OR path LIKE '/api/v1/market/kaipanla/%' THEN 1 ELSE 0 END) AS generated, "
                "SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) AS active "
                "FROM api_doc_endpoints"
            ).fetchone()
            self.assertEqual(before["total"], len(FULL_API_DOCS))
            self.assertEqual(before["generated"], 0)
            self.assertEqual(before["active"], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM api_doc_categories").fetchone()["cnt"],
                12,
            )

            result = api_doc_service.sync_full_api_docs(force=False)

            self.assertEqual(result["legacy_generated_docs_deleted"], len(FULL_API_DOCS))
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM api_doc_endpoints").fetchone()["cnt"],
                len(FULL_API_DOCS),
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) AS cnt FROM api_doc_endpoints "
                    "WHERE status='active' AND ("
                    "path LIKE '/api/v1/market/tushare/%' OR "
                    "path LIKE '/api/v1/market/kaipanla/%')"
                ).fetchone()["cnt"],
                len(FULL_API_DOCS),
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS cnt FROM api_doc_categories").fetchone()["cnt"],
                len({doc["category"] for doc in FULL_API_DOCS}),
            )
            after = api_doc_service.get_api_doc_statistics(include_route_stats=False)
            self.assertEqual(after["generated_count"], len(FULL_API_DOCS))
            self.assertEqual(after["custom_count"], 0)
            self.assertEqual(after["active_count"], len(FULL_API_DOCS))
            self.assertEqual(after["non_active_count"], 0)

        self._run_with_temp_db(assertions)

    def test_same_count_catalog_change_triggers_resync_by_fingerprint(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            original = [dict(item) for item in api_doc_service.FULL_API_DOCS]
            changed = [dict(item) for item in original]
            original_category = original[0]["category"]
            changed[0]["title"] = original[0]["title"] + "（同数量目录变更）"
            for item in changed:
                if item["category"] == original_category:
                    item["category"] = "动态新类目"
                    item["category_description"] = "用于验证同数量目录变化也能自动同步"

            with patch.object(api_doc_service, "FULL_API_DOCS", changed):
                status_before = api_doc_service.full_api_docs_status()
                self.assertNotEqual(
                    status_before["installed_fingerprint"],
                    status_before["expected_fingerprint"],
                )
                api_doc_service.ensure_default_api_docs()
                status_after = api_doc_service.full_api_docs_status()

            row = conn.execute(
                "SELECT e.title,c.name AS category_name "
                "FROM api_doc_endpoints e "
                "JOIN api_doc_categories c ON c.id=e.category_id "
                "WHERE e.path=?",
                (changed[0]["path"],),
            ).fetchone()
            self.assertEqual(row["title"], changed[0]["title"])
            self.assertEqual(row["category_name"], "动态新类目")
            self.assertEqual(
                status_after["installed_fingerprint"],
                status_after["expected_fingerprint"],
            )
            category_names = {
                item["name"] for item in conn.execute(
                    "SELECT name FROM api_doc_categories"
                ).fetchall()
            }
            self.assertIn("动态新类目", category_names)
            self.assertNotIn(original_category, category_names)

        self._run_with_api_doc_only_db(assertions)

    def test_central_statistics_are_computed_from_database(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            now = "2026-07-20 00:00:00"
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('自定义接口','',999,'active',?,?)",
                (now, now),
            )
            category_id = int(cur.lastrowid)
            cur.execute(
                "INSERT INTO api_doc_endpoints "
                "(category_id,title,method,path,scope,status,created_at,updated_at) "
                "VALUES (?,'自定义健康检查','GET','/api/v1/custom/health','custom:read','draft',?,?)",
                (category_id, now, now),
            )
            conn.commit()

            stats = api_doc_service.get_api_doc_statistics(include_route_stats=False)

            self.assertEqual(stats["document_count"], len(FULL_API_DOCS) + 1)
            self.assertEqual(stats["generated_count"], len(FULL_API_DOCS))
            self.assertEqual(stats["custom_count"], 1)
            self.assertEqual(stats["active_count"], len(FULL_API_DOCS))
            self.assertEqual(stats["non_active_count"], 1)
            self.assertEqual(stats["general_count"], 119)
            self.assertEqual(stats["special_count"], 21)
            self.assertEqual(stats["other_scope_count"], 1)
            self.assertEqual(stats["expected_generated_count"], len(FULL_API_DOCS))

        self._run_with_temp_db(assertions)

    def test_ui_revision_changes_when_latest_runtime_report_changes(self):
        def assertions(_conn):
            api_doc_service.sync_full_api_docs(force=True)
            morning = {
                "valid": True,
                "report_name": "全部真实数据接口_20260724_080000.json",
                "report_time": "2026-07-24 08:00:00",
                "report_age_seconds": 60,
                "coverage_count": 140,
                "callable_count": 134,
                "data_count": 130,
                "direct_count": 123,
                "fallback_count": 7,
                "callable_empty_count": 4,
                "uncallable_count": 6,
                "problem_counts": {},
            }
            afternoon = {
                **morning,
                "report_name": "全部真实数据接口_20260724_140000.json",
                "report_time": "2026-07-24 14:00:00",
                "callable_count": 130,
                "data_count": 123,
                "direct_count": 118,
                "fallback_count": 5,
                "callable_empty_count": 7,
                "uncallable_count": 10,
            }
            with patch.object(
                api_doc_service, "get_runtime_status_snapshot", return_value=morning
            ):
                first = api_doc_service.get_api_doc_statistics(
                    include_route_stats=False
                )
            with patch.object(
                api_doc_service, "get_runtime_status_snapshot", return_value=afternoon
            ):
                second = api_doc_service.get_api_doc_statistics(
                    include_route_stats=False
                )

            self.assertEqual(first["runtime_callable_count"], 134)
            self.assertEqual(second["runtime_callable_count"], 130)
            self.assertEqual(second["runtime_data_count"], 123)
            self.assertNotEqual(first["ui_revision"], second["ui_revision"])

        self._run_with_temp_db(assertions)

    def test_route_statistics_match_dynamic_flask_routes(self):
        def assertions(conn):
            api_doc_service.sync_full_api_docs(force=True)
            now = "2026-07-20 00:00:00"
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO api_doc_categories "
                "(name,description,sort_order,status,created_at,updated_at) "
                "VALUES ('自定义接口','',999,'active',?,?)",
                (now, now),
            )
            category_id = int(cur.lastrowid)
            cur.executemany(
                "INSERT INTO api_doc_endpoints "
                "(category_id,title,method,path,scope,status,created_at,updated_at) "
                "VALUES (?,?,'GET',?,?,'active',?,?)",
                [
                    (category_id, '自定义健康检查', '/api/v1/custom/health?verbose=1', 'custom:read', now, now),
                    (category_id, '缺失接口', '/api/v1/custom/missing', 'custom:read', now, now),
                ],
            )
            conn.commit()

            app = Flask(__name__)

            @app.route('/api/v1/market/<provider_code>/<path:data_type>', methods=['GET', 'POST'])
            def market_route(provider_code, data_type):
                return f"{provider_code}:{data_type}"

            @app.get('/api/v1/custom/health')
            def custom_health():
                return 'ok'

            with app.app_context():
                stats = api_doc_service.get_api_doc_statistics()

            app_without_custom_route = Flask(__name__ + "_missing")

            @app_without_custom_route.route(
                '/api/v1/market/<provider_code>/<path:data_type>',
                methods=['GET', 'POST'],
            )
            def market_route_only(provider_code, data_type):
                return f"{provider_code}:{data_type}"

            with app_without_custom_route.app_context():
                stats_without_custom_route = api_doc_service.get_api_doc_statistics()

            self.assertEqual(stats['route_count'], len(FULL_API_DOCS) + 1)
            self.assertEqual(stats['missing_route_count'], 1)
            self.assertEqual(
                stats_without_custom_route['route_count'],
                len(FULL_API_DOCS),
            )
            self.assertNotEqual(
                stats['ui_revision'],
                stats_without_custom_route['ui_revision'],
            )

        self._run_with_temp_db(assertions)


if __name__ == "__main__":
    unittest.main()
