# -*- coding: utf-8 -*-
"""Run the dedicated Tushare official-spec monitor scheduler."""
from __future__ import annotations

import logging
import time

import config
from app import setup_logging
from services.environment_guard import assert_environment_ready
from db_utils import init_db
from services.tushare_spec_monitor_scheduler import start_tushare_spec_monitor_scheduler, stop_tushare_spec_monitor_scheduler


def main() -> int:
    assert_environment_ready(config)
    setup_logging()
    init_db()
    if not start_tushare_spec_monitor_scheduler(force_worker=True):
        logging.error("Tushare官网规格监控未启用或已在运行")
        return 2
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_tushare_spec_monitor_scheduler()


if __name__ == "__main__":
    raise SystemExit(main())
