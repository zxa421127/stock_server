# -*- coding: utf-8 -*-
"""Run administrator API-test batch and retention workers outside the Web process.

Recommended for multi-process Waitress/Gunicorn deployments:

    python tools/admin_api_test_worker.py

Set ADMIN_API_TEST_IN_PROCESS_WORKER=false in every Web process so only this
worker executes persisted batches and cleanup jobs.
"""
from __future__ import annotations

import logging
import signal
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from services.environment_guard import assert_environment_ready  # noqa: E402

from services.admin_api_test_batch_service import (  # noqa: E402
    start_admin_api_test_worker,
    stop_admin_api_test_worker,
)
from services.admin_api_test_cleanup_service import (  # noqa: E402
    start_admin_api_test_cleanup_worker,
    stop_admin_api_test_cleanup_worker,
)


def main() -> int:
    assert_environment_ready(config)
    stop_event = threading.Event()

    def request_stop(signum, _frame) -> None:
        logging.info("收到停止信号: %s", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    start_admin_api_test_worker()
    cleanup_started = start_admin_api_test_cleanup_worker()
    logging.info("管理员接口测试独立Worker已启动；自动清理=%s", cleanup_started)
    try:
        while not stop_event.wait(1.0):
            pass
    finally:
        stop_admin_api_test_cleanup_worker()
        stop_admin_api_test_worker()
        logging.info("管理员接口测试独立Worker已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
