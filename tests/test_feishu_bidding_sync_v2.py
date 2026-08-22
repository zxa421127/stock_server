# -*- coding: utf-8 -*-
from __future__ import annotations
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import pandas as pd
import services.feishu_sync_service as sync_service


def _disable_runtime_guard(monkeypatch):
    monkeypatch.setattr(sync_service,'_ensure_runtime_db_ready',lambda *a,**k: None)
    monkeypatch.setattr(sync_service,'_china_now',lambda:datetime(2026,7,17,20,0,tzinfo=ZoneInfo('Asia/Shanghai')))


def test_bidding_sync_queries_both_types_and_rejects_non_snapshot_data(monkeypatch):
    _disable_runtime_guard(monkeypatch); captured=[]
    class Service:
        def query_history(self,params):
            captured.append(dict(params)); return SimpleNamespace(error=None,data=pd.DataFrame([{'股票代码':'000001'}]),meta={'source_provider':'tushare','data_quality':'partial','fallback_used':True,'snapshot_type':params['snapshot_type']})
    monkeypatch.setattr(sync_service,'get_bitable_manager',lambda: (_ for _ in ()).throw(AssertionError('must not write partial fallback')))
    monkeypatch.setattr('services.kaipanla_bidding_service.get_kaipanla_bidding_service',lambda:Service())
    result=sync_service.sync_bidding_to_feishu()
    assert {(x['trade_date'],x['snapshot_type']) for x in captured}=={('20260717','auction'),('20260717','post_open'),('20260717','close')}
    assert {x['limit'] for x in captured}=={10000}
    assert result.counts==(0,0) and result.status=='error'


def test_bidding_sync_checks_schema_then_writes_combined_complete_snapshots(monkeypatch):
    _disable_runtime_guard(monkeypatch); order=[]
    class Service:
        def query_history(self,params):
            t=params['snapshot_type']
            return SimpleNamespace(error=None,data=pd.DataFrame([{'股票代码':'000001','snapshot_id':f'{t}-id','snapshot_type':t,'source_provider':'kaipanla','data_quality':'complete'}]),meta={'source_provider':'kaipanla_snapshot','data_quality':'complete','fallback_used':False,'snapshot_type':t})
    class Bitable:
        def ensure_bidding_schema(self,create_missing=True): order.append('schema'); return {'ok':True}
        def batch_add_bidding_records(self,rows): order.append(('write',len(rows))); return len(rows),0
    monkeypatch.setattr(sync_service,'get_bitable_manager',lambda:Bitable())
    monkeypatch.setattr('services.kaipanla_bidding_service.get_kaipanla_bidding_service',lambda:Service())
    result=sync_service.sync_bidding_to_feishu()
    assert result.counts==(3,0) and result.status=='ok'
    assert order==['schema',('write',3)]


def test_process_lock_returns_busy_without_starting_second_sync(monkeypatch,tmp_path):
    monkeypatch.setattr(sync_service.config,'FEISHU_SYNC_LOCK_FILE',str(tmp_path/'sync.lock'))
    monkeypatch.setattr(sync_service.config,'FEISHU_SYNC_LOCK_TIMEOUT_SECONDS',0)
    from services.process_lock import process_lock
    with process_lock(str(tmp_path/'sync.lock'), timeout=0) as acquired:
        assert acquired
        result=sync_service.sync_bidding_to_feishu()
        assert result.status=='busy' and result.counts==(0,0)


def test_bidding_sync_writes_available_snapshots_and_reports_missing_close(monkeypatch):
    _disable_runtime_guard(monkeypatch)
    written=[]
    class Service:
        def query_history(self,params):
            t=params['snapshot_type']
            if t == 'close':
                return SimpleNamespace(error='未找到指定条件的 close 历史快照',data=None,meta={'http_status':404,'snapshot_type':'close'})
            return SimpleNamespace(
                error=None,
                data=pd.DataFrame([{'股票代码':'000001','snapshot_id':f'{t}-id','snapshot_type':t,'source_provider':'kaipanla','data_quality':'complete'}]),
                meta={'source_provider':'kaipanla_snapshot','data_quality':'complete','fallback_used':False,'snapshot_type':t},
            )
    class Bitable:
        def ensure_bidding_schema(self,create_missing=True): return {'ok':True}
        def batch_add_bidding_records(self,rows): written.extend(rows); return len(rows),0
    monkeypatch.setattr(sync_service,'get_bitable_manager',lambda:Bitable())
    monkeypatch.setattr('services.kaipanla_bidding_service.get_kaipanla_bidding_service',lambda:Service())

    result=sync_service.sync_bidding_to_feishu()

    assert result.counts==(2,0) and result.status=='partial'
    assert {row['snapshot_type'] for row in written}=={'auction','post_open'}
    assert 'close: 未找到指定条件的 close 历史快照' in result.message


def test_scheduled_bidding_sync_marks_day_complete_only_after_all_three_snapshots(monkeypatch):
    monkeypatch.setattr(sync_service, '_china_now', lambda: datetime(2026,7,17,18,0,tzinfo=ZoneInfo('Asia/Shanghai')))
    monkeypatch.setattr(sync_service.config, 'BIDDING_SYNC_HOUR', 18)
    monkeypatch.setattr(sync_service.config, 'BIDDING_SYNC_MINUTE', 0)
    monkeypatch.setattr(sync_service, '_last_bidding_sync_date', None)

    monkeypatch.setattr(sync_service, 'sync_bidding_to_feishu', lambda: sync_service.SyncResult((2,0), status='partial', message='close missing'))
    sync_service._check_and_sync_bidding()
    assert sync_service._last_bidding_sync_date is None

    monkeypatch.setattr(sync_service, 'sync_bidding_to_feishu', lambda: sync_service.SyncResult((3,0), status='ok', message='all snapshots'))
    sync_service._check_and_sync_bidding()
    assert sync_service._last_bidding_sync_date == '2026-07-17'
