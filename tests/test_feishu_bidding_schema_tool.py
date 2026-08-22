# -*- coding: utf-8 -*-
from __future__ import annotations

import tools.check_feishu_bidding_schema as tool


class Manager:
    def __init__(self):
        self.apply = None
    def check_bidding_schema(self, *, create_missing=False):
        self.apply = create_missing
        return {"ok": True, "missing": [], "created": []}


def test_schema_tool_is_dry_run_by_default(monkeypatch, capsys):
    manager = Manager()
    monkeypatch.setattr(tool, "get_bitable_manager", lambda: manager)
    assert tool.main([]) == 0
    assert manager.apply is False
    assert '"mode": "dry-run"' in capsys.readouterr().out


def test_schema_tool_apply_creates_missing_fields(monkeypatch, capsys):
    manager = Manager()
    monkeypatch.setattr(tool, "get_bitable_manager", lambda: manager)
    assert tool.main(["--apply"]) == 0
    assert manager.apply is True
    assert '"mode": "apply"' in capsys.readouterr().out
