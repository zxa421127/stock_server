from __future__ import annotations


def test_migration_command_initializes_main_and_spool_schema(monkeypatch, capsys, tmp_path):
    from tools.db import migrate_audit_history as command

    calls = []
    monkeypatch.setattr(command, "init_db", lambda: calls.append("main"))
    monkeypatch.setattr(command, "init_spool_schema", lambda path, mode: calls.append((str(path), mode)))
    monkeypatch.setattr(command.config, "AUDIT_SPOOL_DB_FILE", str(tmp_path / "spool.db"))
    monkeypatch.setattr(command.config, "AUDIT_SPOOL_SYNCHRONOUS", "FULL")
    monkeypatch.setattr(command, "_schema_summary", lambda: {
        "operation_audit_logs": 0,
        "api_access_logs": 0,
        "audit_maintenance_state": 0,
    })

    assert command.main() == 0
    assert calls == ["main", (str(tmp_path / "spool.db"), "FULL")]
    output = capsys.readouterr().out
    assert "审计历史数据库迁移完成" in output
    assert "operation_audit_logs" in output
