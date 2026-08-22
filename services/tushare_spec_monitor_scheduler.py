# -*- coding: utf-8 -*-
"""Wednesday/Sunday 02:30 Asia/Shanghai Tushare specification monitor."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from services.tushare_spec_monitor_service import get_tushare_spec_monitor_service

_stop = threading.Event()
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _loop() -> None:
    service = get_tushare_spec_monitor_service()
    zone = ZoneInfo(str(config.TUSHARE_SPEC_MONITOR_TIMEZONE))
    while not _stop.is_set():
        next_run = service.configured_next_run(datetime.now(zone))
        wait_seconds = max(1.0, (next_run - datetime.now(zone)).total_seconds())
        logging.info("下次Tushare官网规格检查: %s", next_run.isoformat())
        if _stop.wait(wait_seconds):
            return
        try:
            result = service.scan(trigger="scheduled")
            logging.info(
                "Tushare官网规格检查完成: success=%s changed=%s failed=%s",
                result.get("success_count"), result.get("changed_count"), result.get("failure_count"),
            )
        except RuntimeError as exc:
            logging.warning("Tushare官网规格检查未执行: %s", exc)
        except Exception:
            logging.exception("Tushare官网规格定时检查失败")


def start_tushare_spec_monitor_scheduler(*, force_worker: bool = False) -> bool:
    global _thread
    if not config.TUSHARE_SPEC_MONITOR_ENABLED:
        return False
    if not force_worker and not config.TUSHARE_SPEC_MONITOR_IN_PROCESS:
        return False
    with _lock:
        if _thread and _thread.is_alive():
            return False
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="tushare-spec-monitor", daemon=True)
        _thread.start()
        return True


def stop_tushare_spec_monitor_scheduler() -> None:
    global _thread
    _stop.set()
    thread = _thread
    if thread and thread.is_alive():
        thread.join(timeout=3)
    _thread = None
