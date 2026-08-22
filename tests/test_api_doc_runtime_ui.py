# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import patch

from flask import Flask

from routes.user_routes import user_bp


def _docs():
    return [{
        "id": 1,
        "name": "开盘啦",
        "description": "开盘啦接口",
        "endpoints": [
            {
                "id": 1,
                "title": "开盘啦早盘竞价",
                "method": "GET",
                "path": "/api/v1/market/kaipanla/morning_bidding",
                "scope": "market:kaipanla:read",
                "description": "接口英文名：morning_bidding\n最新实测状态：新增接口（需生产环境凭据验收）",
                "params_text": "",
                "headers_text": "",
                "request_example": "",
                "response_example": "",
                "error_codes": "",
                "runtime_status": {
                    "status_key": "healthy",
                    "status_label": "实测正常",
                    "http_status": 200,
                    "data_count": 20,
                    "verdict": "成功且取得数据",
                    "problem_category": "正常可用",
                    "fallback_used": False,
                    "data_freshness": "unverified_realtime",
                    "actual_trade_date": None,
                },
            },
            {
                "id": 2,
                "title": "开盘啦历史快照",
                "method": "GET",
                "path": "/api/v1/market/kaipanla/morning_bidding/history",
                "scope": "market:kaipanla:read",
                "description": "接口英文名：morning_bidding_history\n最新实测状态：新增接口（需生产环境凭据验收）",
                "params_text": "",
                "headers_text": "",
                "request_example": "",
                "response_example": "",
                "error_codes": "",
                "runtime_status": {
                    "status_key": "healthy",
                    "status_label": "实测正常",
                    "http_status": 200,
                    "data_count": 115,
                    "verdict": "成功且取得数据",
                    "problem_category": "正常可用",
                    "fallback_used": False,
                    "data_freshness": "latest_snapshot",
                    "actual_trade_date": "20260721",
                },
            },
        ],
    }]


def test_user_docs_uses_runtime_report_kpis_and_endpoint_badges():
    # Historical nodeid preserved: the contract is now least-disclosure.
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(user_bp, url_prefix="/user")

    stats = {
        "category_count": 1,
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
    }

    with patch("routes.user_routes.list_public_docs", return_value=_docs()), \
         patch("routes.user_routes.get_api_doc_statistics", return_value=stats):
        response = app.test_client().get("/user/api-docs")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<b>140</b> 全部接口" in html
    assert "<b>119</b> 通用接口" in html
    assert "<b>21</b> 特殊权限" in html
    assert "状态：可调用" in html
    assert 'data-health="available"' in html
    assert 'data-filter="available"' in html
    assert 'data-filter="unavailable"' in html
    assert 'data-filter="unverified"' in html
    assert "morning_bidding/history" in html
    assert "实测：新增接口（需生产环境凭据验收）" not in html

    # Rich runtime/operational telemetry must not cross the public HTML boundary.
    assert "最近实测更新：2026-07-21 22:02:23" not in html
    assert "<b>135</b> 最近实测可调用" not in html
    assert "<b>131</b> 取得数据" not in html
    assert "<b>9</b> 回退取得数据" not in html
    assert "<b>4</b> 可调用无匹配数据" not in html
    assert "<b>5</b> 真正不可调用" not in html
    assert "HTTP 200 · 20条" not in html
    assert "成功且取得数据" not in html
    assert "正常可用" not in html
    assert "latest_snapshot" not in html
    assert "20260721" not in html
    assert 'data-health="healthy"' not in html
    assert 'data-filter="fallback"' not in html
    assert 'data-filter="callable_empty"' not in html
    assert 'data-filter="uncallable"' not in html
    assert "data-health-group" not in html


def test_user_docs_marks_missing_runtime_record_as_unverified_not_upstream_failure():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(user_bp, url_prefix="/user")
    docs = _docs()
    docs[0]["endpoints"][0].pop("runtime_status")
    stats = {
        "category_count": 1,
        "document_count": 2,
        "general_count": 0,
        "special_count": 2,
        "other_scope_count": 0,
        "route_count": 2,
        "missing_route_count": 0,
        "runtime_report_valid": False,
        "runtime_report_time": "",
        "runtime_report_stale": True,
        "runtime_coverage_count": 0,
    }
    with patch("routes.user_routes.list_public_docs", return_value=docs), \
         patch("routes.user_routes.get_api_doc_statistics", return_value=stats):
        html = app.test_client().get("/user/api-docs").get_data(as_text=True)
    assert "暂无有效实测记录" in html
    assert 'data-health="unverified"' in html
    assert "最近实测结论" not in html
    assert "上游待开通/配置" not in html

def test_api_docs_status_is_anonymous_public_only_contract():
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(user_bp, url_prefix="/user")

    stats = {
        "ui_revision": "runtime-bound-private-revision",
        "category_count": 2,
        "document_count": 140,
        "general_count": 119,
        "special_count": 21,
        "route_count": 140,
        "missing_route_count": 0,
        "runtime_report_time": "2026-07-21 22:02:23",
        "runtime_callable_count": 135,
        "runtime_data_count": 131,
        "runtime_direct_count": 122,
        "runtime_fallback_count": 9,
        "runtime_callable_empty_count": 4,
        "runtime_uncallable_count": 5,
    }

    with patch(
        "routes.user_routes.get_api_doc_statistics",
        return_value=stats,
    ) as get_stats:
        response = app.test_client().get(
            "/user/api-docs/status.json"
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert set(payload) == {
        "success",
        "ui_revision",
        "category_count",
        "document_count",
        "general_count",
        "special_count",
    }
    assert payload["success"] is True
    assert payload["category_count"] == 2
    assert payload["document_count"] == 140
    assert payload["general_count"] == 119
    assert payload["special_count"] == 21
    assert payload["ui_revision"] == "public:2:140:119:21"
    assert payload["ui_revision"] != stats["ui_revision"]
    assert response.headers["Cache-Control"] == "no-store"
    get_stats.assert_called_once_with(public_only=True)

