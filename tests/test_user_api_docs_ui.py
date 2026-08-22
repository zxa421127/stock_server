# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from routes.user_routes import user_bp


class UserApiDocsUiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = "test-secret"
        self.app.register_blueprint(user_bp, url_prefix="/user")
        self.client = self.app.test_client()

    @patch("routes.user_routes.get_api_doc_statistics")
    def test_status_endpoint_returns_current_revision_without_cache(self, statistics_mock):
        statistics_mock.return_value = {
            "ui_revision": "revision-user-live",
            "category_count": 12,
            "document_count": 140,
            "general_count": 119,
            "special_count": 21,
            "route_count": 140,
            "missing_route_count": 0,
            "runtime_report_time": "2026-07-24 12:00:00",
            "runtime_callable_count": 130,
            "runtime_data_count": 123,
            "runtime_direct_count": 120,
            "runtime_fallback_count": 3,
            "runtime_callable_empty_count": 7,
            "runtime_uncallable_count": 10,
        }
        response = self.client.get("/user/api-docs/status.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.get_json()["ui_revision"], "revision-user-live")
        self.assertEqual(response.get_json()["runtime_data_count"], 123)

    @patch("routes.user_routes.get_api_doc_statistics")
    @patch("routes.user_routes.list_public_docs")
    def test_page_uses_central_statistics(self, docs_mock, statistics_mock):
        docs_mock.return_value = [{
            "id": 1,
            "name": "ETF专题",
            "description": "ETF",
            "endpoints": [{
                "id": 1,
                "title": "ETF基本信息",
                "method": "GET",
                "path": "/api/v1/market/tushare/etf_basic?list_status=L",
                "scope": "tushare:points15000:read",
                "description": "接口英文名：etf_basic\n最新实测状态：正常可用",
                "params_text": "",
                "headers_text": "",
                "request_example": "",
                "response_example": "",
                "error_codes": "",
                "runtime_status": {
                    "status_key": "healthy",
                    "status_label": "实测正常",
                    "http_status": 200,
                    "data_count": 1611,
                    "verdict": "成功且取得数据",
                    "problem_category": "正常可用",
                    "fallback_used": False,
                    "data_freshness": "exact_request",
                    "actual_trade_date": None,
                },
            }],
        }]
        statistics_mock.return_value = {
            "document_count": 140,
            "general_count": 119,
            "special_count": 21,
            "other_scope_count": 0,
            "route_count": 140,
            "missing_route_count": 0,
            "runtime_report_valid": True,
            "runtime_report_time": "2026-07-21 22:02:23",
            "runtime_report_stale": False,
            "runtime_coverage_count": 140,
            "runtime_callable_count": 135,
            "runtime_data_count": 131,
            "runtime_direct_count": 122,
            "runtime_fallback_count": 9,
            "runtime_callable_empty_count": 4,
            "runtime_uncallable_count": 5,
            "ui_revision": "revision-user-a",
        }

        response = self.client.get("/user/api-docs")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("完整收录140个接口文档", html)
        self.assertIn("<b>119</b> 通用接口", html)
        self.assertIn("<b>21</b> 特殊权限", html)
        self.assertIn("<b>135</b> 最近实测可调用", html)
        self.assertIn("<b>131</b> 取得数据", html)
        self.assertIn("<b>5</b> 真正不可调用", html)
        self.assertIn("/user/api-docs/status.json", html)
        self.assertIn("setInterval", html)
        self.assertIn("revision-user-a", html)

    def test_source_has_no_stale_hardcoded_count_phrases(self):
        source = Path("routes/user_routes.py").read_text(encoding="utf-8")
        self.assertNotIn("完整收录140个接口", source)
        admin_source = Path("routes/admin_api_doc_routes.py").read_text(encoding="utf-8")
        self.assertNotIn("完整139接口", admin_source)
        tool_source = Path("tools/sync_full_api_docs.py").read_text(encoding="utf-8")
        self.assertNotIn("== 139", tool_source)


if __name__ == "__main__":
    unittest.main()
