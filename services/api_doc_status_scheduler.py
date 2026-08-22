# -*- coding: utf-8 -*-
"""Optional half-day acceptance-test scheduler for API-document health."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import config
from services.api_doc_runtime_status import (
    get_runtime_status_snapshot,
    runtime_report_is_stale,
)

_thread: threading.Thread | None = None
_stop_event = threading.Event()
_lifecycle_lock = threading.RLock()


def _lock_path() -> Path:
    return Path(config.DATA_DIR) / "api_doc_status_refresh.lock"


def _try_acquire_file_lock() -> int | None:
    """Acquire a process-wide atomic lock; remove only clearly stale locks."""
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stale_seconds = int(config.API_DOC_STATUS_SUBPROCESS_TIMEOUT_SECONDS) + 600
    try:
        if path.exists() and time.time() - path.stat().st_mtime > stale_seconds:
            path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    os.write(fd, f"pid={os.getpid()} started={time.time()}\n".encode("utf-8"))
    return fd


def _release_file_lock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    finally:
        try:
            _lock_path().unlink(missing_ok=True)
        except OSError:
            logging.exception("[API文档状态] 删除刷新锁失败")


def run_api_doc_status_refresh() -> bool:
    """Run the existing full-interface evidence test non-interactively."""
    fd = _try_acquire_file_lock()
    if fd is None:
        logging.info("[API文档状态] 另一个进程正在刷新，跳过本轮")
        return False
    try:
        project_root = Path(config.BASE_DIR)
        script = project_root / "e2e_tests" / "core" / "all_data_interfaces_test.py"
        if not script.exists():
            logging.error("[API文档状态] 测试脚本不存在: %s", script)
            return False
        env = os.environ.copy()
        core_path = str(project_root / "e2e_tests" / "core")
        env["PYTHONPATH"] = core_path + os.pathsep + env.get("PYTHONPATH", "")
        env["STOCK_SERVER_ROOT"] = str(project_root)
        env["STOCK_TEST_BASE_URL"] = str(config.API_DOC_STATUS_BASE_URL)
        env["STOCK_TEST_AUTO_CONFIRM"] = "YES"
        env.setdefault("STOCK_TEST_BYPASS_CACHE", "1")
        command = [sys.executable, str(script)]
        logging.info(
            "[API文档状态] 开始半日全接口实测 base_url=%s",
            config.API_DOC_STATUS_BASE_URL,
        )
        completed = subprocess.run(
            command,
            cwd=str(project_root),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(config.API_DOC_STATUS_SUBPROCESS_TIMEOUT_SECONDS),
            check=False,
        )
        output = completed.stdout or ""
        log_path = Path(config.LOG_DIR) / "api_doc_status_refresh.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} exit={completed.returncode} =====\n")
            handle.write(output)
            if output and not output.endswith("\n"):
                handle.write("\n")
        if completed.returncode != 0:
            logging.error(
                "[API文档状态] 全接口实测失败 exit=%s，保留上一次有效报告；详见 %s",
                completed.returncode,
                log_path,
            )
            return False
        snapshot = get_runtime_status_snapshot(force=True)
        if not snapshot.get("valid"):
            logging.error("[API文档状态] 测试结束但未发现有效报告，保留旧状态")
            return False
        logging.info(
            "[API文档状态] 刷新完成 report=%s coverage=%s callable=%s data=%s",
            snapshot.get("report_name"),
            snapshot.get("coverage_count"),
            snapshot.get("callable_count"),
            snapshot.get("data_count"),
        )
        return True
    except subprocess.TimeoutExpired:
        logging.exception("[API文档状态] 全接口实测超时，保留上一次有效报告")
        return False
    except Exception:
        logging.exception("[API文档状态] 半日刷新异常，保留上一次有效报告")
        return False
    finally:
        _release_file_lock(fd)


def _worker_loop() -> None:
    if _stop_event.wait(int(config.API_DOC_STATUS_STARTUP_DELAY_SECONDS)):
        return
    interval = int(config.API_DOC_STATUS_REFRESH_INTERVAL_SECONDS)
    while not _stop_event.is_set():
        snapshot = get_runtime_status_snapshot(force=True)
        if runtime_report_is_stale(snapshot, max_age_seconds=interval):
            run_api_doc_status_refresh()
        else:
            logging.info(
                "[API文档状态] 最近有效报告仍在12小时窗口内: %s",
                snapshot.get("report_name"),
            )
        if _stop_event.wait(interval):
            break


def start_api_doc_status_scheduler() -> bool:
    global _thread
    if not config.API_DOC_STATUS_AUTO_REFRESH_ENABLED:
        logging.info("[API文档状态] 半日自动刷新未启用")
        return False
    if not config.API_DOC_STATUS_IN_PROCESS:
        logging.info("[API文档状态] Web进程内刷新关闭，请运行 python -m tools.api_doc_status_worker")
        return False
    with _lifecycle_lock:
        if _thread is not None and _thread.is_alive():
            return True
        _stop_event.clear()
        _thread = threading.Thread(
            target=_worker_loop,
            name="api-doc-status-scheduler",
            daemon=True,
        )
        _thread.start()
    logging.info(
        "[API文档状态] 半日自动刷新调度器启动 interval=%ss delay=%ss",
        config.API_DOC_STATUS_REFRESH_INTERVAL_SECONDS,
        config.API_DOC_STATUS_STARTUP_DELAY_SECONDS,
    )
    return True


def stop_api_doc_status_scheduler(timeout: float = 5.0) -> None:
    global _thread
    _stop_event.set()
    with _lifecycle_lock:
        worker = _thread
        _thread = None
    if worker is not None and worker.is_alive():
        worker.join(timeout=timeout)
