# -*- coding: utf-8 -*-
"""Database repository for append-only audit history."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Any, Iterable

from db_utils import get_conn, run_db_write_with_retry

_OPERATION_COLUMNS = (
    "event_id", "actor_type", "actor_id", "actor_name", "target_user_id",
    "target_username", "target_phone", "target_email", "action_category",
    "action_code", "action_name", "request_method", "request_path", "success",
    "status_code", "error_code", "error_message", "before_data_json",
    "after_data_json", "request_data_json", "related_event_id", "client_ip",
    "forwarded_for", "user_agent", "created_at",
)
_API_COLUMNS = (
    "event_id", "request_id", "principal_type", "user_id", "username_snapshot",
    "phone_snapshot", "email_snapshot", "auth_state", "token_fingerprint",
    "provider", "api_name", "route_rule", "request_path", "request_method",
    "required_scope", "package_code", "request_params_json", "content_type",
    "status_code", "success", "duration_ms", "error_code", "error_message",
    "client_ip", "forwarded_for", "user_agent", "created_at",
)


def _json_text(value: Any) -> str:
    if value in (None, ""):
        return "{}"
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except (TypeError, ValueError, json.JSONDecodeError):
            return json.dumps({"value": value}, ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _operation_values(event: dict[str, Any]) -> tuple[Any, ...]:
    mapped = dict(event)
    mapped["success"] = 1 if event.get("success") else 0
    mapped["before_data_json"] = _json_text(event.get("before_data_json", event.get("before_data")))
    mapped["after_data_json"] = _json_text(event.get("after_data_json", event.get("after_data")))
    mapped["request_data_json"] = _json_text(event.get("request_data_json", event.get("request_data")))
    return tuple(mapped.get(column) for column in _OPERATION_COLUMNS)


def _api_values(event: dict[str, Any]) -> tuple[Any, ...]:
    mapped = dict(event)
    mapped["success"] = 1 if event.get("success") else 0
    mapped["request_params_json"] = _json_text(
        event.get("request_params_json", event.get("request_params"))
    )
    return tuple(mapped.get(column) for column in _API_COLUMNS)


def insert_operation_event(event: dict[str, Any]) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in _OPERATION_COLUMNS)
    cursor.execute(
        f"INSERT OR IGNORE INTO operation_audit_logs ({','.join(_OPERATION_COLUMNS)}) VALUES ({placeholders})",
        _operation_values(event),
    )
    inserted = int(cursor.rowcount or 0) > 0
    conn.commit()
    return inserted


def insert_api_access_event(event: dict[str, Any]) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in _API_COLUMNS)
    cursor.execute(
        f"INSERT OR IGNORE INTO api_access_logs ({','.join(_API_COLUMNS)}) VALUES ({placeholders})",
        _api_values(event),
    )
    inserted = int(cursor.rowcount or 0) > 0
    conn.commit()
    return inserted


def insert_events_batch(events: list[tuple[str, dict[str, Any]]]) -> set[str]:
    """Insert events atomically, retrying only transient SQLite write locks."""
    if not events:
        return set()

    operation_sql = (
        f"INSERT OR IGNORE INTO operation_audit_logs ({','.join(_OPERATION_COLUMNS)}) "
        f"VALUES ({','.join('?' for _ in _OPERATION_COLUMNS)})"
    )
    api_sql = (
        f"INSERT OR IGNORE INTO api_access_logs ({','.join(_API_COLUMNS)}) "
        f"VALUES ({','.join('?' for _ in _API_COLUMNS)})"
    )

    def _insert() -> set[str]:
        conn = get_conn()
        cursor = conn.cursor()
        try:
            for event_type, event in events:
                event_id = str(event.get("event_id") or "")
                if not event_id:
                    raise ValueError("audit event_id is required")
                if event_type == "operation":
                    cursor.execute(operation_sql, _operation_values(event))
                elif event_type == "api_access":
                    cursor.execute(api_sql, _api_values(event))
                else:
                    raise ValueError(f"unsupported audit event type: {event_type}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        known: set[str] = set()
        op_ids = [str(event[1]["event_id"]) for event in events if event[0] == "operation"]
        api_ids = [str(event[1]["event_id"]) for event in events if event[0] == "api_access"]
        for table, ids in (("operation_audit_logs", op_ids), ("api_access_logs", api_ids)):
            for offset in range(0, len(ids), 500):
                chunk = ids[offset:offset + 500]
                if not chunk:
                    continue
                rows = cursor.execute(
                    f"SELECT event_id FROM {table} WHERE event_id IN ({','.join('?' for _ in chunk)})",
                    chunk,
                ).fetchall()
                known.update(str(row[0]) for row in rows)
        return known

    return run_db_write_with_retry(_insert, operation_name="audit-batch-insert")


def _decode_json_fields(row: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    for source, target in mapping.items():
        raw = result.pop(source, None)
        if raw in (None, ""):
            result[target] = {}
        else:
            try:
                result[target] = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                result[target] = {"raw": str(raw)}
    result["success"] = bool(result.get("success"))
    return result


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _append_date_filters(filters: dict[str, Any], clauses: list[str], params: list[Any]) -> None:
    if filters.get("start_time"):
        clauses.append("created_at>=?")
        params.append(str(filters["start_time"]))
    if filters.get("end_time"):
        clauses.append("created_at<=?")
        params.append(str(filters["end_time"]))


def _operation_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    _append_date_filters(filters, clauses, params)
    exact = {
        "action_code": "action_code",
        "action_category": "action_category",
        "actor_type": "actor_type",
        "status_code": "status_code",
        "client_ip": "client_ip",
    }
    for key, column in exact.items():
        value = filters.get(key)
        if value not in (None, ""):
            clauses.append(f"{column}=?")
            params.append(int(value) if key == "status_code" and str(value).isdigit() else str(value))
    target_user_id = filters.get("target_user_id")
    if target_user_id not in (None, ""):
        clauses.append("target_user_id=?")
        params.append(
            int(target_user_id)
            if str(target_user_id).strip().isdigit()
            else str(target_user_id).strip()
        )
    success = filters.get("success")
    if success not in (None, ""):
        clauses.append("success=?")
        params.append(1 if str(success).lower() in {"1", "true", "success"} else 0)
    actor = str(filters.get("actor") or "").strip()
    if actor:
        like = f"%{_escape_like(actor)}%"
        clauses.append("(actor_name LIKE ? ESCAPE '\\' OR CAST(actor_id AS TEXT)=?)")
        params.extend([like, actor])
    target = str(filters.get("target") or "").strip()
    if target:
        like = f"%{_escape_like(target)}%"
        clauses.append(
            "(target_username LIKE ? ESCAPE '\\' OR target_phone LIKE ? ESCAPE '\\' "
            "OR target_email LIKE ? ESCAPE '\\' OR CAST(target_user_id AS TEXT)=?)"
        )
        params.extend([like, like, like, target])
    keyword = str(filters.get("keyword") or "").strip()
    if keyword:
        like = f"%{_escape_like(keyword)}%"
        clauses.append(
            "(action_name LIKE ? ESCAPE '\\' OR action_code LIKE ? ESCAPE '\\' "
            "OR error_message LIKE ? ESCAPE '\\' OR request_path LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like, like, like])
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _api_where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    _append_date_filters(filters, clauses, params)
    exact = {
        "provider": "provider",
        "api_name": "api_name",
        "request_method": "request_method",
        "status_code": "status_code",
        "auth_state": "auth_state",
        "package_code": "package_code",
        "required_scope": "required_scope",
        "client_ip": "client_ip",
    }
    for key, column in exact.items():
        value = filters.get(key)
        if value not in (None, ""):
            clauses.append(f"{column}=?")
            params.append(int(value) if key == "status_code" and str(value).isdigit() else str(value))
    success = filters.get("success")
    if success not in (None, ""):
        clauses.append("success=?")
        params.append(1 if str(success).lower() in {"1", "true", "success"} else 0)
    user = str(filters.get("user") or "").strip()
    if user:
        like = f"%{_escape_like(user)}%"
        clauses.append(
            "(username_snapshot LIKE ? ESCAPE '\\' OR phone_snapshot LIKE ? ESCAPE '\\' "
            "OR email_snapshot LIKE ? ESCAPE '\\' OR CAST(user_id AS TEXT)=?)"
        )
        params.extend([like, like, like, user])
    path = str(filters.get("path") or "").strip()
    if path:
        clauses.append("request_path LIKE ? ESCAPE '\\'")
        params.append(f"%{_escape_like(path)}%")
    min_duration = filters.get("min_duration_ms")
    if min_duration not in (None, "") and str(min_duration).isdigit():
        clauses.append("duration_ms>=?")
        params.append(int(min_duration))
    max_duration = filters.get("max_duration_ms")
    if max_duration not in (None, "") and str(max_duration).isdigit():
        clauses.append("duration_ms<=?")
        params.append(int(max_duration))
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _page_values(page: int, page_size: int) -> tuple[int, int]:
    valid_sizes = {20, 50, 100, 200}
    size = int(page_size or 50)
    if size not in valid_sizes:
        size = 50
    current = max(int(page or 1), 1)
    return current, size


def query_operation_logs(
    filters: dict[str, Any], page: int, page_size: int, *, include_sensitive: bool = False
) -> dict[str, Any]:
    conn = get_conn()
    where, params = _operation_where(filters)
    current, size = _page_values(page, page_size)
    total = int(conn.execute(f"SELECT COUNT(*) FROM operation_audit_logs{where}", params).fetchone()[0])
    rows = conn.execute(
        f"SELECT * FROM operation_audit_logs{where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, size, (current - 1) * size],
    ).fetchall()
    stat = conn.execute(
        "SELECT COALESCE(SUM(success),0), COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0), "
        "COUNT(DISTINCT target_user_id), "
        "COALESCE(SUM(CASE WHEN actor_type='admin' THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN actor_type='user' THEN 1 ELSE 0 END),0) "
        f"FROM operation_audit_logs{where}",
        params,
    ).fetchone()
    items = [
        _decode_json_fields(dict(row), {
            "before_data_json": "before_data",
            "after_data_json": "after_data",
            "request_data_json": "request_data",
        })
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": current,
        "page_size": size,
        "pages": max(1, math.ceil(total / size)) if total else 1,
        "stats": {
            "total": total,
            "success_count": int(stat[0] or 0),
            "failure_count": int(stat[1] or 0),
            "target_user_count": int(stat[2] or 0),
            "admin_count": int(stat[3] or 0),
            "user_count": int(stat[4] or 0),
        },
    }


def query_api_access_logs(
    filters: dict[str, Any], page: int, page_size: int, *, include_sensitive: bool = False
) -> dict[str, Any]:
    conn = get_conn()
    where, params = _api_where(filters)
    current, size = _page_values(page, page_size)
    total = int(conn.execute(f"SELECT COUNT(*) FROM api_access_logs{where}", params).fetchone()[0])
    rows = conn.execute(
        f"SELECT * FROM api_access_logs{where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, size, (current - 1) * size],
    ).fetchall()
    stat = conn.execute(
        "SELECT COALESCE(SUM(success),0), COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0), "
        "COUNT(DISTINCT CASE WHEN user_id IS NOT NULL THEN user_id END), "
        "COALESCE(SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END),0), "
        "COALESCE(AVG(duration_ms),0), "
        "COALESCE(SUM(CASE WHEN status_code=401 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN status_code=402 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN status_code=403 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN status_code=429 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN status_code>=500 THEN 1 ELSE 0 END),0) "
        f"FROM api_access_logs{where}",
        params,
    ).fetchone()
    slowest = conn.execute(
        f"SELECT provider, api_name, MAX(duration_ms) AS duration_ms FROM api_access_logs{where} "
        "GROUP BY provider, api_name ORDER BY duration_ms DESC LIMIT 1",
        params,
    ).fetchone()
    items = [
        _decode_json_fields(dict(row), {"request_params_json": "request_params"})
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": current,
        "page_size": size,
        "pages": max(1, math.ceil(total / size)) if total else 1,
        "stats": {
            "total": total,
            "success_count": int(stat[0] or 0),
            "failure_count": int(stat[1] or 0),
            "user_count": int(stat[2] or 0),
            "anonymous_count": int(stat[3] or 0),
            "average_duration_ms": int(round(float(stat[4] or 0))),
            "unauthorized_count": int(stat[5] or 0),
            "subscription_required_count": int(stat[6] or 0),
            "forbidden_count": int(stat[7] or 0),
            "rate_limited_count": int(stat[8] or 0),
            "server_error_count": int(stat[9] or 0),
            "slowest_api": dict(slowest) if slowest else None,
        },
    }


def get_operation_log(event_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM operation_audit_logs WHERE event_id=?", (str(event_id),)
    ).fetchone()
    if not row:
        return None
    return _decode_json_fields(dict(row), {
        "before_data_json": "before_data",
        "after_data_json": "after_data",
        "request_data_json": "request_data",
    })


def get_api_access_log(event_id: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM api_access_logs WHERE event_id=?", (str(event_id),)
    ).fetchone()
    if not row:
        return None
    return _decode_json_fields(dict(row), {"request_params_json": "request_params"})


def _delete_table_batches(table: str, cutoff: str, batch_size: int) -> int:
    conn = get_conn()
    total = 0
    while True:
        cursor = conn.execute(
            f"DELETE FROM {table} WHERE id IN (SELECT id FROM {table} WHERE created_at<? ORDER BY id LIMIT ?)",
            (cutoff, int(batch_size)),
        )
        changed = max(int(cursor.rowcount or 0), 0)
        conn.commit()
        total += changed
        if changed < batch_size:
            break
    return total


def delete_expired_audit_rows(
    now: datetime, api_days: int, operation_days: int, batch_size: int = 5000
) -> dict[str, int]:
    result = {"api_access_logs": 0, "operation_audit_logs": 0}
    size = max(1, min(int(batch_size or 5000), 5000))
    if int(api_days) > 0:
        cutoff = (now - timedelta(days=int(api_days))).strftime("%Y-%m-%d %H:%M:%S")
        result["api_access_logs"] = _delete_table_batches("api_access_logs", cutoff, size)
    if int(operation_days) > 0:
        cutoff = (now - timedelta(days=int(operation_days))).strftime("%Y-%m-%d %H:%M:%S")
        result["operation_audit_logs"] = _delete_table_batches("operation_audit_logs", cutoff, size)
    get_conn().execute("PRAGMA optimize")
    return result


def acquire_maintenance_lease(task_name: str, now: datetime, lease_seconds: int) -> bool:
    conn = get_conn()
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    lease_until = (now + timedelta(seconds=int(lease_seconds))).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT lease_until FROM audit_maintenance_state WHERE task_name=?", (task_name,)
    ).fetchone()
    if row and row[0] and str(row[0]) > now_text:
        return False
    conn.execute(
        """
        INSERT INTO audit_maintenance_state(task_name, last_started_at, lease_until, deleted_rows)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(task_name) DO UPDATE SET
            last_started_at=excluded.last_started_at,
            lease_until=excluded.lease_until
        """,
        (task_name, now_text, lease_until),
    )
    conn.commit()
    return True


def complete_maintenance_task(
    task_name: str, result: str, deleted_rows: int, now: datetime
) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO audit_maintenance_state(
            task_name, last_completed_at, lease_until, last_result, deleted_rows
        ) VALUES (?, ?, NULL, ?, ?)
        ON CONFLICT(task_name) DO UPDATE SET
            last_completed_at=excluded.last_completed_at,
            lease_until=NULL,
            last_result=excluded.last_result,
            deleted_rows=excluded.deleted_rows
        """,
        (task_name, now.strftime("%Y-%m-%d %H:%M:%S"), str(result), int(deleted_rows)),
    )
    conn.commit()


def get_maintenance_state(task_name: str) -> dict[str, Any] | None:
    row = get_conn().execute(
        "SELECT * FROM audit_maintenance_state WHERE task_name=?", (task_name,)
    ).fetchone()
    return dict(row) if row else None


def query_operation_logs_for_export(filters: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    conn = get_conn()
    where, params = _operation_where(filters)
    rows = conn.execute(
        f"SELECT * FROM operation_audit_logs{where} ORDER BY created_at DESC, id DESC LIMIT ?",
        [*params, int(limit)],
    ).fetchall()
    return [
        _decode_json_fields(dict(row), {
            "before_data_json": "before_data",
            "after_data_json": "after_data",
            "request_data_json": "request_data",
        })
        for row in rows
    ]


def query_api_access_logs_for_export(filters: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    conn = get_conn()
    where, params = _api_where(filters)
    rows = conn.execute(
        f"SELECT * FROM api_access_logs{where} ORDER BY created_at DESC, id DESC LIMIT ?",
        [*params, int(limit)],
    ).fetchall()
    return [
        _decode_json_fields(dict(row), {"request_params_json": "request_params"})
        for row in rows
    ]
