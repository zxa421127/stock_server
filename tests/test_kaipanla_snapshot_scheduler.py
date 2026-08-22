# -*- coding: utf-8 -*-
from __future__ import annotations
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from integrations.market_data.base import ProviderResponse
from services.kaipanla_snapshot_scheduler import KaipanlaSnapshotScheduler, SnapshotSchedulerSettings


class FakeRepository:
    def __init__(self): self.exists=set(); self.lease_allowed=True; self.acquired=[]; self.released=[]; self.pruned=[]
    def has_snapshot(self,trade_date,snapshot_type='auction'): return (trade_date,snapshot_type) in self.exists
    def acquire_lease(self,name,owner,ttl_seconds,now=None): self.acquired.append((name,owner,ttl_seconds)); return self.lease_allowed
    def release_lease(self,name,owner): self.released.append((name,owner))
    def prune_before(self,trade_date): self.pruned.append(trade_date); return 0


class FakeService:
    def __init__(self): self.open_day=True; self.calls=[]
    def get_open_date_status(self,trade_date): return 'unknown' if self.open_day is None else ('open' if self.open_day else 'closed')
    def capture_snapshot(self,**kwargs):
        self.calls.append(kwargs); return ProviderResponse(data=pd.DataFrame([{'ts_code':'000001.SZ'}]),meta={'snapshot_id':'snap-1','snapshot_created':True,'record_count':1})


class KaipanlaSnapshotSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.repo=FakeRepository(); self.service=FakeService()
        self.settings=SnapshotSchedulerSettings(enabled=True,auction_hour=9,auction_minute=26,auction_second=5,post_open_hour=9,post_open_minute=31,post_open_second=0,window_seconds=120,poll_seconds=5,page_size=1000,max_pages=10,lease_seconds=300,retention_days=1095)
        self.scheduler=KaipanlaSnapshotScheduler(service=self.service,repository=self.repo,settings=self.settings,owner_id='worker-a'); self.tz=ZoneInfo('Asia/Shanghai')
    def test_auction_and_post_open_are_independent(self):
        a=self.scheduler.run_once(now=datetime(2026,7,17,9,26,10,tzinfo=self.tz)); p=self.scheduler.run_once(now=datetime(2026,7,17,9,31,5,tzinfo=self.tz))
        self.assertEqual(a['status'],'captured'); self.assertEqual(p['status'],'captured')
        self.assertEqual([c['snapshot_type'] for c in self.service.calls],['auction','post_open'])
    def test_outside_window_does_nothing(self):
        self.assertEqual(self.scheduler.run_once(now=datetime(2026,7,17,9,26,4,tzinfo=self.tz))['status'],'outside_window')
    def test_closed_and_unknown_calendar_do_not_capture(self):
        self.service.open_day=False; self.assertEqual(self.scheduler.run_once(now=datetime(2026,7,18,9,26,10,tzinfo=self.tz))['status'],'market_closed')
        self.service.open_day=None; self.assertEqual(self.scheduler.run_once(now=datetime(2026,7,18,9,26,10,tzinfo=self.tz))['status'],'calendar_error')
    def test_existing_same_type_or_lease_conflict_prevents_duplicate(self):
        now=datetime(2026,7,17,9,26,10,tzinfo=self.tz); self.repo.exists.add(('20260717','auction'))
        self.assertEqual(self.scheduler.run_once(now=now)['status'],'already_captured')
        self.repo.exists.clear(); self.repo.lease_allowed=False
        self.assertEqual(self.scheduler.run_once(now=now)['status'],'lease_busy')


if __name__=='__main__': unittest.main()
