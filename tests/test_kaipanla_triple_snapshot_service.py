# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

from integrations.market_data.base import ProviderResponse
from services.kaipanla_bidding_service import KaipanlaBiddingService
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


def _repo(tmp_path):
    path = tmp_path / "triple-service.db"

    def factory():
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    return KaipanlaSnapshotRepository(factory)


def _rows(label: str):
    return [
        {
            "股票代码": "000001",
            "ts_code": "000001.SZ",
            "股票名称": label,
            "schema_version": "kaipanla_bidding.v2",
        }
    ]


def test_history_can_select_close_snapshot(tmp_path):
    repo = _repo(tmp_path)
    saved = repo.save_snapshot(
        trade_date="20260724",
        snapshot_time="2026-07-24 15:01:00",
        snapshot_type="close",
        source_params={},
        raw_payload={"close": 1},
        normalized_data=_rows("close"),
    )
    service = KaipanlaBiddingService(repository=repo)

    result = service.query_history(
        {"trade_date": "20260724", "snapshot_type": "close"}
    )

    assert result.error is None
    assert result.meta["snapshot_id"] == saved.snapshot.snapshot_id
    assert result.meta["snapshot_type"] == "close"
    assert result.meta["fallback_used"] is False


def test_missing_close_never_falls_back_to_auction_or_tushare(tmp_path):
    repo = _repo(tmp_path)
    repo.save_snapshot(
        trade_date="20260724",
        snapshot_time="2026-07-24 09:26:05",
        snapshot_type="auction",
        source_params={},
        raw_payload={},
        normalized_data=_rows("auction"),
    )

    def forbidden_query(*args, **kwargs):
        raise AssertionError("close snapshot must not use Tushare fallback")

    service = KaipanlaBiddingService(repository=repo, market_query=forbidden_query)
    result = service.query_history(
        {"trade_date": "20260724", "snapshot_type": "close"}
    )

    assert result.error == "未找到指定条件的 close 历史快照"
    assert result.meta["http_status"] == 404
    assert result.meta["snapshot_type"] == "close"
    assert result.meta["fallback_used"] is False


def test_close_snapshot_id_must_match_requested_type(tmp_path):
    repo = _repo(tmp_path)
    saved = repo.save_snapshot(
        trade_date="20260724",
        snapshot_time="2026-07-24 15:01:00",
        snapshot_type="close",
        source_params={},
        raw_payload={},
        normalized_data=_rows("close"),
    )
    service = KaipanlaBiddingService(repository=repo)

    result = service.query_history(
        {"snapshot_id": saved.snapshot.snapshot_id, "snapshot_type": "auction"}
    )

    assert result.error == "snapshot_id 与 snapshot_type 不一致"
    assert result.meta["http_status"] == 400
