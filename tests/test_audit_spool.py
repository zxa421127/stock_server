from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import services.audit_spool as spool


def _configure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(spool.config, "AUDIT_ENABLED", True)
    monkeypatch.setattr(spool.config, "AUDIT_SPOOL_DB_FILE", str(tmp_path / "audit_spool.db"))
    monkeypatch.setattr(spool.config, "AUDIT_EMERGENCY_DIR", tmp_path / "emergency")
    monkeypatch.setattr(spool.config, "AUDIT_SPOOL_SYNCHRONOUS", "FULL")
    monkeypatch.setattr(spool.config, "AUDIT_SPOOL_BATCH_SIZE", 50)
    monkeypatch.setattr(spool.config, "AUDIT_SPOOL_MAX_RETRIES", 2)


def _event(event_id="e1"):
    return {"event_id": event_id, "created_at": "2026-07-19 12:00:00", "success": True}


def test_enqueue_is_durable_and_flush_removes_confirmed_rows(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    inserted = []

    def fake_insert(events):
        inserted.extend(events)
        return {item[1]["event_id"] for item in events}

    monkeypatch.setattr(spool, "insert_events_batch", fake_insert)
    assert spool.enqueue_event("operation", _event("op1")) is True

    conn = sqlite3.connect(tmp_path / "audit_spool.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_spool_queue").fetchone()[0] == 1
    finally:
        conn.close()

    result = spool.flush_spool_once()
    assert result["flushed"] == 1
    assert inserted[0][0] == "operation"
    assert inserted[0][1]["event_id"] == "op1"

    conn = sqlite3.connect(tmp_path / "audit_spool.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_spool_queue").fetchone()[0] == 0
    finally:
        conn.close()


def test_flush_treats_already_present_event_as_confirmed(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(spool, "insert_events_batch", lambda events: {"already"})
    assert spool.enqueue_event("api_access", _event("already")) is True
    assert spool.flush_spool_once()["flushed"] == 1
    assert spool.audit_spool_stats()["queued"] == 0


def test_repeated_failure_moves_row_to_dead_letters(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)

    def fail(_events):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(spool, "insert_events_batch", fail)
    assert spool.enqueue_event("operation", _event("dead")) is True
    first = spool.flush_spool_once(force_due=True)
    assert first["retried"] == 1
    second = spool.flush_spool_once(force_due=True)
    assert second["dead_lettered"] == 1

    conn = sqlite3.connect(tmp_path / "audit_spool.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_spool_queue").fetchone()[0] == 0
        row = conn.execute("SELECT event_id, attempt_count, last_error FROM audit_spool_dead_letters").fetchone()
        assert row[0] == "dead"
        assert row[1] == 2
        assert "database is locked" in row[2]
    finally:
        conn.close()


def test_emergency_jsonl_is_used_when_spool_write_fails(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(spool, "_insert_spool_row", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("readonly")))
    assert spool.enqueue_event("api_access", _event("emergency"), strict=True) is True
    files = list((tmp_path / "emergency").glob("api_access_emergency_*.jsonl"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert '"event_id": "emergency"' in content


def test_recover_emergency_file_enqueues_valid_lines_and_preserves_bad_line(tmp_path, monkeypatch):
    _configure(monkeypatch, tmp_path)
    emergency = tmp_path / "emergency"
    emergency.mkdir()
    path = emergency / "operation_emergency_2026-07-19.jsonl"
    path.write_text(
        json.dumps({"event_type": "operation", "event": _event("r1")}, ensure_ascii=False) + "\n" +
        "not-json\n",
        encoding="utf-8",
    )
    result = spool.recover_emergency_files()
    assert result["recovered"] == 1
    assert result["invalid"] == 1
    assert spool.audit_spool_stats()["queued"] == 1
    assert list(emergency.glob("*.bad"))
