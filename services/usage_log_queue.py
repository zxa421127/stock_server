# -*- coding: utf-8 -*-
"""Batched asynchronous usage-log writer."""
from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from typing import Any

import config
from db_utils import record_usage_log, record_usage_logs_batch, touch_api_keys_batch

_log_queue: queue.Queue[dict[str, Any] | None] | None = None
_worker: threading.Thread | None = None
_stop_event = threading.Event()
_lock = threading.Lock()
_dropped = 0
_pending_touches: set[str] = set()
_touch_lock = threading.Lock()


def _enabled() -> bool:
    return bool(getattr(config, "ASYNC_USAGE_LOG_ENABLED", True))


def _has_pending_api_key_touches() -> bool:
    with _touch_lock:
        return bool(_pending_touches)


def _drain_api_key_touches() -> list[str]:
    with _touch_lock:
        tokens = list(_pending_touches)
        _pending_touches.clear()
    return tokens


def _flush(batch: list[dict[str, Any]]) -> None:
    tokens = _drain_api_key_touches()
    if not batch and not tokens:
        return
    try:
        if batch:
            record_usage_logs_batch(batch)
        if tokens:
            touch_api_keys_batch(tokens)
    except Exception as exc:
        logging.exception("[usage_logs] 批量写入失败(logs=%s,touches=%s): %s", len(batch), len(tokens), exc)


def _worker_loop() -> None:
    assert _log_queue is not None
    batch_size = int(getattr(config, "USAGE_LOG_BATCH_SIZE", 500) or 500)
    flush_interval = float(getattr(config, "USAGE_LOG_FLUSH_INTERVAL_SECONDS", 1) or 1)
    batch: list[dict[str, Any]] = []
    last_flush = time.monotonic()
    logging.info("[usage_logs] 批量写入线程已启动 batch=%s interval=%ss", batch_size, flush_interval)

    while not _stop_event.is_set():
        timeout = max(0.05, flush_interval - (time.monotonic() - last_flush))
        try:
            item = _log_queue.get(timeout=timeout)
        except queue.Empty:
            item = None

        if item is not None:
            batch.append(item)
            _log_queue.task_done()
        elif _stop_event.is_set():
            break

        if (batch or _has_pending_api_key_touches()) and (len(batch) >= batch_size or time.monotonic() - last_flush >= flush_interval):
            _flush(batch)
            batch.clear()
            last_flush = time.monotonic()

    while True:
        try:
            item = _log_queue.get_nowait()
        except queue.Empty:
            break
        if item is not None:
            batch.append(item)
        _log_queue.task_done()
        if len(batch) >= batch_size:
            _flush(batch)
            batch.clear()
    _flush(batch)
    logging.info("[usage_logs] 批量写入线程已停止")


def start_usage_log_worker() -> None:
    global _log_queue, _worker
    if not _enabled():
        return
    with _lock:
        if _worker is not None and _worker.is_alive():
            return
        _stop_event.clear()
        maxsize = int(getattr(config, "USAGE_LOG_QUEUE_SIZE", 20000) or 20000)
        _log_queue = queue.Queue(maxsize=maxsize)
        _worker = threading.Thread(target=_worker_loop, name="usage-log-writer", daemon=True)
        _worker.start()


def stop_usage_log_worker(timeout: float = 8.0) -> None:
    if not _enabled() or _log_queue is None:
        return
    _stop_event.set()
    if _worker is not None:
        _worker.join(timeout=timeout)


def enqueue_api_key_touch(token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    if not _enabled():
        touch_api_keys_batch([token])
        return
    start_usage_log_worker()
    with _touch_lock:
        _pending_touches.add(token)


def enqueue_usage_log(**payload: Any) -> None:
    global _dropped
    if not _enabled():
        record_usage_log(**payload)
        return
    start_usage_log_worker()
    if _log_queue is None:
        record_usage_log(**payload)
        return
    try:
        _log_queue.put_nowait(payload)
    except queue.Full:
        if bool(getattr(config, "USAGE_LOG_DROP_ON_FULL", True)):
            _dropped += 1
            if _dropped == 1 or _dropped % 1000 == 0:
                logging.warning("[usage_logs] 队列已满，累计丢弃%s条非关键审计日志", _dropped)
        else:
            record_usage_log(**payload)


def usage_log_queue_stats() -> dict[str, int]:
    with _touch_lock:
        pending_touches = len(_pending_touches)
    return {
        "queued": _log_queue.qsize() if _log_queue is not None else 0,
        "dropped": _dropped,
        "pending_api_key_touches": pending_touches,
    }


atexit.register(stop_usage_log_worker)
