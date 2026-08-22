# -*- coding: utf-8 -*-
"""Run the optional Feishu scheduled sync as one dedicated process.

Use this when the web server has multiple workers, so each web worker does not
start a duplicate scheduler.
"""
from __future__ import annotations

import logging
import signal
import threading
from logging.handlers import TimedRotatingFileHandler

import config
from services.environment_guard import assert_environment_ready
from services.feishu_sync_service import start_sync_service, stop_sync_service


def setup_worker_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler = TimedRotatingFileHandler(
        filename=config.LOG_DIR / "feishu_worker.log",
        when="midnight",
        interval=1,
        backupCount=config.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler], force=True)


def main() -> int:
    assert_environment_ready(config)
    setup_worker_logging()
    if not config.ENABLE_FEISHU_SYNC:
        logging.error("ENABLE_FEISHU_SYNC=False，独立飞书 worker 未启动")
        return 2

    stopped = threading.Event()

    def handle_stop(signum, frame):  # noqa: ARG001
        logging.info("收到退出信号: %s", signum)
        stopped.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_stop)

    start_sync_service()
    logging.info("独立飞书同步 worker 已启动")
    try:
        stopped.wait()
    finally:
        stop_sync_service()
        logging.info("独立飞书同步 worker 已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
