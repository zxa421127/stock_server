# -*- coding: utf-8 -*-
from __future__ import annotations
import sqlite3
import pandas as pd
from integrations.market_data.base import ProviderResponse
from services.kaipanla_bidding_service import KaipanlaBiddingService
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


def make_repo(tmp_path):
    path=tmp_path/'service.db'
    def factory():
        conn=sqlite3.connect(path,check_same_thread=False); conn.row_factory=sqlite3.Row; return conn
    return KaipanlaSnapshotRepository(factory)


def normalized(code='000001'):
    return [{'股票代码':code,'ts_code':f'{code}.SZ','auction_match_amount':1,'main_net_amount':3,'main_buy_amount':5,'main_sell_amount':2,'schema_version':'kaipanla_bidding.v2'}]


def test_exact_snapshot_id_returns_same_batch_for_list_and_detail(tmp_path):
    r=make_repo(tmp_path); rows=normalized('000001')+normalized('000002')+normalized('000003')
    saved=r.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:26:05',snapshot_type='auction',source_params={},raw_payload=rows,normalized_data=rows)
    svc=KaipanlaBiddingService(repository=r,market_query=lambda *a,**k: ProviderResponse(error='must not fallback'))
    top=svc.query_history({'snapshot_id':saved.snapshot.snapshot_id,'snapshot_type':'auction','limit':'2'})
    detail=svc.query_history({'snapshot_id':saved.snapshot.snapshot_id,'snapshot_type':'auction','ts_code':'000002.SZ'})
    assert top.error is None and detail.error is None
    assert top.meta['snapshot_id']==detail.meta['snapshot_id']==saved.snapshot.snapshot_id
    assert top.meta['snapshot_type']=='auction'
    assert len(top.data)==2 and detail.data.iloc[0]['ts_code']=='000002.SZ'


def test_history_default_is_auction_and_latest_lookup_is_type_isolated(tmp_path):
    r=make_repo(tmp_path)
    r.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:26:05',snapshot_type='auction',source_params={},raw_payload=normalized(),normalized_data=normalized())
    r.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:31:00',snapshot_type='post_open',source_params={},raw_payload=normalized(),normalized_data=normalized())
    svc=KaipanlaBiddingService(repository=r,market_query=lambda *a,**k: ProviderResponse(error='must not fallback'))
    default=svc.query_history({'trade_date':'20260714'})
    post=svc.query_history({'trade_date':'20260714','snapshot_type':'post_open'})
    assert default.meta['snapshot_type']=='auction'
    assert post.meta['snapshot_type']=='post_open'
    assert default.meta['snapshot_id'] != post.meta['snapshot_id']


def test_auction_missing_can_fallback_to_tushare_partial_without_raw_public_fields(tmp_path):
    r=make_repo(tmp_path)
    def market_query(provider,api,params,**kwargs):
        assert provider=='tushare'
        if api=='trade_cal': return ProviderResponse(data=pd.DataFrame([{'cal_date':'20260714','is_open':1}]))
        if api=='stk_auction_o': return ProviderResponse(data=pd.DataFrame([{'ts_code':'000001.SZ','name':'平安银行','price':12.3,'pre_close':12.0,'amount':1000,'trade_date':'20260714'}]),meta={'actual_trade_date':'20260714'})
        return ProviderResponse(data=pd.DataFrame())
    result=KaipanlaBiddingService(repository=r,market_query=market_query).query_history({'trade_date':'20260714'})
    assert result.error is None and result.meta['source_provider']=='tushare' and result.meta['data_quality']=='partial'
    assert pd.isna(result.data.iloc[0]['auction_match_amount'])
    for raw in ('10','13','14','15'):
        assert raw not in result.data.columns


def test_post_open_missing_never_falls_back_to_auction_or_tushare(tmp_path):
    r=make_repo(tmp_path)
    r.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:26:05',snapshot_type='auction',source_params={},raw_payload=normalized(),normalized_data=normalized())
    svc=KaipanlaBiddingService(repository=r,market_query=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no fallback')))
    result=svc.query_history({'trade_date':'20260714','snapshot_type':'post_open'})
    assert result.error and result.meta['http_status']==404 and result.meta['snapshot_type']=='post_open'


def test_invalid_snapshot_type_is_400_and_exact_id_type_mismatch_is_400(tmp_path):
    r=make_repo(tmp_path)
    saved=r.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:26:05',snapshot_type='auction',source_params={},raw_payload=normalized(),normalized_data=normalized())
    svc=KaipanlaBiddingService(repository=r,market_query=lambda *a,**k: ProviderResponse())
    invalid=svc.query_history({'snapshot_type':'bad'})
    mismatch=svc.query_history({'snapshot_id':saved.snapshot.snapshot_id,'snapshot_type':'post_open'})
    assert invalid.meta['http_status']==400
    assert mismatch.meta['http_status']==400
