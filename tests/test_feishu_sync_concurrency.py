# -*- coding: utf-8 -*-
from __future__ import annotations

import multiprocessing
import threading

from services.process_lock import process_lock
from services.sync_result import SyncResult


def _hold_lock_in_child(path: str, ready, release) -> None:
    with process_lock(path, timeout=0.0) as acquired:
        ready.put(acquired)
        if acquired:
            release.wait(timeout=5)



def test_sync_result_remains_tuple_compatible_and_exposes_status():
    result = SyncResult((0, 0), status="database_busy", message="数据库繁忙")

    added, linked = result
    assert (added, linked) == (0, 0)
    assert result == (0, 0)
    assert result.status == "database_busy"
    assert result.message == "数据库繁忙"
    assert result.success is False
    assert "database_busy" in str(result)


def test_process_lock_blocks_second_thread_for_same_file(tmp_path):
    lock_path = tmp_path / "feishu_sync.lock"
    first_entered = threading.Event()
    release_first = threading.Event()
    outcomes: list[tuple[str, bool]] = []

    def first_worker():
        with process_lock(lock_path, timeout=0.0) as acquired:
            outcomes.append(("first", acquired))
            first_entered.set()
            release_first.wait(timeout=5)

    thread = threading.Thread(target=first_worker)
    thread.start()
    assert first_entered.wait(timeout=2)

    with process_lock(lock_path, timeout=0.0) as acquired:
        outcomes.append(("second", acquired))

    release_first.set()
    thread.join(timeout=2)

    assert outcomes == [("first", True), ("second", False)]


def test_process_lock_can_be_reacquired_after_release(tmp_path):
    lock_path = tmp_path / "feishu_sync.lock"

    with process_lock(lock_path, timeout=0.0) as first:
        assert first is True

    with process_lock(lock_path, timeout=0.0) as second:
        assert second is True


def test_local_publish_does_not_run_full_database_initialization(tmp_path, monkeypatch):
    import services.feishu_sync_service as sync_service

    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_FILE", str(tmp_path / "sync.lock"), raising=False)
    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_TIMEOUT_SECONDS", 0.0, raising=False)
    monkeypatch.setattr(sync_service, "_feishu_config_ready", lambda: True)
    monkeypatch.setattr(
        sync_service,
        "init_db",
        lambda: (_ for _ in ()).throw(AssertionError("runtime sync must not call init_db")),
        raising=False,
    )
    monkeypatch.setattr(sync_service, "_ensure_runtime_db_ready", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(sync_service, "_get_local_member_rows", lambda _user_id=None: [])
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: object())

    result = sync_service.sync_local_to_feishu()

    assert result == (0, 0, 0)
    assert result.status == "empty"


def test_second_sync_returns_busy_without_calling_feishu(tmp_path, monkeypatch):
    import services.feishu_sync_service as sync_service

    lock_path = tmp_path / "sync.lock"
    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_FILE", str(lock_path), raising=False)
    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_TIMEOUT_SECONDS", 0.0, raising=False)
    monkeypatch.setattr(sync_service, "_feishu_config_ready", lambda: True)
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: (_ for _ in ()).throw(AssertionError("must not call Feishu")))

    with process_lock(lock_path, timeout=0.0) as acquired:
        assert acquired is True
        result = sync_service.sync_local_to_feishu()

    assert result == (0, 0, 0)
    assert result.status == "busy"
    assert result.success is False


def test_reverse_import_reports_database_busy_instead_of_plain_zero_tuple(tmp_path, monkeypatch):
    import sqlite3
    import services.feishu_sync_service as sync_service

    class FakeBitable:
        def list_all_records(self):
            return [("rec-new", {"用户名称": "new", "手机号": "13800009999"})]

    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_FILE", str(tmp_path / "sync.lock"), raising=False)
    monkeypatch.setattr(sync_service.config, "FEISHU_SYNC_LOCK_TIMEOUT_SECONDS", 0.0, raising=False)
    monkeypatch.setattr(sync_service, "_feishu_config_ready", lambda: True)
    monkeypatch.setattr(sync_service, "_ensure_runtime_db_ready", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(sync_service, "get_bitable_manager", lambda: FakeBitable())
    monkeypatch.setattr(
        sync_service,
        "_find_unique_local_user_by_identity",
        lambda cursor, **kwargs: (None, "not_found"),
    )
    monkeypatch.setattr(
        sync_service,
        "_create_feishu_user_atomic",
        lambda **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")),
        raising=False,
    )
    monkeypatch.setattr(sync_service, "get_conn", lambda: type("Conn", (), {"cursor": lambda self: type("Cursor", (), {})()})())

    result = sync_service.sync_feishu_to_local()

    assert result == (0, 0)
    assert result.status == "database_busy"
    assert "数据库" in result.message


def test_process_lock_blocks_another_process(tmp_path):
    ctx = multiprocessing.get_context("spawn")
    ready = ctx.Queue()
    release = ctx.Event()
    lock_path = str(tmp_path / "cross-process.lock")
    child = ctx.Process(target=_hold_lock_in_child, args=(lock_path, ready, release))
    child.start()
    assert ready.get(timeout=5) is True

    with process_lock(lock_path, timeout=0.0) as acquired:
        assert acquired is False

    release.set()
    child.join(timeout=5)
    assert child.exitcode == 0
