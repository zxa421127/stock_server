# -*- coding: utf-8 -*-
"""Dedicated production process for audit retention cleanup."""
from __future__ import annotations

import signal
import threading

import config
from app import setup_logging
from services.environment_guard import assert_environment_ready
from services.audit_cleanup import start_audit_cleanup_worker, stop_audit_cleanup_worker

_stop = threading.Event()


def _handle_signal(*_args):
    _stop.set()


def main() -> int:
    assert_environment_ready(config)
    setup_logging()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    start_audit_cleanup_worker()
    try:
        while not _stop.wait(5):
            pass
    finally:
        stop_audit_cleanup_worker()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
