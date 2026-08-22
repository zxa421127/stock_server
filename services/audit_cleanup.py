# -*- coding: utf-8 -*-
"""Daily retention cleanup for immutable audit tables."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

import config
from services.audit_repository import (
    acquire_maintenance_lease,
    complete_maintenance_task,
    delete_expired_audit_rows,
    get_maintenance_state,
)

_TASK_NAME = "audit_cleanup"
_stop_event = threading.Event()
_worker: threading.Thread | None = None
_lock = threading.Lock()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def run_cleanup_once(now: datetime | None = None) -> dict[str, int | bool]:
    current = now or datetime.now()
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return {"ran": False, "api_access_logs": 0, "operation_audit_logs": 0}
    interval_hours = max(1, int(getattr(config, "AUDIT_CLEANUP_INTERVAL_HOURS", 24) or 24))
    state = get_maintenance_state(_TASK_NAME) or {}
    completed = _parse_time(state.get("last_completed_at"))
    if completed and current - completed < timedelta(hours=interval_hours):
        return {"ran": False, "api_access_logs": 0, "operation_audit_logs": 0}
    lease_seconds = max(3600, interval_hours * 3600)
    if not acquire_maintenance_lease(_TASK_NAME, current, lease_seconds):
        return {"ran": False, "api_access_logs": 0, "operation_audit_logs": 0}
    try:
        deleted = delete_expired_audit_rows(
            now=current,
            api_days=int(getattr(config, "API_ACCESS_LOG_RETENTION_DAYS", 30)),
            operation_days=int(getattr(config, "OPERATION_LOG_RETENTION_DAYS", 365)),
            batch_size=5000,
        )
        total = int(deleted.get("api_access_logs", 0)) + int(deleted.get("operation_audit_logs", 0))
        complete_maintenance_task(_TASK_NAME, "ok", total, current)
        logging.info("[audit] 历史自动清理完成: %s", deleted)
        return {"ran": True, **deleted}
    except Exception as exc:
        try:
            complete_maintenance_task(_TASK_NAME, f"error: {exc}"[:1000], 0, current)
        except Exception:
            logging.exception("[audit] 清理失败状态写入失败")
        logging.exception("[audit] 历史自动清理失败")
        return {"ran": True, "api_access_logs": 0, "operation_audit_logs": 0}


def _worker_loop() -> None:
    logging.info("[audit] 自动清理线程已启动")
    while not _stop_event.is_set():
        try:
            run_cleanup_once()
        except Exception:
            logging.exception("[audit] 自动清理线程异常")
        _stop_event.wait(timeout=3600)
    logging.info("[audit] 自动清理线程已停止")


def start_audit_cleanup_worker() -> None:
    global _worker
    if not bool(getattr(config, "AUDIT_ENABLED", True)):
        return
    with _lock:
        if _worker is not None and _worker.is_alive():
            return
        _stop_event.clear()
        _worker = threading.Thread(target=_worker_loop, name="audit-cleanup", daemon=True)
        _worker.start()


def stop_audit_cleanup_worker(timeout: float = 5.0) -> None:
    _stop_event.set()
    worker = _worker
    if worker is not None:
        worker.join(timeout=timeout)
