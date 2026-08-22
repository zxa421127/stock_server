# -*- coding: utf-8 -*-
"""Dedicated API-document status worker for multi-process deployments."""
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
import signal
import threading

import config
from services.environment_guard import assert_environment_ready
from services.api_doc_status_scheduler import (
    start_api_doc_status_scheduler,
    stop_api_doc_status_scheduler,
)


def _setup_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename=config.LOG_DIR / "api_doc_status_worker.log",
        when="midnight",
        interval=1,
        backupCount=config.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    root.addHandler(logging.StreamHandler())


def main() -> int:
    assert_environment_ready(config)
    _setup_logging()
    if not config.API_DOC_STATUS_AUTO_REFRESH_ENABLED:
        logging.error("API_DOC_STATUS_AUTO_REFRESH_ENABLED=false，状态worker未启动")
        return 1
    stopped = threading.Event()

    def _stop(*_args):
        stopped.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)
    # Dedicated mode owns the scheduler even when Web in-process mode is off.
    config.API_DOC_STATUS_IN_PROCESS = True
    if not start_api_doc_status_scheduler():
        return 1
    logging.info("独立API文档状态worker已启动")
    stopped.wait()
    stop_api_doc_status_scheduler()
    logging.info("独立API文档状态worker已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
