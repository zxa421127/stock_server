# -*- coding: utf-8 -*-
"""Retention cleanup and disk protection for administrator API-test results."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from services.admin_api_test_repository import AdminApiTestRepository
from services.admin_api_test_storage import AdminApiTestStorage


class AdminApiTestCleanupService:
    def __init__(
        self, repository: AdminApiTestRepository | None = None,
        storage: AdminApiTestStorage | None = None, *, retention_days: int | None = None,
        cleanup_hour: int | None = None, critical_percent: float | None = None,
    ):
        import config
        self.repository = repository or AdminApiTestRepository()
        self.storage = storage or AdminApiTestStorage()
        self.retention_days = int(retention_days or config.ADMIN_API_TEST_RETENTION_DAYS)
        self.cleanup_hour = int(config.ADMIN_API_TEST_CLEANUP_HOUR if cleanup_hour is None else cleanup_hour)
        self.critical_percent = float(config.ADMIN_API_TEST_DISK_CRITICAL_PERCENT if critical_percent is None else critical_percent)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def disk_status(self) -> dict[str, Any]:
        status = dict(self.storage.disk_status())
        status["critical_percent"] = self.critical_percent
        status["critical"] = float(status.get("used_percent") or 0) >= self.critical_percent
        return status

    def assert_can_start_batch(self) -> None:
        status = self.disk_status()
        if status["critical"]:
            raise RuntimeError(
                f"结果目录磁盘使用率{status.get('used_percent')}%已达到临界值{self.critical_percent}%，"
                "请先清理未锁定批次或扩容后再启动完整测试"
            )

    def cleanup_once(self, *, now: str | None = None, limit: int = 100) -> dict[str, Any]:
        expired = self.repository.expired_batches(now=now, limit=limit)
        deleted: list[str] = []
        failed: list[str] = []
        for batch in expired:
            batch_id = str(batch["id"])
            try:
                self.repository.update_batch(batch_id, cleanup_status="deleting")
                self.repository.add_event(batch_id, "cleanup_started", {"expires_at": batch.get("expires_at")})
                self.storage.delete_batch(batch_id)
                self.repository.delete_batch_metadata(batch_id)
                deleted.append(batch_id)
            except Exception as exc:
                logging.exception("管理员接口测试结果清理失败: batch=%s", batch_id)
                self.repository.update_batch(batch_id, cleanup_status="delete_failed", error_message=str(exc))
                try:
                    self.repository.add_event(batch_id, "cleanup_failed", {"error": str(exc)})
                except Exception:
                    pass
                failed.append(batch_id)
        return {"checked": len(expired), "deleted": deleted, "failed": failed, "disk": self.disk_status()}

    def delete_batch(self, batch_id: str, *, force_unlocked_only: bool = True) -> None:
        batch = self.repository.get_batch(batch_id)
        if not batch:
            raise KeyError(f"批次不存在：{batch_id}")
        if force_unlocked_only and batch.get("is_locked"):
            raise ValueError("永久保留批次必须先解除锁定才能删除")
        if batch.get("status") in {"queued", "running", "cancelling"}:
            raise ValueError("运行中或等待中的批次不能删除")
        self.repository.update_batch(batch_id, cleanup_status="deleting")
        self.repository.add_event(batch_id, "manual_delete_started", {})
        try:
            self.storage.delete_batch(batch_id)
            self.repository.delete_batch_metadata(batch_id)
        except Exception as exc:
            self.repository.update_batch(batch_id, cleanup_status="delete_failed", error_message=str(exc))
            self.repository.add_event(batch_id, "manual_delete_failed", {"error": str(exc)})
            raise

    def start_worker(self) -> bool:
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="admin-api-test-cleanup", daemon=True)
        self._thread.start()
        return True

    def stop_worker(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            now = datetime.now()
            target = now.replace(hour=self.cleanup_hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            if self._stop.wait(max(1.0, (target - now).total_seconds())):
                return
            try:
                self.cleanup_once()
            except Exception:
                logging.exception("管理员接口测试自动清理任务异常")


_default_service: AdminApiTestCleanupService | None = None
_default_lock = threading.Lock()


def get_admin_api_test_cleanup_service() -> AdminApiTestCleanupService:
    global _default_service
    with _default_lock:
        if _default_service is None:
            _default_service = AdminApiTestCleanupService()
        return _default_service


def start_admin_api_test_cleanup_worker() -> bool:
    import config
    if not config.ADMIN_API_TEST_CLEANUP_ENABLED:
        return False
    return get_admin_api_test_cleanup_service().start_worker()


def stop_admin_api_test_cleanup_worker() -> None:
    if _default_service is not None:
        _default_service.stop_worker()
