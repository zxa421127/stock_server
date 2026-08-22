# -*- coding: utf-8 -*-
from __future__ import annotations
import sqlite3
import pandas as pd
from integrations.market_data.base import ProviderResponse
from services.kaipanla_bidding_service import KaipanlaBiddingService
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


def repo(tmp_path):
    path = tmp_path / 'svc-dual.db'
    def factory():
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    return KaipanlaSnapshotRepository(factory)


def rows(label):
    return [{'股票代码':'000001','ts_code':'000001.SZ','股票名称':label,'schema_version':'kaipanla_bidding.v2'}]


def test_history_defaults_to_auction_and_selects_type(tmp_path):
    r = repo(tmp_path)
    a = r.save_snapshot(trade_date='20260723', snapshot_time='2026-07-23 09:26:05', snapshot_type='auction', source_params={}, raw_payload={'a':1}, normalized_data=rows('auction'))
    p = r.save_snapshot(trade_date='20260723', snapshot_time='2026-07-23 09:31:00', snapshot_type='post_open', source_params={}, raw_payload={'p':1}, normalized_data=rows('post'))
    svc = KaipanlaBiddingService(repository=r, market_query=lambda *a, **k: ProviderResponse(error='no fallback'))
    default = svc.query_history({'trade_date':'20260723'})
    post = svc.query_history({'trade_date':'20260723','snapshot_type':'post_open'})
    assert default.meta['snapshot_id'] == a.snapshot.snapshot_id
    assert default.meta['snapshot_type'] == 'auction'
    assert post.meta['snapshot_id'] == p.snapshot.snapshot_id
    assert post.meta['snapshot_type'] == 'post_open'


def test_invalid_snapshot_type_returns_400(tmp_path):
    result = KaipanlaBiddingService(repository=repo(tmp_path)).query_history({'snapshot_type':'later'})
    assert result.error == 'snapshot_type 只允许 auction、post_open 或 close'
    assert result.meta['http_status'] == 400


def test_missing_post_open_never_falls_back_to_auction_or_tushare(tmp_path):
    r = repo(tmp_path)
    r.save_snapshot(trade_date='20260723', snapshot_time='2026-07-23 09:26:05', snapshot_type='auction', source_params={}, raw_payload={}, normalized_data=rows('auction'))
    svc = KaipanlaBiddingService(repository=r, market_query=lambda *a, **k: (_ for _ in ()).throw(AssertionError('must not fallback')))
    result = svc.query_history({'trade_date':'20260723','snapshot_type':'post_open'})
    assert result.meta['http_status'] == 404
    assert result.meta['snapshot_type'] == 'post_open'


def test_snapshot_id_type_must_match_requested_type(tmp_path):
    r = repo(tmp_path)
    saved = r.save_snapshot(trade_date='20260723', snapshot_time='2026-07-23 09:31:00', snapshot_type='post_open', source_params={}, raw_payload={}, normalized_data=rows('post'))
    svc = KaipanlaBiddingService(repository=r)
    result = svc.query_history({'snapshot_id':saved.snapshot.snapshot_id,'snapshot_type':'auction'})
    assert result.meta['http_status'] == 400
