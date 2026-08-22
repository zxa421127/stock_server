# -*- coding: utf-8 -*-
"""SQLite persistence for the administrator market-interface tester."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def create_admin_api_test_tables(cursor: sqlite3.Cursor) -> None:
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_api_test_batches (
            id TEXT PRIMARY KEY,
            parent_batch_id TEXT,
            kind TEXT NOT NULL DEFAULT 'batch',
            status TEXT NOT NULL DEFAULT 'queued',
            requested_by TEXT NOT NULL DEFAULT 'admin',
            requested_interfaces_json TEXT NOT NULL DEFAULT '[]',
            spec_version TEXT NOT NULL DEFAULT '',
            release_id TEXT NOT NULL DEFAULT '',
            total_count INTEGER NOT NULL DEFAULT 0,
            completed_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            skipped_count INTEGER NOT NULL DEFAULT 0,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            retention_days INTEGER NOT NULL DEFAULT 30,
            expires_at TEXT,
            is_locked INTEGER NOT NULL DEFAULT 0,
            locked_at TEXT,
            locked_by TEXT NOT NULL DEFAULT '',
            lock_reason TEXT NOT NULL DEFAULT '',
            cleanup_status TEXT NOT NULL DEFAULT 'active',
            result_dir TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(parent_batch_id) REFERENCES admin_api_test_batches(id)
        );

        CREATE TABLE IF NOT EXISTS admin_api_test_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            api_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'upstream',
            status TEXT NOT NULL DEFAULT 'queued',
            params_json TEXT NOT NULL DEFAULT '{}',
            fields_json TEXT NOT NULL DEFAULT '[]',
            spec_version TEXT NOT NULL DEFAULT '',
            spec_hash TEXT NOT NULL DEFAULT '',
            attempt_no INTEGER NOT NULL DEFAULT 1,
            http_status INTEGER,
            row_count INTEGER NOT NULL DEFAULT 0,
            column_count INTEGER NOT NULL DEFAULT 0,
            elapsed_ms REAL NOT NULL DEFAULT 0,
            cache_hit INTEGER NOT NULL DEFAULT 0,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            actual_trade_date TEXT NOT NULL DEFAULT '',
            result_dir TEXT NOT NULL DEFAULT '',
            request_file_path TEXT NOT NULL DEFAULT '',
            result_file_path TEXT NOT NULL DEFAULT '',
            schema_file_path TEXT NOT NULL DEFAULT '',
            csv_file_path TEXT NOT NULL DEFAULT '',
            result_size_bytes INTEGER NOT NULL DEFAULT 0,
            result_sha256 TEXT NOT NULL DEFAULT '',
            error_code TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(batch_id, provider, api_name, attempt_no),
            FOREIGN KEY(batch_id) REFERENCES admin_api_test_batches(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS admin_api_test_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS admin_api_test_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            item_id INTEGER,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES admin_api_test_batches(id) ON DELETE CASCADE,
            FOREIGN KEY(item_id) REFERENCES admin_api_test_items(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_admin_api_test_batches_status
            ON admin_api_test_batches(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_admin_api_test_batches_expiry
            ON admin_api_test_batches(is_locked, cleanup_status, expires_at);
        CREATE INDEX IF NOT EXISTS idx_admin_api_test_items_batch
            ON admin_api_test_items(batch_id, id);
        CREATE INDEX IF NOT EXISTS idx_admin_api_test_items_status
            ON admin_api_test_items(batch_id, status);
        CREATE INDEX IF NOT EXISTS idx_admin_api_test_events_batch
            ON admin_api_test_events(batch_id, id);
        """
    )


class AdminApiTestRepository:
    FAILURE_STATUSES = {
        "permission_denied", "scope_denied", "invalid_params", "unsupported",
        "timeout", "upstream_error", "schema_mismatch", "result_too_large",
        "internal_error", "storage_error",
    }

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        if connection_factory is None:
            from db_utils import get_conn
            connection_factory = get_conn
        self._connection_factory = connection_factory

    def _conn(self) -> sqlite3.Connection:
        conn = self._connection_factory()
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _batch(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["cancel_requested"] = bool(result.get("cancel_requested"))
        result["is_locked"] = bool(result.get("is_locked"))
        result["requested_interfaces"] = _loads(result.pop("requested_interfaces_json", "[]"), [])
        return result

    @staticmethod
    def _item(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["params"] = _loads(result.pop("params_json", "{}"), {})
        result["fields"] = _loads(result.pop("fields_json", "[]"), [])
        result["cache_hit"] = bool(result.get("cache_hit"))
        result["fallback_used"] = bool(result.get("fallback_used"))
        return result

    @staticmethod
    def _event(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["payload"] = _loads(result.pop("payload_json", "{}"), {})
        return result


    def get_setting(self, key: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT setting_key,setting_value,updated_at,updated_by "
            "FROM admin_api_test_settings WHERE setting_key=?",
            (str(key),),
        ).fetchone()
        return dict(row) if row is not None else None

    def set_setting(self, key: str, value: Any, *, updated_by: str) -> dict[str, Any]:
        now = _now()
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO admin_api_test_settings(setting_key,setting_value,updated_at,updated_by)
            VALUES(?,?,?,?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value=excluded.setting_value,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by
            """,
            (str(key), str(value), now, str(updated_by or "admin")),
        )
        conn.commit()
        return self.get_setting(key) or {}

    def get_default_retention_days(self, fallback: int = 30) -> int:
        fallback = max(1, min(int(fallback), 36500))
        row = self.get_setting("default_retention_days")
        if not row:
            return fallback
        try:
            days = int(row.get("setting_value"))
        except (TypeError, ValueError):
            return fallback
        return days if 1 <= days <= 36500 else fallback

    def set_default_retention_days(self, days: int, *, updated_by: str) -> dict[str, Any]:
        try:
            value = int(days)
        except (TypeError, ValueError) as exc:
            raise ValueError("默认保留天数必须为1到36500之间的整数") from exc
        if not 1 <= value <= 36500:
            raise ValueError("默认保留天数必须为1到36500之间的整数")
        row = self.set_setting("default_retention_days", value, updated_by=updated_by)
        return {
            "days": value,
            "updated_at": row.get("updated_at", ""),
            "updated_by": row.get("updated_by", ""),
        }

    def create_batch(
        self, *, batch_id: str, kind: str, requested_by: str, spec_version: str,
        total_count: int, retention_days: int, parent_batch_id: str | None = None,
        requested_interfaces: list[dict[str, str]] | None = None, release_id: str = "",
        result_dir: str = "",
    ) -> dict[str, Any]:
        now = _now()
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO admin_api_test_batches(
                id,parent_batch_id,kind,status,requested_by,requested_interfaces_json,
                spec_version,release_id,total_count,retention_days,result_dir,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (batch_id, parent_batch_id, kind, "queued", requested_by,
             _dumps(requested_interfaces or []), spec_version, release_id,
             int(total_count), int(retention_days), result_dir, now, now),
        )
        conn.commit()
        return self.get_batch(batch_id) or {}

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        row = self._conn().execute("SELECT * FROM admin_api_test_batches WHERE id=?", (batch_id,)).fetchone()
        return self._batch(row)

    def list_batches(self, *, limit: int = 100, status: str = "") -> list[dict[str, Any]]:
        conn = self._conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM admin_api_test_batches WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, max(1, min(int(limit), 1000))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM admin_api_test_batches ORDER BY created_at DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
        return [self._batch(row) for row in rows if row is not None]

    def update_batch(self, batch_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "completed_count", "success_count", "failure_count", "skipped_count",
            "cancel_requested", "retention_days", "expires_at", "is_locked", "locked_at",
            "locked_by", "lock_reason", "cleanup_status", "result_dir", "error_message",
            "started_at", "finished_at", "total_count", "spec_version", "release_id",
        }
        values = {key: value for key, value in fields.items() if key in allowed}
        if not values:
            return self.get_batch(batch_id)
        for key in ("cancel_requested", "is_locked"):
            if key in values:
                values[key] = 1 if values[key] else 0
        values["updated_at"] = _now()
        sql = "UPDATE admin_api_test_batches SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?"
        conn = self._conn()
        conn.execute(sql, (*values.values(), batch_id))
        conn.commit()
        return self.get_batch(batch_id)

    def request_cancel(self, batch_id: str) -> dict[str, Any] | None:
        batch = self.get_batch(batch_id)
        if not batch:
            return None
        status = "cancelling" if batch["status"] in {"queued", "running"} else batch["status"]
        updated = self.update_batch(batch_id, cancel_requested=True, status=status)
        self.add_event(batch_id, "cancel_requested", {})
        return updated

    def lock_batch(self, batch_id: str, *, locked_by: str, reason: str) -> dict[str, Any] | None:
        updated = self.update_batch(
            batch_id, is_locked=True, locked_at=_now(), locked_by=locked_by,
            lock_reason=reason.strip(),
        )
        if updated:
            self.add_event(batch_id, "locked", {"by": locked_by, "reason": reason.strip()})
        return updated

    def unlock_batch(self, batch_id: str) -> dict[str, Any] | None:
        batch = self.get_batch(batch_id)
        if not batch:
            return None
        retention = int(batch.get("retention_days") or 30)
        expires = (datetime.now() + timedelta(days=retention)).strftime("%Y-%m-%d %H:%M:%S")
        updated = self.update_batch(
            batch_id, is_locked=False, locked_at=None, locked_by="", lock_reason="", expires_at=expires,
        )
        self.add_event(batch_id, "unlocked", {"expires_at": expires})
        return updated

    def set_retention_days(self, batch_id: str, days: int) -> dict[str, Any] | None:
        days = int(days)
        if days < 1 or days > 36500:
            raise ValueError("保留天数必须为1到36500之间的整数")
        batch = self.get_batch(batch_id)
        if not batch:
            return None
        expires = batch.get("expires_at")
        if not batch.get("is_locked") and batch.get("finished_at"):
            base = datetime.strptime(batch["finished_at"], "%Y-%m-%d %H:%M:%S")
            expires = (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        updated = self.update_batch(batch_id, retention_days=days, expires_at=expires)
        self.add_event(batch_id, "retention_changed", {"days": days, "expires_at": expires})
        return updated

    def create_item(
        self, *, batch_id: str, provider: str, api_name: str, title: str,
        category: str, mode: str, params: dict[str, Any], fields: list[str],
        spec_version: str, spec_hash: str, attempt_no: int = 1,
    ) -> dict[str, Any]:
        now = _now()
        conn = self._conn()
        cursor = conn.execute(
            """
            INSERT INTO admin_api_test_items(
                batch_id,provider,api_name,title,category,mode,status,params_json,fields_json,
                spec_version,spec_hash,attempt_no,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (batch_id, provider, api_name, title, category, mode, "queued",
             _dumps(params), _dumps(fields), spec_version, spec_hash, int(attempt_no), now, now),
        )
        conn.commit()
        return self.get_item(int(cursor.lastrowid)) or {}

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        row = self._conn().execute("SELECT * FROM admin_api_test_items WHERE id=?", (int(item_id),)).fetchone()
        return self._item(row)

    def list_items(self, batch_id: str) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT * FROM admin_api_test_items WHERE batch_id=? ORDER BY id", (batch_id,)
        ).fetchall()
        return [self._item(row) for row in rows if row is not None]

    def list_queued_items(self, batch_id: str) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT * FROM admin_api_test_items WHERE batch_id=? AND status='queued' ORDER BY id", (batch_id,)
        ).fetchall()
        return [self._item(row) for row in rows if row is not None]

    def list_failed_items(self, batch_id: str) -> list[dict[str, Any]]:
        marks = ",".join("?" for _ in self.FAILURE_STATUSES)
        rows = self._conn().execute(
            f"SELECT * FROM admin_api_test_items WHERE batch_id=? AND status IN ({marks}) ORDER BY id",
            (batch_id, *sorted(self.FAILURE_STATUSES)),
        ).fetchall()
        return [self._item(row) for row in rows if row is not None]

    def update_item(self, item_id: int, **fields: Any) -> dict[str, Any] | None:
        allowed = {
            "status", "params_json", "fields_json", "http_status", "row_count", "column_count",
            "elapsed_ms", "cache_hit", "fallback_used", "actual_trade_date", "result_dir",
            "request_file_path", "result_file_path", "schema_file_path", "csv_file_path",
            "result_size_bytes", "result_sha256", "error_code", "error_message",
            "started_at", "finished_at", "spec_version", "spec_hash",
        }
        values = {key: value for key, value in fields.items() if key in allowed}
        if "params" in fields:
            values["params_json"] = _dumps(fields["params"])
        if "fields" in fields:
            values["fields_json"] = _dumps(fields["fields"])
        for key in ("cache_hit", "fallback_used"):
            if key in values:
                values[key] = 1 if values[key] else 0
        if not values:
            return self.get_item(item_id)
        values["updated_at"] = _now()
        sql = "UPDATE admin_api_test_items SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?"
        conn = self._conn()
        conn.execute(sql, (*values.values(), int(item_id)))
        conn.commit()
        return self.get_item(item_id)

    def add_event(self, batch_id: str, event_type: str, payload: dict[str, Any], item_id: int | None = None) -> dict[str, Any]:
        conn = self._conn()
        cursor = conn.execute(
            "INSERT INTO admin_api_test_events(batch_id,item_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
            (batch_id, item_id, event_type, _dumps(payload), _now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM admin_api_test_events WHERE id=?", (cursor.lastrowid,)).fetchone()
        return self._event(row) or {}

    def list_events(self, batch_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT * FROM admin_api_test_events WHERE batch_id=? ORDER BY id DESC LIMIT ?",
            (batch_id, max(1, min(int(limit), 5000))),
        ).fetchall()
        return [self._event(row) for row in reversed(rows) if row is not None]

    def recalculate_batch_counts(self, batch_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        rows = conn.execute(
            "SELECT status,COUNT(*) AS n FROM admin_api_test_items WHERE batch_id=? GROUP BY status",
            (batch_id,),
        ).fetchall()
        counts = {str(row["status"]): int(row["n"]) for row in rows}
        completed = sum(n for status, n in counts.items() if status not in {"queued", "running"})
        success = sum(counts.get(status, 0) for status in {"success_data", "success_empty", "success_fallback"})
        skipped = sum(counts.get(status, 0) for status in {"cancelled", "spec_change_pending"})
        failure = sum(counts.get(status, 0) for status in self.FAILURE_STATUSES)
        return self.update_batch(
            batch_id, completed_count=completed, success_count=success,
            failure_count=failure, skipped_count=skipped,
        )

    def expired_batches(self, *, now: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        now = now or _now()
        rows = self._conn().execute(
            """
            SELECT * FROM admin_api_test_batches
            WHERE is_locked=0 AND cleanup_status IN ('active','delete_failed')
              AND status IN ('completed','completed_with_failures','cancelled','failed')
              AND expires_at IS NOT NULL AND expires_at<?
            ORDER BY expires_at LIMIT ?
            """,
            (now, max(1, min(int(limit), 1000))),
        ).fetchall()
        return [self._batch(row) for row in rows if row is not None]

    def delete_batch_metadata(self, batch_id: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM admin_api_test_batches WHERE id=?", (batch_id,))
        conn.commit()

    def recover_interrupted_batches(self) -> list[str]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT id FROM admin_api_test_batches WHERE status IN ('running','cancelling')"
        ).fetchall()
        ids = [str(row["id"]) for row in rows]
        now = _now()
        for batch_id in ids:
            conn.execute(
                "UPDATE admin_api_test_batches SET status='queued',cancel_requested=0,error_message=?,updated_at=? WHERE id=?",
                ("服务重启后重新排队", now, batch_id),
            )
            conn.execute(
                "UPDATE admin_api_test_items SET status='queued',updated_at=? WHERE batch_id=? AND status='running'",
                (now, batch_id),
            )
        conn.commit()
        return ids
