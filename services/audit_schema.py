# -*- coding: utf-8 -*-
"""Idempotent SQLite schemas for durable audit history."""
from __future__ import annotations

import sqlite3
from pathlib import Path


def init_main_audit_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS operation_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            actor_type TEXT NOT NULL,
            actor_id INTEGER,
            actor_name TEXT,
            target_user_id INTEGER,
            target_username TEXT,
            target_phone TEXT,
            target_email TEXT,
            action_category TEXT NOT NULL,
            action_code TEXT NOT NULL,
            action_name TEXT NOT NULL,
            request_method TEXT,
            request_path TEXT,
            success INTEGER NOT NULL,
            status_code INTEGER,
            error_code TEXT,
            error_message TEXT,
            before_data_json TEXT,
            after_data_json TEXT,
            request_data_json TEXT,
            related_event_id TEXT,
            client_ip TEXT,
            forwarded_for TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS api_access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            request_id TEXT NOT NULL,
            principal_type TEXT NOT NULL,
            user_id INTEGER,
            username_snapshot TEXT,
            phone_snapshot TEXT,
            email_snapshot TEXT,
            auth_state TEXT NOT NULL,
            token_fingerprint TEXT,
            provider TEXT,
            api_name TEXT,
            route_rule TEXT,
            request_path TEXT NOT NULL,
            request_method TEXT NOT NULL,
            required_scope TEXT,
            package_code TEXT,
            request_params_json TEXT,
            content_type TEXT,
            status_code INTEGER NOT NULL,
            success INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL,
            error_code TEXT,
            error_message TEXT,
            client_ip TEXT,
            forwarded_for TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_maintenance_state (
            task_name TEXT PRIMARY KEY,
            last_started_at TEXT,
            last_completed_at TEXT,
            lease_until TEXT,
            last_result TEXT,
            deleted_rows INTEGER DEFAULT 0
        )
        """
    )

    indexes = (
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_created ON operation_audit_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_action_created ON operation_audit_logs(action_code, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_actor_created ON operation_audit_logs(actor_type, actor_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_target_created ON operation_audit_logs(target_user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_success_created ON operation_audit_logs(success, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_operation_audit_ip_created ON operation_audit_logs(client_ip, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_created ON api_access_logs(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_user_created ON api_access_logs(user_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_provider_created ON api_access_logs(provider, api_name, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_status_created ON api_access_logs(status_code, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_auth_created ON api_access_logs(auth_state, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_success_created ON api_access_logs(success, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_ip_created ON api_access_logs(client_ip, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_api_access_duration ON api_access_logs(duration_ms)",
    )
    for statement in indexes:
        cursor.execute(statement)


def init_spool_schema(db_file: str | Path, synchronous: str = "FULL") -> None:
    path = Path(db_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = str(synchronous or "FULL").upper()
    if mode not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
        mode = "FULL"
    conn = sqlite3.connect(path, timeout=10)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA synchronous={mode}")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_spool_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_attempt_at TEXT,
                next_retry_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_spool_dead_letters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                attempt_count INTEGER NOT NULL,
                last_attempt_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL,
                failed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_spool_due "
            "ON audit_spool_queue(next_retry_at, id)"
        )
        conn.commit()
    finally:
        conn.close()
