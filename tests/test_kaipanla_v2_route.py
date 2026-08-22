# -*- coding: utf-8 -*-
from __future__ import annotations
from unittest.mock import patch
import pandas as pd
from flask import Flask
from routes.market_data_routes import _query_response
from services.market_data_service import MarketDataResult


def test_history_route_exposes_snapshot_quality_and_same_snapshot_identity():
    app=Flask(__name__); sid='20260714_092605_auction_abcdef123456'
    result=MarketDataResult(provider='kaipanla',data_type='morning_bidding_history',data=pd.DataFrame([{'股票代码':'000001','10':1,'13':3,'14':5,'15':-2,'snapshot_id':sid}]),meta={
        'source_provider':'kaipanla_snapshot','source_api':'morning_bidding','actual_trade_date':'20260714','requested_trade_date':'20260714','fallback_used':False,
        'snapshot_id':sid,'snapshot_time':'2026-07-14 09:26:05','payload_hash':'a'*64,'data_quality':'complete','schema_version':'kaipanla_bidding.v2'})
    with app.test_request_context('/?snapshot_id='+sid), patch('routes.market_data_routes.query_market_data',return_value=result):
        response=_query_response('kaipanla','morning_bidding/history')
    payload=response.get_json()
    assert payload['success'] is True
    assert payload['snapshot']['snapshot_id']==sid
    assert payload['quality']['schema_version']=='kaipanla_bidding.v2'
    assert payload['data'][0]['snapshot_id']==sid


def test_history_route_uses_service_http_status_for_missing_snapshot():
    app=Flask(__name__)
    result=MarketDataResult(provider='kaipanla',data_type='morning_bidding_history',data=pd.DataFrame(),error='not found',meta={'http_status':404,'snapshot_id':'missing'})
    with app.test_request_context('/?snapshot_id=missing'), patch('routes.market_data_routes.query_market_data',return_value=result):
        response,status=_query_response('kaipanla','morning_bidding/history')
    assert status==404
    assert response.get_json()['code']==404
