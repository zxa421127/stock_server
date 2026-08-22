# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3

import pytest

from services.kaipanla_snapshot_repository import (
    KaipanlaSnapshotRepository,
    create_kaipanla_snapshot_tables,
    validate_snapshot_type,
)


def _repo(tmp_path):
    path = tmp_path / "snapshots.db"

    def factory():
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    return KaipanlaSnapshotRepository(factory)


def _row(value: int = 1) -> dict:
    return {"股票代码": "000001", "auction_net_amount": value}


def test_validate_snapshot_type_defaults_to_auction_and_rejects_other_values():
    assert validate_snapshot_type(None) == "auction"
    assert validate_snapshot_type("") == "auction"
    assert validate_snapshot_type("post_open") == "post_open"
    assert validate_snapshot_type("close") == "close"
    with pytest.raises(ValueError, match="auction、post_open 或 close"):
        validate_snapshot_type("evening")


def test_same_trade_date_supports_two_independent_snapshot_types(tmp_path):
    repo = _repo(tmp_path)
    auction = repo.save_snapshot(
        trade_date="20260723",
        snapshot_time="2026-07-23 09:26:05",
        snapshot_type="auction",
        source_params={},
        raw_payload=[_row(1)],
        normalized_data=[_row(1)],
    )
    post_open = repo.save_snapshot(
        trade_date="20260723",
        snapshot_time="2026-07-23 09:31:00",
        snapshot_type="post_open",
        source_params={},
        raw_payload=[_row(1)],
        normalized_data=[_row(1)],
    )

    assert auction.created is True
    assert post_open.created is True
    assert auction.snapshot.snapshot_type == "auction"
    assert post_open.snapshot.snapshot_type == "post_open"
    assert "_auction_" in auction.snapshot.snapshot_id
    assert "_post_open_" in post_open.snapshot.snapshot_id
    assert repo.get_snapshot("20260723", "auction").snapshot_id == auction.snapshot.snapshot_id
    assert repo.get_snapshot("20260723", "post_open").snapshot_id == post_open.snapshot.snapshot_id


def test_same_type_same_payload_is_idempotent_but_does_not_block_other_type(tmp_path):
    repo = _repo(tmp_path)
    first = repo.save_snapshot(
        trade_date="20260723",
        snapshot_time="2026-07-23 09:26:05",
        snapshot_type="auction",
        source_params={},
        raw_payload=[_row()],
        normalized_data=[_row()],
    )
    duplicate = repo.save_snapshot(
        trade_date="20260723",
        snapshot_time="2026-07-23 09:26:30",
        snapshot_type="auction",
        source_params={},
        raw_payload=[_row()],
        normalized_data=[_row()],
    )
    other_type = repo.save_snapshot(
        trade_date="20260723",
        snapshot_time="2026-07-23 09:31:00",
        snapshot_type="post_open",
        source_params={},
        raw_payload=[_row()],
        normalized_data=[_row()],
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert other_type.created is True


def test_legacy_rows_are_migrated_to_auction_idempotently(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE kaipanla_bidding_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            trade_date TEXT NOT NULL,
            snapshot_time TEXT NOT NULL,
            source_provider TEXT NOT NULL,
            source_api TEXT NOT NULL,
            source_params_json TEXT NOT NULL,
            raw_payload_gzip BLOB NOT NULL,
            normalized_payload_gzip BLOB NOT NULL,
            record_count INTEGER NOT NULL,
            payload_hash TEXT NOT NULL,
            data_quality TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX ux_kaipanla_snapshot_trade_hash ON kaipanla_bidding_snapshots(trade_date,payload_hash)"
    )
    conn.commit()

    create_kaipanla_snapshot_tables(conn.cursor())
    conn.commit()
    create_kaipanla_snapshot_tables(conn.cursor())
    conn.commit()

    columns = {row[1] for row in conn.execute("PRAGMA table_info(kaipanla_bidding_snapshots)")}
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(kaipanla_bidding_snapshots)")}
    assert "snapshot_type" in columns
    assert "ux_kaipanla_snapshot_trade_type_hash" in indexes
    assert "ux_kaipanla_snapshot_trade_hash" not in indexes
