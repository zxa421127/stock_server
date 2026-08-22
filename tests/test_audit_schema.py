from __future__ import annotations

import sqlite3
from pathlib import Path

from services.audit_schema import init_main_audit_schema, init_spool_schema


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}


def test_main_audit_schema_is_idempotent_and_complete(tmp_path: Path):
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    try:
        init_main_audit_schema(conn.cursor())
        init_main_audit_schema(conn.cursor())
        conn.commit()

        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"operation_audit_logs", "api_access_logs", "audit_maintenance_state"} <= tables

        assert {
            "event_id", "actor_type", "actor_id", "actor_name", "target_user_id",
            "target_username", "target_phone", "target_email", "action_category",
            "action_code", "action_name", "request_method", "request_path", "success",
            "status_code", "error_code", "error_message", "before_data_json",
            "after_data_json", "request_data_json", "related_event_id", "client_ip",
            "forwarded_for", "user_agent", "created_at",
        } <= _columns(conn, "operation_audit_logs")
        assert {
            "event_id", "request_id", "principal_type", "user_id", "username_snapshot",
            "phone_snapshot", "email_snapshot", "auth_state", "token_fingerprint",
            "provider", "api_name", "route_rule", "request_path", "request_method",
            "required_scope", "package_code", "request_params_json", "content_type",
            "status_code", "success", "duration_ms", "error_code", "error_message",
            "client_ip", "forwarded_for", "user_agent", "created_at",
        } <= _columns(conn, "api_access_logs")
        assert "sqlite_autoindex_operation_audit_logs_1" in _indexes(conn, "operation_audit_logs")
        assert "sqlite_autoindex_api_access_logs_1" in _indexes(conn, "api_access_logs")
        assert "idx_operation_audit_created" in _indexes(conn, "operation_audit_logs")
        assert "idx_api_access_created" in _indexes(conn, "api_access_logs")
    finally:
        conn.close()


def test_spool_schema_is_idempotent_and_has_unique_event_ids(tmp_path: Path):
    db = tmp_path / "audit_spool.db"
    init_spool_schema(db, synchronous="FULL")
    init_spool_schema(db, synchronous="FULL")

    conn = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"audit_spool_queue", "audit_spool_dead_letters"} <= tables
        assert {
            "event_id", "event_type", "payload_json", "attempt_count", "last_attempt_at",
            "next_retry_at", "last_error", "created_at",
        } <= _columns(conn, "audit_spool_queue")
        assert "sqlite_autoindex_audit_spool_queue_1" in _indexes(conn, "audit_spool_queue")
        assert "sqlite_autoindex_audit_spool_dead_letters_1" in _indexes(conn, "audit_spool_dead_letters")
    finally:
        conn.close()
