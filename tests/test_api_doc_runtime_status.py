# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from services.api_doc_runtime_status import (
    endpoint_identity_from_path,
    load_latest_runtime_report,
)


def _write_report(path: Path, payload: dict, mtime: float) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def test_latest_valid_report_skips_newer_zero_interface_failure(tmp_path):
    valid = {
        "总接口数": 2,
        "取得数据接口数": 1,
        "未取得数据接口数": 1,
        "可调用接口数": 2,
        "当前日期或原请求直接取得数据接口数": 1,
        "回退最近可用日期后取得数据接口数": 0,
        "不可调用接口数": 0,
        "问题分类统计": {"正常可用": 1, "参数或数据覆盖待确认": 1},
        "结果": [
            {
                "数据来源": "kaipanla",
                "接口": "morning_bidding",
                "是否取得数据": "是",
                "接口是否可调用": "是",
                "结论": "成功且取得数据",
                "问题分类": "正常可用",
                "HTTP状态": 200,
                "数据条数": 20,
                "是否回退最近数据": False,
                "数据新鲜度": "unverified_realtime",
            },
            {
                "数据来源": "tushare",
                "接口": "stk_alert",
                "是否取得数据": "否",
                "接口是否可调用": "是",
                "结论": "接口可调用但没有匹配数据",
                "问题分类": "参数或数据覆盖待确认",
                "HTTP状态": 200,
                "数据条数": 0,
                "是否回退最近数据": False,
            },
        ],
    }
    invalid = {
        "总接口数": 0,
        "取得数据接口数": 0,
        "未取得数据接口数": 0,
        "可调用接口数": 0,
        "不可调用接口数": 0,
        "问题分类统计": {},
        "结果": [],
    }
    _write_report(tmp_path / "全部真实数据接口_20260721_220223.json", valid, 1000)
    _write_report(tmp_path / "全部真实数据接口_20260721_230000.json", invalid, 2000)

    snapshot = load_latest_runtime_report(result_dir=tmp_path)

    assert snapshot["valid"] is True
    assert snapshot["report_name"] == "全部真实数据接口_20260721_220223.json"
    assert snapshot["total_count"] == 2
    assert snapshot["callable_count"] == 2
    assert snapshot["data_count"] == 1
    assert snapshot["callable_empty_count"] == 1
    assert snapshot["uncallable_count"] == 0
    assert snapshot["endpoints"]["kaipanla.morning_bidding"]["status_key"] == "healthy"
    assert snapshot["endpoints"]["tushare.stk_alert"]["status_key"] == "callable_empty"


def test_report_status_distinguishes_fallback_and_upstream_failure(tmp_path):
    payload = {
        "生成时间": "2026-07-21 22:02:23",
        "总接口数": 2,
        "取得数据接口数": 1,
        "未取得数据接口数": 1,
        "可调用接口数": 1,
        "当前日期或原请求直接取得数据接口数": 0,
        "回退最近可用日期后取得数据接口数": 1,
        "不可调用接口数": 1,
        "问题分类统计": {"正常可用": 1, "中转路由未配置": 1},
        "结果": [
            {
                "数据来源": "tushare",
                "接口": "margin",
                "是否取得数据": "是",
                "接口是否可调用": "是",
                "结论": "接口正常，已返回最近可用数据",
                "问题分类": "正常可用",
                "HTTP状态": 200,
                "数据条数": 3,
                "是否回退最近数据": True,
                "实际数据日期": "20260718",
            },
            {
                "数据来源": "tushare",
                "接口": "rt_min_daily",
                "是否取得数据": "否",
                "接口是否可调用": "否",
                "结论": "中转未配置官方接口",
                "问题分类": "中转路由未配置",
                "HTTP状态": 502,
                "数据条数": 0,
                "是否回退最近数据": False,
            },
        ],
    }
    _write_report(tmp_path / "全部真实数据接口_20260721_220223.json", payload, 1000)

    snapshot = load_latest_runtime_report(result_dir=tmp_path)

    assert snapshot["fallback_count"] == 1
    assert snapshot["uncallable_count"] == 1
    assert snapshot["endpoints"]["tushare.margin"]["status_key"] == "fallback"
    assert snapshot["endpoints"]["tushare.rt_min_daily"]["status_key"] == "upstream_route_missing"
    assert snapshot["endpoints"]["tushare.rt_min_daily"]["status_label"] == "中转路由未配置"


def test_endpoint_identity_keeps_nested_kaipanla_history_name():
    assert endpoint_identity_from_path(
        "/api/v1/market/kaipanla/morning_bidding/history?trade_date=20260721"
    ) == ("kaipanla", "morning_bidding/history")
    assert endpoint_identity_from_path(
        "/api/v1/market/tushare/daily?trade_date=20260721"
    ) == ("tushare", "daily")
