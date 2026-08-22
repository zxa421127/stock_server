# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

import pytest

from services.kaipanla_snapshot_repository import (
    KaipanlaSnapshotRepository,
    SNAPSHOT_TYPES,
    validate_snapshot_type,
)


def _repo(tmp_path):
    path = tmp_path / "triple-snapshots.db"

    def factory():
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    return KaipanlaSnapshotRepository(factory)


def _row(value: int) -> dict:
    return {"股票代码": "000001", "auction_net_amount": value}


def test_snapshot_type_contract_accepts_close_and_rejects_unknown_values():
    assert SNAPSHOT_TYPES == ("auction", "post_open", "close")
    assert validate_snapshot_type(None) == "auction"
    assert validate_snapshot_type("close") == "close"
    with pytest.raises(ValueError, match="auction、post_open 或 close"):
        validate_snapshot_type("evening")


def test_same_trade_date_stores_three_independent_snapshot_types(tmp_path):
    repo = _repo(tmp_path)
    saved = {
        "auction": repo.save_snapshot(
            trade_date="20260724",
            snapshot_time="2026-07-24 09:26:05",
            snapshot_type="auction",
            source_params={},
            raw_payload=[_row(1)],
            normalized_data=[_row(1)],
        ),
        "post_open": repo.save_snapshot(
            trade_date="20260724",
            snapshot_time="2026-07-24 09:31:00",
            snapshot_type="post_open",
            source_params={},
            raw_payload=[_row(2)],
            normalized_data=[_row(2)],
        ),
        "close": repo.save_snapshot(
            trade_date="20260724",
            snapshot_time="2026-07-24 15:01:00",
            snapshot_type="close",
            source_params={},
            raw_payload=[_row(3)],
            normalized_data=[_row(3)],
        ),
    }

    ids = {item.snapshot.snapshot_id for item in saved.values()}
    assert len(ids) == 3
    for snapshot_type, item in saved.items():
        assert item.created is True
        assert item.snapshot.snapshot_type == snapshot_type
        assert f"_{snapshot_type}_" in item.snapshot.snapshot_id
        loaded = repo.get_snapshot("20260724", snapshot_type)
        assert loaded is not None
        assert loaded.snapshot_id == item.snapshot.snapshot_id
