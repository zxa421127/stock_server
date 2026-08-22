# -*- coding: utf-8 -*-
from services.api_doc_catalog_runtime import FULL_API_DOCS, FULL_API_DOCS_VERSION


def test_runtime_catalog_overlays_current_official_interface_spec():
    ci_daily = next(item for item in FULL_API_DOCS if item.get("api_name") == "ci_daily")

    assert [item["name"] for item in ci_daily["params"]] == [
        "ts_code",
        "trade_date",
        "start_date",
        "end_date",
    ]
    assert [item["type"] for item in ci_daily["params"]] == ["str", "str", "str", "str"]
    assert "获取中信行业指数日线行情" in ci_daily["description"]
    assert "5000积分" in ci_daily["description"]
    assert "单次最大4000条" in ci_daily["description"]
    assert "catalog_seed" not in ci_daily["description"]
    assert "spec-20260726-etf-index-official-sync-fix-v5" in FULL_API_DOCS_VERSION


def test_runtime_catalog_overlays_etf_index_official_contract():
    etf_index = next(item for item in FULL_API_DOCS if item.get("api_name") == "etf_index")
    assert [item["name"] for item in etf_index["params"]] == [
        "ts_code", "pub_date", "base_date",
    ]
    assert [item["type"] for item in etf_index["params"]] == ["str", "str", "str"]
    assert etf_index["scope"] == "tushare:points8000:read"
    assert "获取ETF基准指数列表信息" in etf_index["description"]
    assert "8000积分" in etf_index["description"]
    assert "最大返回5000" in etf_index["description"]
