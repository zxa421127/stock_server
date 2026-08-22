# -*- coding: utf-8 -*-
from __future__ import annotations

from integrations.feishu.bitable import BIDDING_FIELD_SPECS, FeishuBitableManager


def manager_without_init():
    manager = FeishuBitableManager.__new__(FeishuBitableManager)
    manager.bidding_app_token = "app"
    manager.bidding_table_id = "table"
    manager._bidding_schema_checked = False
    return manager


def test_bidding_schema_has_final_field_types_only():
    assert BIDDING_FIELD_SPECS["股票代码"].type == 1
    assert BIDDING_FIELD_SPECS["竞价净额"].type == 2
    assert BIDDING_FIELD_SPECS["主力卖出额"].type == 2
    assert BIDDING_FIELD_SPECS["快照类型"].accepts(1)
    assert BIDDING_FIELD_SPECS["快照类型"].accepts(3)
    for removed in ("原始字段10","原始字段13","原始字段14","原始字段15","主力卖出","主力资金关系校验","字段校验警告","limit_step连板","连板来源","kpl_list状态"):
        assert removed not in BIDDING_FIELD_SPECS


def test_check_schema_creates_only_final_missing_fields_and_reports_conflicts(monkeypatch):
    manager = manager_without_init()
    existing = {"股票代码":{"field_name":"股票代码","type":2},"股票名称":{"field_name":"股票名称","type":1}}
    created=[]
    monkeypatch.setattr(manager,"list_fields",lambda **kwargs: existing)
    monkeypatch.setattr(manager,"create_field",lambda spec,**kwargs: created.append(spec.name) or True)
    report=manager.check_bidding_schema(create_missing=True)
    assert any(item["field_name"]=="股票代码" for item in report["type_mismatches"])
    assert "股票代码" not in created
    assert "竞价净额" in created and "快照类型" in created
    assert not any(name.startswith("原始字段") for name in created)
    assert report["ok"] is False


def test_ensure_schema_stops_on_incompatible_existing_column(monkeypatch):
    manager=manager_without_init()
    monkeypatch.setattr(manager,"check_bidding_schema",lambda **kwargs:{"ok":False,"missing":[],"created":[],"unresolved_missing":[],"type_mismatches":[{"field_name":"股票代码"}],"errors":[]})
    try:
        manager.ensure_bidding_schema(create_missing=True)
    except RuntimeError as exc:
        assert "股票代码" in str(exc)
    else:
        raise AssertionError("schema mismatch must stop sync")
