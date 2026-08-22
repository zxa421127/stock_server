# -*- coding: utf-8 -*-
"""Run the Kaipanla snapshot scheduler as one dedicated process.

Use this with multi-worker Gunicorn (especially ``--preload``) so the web
workers do not own scheduler threads. SQLite leases still protect against an
accidental second worker, but operations should normally run one instance.
"""
from __future__ import annotations

import logging
import signal
import threading
from logging.handlers import TimedRotatingFileHandler

import config
from services.environment_guard import assert_environment_ready
from services.kaipanla_snapshot_scheduler import (
    start_kaipanla_snapshot_scheduler,
    stop_kaipanla_snapshot_scheduler,
)


def setup_worker_logging() -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler = TimedRotatingFileHandler(
        filename=config.LOG_DIR / "kaipanla_snapshot_worker.log",
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
    if not config.KAIPANLA_SNAPSHOT_ENABLED:
        logging.error("KAIPANLA_SNAPSHOT_ENABLED=false，独立快照 worker 未启动")
        return 2

    stopped = threading.Event()

    def handle_stop(signum, frame):  # noqa: ARG001
        logging.info("收到退出信号: %s", signum)
        stopped.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_stop)

    if not start_kaipanla_snapshot_scheduler():
        logging.error("开盘啦快照调度器未启动，请检查配置和日志")
        return 3
    logging.info("独立开盘啦快照 worker 已启动")
    try:
        stopped.wait()
    finally:
        stop_kaipanla_snapshot_scheduler()
        logging.info("独立开盘啦快照 worker 已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
