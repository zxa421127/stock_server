from __future__ import annotations

import gc
import tempfile
import time
from pathlib import Path

import pytest

import db_utils
from services import admin_user_service as service


@pytest.fixture()
def isolated_db(monkeypatch):
    old_db = db_utils.DB_FILE
    old_service_db = getattr(service.db_utils, "DB_FILE", old_db)
    tempdir = tempfile.TemporaryDirectory()
    db_path = str(Path(tempdir.name) / "admin-user-center.db")

    db_utils.close_thread_connection()
    db_utils._db_pragmas_initialized = False
    monkeypatch.setattr(db_utils, "DB_FILE", db_path)
    monkeypatch.setattr(service.db_utils, "DB_FILE", db_path)
    db_utils.init_db()
    test_conn = db_utils.get_conn()

    try:
        yield test_conn
    finally:
        # Windows does not allow TemporaryDirectory to remove an SQLite file
        # while any connection still owns a file handle. Close both the exact
        # fixture connection and the current thread-local connection before
        # restoring the original database path.
        current_conn = getattr(db_utils._local, "conn", None)
        closed_ids: set[int] = set()
        for connection in (current_conn, test_conn):
            if connection is None or id(connection) in closed_ids:
                continue
            closed_ids.add(id(connection))
            try:
                connection.rollback()
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass

        db_utils._local.conn = None
        db_utils._db_pragmas_initialized = False
        db_utils.DB_FILE = old_db
        service.db_utils.DB_FILE = old_service_db

        # Cursor finalizers and Windows filesystem/antivirus filters can release
        # the last handle a few milliseconds after Connection.close(). Retry the
        # cleanup briefly instead of turning a successful test into a flaky error.
        cleanup_error: PermissionError | None = None
        for _ in range(20):
            try:
                gc.collect()
                tempdir.cleanup()
                cleanup_error = None
                break
            except PermissionError as exc:
                cleanup_error = exc
                time.sleep(0.05)
        if cleanup_error is not None:
            raise cleanup_error


def _insert_user(conn, *, username="alice", phone="13800000000", email="Alice@Example.com", source="self", status="active") -> int:
    conn.execute(
        "INSERT INTO users(username,phone,email,taobao_nick,register_source,status,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (username, phone, email, "旧昵称", source, status, "2026-07-01 10:00:00", "2026-07-01 10:00:00"),
    )
    conn.commit()
    return int(conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()[0])


def test_normalize_profile_input_trims_and_normalizes_email():
    current = {"register_source": "self"}
    normalized = service.normalize_profile_input(current, {
        "phone": " 13800138000 ",
        "email": " Admin@Example.COM ",
        "taobao_nick": "  淘宝昵称  ",
        "register_source": "admin",
    })
    assert normalized == {
        "phone": "13800138000",
        "email": "admin@example.com",
        "taobao_nick": "淘宝昵称",
        "register_source": "admin",
    }


@pytest.mark.parametrize("payload,code", [
    ({"email": "not-an-email"}, "invalid_email"),
    ({"phone": "1" * 65}, "phone_too_long"),
    ({"email": "a" * 250 + "@x.com"}, "email_too_long"),
    ({"taobao_nick": "淘" * 129}, "taobao_nick_too_long"),
    ({"register_source": "invented"}, "invalid_register_source"),
])
def test_normalize_profile_input_rejects_invalid_values(payload, code):
    with pytest.raises(service.UserProfileValidationError) as exc:
        service.normalize_profile_input({"register_source": "self"}, payload)
    assert exc.value.code == code


def test_unknown_existing_register_source_can_be_preserved():
    normalized = service.normalize_profile_input(
        {"register_source": "legacy_custom"},
        {"phone": "", "email": "", "taobao_nick": "", "register_source": "legacy_custom"},
    )
    assert normalized["register_source"] == "legacy_custom"


def test_update_profile_rejects_duplicate_phone_and_case_insensitive_email(isolated_db):
    first = _insert_user(isolated_db, username="first", phone="13800000001", email="first@example.com")
    second = _insert_user(isolated_db, username="second", phone="13800000002", email="SECOND@EXAMPLE.COM")

    with pytest.raises(service.UserProfileConflictError) as phone_exc:
        service.update_user_profile(first, {"phone": "13800000002", "email": "first@example.com", "taobao_nick": "", "register_source": "self"})
    assert phone_exc.value.code == "duplicate_phone"

    with pytest.raises(service.UserProfileConflictError) as email_exc:
        service.update_user_profile(first, {"phone": "13800000001", "email": "second@example.com", "taobao_nick": "", "register_source": "self"})
    assert email_exc.value.code == "duplicate_email"
    assert db_utils.get_user_by_id(second)["email"] == "SECOND@EXAMPLE.COM"


def test_update_profile_returns_before_after_and_changed_fields(isolated_db):
    user_id = _insert_user(isolated_db)
    result = service.update_user_profile(user_id, {
        "phone": " 13900139000 ",
        "email": " NEW@Example.com ",
        "taobao_nick": " 新昵称 ",
        "register_source": "admin",
    })
    assert result["before"]["phone"] == "13800000000"
    assert result["after"]["phone"] == "13900139000"
    assert result["after"]["email"] == "new@example.com"
    assert set(result["changed_fields"]) == {"phone", "email", "taobao_nick", "register_source"}
    stored = db_utils.get_user_by_id(user_id)
    assert stored["taobao_nick"] == "新昵称"


def test_set_user_status_changes_only_user_record(isolated_db):
    user_id = _insert_user(isolated_db)
    isolated_db.execute("INSERT INTO api_keys(user_id,token,status,created_at) VALUES(?,?,?,?)", (user_id, "TOKEN-A", "active", "2026-07-01"))
    isolated_db.execute(
        "INSERT INTO subscriptions(user_id,plan_code,plan_type,start_time,expire_time,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (user_id, "general_month", "general", "2026-07-01 00:00:00", "2099-01-01 00:00:00", "active", "2026-07-01", "2026-07-01"),
    )
    isolated_db.commit()

    result = service.set_user_status(user_id, "disabled")
    assert result["before"]["status"] == "active"
    assert result["after"]["status"] == "disabled"
    assert isolated_db.execute("SELECT status FROM api_keys WHERE user_id=?", (user_id,)).fetchone()[0] == "active"
    assert isolated_db.execute("SELECT status FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()[0] == "active"

    enabled = service.set_user_status(user_id, "active")
    assert enabled["after"]["status"] == "active"


def test_get_admin_user_detail_aggregates_token_and_plan_summary(isolated_db):
    user_id = _insert_user(isolated_db)
    isolated_db.execute("INSERT INTO api_keys(user_id,token,status,created_at) VALUES(?,?,?,?)", (user_id, "TOKEN-A", "active", "2026-07-01"))
    isolated_db.execute("INSERT INTO api_keys(user_id,token,status,created_at) VALUES(?,?,?,?)", (user_id, "TOKEN-B", "disabled", "2026-07-02"))
    isolated_db.execute(
        "INSERT INTO subscriptions(user_id,plan_code,plan_type,start_time,expire_time,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (user_id, "general_month", "general", "2026-07-01 00:00:00", "2099-01-01 00:00:00", "active", "2026-07-01", "2026-07-01"),
    )
    isolated_db.commit()
    detail = service.get_admin_user_detail(user_id)
    assert detail["user"]["username"] == "alice"
    assert detail["token_summary"] == {"total": 2, "active": 1, "disabled": 1}
    assert detail["current_subscription"]["plan_code"] == "general_month"


def test_sync_user_profile_to_feishu_reports_disabled_success_and_failure(monkeypatch):
    monkeypatch.setattr(service.config, "ENABLE_FEISHU_SYNC", False)
    assert service.sync_user_profile_to_feishu(5)["status"] == "disabled"

    monkeypatch.setattr(service.config, "ENABLE_FEISHU_SYNC", True)
    import services.feishu_sync_service as feishu
    monkeypatch.setattr(feishu, "sync_single_user_to_feishu", lambda user_id: "updated")
    success = service.sync_user_profile_to_feishu(5)
    assert success == {"status": "success", "result": "updated", "error": ""}

    monkeypatch.setattr(feishu, "sync_single_user_to_feishu", lambda user_id: (_ for _ in ()).throw(RuntimeError("network down")))
    failed = service.sync_user_profile_to_feishu(5)
    assert failed["status"] == "failed"
    assert "network down" in failed["error"]
