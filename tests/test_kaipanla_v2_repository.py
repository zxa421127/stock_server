# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


def repo(tmp_path):
    path=tmp_path/"snapshots.db"
    def factory():
        conn=sqlite3.connect(path,timeout=10,check_same_thread=False); conn.row_factory=sqlite3.Row; return conn
    return KaipanlaSnapshotRepository(factory)


def row(value=1):
    return {"股票代码":"000001","auction_match_amount":value,"main_net_amount":3,"main_buy_amount":5,"main_sell_amount":2,"schema_version":"kaipanla_bidding.v2"}


def test_same_date_and_type_is_immutable_even_when_payload_changes(tmp_path):
    r=repo(tmp_path)
    first=r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:26:05",snapshot_type="auction",source_params={},raw_payload=[row(1)],normalized_data=[row(1)])
    later=r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:26:35",snapshot_type="auction",source_params={},raw_payload=[row(999)],normalized_data=[row(999)])
    assert first.created is True
    assert later.created is False
    assert later.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert r.get_snapshot("20260714","auction").normalized_data[0]["auction_match_amount"] == 1


def test_same_date_allows_auction_and_post_open_without_overwrite(tmp_path):
    r=repo(tmp_path)
    auction=r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:26:05",snapshot_type="auction",source_params={},raw_payload=[row(1)],normalized_data=[row(1)])
    post=r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:31:00",snapshot_type="post_open",source_params={},raw_payload=[row(2)],normalized_data=[row(2)])
    assert auction.created and post.created
    assert "_auction_" in auction.snapshot.snapshot_id
    assert "_post_open_" in post.snapshot.snapshot_id
    assert r.get_snapshot("20260714","auction").normalized_data[0]["auction_match_amount"] == 1
    assert r.get_snapshot("20260714","post_open").normalized_data[0]["auction_match_amount"] == 2


def test_snapshot_read_injects_type_without_exposing_raw_numeric_positions(tmp_path):
    r=repo(tmp_path)
    saved=r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:26:05",source_params={},raw_payload=[{"10":1}],normalized_data=[row()])
    loaded=r.get_by_id(saved.snapshot.snapshot_id)
    assert loaded.raw_payload == [{"10":1}]
    assert loaded.normalized_data[0]["snapshot_type"] == "auction"
    assert "10" not in loaded.normalized_data[0]


def test_latest_on_or_before_is_isolated_by_type(tmp_path):
    r=repo(tmp_path)
    r.save_snapshot(trade_date="20260714",snapshot_time="2026-07-14 09:26:05",snapshot_type="auction",source_params={},raw_payload=[row(14)],normalized_data=[row(14)])
    r.save_snapshot(trade_date="20260716",snapshot_time="2026-07-16 09:31:00",snapshot_type="post_open",source_params={},raw_payload=[row(16)],normalized_data=[row(16)])
    assert r.get_latest_snapshot("20260715","auction").trade_date == "20260714"
    assert r.get_latest_snapshot("20260715","post_open") is None


def test_database_lease_names_can_isolate_snapshot_types(tmp_path):
    r=repo(tmp_path); now=datetime(2026,7,14,1,26,tzinfo=timezone.utc)
    assert r.acquire_lease("capture:20260714:auction","a",60,now=now)
    assert not r.acquire_lease("capture:20260714:auction","b",60,now=now)
    assert r.acquire_lease("capture:20260714:post_open","b",60,now=now)


def test_concurrent_same_type_writers_create_only_one_row(tmp_path):
    r=repo(tmp_path)
    def save(n):
        return r.save_snapshot(trade_date="20260714",snapshot_time=f"2026-07-14 09:26:{n:02d}",snapshot_type="auction",source_params={},raw_payload=[row(n)],normalized_data=[row(n)])
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(save,range(4)))
    assert sum(x.created for x in results)==1
    assert len({x.snapshot.snapshot_id for x in results})==1
