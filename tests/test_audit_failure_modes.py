from __future__ import annotations

from pathlib import Path

import services.audit_spool as spool


def test_enqueue_returns_false_only_when_spool_and_emergency_both_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(spool.config, "AUDIT_ENABLED", True)
    monkeypatch.setattr(spool.config, "AUDIT_SPOOL_DB_FILE", str(tmp_path / "spool.db"))
    monkeypatch.setattr(spool.config, "AUDIT_EMERGENCY_DIR", tmp_path / "emergency")
    monkeypatch.setattr(spool, "_insert_spool_row", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("spool failed")))
    monkeypatch.setattr(spool, "_write_emergency", lambda *args, **kwargs: False)
    event = {"event_id": "lost", "created_at": "2026-07-19 12:00:00"}
    assert spool.enqueue_event("operation", event, strict=False) is False
    assert spool.enqueue_event("operation", event, strict=True) is False
