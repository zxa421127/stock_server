# -*- coding: utf-8 -*-
"""Thread-safe in-memory daily upstream call statistics."""
from __future__ import annotations

import logging
import threading
from datetime import datetime

_lock = threading.Lock()
_stats = {
    "date": None,
    "tushare_calls": 0,
    "tushare_success": 0,
    "tushare_failed": 0,
    "kaipanla_calls": 0,
    "kaipanla_success": 0,
    "kaipanla_failed": 0,
}


def _roll_day_locked() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    if _stats["date"] == today:
        return
    if _stats["date"] is not None:
        logging.info(
            "[每日数据源统计] date=%s tushare=%s/%s kaipanla=%s/%s",
            _stats["date"],
            _stats["tushare_success"],
            _stats["tushare_calls"],
            _stats["kaipanla_success"],
            _stats["kaipanla_calls"],
        )
    _stats.update({
        "date": today,
        "tushare_calls": 0,
        "tushare_success": 0,
        "tushare_failed": 0,
        "kaipanla_calls": 0,
        "kaipanla_success": 0,
        "kaipanla_failed": 0,
    })


def _record(prefix: str, success: bool) -> None:
    with _lock:
        _roll_day_locked()
        _stats[f"{prefix}_calls"] += 1
        _stats[f"{prefix}_success" if success else f"{prefix}_failed"] += 1


def record_tushare_call(success: bool) -> None:
    _record("tushare", success)


def record_kaipanla_call(success: bool) -> None:
    _record("kaipanla", success)


def snapshot() -> dict:
    with _lock:
        _roll_day_locked()
        return dict(_stats)
