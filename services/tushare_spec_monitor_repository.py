# -*- coding: utf-8 -*-
"""SQLite persistence for scheduled Tushare official-spec monitoring."""
from __future__ import annotations

import json
import sqlite3
import uuid
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


def create_tushare_spec_monitor_tables(cursor: sqlite3.Cursor) -> None:
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS tushare_spec_scan_runs (
            id TEXT PRIMARY KEY,
            trigger_type TEXT NOT NULL DEFAULT 'scheduled',
            status TEXT NOT NULL DEFAULT 'running',
            target_count INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            changed_count INTEGER NOT NULL DEFAULT 0,
            unchanged_count INTEGER NOT NULL DEFAULT 0,
            error_summary TEXT NOT NULL DEFAULT '',
            next_scheduled_at TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tushare_spec_snapshots (
            provider TEXT NOT NULL DEFAULT 'tushare',
            api_name TEXT NOT NULL,
            official_url TEXT NOT NULL DEFAULT '',
            raw_content_hash TEXT NOT NULL DEFAULT '',
            semantic_spec_hash TEXT NOT NULL DEFAULT '',
            parsed_spec_json TEXT NOT NULL DEFAULT '{}',
            source_format TEXT NOT NULL DEFAULT '',
            fetched_at TEXT NOT NULL DEFAULT '',
            scan_run_id TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(provider, api_name)
        );

        CREATE TABLE IF NOT EXISTS tushare_spec_change_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL DEFAULT 'tushare',
            api_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            semantic_spec_hash TEXT NOT NULL DEFAULT '',
            severity TEXT NOT NULL DEFAULT 'info',
            status TEXT NOT NULL DEFAULT 'new',
            diffs_json TEXT NOT NULL DEFAULT '[]',
            scan_run_id TEXT NOT NULL DEFAULT '',
            candidate_version TEXT NOT NULL DEFAULT '',
            release_version TEXT NOT NULL DEFAULT '',
            verification_error TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            viewed_at TEXT,
            synchronized_at TEXT,
            published_at TEXT,
            verified_at TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(provider, api_name, semantic_spec_hash)
        );

        CREATE TABLE IF NOT EXISTS tushare_spec_monitor_leases (
            lease_key TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tushare_spec_scan_runs_started
            ON tushare_spec_scan_runs(started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_tushare_spec_alerts_status
            ON tushare_spec_change_alerts(status, last_seen_at DESC);
        CREATE INDEX IF NOT EXISTS idx_tushare_spec_alerts_api
            ON tushare_spec_change_alerts(provider, api_name, last_seen_at DESC);
        """
    )


class TushareSpecMonitorRepository:
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection] | None = None):
        if connection_factory is None:
            from db_utils import get_conn
            connection_factory = get_conn
        self.connection_factory = connection_factory
        self._ensure_tables()

    def _conn(self) -> sqlite3.Connection:
        return self.connection_factory()

    def _ensure_tables(self) -> None:
        conn = self._conn()
        create_tushare_spec_monitor_tables(conn.cursor())
        conn.commit()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        value = dict(row)
        if "parsed_spec_json" in value:
            value["parsed_spec"] = _loads(value.pop("parsed_spec_json"), {})
        if "diffs_json" in value:
            value["diffs"] = _loads(value.pop("diffs_json"), [])
        return value

    def start_scan_run(self, *, trigger: str, target_count: int, next_scheduled_at: str = "") -> dict[str, Any]:
        conn = self._conn()
        now = _now()
        run_id = f"TS-SCAN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO tushare_spec_scan_runs
               (id, trigger_type, status, target_count, next_scheduled_at, started_at, created_at, updated_at)
               VALUES (?, ?, 'running', ?, ?, ?, ?, ?)""",
            (run_id, str(trigger or "manual"), int(target_count), str(next_scheduled_at or ""), now, now, now),
        )
        conn.commit()
        return self.get_scan_run(run_id) or {}

    def finish_scan_run(
        self, run_id: str, *, status: str, success_count: int, failure_count: int,
        changed_count: int, unchanged_count: int = 0, error_summary: str = "",
        next_scheduled_at: str = "",
    ) -> dict[str, Any]:
        conn = self._conn()
        now = _now()
        conn.execute(
            """UPDATE tushare_spec_scan_runs
               SET status=?, success_count=?, failure_count=?, changed_count=?, unchanged_count=?,
                   error_summary=?, next_scheduled_at=?, finished_at=?, updated_at=?
               WHERE id=?""",
            (status, int(success_count), int(failure_count), int(changed_count), int(unchanged_count),
             str(error_summary or ""), str(next_scheduled_at or ""), now, now, run_id),
        )
        conn.commit()
        return self.get_scan_run(run_id) or {}

    def get_scan_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._conn().execute("SELECT * FROM tushare_spec_scan_runs WHERE id=?", (run_id,)).fetchone()
        return self._row(row)

    def latest_scan_run(self) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT * FROM tushare_spec_scan_runs ORDER BY started_at DESC, created_at DESC LIMIT 1"
        ).fetchone()
        return self._row(row)

    def list_scan_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT * FROM tushare_spec_scan_runs ORDER BY started_at DESC LIMIT ?", (max(1, min(int(limit), 200)),)
        ).fetchall()
        return [self._row(row) or {} for row in rows]

    def upsert_snapshot(
        self, *, provider: str, api_name: str, official_url: str,
        raw_content_hash: str, semantic_spec_hash: str, parsed_spec: dict[str, Any],
        source_format: str, fetched_at: str, scan_run_id: str,
    ) -> dict[str, Any]:
        conn = self._conn()
        now = _now()
        conn.execute(
            """INSERT INTO tushare_spec_snapshots
               (provider, api_name, official_url, raw_content_hash, semantic_spec_hash,
                parsed_spec_json, source_format, fetched_at, scan_run_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(provider, api_name) DO UPDATE SET
                 official_url=excluded.official_url,
                 raw_content_hash=excluded.raw_content_hash,
                 semantic_spec_hash=excluded.semantic_spec_hash,
                 parsed_spec_json=excluded.parsed_spec_json,
                 source_format=excluded.source_format,
                 fetched_at=excluded.fetched_at,
                 scan_run_id=excluded.scan_run_id,
                 updated_at=excluded.updated_at""",
            (provider, api_name, official_url, raw_content_hash, semantic_spec_hash,
             _dumps(parsed_spec), source_format, fetched_at, scan_run_id, now, now),
        )
        conn.commit()
        return self.get_snapshot(provider, api_name) or {}

    def get_snapshot(self, provider: str, api_name: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT * FROM tushare_spec_snapshots WHERE provider=? AND api_name=?",
            (provider, api_name),
        ).fetchone()
        return self._row(row)


    def supersede_other_alerts(self, provider: str, api_name: str, semantic_spec_hash: str) -> None:
        conn = self._conn()
        now = _now()
        conn.execute(
            """UPDATE tushare_spec_change_alerts
               SET status='superseded', updated_at=?
               WHERE provider=? AND api_name=? AND semantic_spec_hash<>?
                 AND status IN ('new','viewed','syncing','candidate_ready','published','failed','verification_failed')""",
            (now, provider, api_name, semantic_spec_hash),
        )
        conn.commit()

    def resolve_alerts_for_current_spec(self, provider: str, api_name: str) -> None:
        conn = self._conn()
        now = _now()
        conn.execute(
            """UPDATE tushare_spec_change_alerts
               SET status='verified', verified_at=?, verification_error='', updated_at=?
               WHERE provider=? AND api_name=?
                 AND status IN ('new','viewed','syncing','failed','verification_failed')""",
            (now, now, provider, api_name),
        )
        conn.commit()

    def upsert_change_alert(
        self, *, provider: str, api_name: str, title: str, semantic_spec_hash: str,
        severity: str, diffs: list[dict[str, Any]], scan_run_id: str,
    ) -> dict[str, Any]:
        conn = self._conn()
        now = _now()
        conn.execute(
            """INSERT INTO tushare_spec_change_alerts
               (provider, api_name, title, semantic_spec_hash, severity, status, diffs_json,
                scan_run_id, first_seen_at, last_seen_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, ?)
               ON CONFLICT(provider, api_name, semantic_spec_hash) DO UPDATE SET
                 title=excluded.title,
                 severity=excluded.severity,
                 diffs_json=excluded.diffs_json,
                 scan_run_id=excluded.scan_run_id,
                 status=CASE
                   WHEN tushare_spec_change_alerts.status IN ('verified','superseded','ignored') THEN 'new'
                   ELSE tushare_spec_change_alerts.status
                 END,
                 candidate_version=CASE
                   WHEN tushare_spec_change_alerts.status IN ('verified','superseded','ignored') THEN ''
                   ELSE tushare_spec_change_alerts.candidate_version
                 END,
                 release_version=CASE
                   WHEN tushare_spec_change_alerts.status IN ('verified','superseded','ignored') THEN ''
                   ELSE tushare_spec_change_alerts.release_version
                 END,
                 verification_error='',
                 last_seen_at=excluded.last_seen_at,
                 updated_at=excluded.updated_at""",
            (provider, api_name, title, semantic_spec_hash, severity, _dumps(diffs), scan_run_id, now, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tushare_spec_change_alerts WHERE provider=? AND api_name=? AND semantic_spec_hash=?",
            (provider, api_name, semantic_spec_hash),
        ).fetchone()
        return self._row(row) or {}

    def get_alert(self, alert_id: int) -> dict[str, Any] | None:
        row = self._conn().execute("SELECT * FROM tushare_spec_change_alerts WHERE id=?", (int(alert_id),)).fetchone()
        return self._row(row)

    def list_alerts(
        self, *, statuses: Iterable[str] | None = None, api_names: Iterable[str] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        statuses = [str(value) for value in statuses or [] if str(value)]
        api_names = [str(value) for value in api_names or [] if str(value)]
        if statuses:
            where.append("status IN (%s)" % ",".join("?" for _ in statuses))
            params.extend(statuses)
        if api_names:
            where.append("api_name IN (%s)" % ",".join("?" for _ in api_names))
            params.extend(api_names)
        sql = "SELECT * FROM tushare_spec_change_alerts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY CASE severity WHEN 'blocking' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, last_seen_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 2000)))
        rows = self._conn().execute(sql, params).fetchall()
        return [self._row(row) or {} for row in rows]

    def _mark_alerts(self, alert_ids: Iterable[int], *, status: str, **values: Any) -> None:
        ids = [int(value) for value in alert_ids]
        if not ids:
            return
        now = _now()
        assignments = ["status=?", "updated_at=?"]
        params: list[Any] = [status, now]
        allowed = {
            "candidate_version", "release_version", "verification_error", "viewed_at",
            "synchronized_at", "published_at", "verified_at",
        }
        for key, value in values.items():
            if key not in allowed:
                continue
            assignments.append(f"{key}=?")
            params.append(value)
        params.extend(ids)
        conn = self._conn()
        conn.execute(
            f"UPDATE tushare_spec_change_alerts SET {', '.join(assignments)} WHERE id IN ({','.join('?' for _ in ids)})",
            params,
        )
        conn.commit()

    def mark_alerts_viewed(self, alert_ids: Iterable[int]) -> None:
        self._mark_alerts(alert_ids, status="viewed", viewed_at=_now())

    def mark_alerts_syncing(self, alert_ids: Iterable[int]) -> None:
        self._mark_alerts(alert_ids, status="syncing", synchronized_at=_now())

    def mark_alerts_candidate(self, alert_ids: Iterable[int], candidate_version: str) -> None:
        self._mark_alerts(alert_ids, status="candidate_ready", candidate_version=candidate_version, synchronized_at=_now())

    def mark_alerts_published(self, alert_ids: Iterable[int], release_version: str) -> None:
        self._mark_alerts(alert_ids, status="published", release_version=release_version, published_at=_now())

    def mark_alerts_verified(self, alert_ids: Iterable[int]) -> None:
        self._mark_alerts(alert_ids, status="verified", verified_at=_now(), verification_error="")

    def mark_alerts_failed(self, alert_ids: Iterable[int], error: str, *, status: str = "failed") -> None:
        self._mark_alerts(alert_ids, status=status, verification_error=str(error or ""))

    def alert_ids_for_candidate(self, candidate_version: str, api_names: Iterable[str] | None = None) -> list[int]:
        where = ["candidate_version=?"]
        params: list[Any] = [candidate_version]
        names = [str(value) for value in api_names or [] if str(value)]
        if names:
            where.append("api_name IN (%s)" % ",".join("?" for _ in names))
            params.extend(names)
        rows = self._conn().execute(
            "SELECT id FROM tushare_spec_change_alerts WHERE " + " AND ".join(where), params
        ).fetchall()
        return [int(row[0]) for row in rows]

    def acquire_lease(self, lease_key: str, *, owner: str, lease_seconds: int) -> bool:
        conn = self._conn()
        now_dt = datetime.now()
        now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        expires = (now_dt + timedelta(seconds=max(30, int(lease_seconds)))).strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT owner, expires_at FROM tushare_spec_monitor_leases WHERE lease_key=?", (lease_key,)
            ).fetchone()
            if row and str(row["expires_at"] or "") > now and str(row["owner"] or "") != owner:
                conn.rollback()
                return False
            conn.execute(
                """INSERT INTO tushare_spec_monitor_leases(lease_key, owner, acquired_at, expires_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(lease_key) DO UPDATE SET owner=excluded.owner, acquired_at=excluded.acquired_at,
                     expires_at=excluded.expires_at, updated_at=excluded.updated_at""",
                (lease_key, owner, now, expires, now),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise

    def release_lease(self, lease_key: str, *, owner: str) -> None:
        conn = self._conn()
        conn.execute("DELETE FROM tushare_spec_monitor_leases WHERE lease_key=? AND owner=?", (lease_key, owner))
        conn.commit()

    def dashboard(self, *, next_scheduled_at: str = "") -> dict[str, Any]:
        latest = self.latest_scan_run() or {}
        pending_statuses = ["new", "viewed", "syncing", "candidate_ready", "published", "verification_failed", "failed"]
        alerts = self.list_alerts(statuses=pending_statuses, limit=1000)
        return {
            "latest_run": latest,
            "next_scheduled_at": next_scheduled_at or latest.get("next_scheduled_at", ""),
            "pending_count": len(alerts),
            "blocking_count": sum(1 for row in alerts if row.get("severity") == "blocking"),
            "alerts": alerts,
        }
