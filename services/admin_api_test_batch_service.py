# -*- coding: utf-8 -*-
"""Persisted batch execution for the administrator market-interface tester."""
from __future__ import annotations

import logging
import queue
import threading
import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import Any, Iterable

from services.admin_api_test_repository import AdminApiTestRepository
from services.admin_api_test_storage import AdminApiTestStorage
from services.admin_api_test_security import assert_no_sensitive_keys
from services.admin_market_test_service import AdminMarketTestService
from services.market_interface_spec_service import MarketInterfaceSpecService

_TERMINAL_ITEM = {
    "success_data", "success_empty", "success_fallback", "permission_denied",
    "scope_denied", "invalid_params", "unsupported", "timeout", "upstream_error",
    "schema_mismatch", "result_too_large", "internal_error", "spec_change_pending",
    "cancelled", "storage_error",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _batch_id(kind: str = "batch") -> str:
    prefix = {"single": "SINGLE", "validation": "VALIDATE", "retry": "RETRY"}.get(kind, "BATCH")
    return f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8].upper()}"


class AdminApiTestBatchService:
    """Create, execute, cancel, and retry persisted test batches."""

    def __init__(
        self, repository: AdminApiTestRepository | None = None,
        spec_service: MarketInterfaceSpecService | None = None,
        storage: AdminApiTestStorage | None = None,
        test_service: AdminMarketTestService | None = None,
        *, max_workers: int | None = None, retention_days: int | None = None,
        start_guard=None, auto_start_worker: bool | None = None,
        persisted_poll_seconds: float = 1.0,
    ):
        import config
        self.repository = repository or AdminApiTestRepository()
        self.spec_service = spec_service or MarketInterfaceSpecService()
        self.spec_service.ensure_seed_release()
        self.storage = storage or AdminApiTestStorage()
        self.test_service = test_service or AdminMarketTestService(
            self.repository, self.spec_service, self.storage
        )
        self.max_workers = max(1, int(max_workers or config.ADMIN_API_TEST_MAX_CONCURRENT_ITEMS))
        self.retention_days = max(1, min(int(retention_days or config.ADMIN_API_TEST_RETENTION_DAYS), 36500))
        self.start_guard = start_guard
        self.auto_start_worker = (
            config.ADMIN_API_TEST_IN_PROCESS_WORKER
            if auto_start_worker is None else bool(auto_start_worker)
        )
        self.persisted_poll_seconds = max(0.05, float(persisted_poll_seconds))
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active_lock = threading.Lock()
        self._active_batches: set[str] = set()

    def _normalize_selection(self, interfaces: Iterable[Any] | None) -> list[dict[str, Any]]:
        if interfaces is None:
            return [
                {"provider": row["provider"], "api_name": row["api_name"]}
                for row in self.spec_service.list_effective_specs()
            ]
        result: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for value in interfaces:
            if isinstance(value, dict):
                provider = str(value.get("provider") or "").strip().lower()
                api_name = str(value.get("api_name") or "").strip().lower()
                row = dict(value)
            else:
                provider, api_name = value
                provider, api_name = str(provider).strip().lower(), str(api_name).strip().lower()
                row = {"provider": provider, "api_name": api_name}
            key = (provider, api_name)
            if not all(key) or key in seen:
                continue
            if not self.spec_service.get_effective_spec(provider, api_name):
                raise KeyError(f"未找到接口规格：{provider}/{api_name}")
            seen.add(key)
            row.update({"provider": provider, "api_name": api_name})
            result.append(row)
        if not result:
            raise ValueError("至少选择一个接口")
        return result

    def create_batch(
        self, *, interfaces: Iterable[Any] | None = None, requested_by: str,
        mode: str = "upstream", kind: str = "batch", parent_batch_id: str | None = None,
        release_id: str = "", retention_days: int | None = None, enqueue: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"upstream", "normal"}:
            raise ValueError("mode只允许upstream或normal")
        if self.start_guard:
            self.start_guard()
        selection = self._normalize_selection(interfaces)
        # Reject secrets before creating the batch or writing item parameters to SQLite.
        for row in selection:
            assert_no_sensitive_keys(row.get("params") or {})
        version = self.spec_service.current_version()
        batch_id = _batch_id(kind)
        result_dir = str(self.storage._batch_dir(batch_id, create=True))
        effective_retention = (
            self.repository.get_default_retention_days(self.retention_days)
            if retention_days is None else int(retention_days)
        )
        if not 1 <= effective_retention <= 36500:
            raise ValueError("保留天数必须为1到36500之间的整数")
        batch = self.repository.create_batch(
            batch_id=batch_id, kind=kind, requested_by=requested_by or "admin",
            spec_version=version, total_count=len(selection),
            retention_days=effective_retention,
            parent_batch_id=parent_batch_id,
            requested_interfaces=[{"provider": row["provider"], "api_name": row["api_name"]} for row in selection],
            release_id=release_id, result_dir=result_dir,
        )
        for row in selection:
            spec = self.spec_service.get_effective_spec(row["provider"], row["api_name"])
            assert spec is not None
            params = row.get("params")
            if params is None:
                params = self.spec_service.default_test_params(row["provider"], row["api_name"])
            # Output columns are controlled exclusively by the published interface
            # specification. Client-supplied subsets are never persisted or executed.
            fields = self.spec_service.all_output_field_names(row["provider"], row["api_name"])
            item = self.repository.create_item(
                batch_id=batch_id, provider=row["provider"], api_name=row["api_name"],
                title=str(spec.get("title") or row["api_name"]),
                category=str(spec.get("category") or ""), mode=mode,
                params=dict(params or {}), fields=list(fields or []),
                spec_version=version, spec_hash=str(spec.get("spec_hash") or ""),
            )
            eligible, eligibility_issues = self.spec_service.batch_eligibility(row["provider"], row["api_name"])
            # A single manual test remains available for diagnosing provisional
            # catalog definitions. Formal batch/retry/validation baselines require
            # Tushare official input/output definitions to have been reviewed and published.
            if kind != "single" and not eligible:
                self.repository.update_item(
                    item["id"], status="spec_change_pending", http_status=409,
                    error_code="spec_change_pending",
                    error_message="；".join(eligibility_issues), finished_at=_now(),
                )
        self.repository.recalculate_batch_counts(batch_id)
        self.repository.add_event(batch_id, "batch_created", {
            "kind": kind, "mode": mode, "total_count": len(selection), "release_id": release_id,
        })
        if enqueue:
            self.enqueue_batch(batch_id)
        return self.repository.get_batch(batch_id) or batch

    def create_single_test(
        self, provider: str, api_name: str, *, params: dict[str, Any],
        mode: str, requested_by: str, enqueue: bool = False,
    ) -> dict[str, Any]:
        return self.create_batch(
            interfaces=[{"provider": provider, "api_name": api_name, "params": params}],
            requested_by=requested_by, mode=mode, kind="single", enqueue=enqueue,
        )

    def create_validation_batch(
        self, selected: Iterable[tuple[str, str]], *, release_id: str,
        requested_by: str, enqueue: bool = True,
    ) -> dict[str, Any]:
        return self.create_batch(
            interfaces=list(selected), requested_by=requested_by, mode="upstream",
            kind="validation", release_id=release_id, enqueue=enqueue,
        )

    def retry_failed(self, batch_id: str, *, requested_by: str, enqueue: bool = True) -> dict[str, Any]:
        parent = self.repository.get_batch(batch_id)
        if not parent:
            raise KeyError(f"批次不存在：{batch_id}")
        failed = self.repository.list_failed_items(batch_id)
        if not failed:
            raise ValueError("该批次没有可重测的失败接口")
        selection = [
            {"provider": row["provider"], "api_name": row["api_name"],
             "params": row.get("params") or {}}
            for row in failed if row["status"] != "spec_change_pending"
        ]
        if not selection:
            raise ValueError("失败项均为规格变化待确认，不能直接重测")
        return self.create_batch(
            interfaces=selection, requested_by=requested_by, mode=failed[0].get("mode") or "upstream",
            kind="retry", parent_batch_id=batch_id, enqueue=enqueue,
        )

    def request_cancel(self, batch_id: str) -> dict[str, Any]:
        batch = self.repository.request_cancel(batch_id)
        if not batch:
            raise KeyError(f"批次不存在：{batch_id}")
        return batch

    def progress(self, batch_id: str) -> dict[str, Any]:
        batch = self.repository.recalculate_batch_counts(batch_id)
        if not batch:
            raise KeyError(f"批次不存在：{batch_id}")
        statuses: dict[str, int] = {}
        current = []
        for item in self.repository.list_items(batch_id):
            statuses[item["status"]] = statuses.get(item["status"], 0) + 1
            if item["status"] == "running":
                current.append({"id": item["id"], "provider": item["provider"], "api_name": item["api_name"]})
        return {**batch, "status_counts": statuses, "running_items": current}

    def enqueue_batch(self, batch_id: str) -> None:
        batch = self.repository.get_batch(batch_id)
        if not batch:
            raise KeyError(f"批次不存在：{batch_id}")
        if batch["status"] not in {"queued", "cancelling"}:
            # A persisted worker may claim the just-created batch before this
            # notification runs. Treat already-running/finished states as an
            # idempotent enqueue instead of failing the create request.
            if batch["status"] in {"running", "completed", "completed_with_errors", "cancelled"}:
                return
            raise ValueError(f"批次状态不允许排队：{batch['status']}")
        if not self.auto_start_worker:
            self.repository.add_event(batch_id, "queued_for_external_worker", {})
            return
        started = self.start_worker()
        # A newly started worker scans every persisted queued batch, including this one.
        # Only append explicitly when the worker was already running, otherwise the
        # same batch could be executed twice.
        if not started:
            self._queue.put(batch_id)

    def run_batch_now(self, batch_id: str) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        if not batch:
            raise KeyError(f"批次不存在：{batch_id}")
        with self._active_lock:
            if batch_id in self._active_batches:
                raise RuntimeError("批次已经在执行")
            self._active_batches.add(batch_id)
        try:
            batch = self.repository.get_batch(batch_id) or batch
            if batch.get("cancel_requested"):
                self._cancel_queued(batch_id)
                return self._finish_batch(batch_id, "cancelled")
            self.repository.update_batch(batch_id, status="running", started_at=batch.get("started_at") or _now())
            self.repository.add_event(batch_id, "batch_started", {"max_workers": self.max_workers})
            queued = self.repository.list_queued_items(batch_id)
            iterator = iter(queued)
            futures: dict[Future, int] = {}
            with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="admin-api-test") as executor:
                def submit_next() -> bool:
                    fresh = self.repository.get_batch(batch_id) or {}
                    if fresh.get("cancel_requested"):
                        return False
                    try:
                        item = next(iterator)
                    except StopIteration:
                        return False
                    futures[executor.submit(self.test_service.run_item, item["id"])] = item["id"]
                    return True

                for _ in range(self.max_workers):
                    if not submit_next():
                        break
                while futures:
                    done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
                    for future in done:
                        item_id = futures.pop(future)
                        try:
                            future.result()
                        except Exception as exc:  # final safety net; runner normally classifies errors.
                            logging.exception("管理员接口测试项目执行异常: item_id=%s", item_id)
                            item = self.repository.get_item(item_id)
                            if item:
                                self.repository.update_item(
                                    item_id, status="internal_error", http_status=500,
                                    error_code="internal_error", error_message=f"{exc.__class__.__name__}: {exc}", finished_at=_now(),
                                )
                                self.repository.add_event(batch_id, "item_worker_error", {"error_type": exc.__class__.__name__, "error": str(exc)}, item_id=item_id)
                        submit_next()
            fresh = self.repository.get_batch(batch_id) or {}
            if fresh.get("cancel_requested"):
                self._cancel_queued(batch_id)
                return self._finish_batch(batch_id, "cancelled")
            counts = self.repository.recalculate_batch_counts(batch_id) or {}
            final_status = "completed_with_failures" if counts.get("failure_count") or counts.get("skipped_count") else "completed"
            return self._finish_batch(batch_id, final_status)
        except Exception as exc:
            logging.exception("管理员批量接口测试失败: batch=%s", batch_id)
            self.repository.update_batch(batch_id, status="failed", error_message=str(exc), finished_at=_now())
            self.repository.add_event(batch_id, "batch_failed", {"error": str(exc)})
            self._write_manifest(batch_id)
            return self.repository.get_batch(batch_id) or {}
        finally:
            with self._active_lock:
                self._active_batches.discard(batch_id)

    def _cancel_queued(self, batch_id: str) -> None:
        for item in self.repository.list_queued_items(batch_id):
            self.repository.update_item(
                item["id"], status="cancelled", http_status=499,
                error_code="cancelled", error_message="管理员取消批次，项目未执行", finished_at=_now(),
            )
        self.repository.recalculate_batch_counts(batch_id)

    def _finish_batch(self, batch_id: str, status: str) -> dict[str, Any]:
        finished = datetime.now()
        batch = self.repository.recalculate_batch_counts(batch_id) or {}
        retention = int(batch.get("retention_days") or self.retention_days)
        expires = (finished + timedelta(days=retention)).strftime("%Y-%m-%d %H:%M:%S")
        updated = self.repository.update_batch(
            batch_id, status=status, finished_at=finished.strftime("%Y-%m-%d %H:%M:%S"),
            expires_at=expires,
        ) or {}
        self.repository.add_event(batch_id, "batch_finished", {
            "status": status, "success_count": updated.get("success_count"),
            "failure_count": updated.get("failure_count"), "skipped_count": updated.get("skipped_count"),
        })
        self._write_manifest(batch_id)
        return self.repository.get_batch(batch_id) or updated

    def _write_manifest(self, batch_id: str) -> str:
        batch = self.repository.get_batch(batch_id) or {}
        items = self.repository.list_items(batch_id)
        path = self.storage.write_batch_manifest(batch_id, {
            "batch": batch,
            "items": [{
                "id": row["id"], "provider": row["provider"], "api_name": row["api_name"],
                "status": row["status"], "row_count": row["row_count"],
                "result_file_path": row.get("result_file_path"), "result_sha256": row.get("result_sha256"),
                "error_code": row.get("error_code"), "error_message": row.get("error_message"),
            } for row in items],
        })
        if not batch.get("result_dir"):
            self.repository.update_batch(batch_id, result_dir=str(self.storage.safe_resolve(path).parent))
        return path

    def _persisted_waiting_batch_ids(self) -> list[str]:
        rows = self.repository.list_batches(limit=1000)
        return [
            str(row["id"])
            for row in reversed(rows)
            if row.get("status") in {"queued", "cancelling"}
        ]

    def start_worker(self) -> bool:
        if self._thread and self._thread.is_alive():
            return False
        self._stop.clear()
        self.repository.recover_interrupted_batches()
        # Fill the in-memory queue before starting the thread. This removes the
        # race where the worker's persisted poll and startup scan enqueue the
        # same batch simultaneously.
        for batch_id in self._persisted_waiting_batch_ids():
            self._queue.put(batch_id)
        self._thread = threading.Thread(target=self._worker_loop, name="admin-api-test-batch-worker", daemon=True)
        self._thread.start()
        return True

    def stop_worker(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._queue.put(None)
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            from_queue = True
            try:
                batch_id = self._queue.get(timeout=self.persisted_poll_seconds)
            except queue.Empty:
                from_queue = False
                waiting = self._persisted_waiting_batch_ids()
                batch_id = waiting[0] if waiting else None
                if batch_id is None:
                    continue
            try:
                if batch_id is None:
                    return
                current = self.repository.get_batch(str(batch_id))
                if current and current.get("status") in {"queued", "cancelling"}:
                    self.run_batch_now(str(batch_id))
            finally:
                if from_queue:
                    self._queue.task_done()


_default_service: AdminApiTestBatchService | None = None
_default_lock = threading.Lock()


def get_admin_api_test_batch_service() -> AdminApiTestBatchService:
    global _default_service
    with _default_lock:
        if _default_service is None:
            _default_service = AdminApiTestBatchService()
        return _default_service


def start_admin_api_test_worker() -> bool:
    return get_admin_api_test_batch_service().start_worker()


def stop_admin_api_test_worker() -> None:
    global _default_service
    if _default_service is not None:
        _default_service.stop_worker()
