# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

import pytest

import db_utils


def test_database_busy_detection_accepts_locked_and_busy_messages():
    assert db_utils.is_database_busy_error(sqlite3.OperationalError("database is locked"))
    assert db_utils.is_database_busy_error(sqlite3.OperationalError("database table is locked"))
    assert db_utils.is_database_busy_error(sqlite3.OperationalError("database is busy"))
    assert not db_utils.is_database_busy_error(sqlite3.OperationalError("no such table: users"))


def test_write_retry_reconnects_and_succeeds_after_transient_lock(monkeypatch):
    attempts = []
    closed = []
    sleeps = []

    def operation():
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise sqlite3.OperationalError("database is locked")
        return "done"

    monkeypatch.setattr(db_utils, "close_thread_connection", lambda: closed.append(True))
    monkeypatch.setattr(db_utils.time, "sleep", lambda delay: sleeps.append(delay))

    result = db_utils.run_db_write_with_retry(
        operation,
        attempts=4,
        delays=(0.1, 0.2, 0.3),
        operation_name="test-write",
    )

    assert result == "done"
    assert attempts == [1, 2, 3]
    assert len(closed) == 2
    assert sleeps == [0.1, 0.2]


def test_write_retry_does_not_retry_non_busy_error(monkeypatch):
    calls = []
    monkeypatch.setattr(db_utils.time, "sleep", lambda delay: calls.append(delay))

    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        db_utils.run_db_write_with_retry(
            lambda: (_ for _ in ()).throw(sqlite3.OperationalError("no such table: missing")),
            attempts=4,
            delays=(0.1,),
        )

    assert calls == []


def test_audit_batch_insert_retries_transient_database_lock(monkeypatch):
    import services.audit_repository as repository

    class FakeCursor:
        def __init__(self, *, locked=False):
            self.locked = locked
            self.rowcount = 1
            self._last_sql = ""

        def execute(self, sql, params=()):
            self._last_sql = sql
            if self.locked and "INSERT OR IGNORE" in sql:
                raise sqlite3.OperationalError("database is locked")
            return self

        def fetchall(self):
            if "SELECT event_id" in self._last_sql:
                return [("audit-1",)]
            return []

    class FakeConnection:
        def __init__(self, *, locked=False):
            self.cursor_obj = FakeCursor(locked=locked)
            self.commits = 0
            self.rollbacks = 0

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

    connections = [FakeConnection(locked=True), FakeConnection(locked=False)]
    monkeypatch.setattr(repository, "get_conn", lambda: connections.pop(0))
    monkeypatch.setattr(db_utils.time, "sleep", lambda _delay: None)

    known = repository.insert_events_batch([
        ("operation", {"event_id": "audit-1", "success": True})
    ])

    assert known == {"audit-1"}
    assert len(connections) == 0
