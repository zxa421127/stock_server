# -*- coding: utf-8 -*-
from pathlib import Path

from services.market_interface_spec_service import MarketInterfaceSpecService
from tools.audit_interface_specs import build_audit_report


def test_audit_report_counts_full_catalog_and_forbidden_fields(tmp_path):
    service = MarketInterfaceSpecService(tmp_path / "specs")
    service.ensure_seed_release()
    report = build_audit_report(service)
    assert report["total"] == 140
    assert report["providers"] == {"kaipanla": 2, "tushare": 138}
    assert report["official_verified"] == 5
    assert report["tushare_pending_official"] == 135
    assert report["forbidden_fields_input_count"] == 0
    assert report["categories"]["ETF专题"] == 13
    assert any(row["api_name"] == "etf_basic" and row["input_count"] == 6 and row["output_count"] == 14 for row in report["interfaces"])
