# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from integrations.market_data.base import ProviderResponse
from services.kaipanla_snapshot_scheduler import (
    KaipanlaSnapshotScheduler,
    SnapshotSchedulerSettings,
)


class Repo:
    def __init__(self):
        self.types: set[str] = set()
        self.leases: list[str] = []

    def has_snapshot(self, trade_date, snapshot_type="auction"):
        return snapshot_type in self.types

    def acquire_lease(self, name, owner, ttl, now=None):
        self.leases.append(name)
        return True

    def release_lease(self, name, owner):
        return None

    def prune_before(self, cutoff):
        return 0


class Service:
    def __init__(self, repo, market_status="open"):
        self.repository = repo
        self.market_status = market_status
        self.calls: list[dict] = []

    def get_open_date_status(self, trade_date):
        return self.market_status

    def capture_snapshot(self, **kwargs):
        self.calls.append(dict(kwargs))
        self.repository.types.add(kwargs["snapshot_type"])
        return ProviderResponse(
            data=[],
            meta={
                "snapshot_id": f"{kwargs['snapshot_type']}-id",
                "snapshot_created": True,
                "record_count": 1,
                "snapshot_type": kwargs["snapshot_type"],
            },
        )


def _settings():
    return SnapshotSchedulerSettings(
        enabled=True,
        auction_hour=9,
        auction_minute=26,
        auction_second=5,
        post_open_hour=9,
        post_open_minute=31,
        post_open_second=0,
        close_hour=15,
        close_minute=1,
        close_second=0,
        window_seconds=120,
        poll_seconds=5,
        page_size=1000,
        max_pages=10,
        lease_seconds=300,
        retention_days=1095,
    )


def test_scheduler_captures_all_three_types_in_independent_windows_and_leases():
    tz = ZoneInfo("Asia/Shanghai")
    repo = Repo()
    service = Service(repo)
    scheduler = KaipanlaSnapshotScheduler(
        service=service,
        repository=repo,
        settings=_settings(),
        owner_id="worker",
    )

    results = [
        scheduler.run_once(now=datetime(2026, 7, 24, 9, 26, 5, tzinfo=tz)),
        scheduler.run_once(now=datetime(2026, 7, 24, 9, 31, 0, tzinfo=tz)),
        scheduler.run_once(now=datetime(2026, 7, 24, 15, 1, 0, tzinfo=tz)),
    ]

    assert [item["snapshot_type"] for item in results] == [
        "auction",
        "post_open",
        "close",
    ]
    assert [call["snapshot_type"] for call in service.calls] == [
        "auction",
        "post_open",
        "close",
    ]
    assert repo.leases == [
        "kaipanla_morning_bidding:20260724:auction",
        "kaipanla_morning_bidding:20260724:post_open",
        "kaipanla_morning_bidding:20260724:close",
    ]


def test_scheduler_does_not_capture_close_twice():
    tz = ZoneInfo("Asia/Shanghai")
    repo = Repo()
    repo.types.add("close")
    service = Service(repo)
    scheduler = KaipanlaSnapshotScheduler(
        service=service,
        repository=repo,
        settings=_settings(),
        owner_id="worker",
    )

    result = scheduler.run_once(now=datetime(2026, 7, 24, 15, 1, 30, tzinfo=tz))

    assert result == {
        "status": "already_captured",
        "trade_date": "20260724",
        "snapshot_type": "close",
    }
    assert service.calls == []


def test_scheduler_skips_close_on_non_trading_day():
    tz = ZoneInfo("Asia/Shanghai")
    repo = Repo()
    service = Service(repo, market_status="closed")
    scheduler = KaipanlaSnapshotScheduler(
        service=service,
        repository=repo,
        settings=_settings(),
        owner_id="worker",
    )

    result = scheduler.run_once(now=datetime(2026, 7, 25, 15, 1, 0, tzinfo=tz))

    assert result == {
        "status": "market_closed",
        "trade_date": "20260725",
        "snapshot_type": "close",
    }
    assert service.calls == []
