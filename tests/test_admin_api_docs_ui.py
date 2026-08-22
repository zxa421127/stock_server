# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

import config
from flask import Flask

from routes.admin_api_doc_routes import admin_api_doc_bp


class AdminApiDocsUiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(admin_api_doc_bp, url_prefix="/admin")
        self.client = self.app.test_client()

    @staticmethod
    def _categories():
        return [
            {
                "id": 1,
                "name": "ETF专题",
                "description": "ETF相关接口",
                "sort_order": 10,
                "status": "active",
            }
        ]

    @staticmethod
    def _endpoints():
        return [
            {
                "id": 6,
                "category_id": 1,
                "category_name": "ETF专题",
                "title": "ETF基本信息",
                "method": "GET",
                "path": "/api/v1/market/tushare/etf_basic?list_status=L",
                "scope": "tushare:points15000:read",
                "sort_order": 20,
                "status": "active",
            },
            {
                "id": 7,
                "category_id": 1,
                "category_name": "ETF专题",
                "title": "ETF实时日线",
                "method": "GET",
                "path": "/api/v1/market/tushare/rt_etf_k?ts_code=159919.SZ",
                "scope": "tushare:independent:realtime:read",
                "sort_order": 30,
                "status": "draft",
            },
        ]

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["admin_logged_in"] = True

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get("/admin/api-docs")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/login"))

    @patch("routes.admin_api_doc_routes.get_api_doc_statistics")
    def test_status_endpoint_is_authenticated_and_no_store(self, statistics_mock):
        denied = self.client.get("/admin/api-docs/status.json")
        self.assertEqual(denied.status_code, 401)

        self._login()
        statistics_mock.return_value = {
            "ui_revision": "revision-live",
            "category_count": 12,
            "document_count": 140,
            "active_count": 140,
            "route_count": 140,
            "missing_route_count": 0,
            "runtime_report_time": "2026-07-24 12:00:00",
            "runtime_callable_count": 130,
            "runtime_data_count": 123,
            "runtime_uncallable_count": 10,
        }
        response = self.client.get("/admin/api-docs/status.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.get_json()["ui_revision"], "revision-live")
        self.assertEqual(response.get_json()["runtime_callable_count"], 130)

    @patch("routes.admin_api_doc_routes.get_api_doc_statistics")
    @patch("routes.admin_api_doc_routes.list_endpoints")
    @patch("routes.admin_api_doc_routes.list_categories")
    def test_admin_page_has_scroll_search_and_sticky_columns(
        self,
        list_categories_mock,
        list_endpoints_mock,
        statistics_mock,
    ):
        self._login()
        list_categories_mock.return_value = self._categories()
        list_endpoints_mock.return_value = self._endpoints()
        statistics_mock.return_value = {
            "document_count": 140,
            "active_count": 139,
            "non_active_count": 1,
            "generated_count": 140,
            "custom_count": 0,
            "general_count": 119,
            "special_count": 21,
            "other_scope_count": 0,
            "expected_generated_count": 140,
            "installed_generated_count": 140,
            "installed_version": "20260720_dynamic_catalog_v2",
            "route_count": 140,
            "missing_route_count": 0,
            "runtime_report_valid": True,
            "runtime_report_time": "2026-07-24 08:00:00",
            "runtime_report_stale": False,
            "runtime_callable_count": 134,
            "runtime_data_count": 130,
            "runtime_uncallable_count": 6,
            "catalog_fingerprint": "catalog-a",
            "ui_revision": "revision-a",
        }

        response = self.client.get("/admin/api-docs")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('id="endpointSearch"', html)
        self.assertIn('id="categoryFilter"', html)
        self.assertIn('id="statusFilter"', html)
        self.assertIn('class="table-scroll endpoints"', html)
        self.assertIn("overflow: auto", html)
        self.assertIn("position: sticky", html)
        self.assertIn("min-width: 1640px", html)
        self.assertIn("当前显示", html)
        self.assertNotIn("完整139接口", html)
        self.assertIn("接口文档总数", html)
        self.assertIn("自动生成文档", html)
        self.assertIn("实际路由存在", html)
        self.assertIn("重新生成完整140接口文档", html)
        self.assertIn("REBUILD API DOCS", html)
        self.assertIn("DELETE ENDPOINT 6", html)
        self.assertIn('name="admin_password"', html)
        self.assertIn('name="confirmation_text"', html)
        self.assertIn("ETF基本信息", html)
        self.assertIn("tushare:points15000:read", html)
        self.assertIn("data-category=\"ETF专题\"", html)
        self.assertIn("noEndpointMatch", html)
        self.assertIn("最近实测可调用", html)
        self.assertIn("每60秒检查一次", html)
        self.assertIn("/admin/api-docs/status.json", html)
        self.assertIn("setInterval", html)
        self.assertIn("revision-a", html)

    @patch("routes.admin_api_doc_routes.get_api_doc_statistics")
    @patch("routes.admin_api_doc_routes.list_endpoints")
    @patch("routes.admin_api_doc_routes.list_categories")
    def test_user_docs_links_use_paired_public_domain(
        self,
        list_categories_mock,
        list_endpoints_mock,
        statistics_mock,
    ):
        self._login()
        list_categories_mock.return_value = []
        list_endpoints_mock.return_value = []
        statistics_mock.return_value = {}

        with patch.object(config, "ADMIN_CLIENT_CERT_ADMIN_HOST", "test-admin-api.lifesupermarket.cn"):
            response = self.client.get("/admin/api-docs")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        expected = 'href="https://test-api.lifesupermarket.cn/user/api-docs"'
        self.assertEqual(html.count(expected), 2)
        self.assertNotIn('href="/user/api-docs"', html)



if __name__ == "__main__":
    unittest.main()
