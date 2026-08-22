from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import services.audit_repository as repo
from services.audit_schema import init_main_audit_schema


def _conn(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_main_audit_schema(conn.cursor())
    conn.commit()
    return conn


def _operation(event_id: str, created_at: str, success: bool = True, **extra):
    return {
        "event_id": event_id,
        "actor_type": extra.get("actor_type", "admin"),
        "actor_id": extra.get("actor_id", 1),
        "actor_name": extra.get("actor_name", "admin"),
        "target_user_id": extra.get("target_user_id", 2),
        "target_username": extra.get("target_username", "alice"),
        "target_phone": extra.get("target_phone", "13812345678"),
        "target_email": extra.get("target_email", "alice@example.com"),
        "action_category": extra.get("action_category", "membership"),
        "action_code": extra.get("action_code", "admin.subscription_renew"),
        "action_name": extra.get("action_name", "套餐续费"),
        "request_method": "POST",
        "request_path": "/admin/members/open",
        "success": success,
        "status_code": 200 if success else 400,
        "error_code": "" if success else "validation_error",
        "error_message": "" if success else "bad input",
        "before_data": {"plan": "general_month"},
        "after_data": {"plan": "general_year"},
        "request_data": {"extra_days": 3},
        "related_event_id": "",
        "client_ip": "1.2.3.4",
        "forwarded_for": "",
        "user_agent": "pytest",
        "created_at": created_at,
    }


def _access(event_id: str, created_at: str, status: int = 200, **extra):
    return {
        "event_id": event_id,
        "request_id": "req-" + event_id,
        "principal_type": extra.get("principal_type", "user"),
        "user_id": extra.get("user_id", 2),
        "username_snapshot": extra.get("username_snapshot", "alice"),
        "phone_snapshot": extra.get("phone_snapshot", "13812345678"),
        "email_snapshot": extra.get("email_snapshot", "alice@example.com"),
        "auth_state": extra.get("auth_state", "valid"),
        "token_fingerprint": "abc",
        "provider": extra.get("provider", "tushare"),
        "api_name": extra.get("api_name", "daily"),
        "route_rule": "/api/v1/market/<provider>/<path:data_type>",
        "request_path": extra.get("request_path", "/api/v1/market/tushare/daily"),
        "request_method": extra.get("request_method", "GET"),
        "required_scope": "tushare:read",
        "package_code": "general_month",
        "request_params": {"trade_date": "20260718"},
        "content_type": "application/json",
        "status_code": status,
        "success": status < 400,
        "duration_ms": extra.get("duration_ms", 10),
        "error_code": "" if status < 400 else "request_failed",
        "error_message": "",
        "client_ip": extra.get("client_ip", "1.2.3.4"),
        "forwarded_for": "",
        "user_agent": "pytest",
        "created_at": created_at,
    }


def test_insert_is_idempotent_and_query_filters_decode_json(tmp_path, monkeypatch):
    conn = _conn(tmp_path / "main.db")
    monkeypatch.setattr(repo, "get_conn", lambda: conn)
    try:
        assert repo.insert_operation_event(_operation("op1", "2026-07-19 10:00:00")) is True
        assert repo.insert_operation_event(_operation("op1", "2026-07-19 10:00:00")) is False
        repo.insert_operation_event(_operation("op2", "2026-07-19 11:00:00", False, target_username="bob"))

        result = repo.query_operation_logs({"success": "0", "target": "bob"}, 1, 50)
        assert result["total"] == 1
        assert result["items"][0]["event_id"] == "op2"
        assert result["items"][0]["before_data"] == {"plan": "general_month"}
        assert result["stats"]["failure_count"] == 1
    finally:
        conn.close()


def test_api_query_filters_and_stats(tmp_path, monkeypatch):
    conn = _conn(tmp_path / "main.db")
    monkeypatch.setattr(repo, "get_conn", lambda: conn)
    try:
        repo.insert_api_access_event(_access("a1", "2026-07-19 10:00:00", 200, duration_ms=10))
        repo.insert_api_access_event(_access("a2", "2026-07-19 10:01:00", 401, user_id=None, principal_type="anonymous", auth_state="missing_token", duration_ms=30))
        repo.insert_api_access_event(_access("a3", "2026-07-19 10:02:00", 502, provider="kaipanla", api_name="morning_bidding", duration_ms=50))

        result = repo.query_api_access_logs({"provider": "kaipanla", "status_code": "502"}, 1, 20)
        assert result["total"] == 1
        assert result["items"][0]["event_id"] == "a3"
        assert result["items"][0]["request_params"] == {"trade_date": "20260718"}
        assert result["stats"]["failure_count"] == 1
        assert result["stats"]["server_error_count"] == 1
        assert result["stats"]["average_duration_ms"] == 50
    finally:
        conn.close()


def test_retention_deletes_only_strictly_older_rows_and_zero_means_keep(tmp_path, monkeypatch):
    conn = _conn(tmp_path / "main.db")
    monkeypatch.setattr(repo, "get_conn", lambda: conn)
    try:
        repo.insert_api_access_event(_access("old-api", "2026-06-18 23:59:59"))
        repo.insert_api_access_event(_access("edge-api", "2026-06-19 12:00:00"))
        repo.insert_operation_event(_operation("old-op", "2025-07-18 23:59:59"))
        repo.insert_operation_event(_operation("edge-op", "2025-07-19 12:00:00"))

        deleted = repo.delete_expired_audit_rows(
            datetime(2026, 7, 19, 12, 0, 0), api_days=30, operation_days=365, batch_size=1
        )
        assert deleted == {"api_access_logs": 1, "operation_audit_logs": 1}
        assert repo.get_api_access_log("old-api") is None
        assert repo.get_api_access_log("edge-api") is not None
        assert repo.get_operation_log("old-op") is None
        assert repo.get_operation_log("edge-op") is not None

        kept = repo.delete_expired_audit_rows(
            datetime(2027, 7, 19, 12, 0, 0), api_days=0, operation_days=0
        )
        assert kept == {"api_access_logs": 0, "operation_audit_logs": 0}
        assert repo.get_api_access_log("edge-api") is not None
        assert repo.get_operation_log("edge-op") is not None
    finally:
        conn.close()


def test_maintenance_lease_blocks_competitor_until_expired(tmp_path, monkeypatch):
    conn = _conn(tmp_path / "main.db")
    monkeypatch.setattr(repo, "get_conn", lambda: conn)
    try:
        now = datetime(2026, 7, 19, 12, 0, 0)
        assert repo.acquire_maintenance_lease("audit_cleanup", now, 60) is True
        assert repo.acquire_maintenance_lease("audit_cleanup", now, 60) is False
        assert repo.acquire_maintenance_lease("audit_cleanup", datetime(2026, 7, 19, 12, 1, 1), 60) is True
        repo.complete_maintenance_task("audit_cleanup", "ok", 7, datetime(2026, 7, 19, 12, 1, 2))
        row = conn.execute("SELECT * FROM audit_maintenance_state WHERE task_name='audit_cleanup'").fetchone()
        assert row["last_result"] == "ok"
        assert row["deleted_rows"] == 7
        assert row["lease_until"] is None
    finally:
        conn.close()


def test_cleanup_runner_skips_until_interval_then_records_completion(monkeypatch):
    from services import audit_cleanup

    calls = []
    monkeypatch.setattr(audit_cleanup, "get_maintenance_state", lambda task: {
        "last_completed_at": "2026-07-19 11:30:00", "lease_until": None,
    })
    monkeypatch.setattr(audit_cleanup, "acquire_maintenance_lease", lambda *args, **kwargs: calls.append("lease") or True)
    monkeypatch.setattr(audit_cleanup, "delete_expired_audit_rows", lambda **kwargs: calls.append(kwargs) or {"api_access_logs": 2, "operation_audit_logs": 3})
    monkeypatch.setattr(audit_cleanup, "complete_maintenance_task", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(audit_cleanup.config, "AUDIT_CLEANUP_INTERVAL_HOURS", 24)
    monkeypatch.setattr(audit_cleanup.config, "API_ACCESS_LOG_RETENTION_DAYS", 30)
    monkeypatch.setattr(audit_cleanup.config, "OPERATION_LOG_RETENTION_DAYS", 365)

    skipped = audit_cleanup.run_cleanup_once(datetime(2026, 7, 19, 12, 0, 0))
    assert skipped["ran"] is False
    assert calls == []

    monkeypatch.setattr(audit_cleanup, "get_maintenance_state", lambda task: {
        "last_completed_at": "2026-07-18 11:59:59", "lease_until": None,
    })
    result = audit_cleanup.run_cleanup_once(datetime(2026, 7, 19, 12, 0, 0))
    assert result == {"ran": True, "api_access_logs": 2, "operation_audit_logs": 3}
    assert calls[0] == "lease"
    assert calls[1]["api_days"] == 30
    assert calls[1]["operation_days"] == 365
