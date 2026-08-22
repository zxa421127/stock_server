# -*- coding: utf-8 -*-
"""Shanghai-time three-snapshot scheduler with per-type SQLite leases."""
from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import config
from services.kaipanla_bidding_service import KaipanlaBiddingService, get_kaipanla_bidding_service
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class SnapshotSchedulerSettings:
    enabled: bool
    auction_hour: int
    auction_minute: int
    auction_second: int
    post_open_hour: int
    post_open_minute: int
    post_open_second: int
    window_seconds: int
    poll_seconds: int
    page_size: int
    max_pages: int
    lease_seconds: int
    retention_days: int
    close_hour: int = 15
    close_minute: int = 1
    close_second: int = 0

    @classmethod
    def from_config(cls) -> "SnapshotSchedulerSettings":
        return cls(
            enabled=bool(getattr(config, "KAIPANLA_SNAPSHOT_ENABLED", False)),
            auction_hour=int(getattr(config, "KAIPANLA_AUCTION_SNAPSHOT_HOUR", 9)),
            auction_minute=int(getattr(config, "KAIPANLA_AUCTION_SNAPSHOT_MINUTE", 26)),
            auction_second=int(getattr(config, "KAIPANLA_AUCTION_SNAPSHOT_SECOND", 5)),
            post_open_hour=int(getattr(config, "KAIPANLA_POST_OPEN_SNAPSHOT_HOUR", 9)),
            post_open_minute=int(getattr(config, "KAIPANLA_POST_OPEN_SNAPSHOT_MINUTE", 31)),
            post_open_second=int(getattr(config, "KAIPANLA_POST_OPEN_SNAPSHOT_SECOND", 0)),
            window_seconds=int(getattr(config, "KAIPANLA_SNAPSHOT_WINDOW_SECONDS", 120)),
            poll_seconds=int(getattr(config, "KAIPANLA_SNAPSHOT_POLL_SECONDS", 5)),
            page_size=int(getattr(config, "KAIPANLA_SNAPSHOT_PAGE_SIZE", 1000)),
            max_pages=int(getattr(config, "KAIPANLA_SNAPSHOT_MAX_PAGES", 10)),
            lease_seconds=int(getattr(config, "KAIPANLA_SNAPSHOT_LEASE_SECONDS", 300)),
            retention_days=int(getattr(config, "KAIPANLA_SNAPSHOT_RETENTION_DAYS", 1095)),
            close_hour=int(getattr(config, "KAIPANLA_CLOSE_SNAPSHOT_HOUR", 15)),
            close_minute=int(getattr(config, "KAIPANLA_CLOSE_SNAPSHOT_MINUTE", 1)),
            close_second=int(getattr(config, "KAIPANLA_CLOSE_SNAPSHOT_SECOND", 0)),
        )


class KaipanlaSnapshotScheduler:
    def __init__(self, *, service: KaipanlaBiddingService | None = None, repository: KaipanlaSnapshotRepository | None = None, settings: SnapshotSchedulerSettings | None = None, owner_id: str | None = None) -> None:
        self.service = service or get_kaipanla_bidding_service()
        self.repository = repository or self.service.repository
        self.settings = settings or SnapshotSchedulerSettings.from_config()
        self.owner_id = owner_id or f"{os.getpid()}-{uuid.uuid4().hex[:12]}"
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    @staticmethod
    def _china_now(now: datetime | None = None) -> datetime:
        if now is None:
            return datetime.now(_SHANGHAI_TZ)
        return now.replace(tzinfo=_SHANGHAI_TZ) if now.tzinfo is None else now.astimezone(_SHANGHAI_TZ)

    def _matching_type(self, now: datetime) -> str | None:
        targets = {
            "auction": (self.settings.auction_hour, self.settings.auction_minute, self.settings.auction_second),
            "post_open": (self.settings.post_open_hour, self.settings.post_open_minute, self.settings.post_open_second),
            "close": (self.settings.close_hour, self.settings.close_minute, self.settings.close_second),
        }
        for snapshot_type, (hour, minute, second) in targets.items():
            target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
            elapsed = (now - target).total_seconds()
            if 0 <= elapsed <= self.settings.window_seconds:
                return snapshot_type
        return None

    def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled"}
        current = self._china_now(now)
        snapshot_type = self._matching_type(current)
        if snapshot_type is None:
            return {"status": "outside_window"}
        trade_date = current.strftime("%Y%m%d")
        if hasattr(self.service, "get_open_date_status"):
            market_status = self.service.get_open_date_status(trade_date)
        else:
            market_status = "open" if self.service.is_open_date(trade_date) else "closed"
        base = {"trade_date": trade_date, "snapshot_type": snapshot_type}
        if market_status == "unknown":
            return {"status": "calendar_error", **base}
        if market_status != "open":
            return {"status": "market_closed", **base}
        if self.repository.has_snapshot(trade_date, snapshot_type):
            return {"status": "already_captured", **base}
        lease_name = f"kaipanla_morning_bidding:{trade_date}:{snapshot_type}"
        if not self.repository.acquire_lease(lease_name, self.owner_id, self.settings.lease_seconds, now=current):
            return {"status": "lease_busy", **base}
        try:
            if self.repository.has_snapshot(trade_date, snapshot_type):
                return {"status": "already_captured", **base}
            response = self.service.capture_snapshot(
                trade_date=trade_date,
                snapshot_type=snapshot_type,
                snapshot_time=current.strftime("%Y-%m-%d %H:%M:%S"),
                page_size=self.settings.page_size,
                max_pages=self.settings.max_pages,
            )
            if response.error:
                return {"status": "capture_error", "error": response.error, **base}
            if self.settings.retention_days > 0:
                cutoff = (current.date() - timedelta(days=self.settings.retention_days)).strftime("%Y%m%d")
                self.repository.prune_before(cutoff)
            return {"status": "captured", "snapshot_id": response.meta.get("snapshot_id"), "created": bool(response.meta.get("snapshot_created")), "record_count": int(response.meta.get("record_count", len(response.data))), **base}
        finally:
            self.repository.release_lease(lease_name, self.owner_id)

    def _loop(self) -> None:
        logging.info(
            "[开盘啦快照] 三时点调度器启动：auction %02d:%02d:%02d，post_open %02d:%02d:%02d，close %02d:%02d:%02d",
            self.settings.auction_hour,
            self.settings.auction_minute,
            self.settings.auction_second,
            self.settings.post_open_hour,
            self.settings.post_open_minute,
            self.settings.post_open_second,
            self.settings.close_hour,
            self.settings.close_minute,
            self.settings.close_second,
        )
        while not self._stop_event.is_set():
            try:
                result = self.run_once()
                if result.get("status") in {"captured", "capture_error", "calendar_error"}:
                    (logging.info if result["status"] == "captured" else logging.error)("[开盘啦快照] %s", result)
            except Exception:
                logging.exception("[开盘啦快照] 调度循环异常")
            self._stop_event.wait(max(self.settings.poll_seconds, 1))

    def start(self) -> bool:
        if not self.settings.enabled:
            logging.info("[开盘啦快照] 自动采集未启用")
            return False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, name="kaipanla-snapshot-scheduler", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            self._stop_event.set(); thread = self._thread; self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(self.settings.poll_seconds + 1, 2))


_scheduler: KaipanlaSnapshotScheduler | None = None
_scheduler_lock = threading.Lock()


def start_kaipanla_snapshot_scheduler() -> bool:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            _scheduler = KaipanlaSnapshotScheduler()
        return _scheduler.start()


def stop_kaipanla_snapshot_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        scheduler = _scheduler; _scheduler = None
    if scheduler is not None:
        scheduler.stop()
