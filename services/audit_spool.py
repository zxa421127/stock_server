# -*- coding: utf-8 -*-
"""Durable audit spool with retry, dead letters and emergency JSONL fallback."""
from __future__ import annotations

import atexit
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import config
from db_utils import is_database_busy_error
from services.audit_repository import insert_events_batch
from services.audit_schema import init_spool_schema

EventType = Literal["operation", "api_access"]

_worker: threading.Thread | None = None
_stop_event = threading.Event()
_wakeup_event = threading.Event()
_lifecycle_lock = threading.Lock()
_RETRY_DELAYS = (1, 5, 30, 120, 600)


def _now() -> datetime:
    return datetime.now()


def _now_text(value: datetime | None = None) -> str:
    return (value or _now()).strftime("%Y-%m-%d %H:%M:%S")


def _spool_path() -> Path:
    return Path(config.AUDIT_SPOOL_DB_FILE)


def _emergency_dir() -> Path:
    return Path(config.AUDIT_EMERGENCY_DIR)


def _connect() -> sqlite3.Connection:
    init_spool_schema(_spool_path(), getattr(config, "AUDIT_SPOOL_SYNCHRONOUS", "FULL"))
    conn = sqlite3.connect(_spool_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def _validate_event(event_type: str, event: dict[str, Any]) -> None:
    if event_type not in {"operation", "api_access"}:
        raise ValueError(f"unsupported audit event type: {event_type}")
    if not isinstance(event, dict):
        raise TypeError("audit event must be a dict")
    if not str(event.get("event_id") or ""):
        raise ValueError("audit event_id is required")


def _insert_spool_row(event_type: EventType, event: dict[str, Any]) -> bool:
    _validate_event(event_type, event)
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
    conn = _connect()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO audit_spool_queue(
                event_id, event_type, payload_json, attempt_count,
                last_attempt_at, next_retry_at, last_error, created_at
            ) VALUES (?, ?, ?, 0, NULL, NULL, NULL, ?)
            """,
            (str(event["event_id"]), event_type, payload, str(event.get("created_at") or _now_text())),
        )
        conn.commit()
        return int(cursor.rowcount or 0) > 0 or conn.execute(
            "SELECT 1 FROM audit_spool_queue WHERE event_id=?", (str(event["event_id"]),)
        ).fetchone() is not None
    finally:
        conn.close()


def _write_emergency(event_type: EventType, event: dict[str, Any]) -> bool:
    try:
        directory = _emergency_dir()
        directory.mkdir(parents=True, exist_ok=True)
        day = _now().strftime("%Y-%m-%d")
        path = directory / f"{event_type}_emergency_{day}.jsonl"
        line = json.dumps(
            {"event_type": event_type, "event": event, "written_at": _now_text()},
            ensure_ascii=False,
            default=str,
        )
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return True
    except Exception:
        logging.critical("[audit] 应急JSONL写入失败", exc_info=True)
        return False


def enqueue_event(
    event_type: EventType,
    event: dict[str, Any],
    *,
    strict: bool = False,
) -> bool:
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return not strict
    try:
        durable = _insert_spool_row(event_type, event)
        if durable:
            _wakeup_event.set()
            return True
    except Exception:
        logging.exception("[audit] 写入持久化缓冲失败 event_type=%s", event_type)
    emergency = _write_emergency(event_type, event)
    if emergency:
        return True
    logging.critical(
        "[audit] 审计事件无法持久化 event_type=%s event_id=%s strict=%s",
        event_type,
        event.get("event_id"),
        strict,
    )
    return False


def _retry_delay(attempt_count: int) -> int:
    index = max(0, min(int(attempt_count) - 1, len(_RETRY_DELAYS) - 1))
    return _RETRY_DELAYS[index]


def _mark_failure(conn: sqlite3.Connection, row: sqlite3.Row, error: str) -> str:
    attempt = int(row["attempt_count"] or 0) + 1
    now = _now()
    max_retries = int(getattr(config, "AUDIT_SPOOL_MAX_RETRIES", 10) or 10)
    if attempt >= max_retries:
        conn.execute(
            """
            INSERT OR REPLACE INTO audit_spool_dead_letters(
                event_id, event_type, payload_json, attempt_count,
                last_attempt_at, last_error, created_at, failed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["event_id"], row["event_type"], row["payload_json"], attempt,
                _now_text(now), str(error)[:4000], row["created_at"], _now_text(now),
            ),
        )
        conn.execute("DELETE FROM audit_spool_queue WHERE id=?", (row["id"],))
        return "dead"
    next_retry = now + timedelta(seconds=_retry_delay(attempt))
    conn.execute(
        """
        UPDATE audit_spool_queue
        SET attempt_count=?, last_attempt_at=?, next_retry_at=?, last_error=?
        WHERE id=?
        """,
        (attempt, _now_text(now), _now_text(next_retry), str(error)[:4000], row["id"]),
    )
    return "retry"


def flush_spool_once(limit: int | None = None, *, force_due: bool = False) -> dict[str, int]:
    result = {"selected": 0, "flushed": 0, "retried": 0, "dead_lettered": 0}
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return result
    size = max(1, int(limit or getattr(config, "AUDIT_SPOOL_BATCH_SIZE", 500) or 500))
    conn = _connect()
    try:
        if force_due:
            rows = conn.execute(
                "SELECT * FROM audit_spool_queue ORDER BY id LIMIT ?", (size,)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM audit_spool_queue
                WHERE next_retry_at IS NULL OR next_retry_at<=?
                ORDER BY id LIMIT ?
                """,
                (_now_text(), size),
            ).fetchall()
        result["selected"] = len(rows)
        if not rows:
            return result

        events: list[tuple[str, dict[str, Any]]] = []
        valid_rows: list[sqlite3.Row] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
                _validate_event(str(row["event_type"]), payload)
                events.append((str(row["event_type"]), payload))
                valid_rows.append(row)
            except Exception as exc:
                state = _mark_failure(conn, row, f"invalid payload: {exc}")
                result["dead_lettered" if state == "dead" else "retried"] += 1
        conn.commit()
        if not events:
            return result

        try:
            confirmed = insert_events_batch(events)
        except Exception as exc:
            for row in valid_rows:
                state = _mark_failure(conn, row, str(exc))
                result["dead_lettered" if state == "dead" else "retried"] += 1
            conn.commit()
            if is_database_busy_error(exc):
                logging.warning(
                    "[audit] 主库繁忙，审计事件保留在缓冲队列等待重试 count=%s error=%s",
                    len(valid_rows),
                    exc,
                )
            else:
                logging.exception("[audit] 缓冲批量落库失败 count=%s", len(valid_rows))
            return result

        for row in valid_rows:
            if str(row["event_id"]) in confirmed:
                conn.execute("DELETE FROM audit_spool_queue WHERE id=?", (row["id"],))
                result["flushed"] += 1
            else:
                state = _mark_failure(conn, row, "main database did not confirm event")
                result["dead_lettered" if state == "dead" else "retried"] += 1
        conn.commit()
        return result
    finally:
        conn.close()


def audit_spool_stats() -> dict[str, int]:
    try:
        conn = _connect()
        try:
            queued = int(conn.execute("SELECT COUNT(*) FROM audit_spool_queue").fetchone()[0])
            dead = int(conn.execute("SELECT COUNT(*) FROM audit_spool_dead_letters").fetchone()[0])
            return {"queued": queued, "dead_letters": dead}
        finally:
            conn.close()
    except Exception:
        logging.exception("[audit] 读取缓冲统计失败")
        return {"queued": -1, "dead_letters": -1}


def recover_emergency_files() -> dict[str, int]:
    result = {"files": 0, "recovered": 0, "invalid": 0, "failed": 0}
    directory = _emergency_dir()
    if not directory.exists():
        return result
    candidates = sorted(
        [*directory.glob("operation_emergency_*.jsonl"), *directory.glob("api_access_emergency_*.jsonl")]
    )
    for original in candidates:
        result["files"] += 1
        processing = original.with_suffix(original.suffix + ".processing")
        try:
            original.replace(processing)
        except OSError:
            result["failed"] += 1
            logging.exception("[audit] 应急文件改名失败: %s", original)
            continue
        bad_lines: list[str] = []
        all_durable = True
        try:
            with processing.open("r", encoding="utf-8") as handle:
                for line in handle:
                    raw = line.rstrip("\r\n")
                    if not raw:
                        continue
                    try:
                        item = json.loads(raw)
                        event_type = str(item["event_type"])
                        event = item["event"]
                        _validate_event(event_type, event)
                    except Exception:
                        result["invalid"] += 1
                        bad_lines.append(raw)
                        continue
                    try:
                        if _insert_spool_row(event_type, event):
                            result["recovered"] += 1
                        else:
                            all_durable = False
                            result["failed"] += 1
                    except Exception:
                        all_durable = False
                        result["failed"] += 1
                        logging.exception("[audit] 应急记录恢复失败 file=%s", processing)
            if bad_lines:
                bad_path = original.with_suffix(original.suffix + ".bad")
                with bad_path.open("a", encoding="utf-8", newline="\n") as bad:
                    for raw in bad_lines:
                        bad.write(raw + "\n")
            if all_durable:
                processing.unlink(missing_ok=True)
            else:
                processing.replace(original)
        except Exception:
            result["failed"] += 1
            logging.exception("[audit] 应急文件恢复失败: %s", processing)
            if processing.exists() and not original.exists():
                try:
                    processing.replace(original)
                except OSError:
                    logging.exception("[audit] 应急文件恢复原名失败: %s", processing)
    if result["recovered"]:
        _wakeup_event.set()
    return result


def _worker_loop() -> None:
    try:
        recover_emergency_files()
    except Exception:
        logging.exception("[audit] 启动时恢复应急文件失败")
    interval = max(1, int(getattr(config, "AUDIT_SPOOL_FLUSH_INTERVAL_SECONDS", 1) or 1))
    logging.info("[audit] 持久化缓冲线程已启动 interval=%ss", interval)
    while not _stop_event.is_set():
        _wakeup_event.wait(timeout=interval)
        _wakeup_event.clear()
        try:
            while not _stop_event.is_set():
                outcome = flush_spool_once()
                if outcome["selected"] == 0 or outcome["flushed"] == 0:
                    break
        except Exception:
            logging.exception("[audit] 缓冲线程执行失败")
    try:
        flush_spool_once(force_due=True)
    except Exception:
        logging.exception("[audit] 退出前刷新失败")
    logging.info("[audit] 持久化缓冲线程已停止")


def start_audit_spool_worker() -> None:
    global _worker
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return
    with _lifecycle_lock:
        if _worker is not None and _worker.is_alive():
            return
        init_spool_schema(_spool_path(), getattr(config, "AUDIT_SPOOL_SYNCHRONOUS", "FULL"))
        _stop_event.clear()
        _worker = threading.Thread(target=_worker_loop, name="audit-spool-writer", daemon=True)
        _worker.start()


def stop_audit_spool_worker(timeout: float = 8.0) -> None:
    _stop_event.set()
    _wakeup_event.set()
    worker = _worker
    if worker is not None:
        worker.join(timeout=timeout)


atexit.register(stop_audit_spool_worker)
