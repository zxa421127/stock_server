# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from integrations.market_data.base import ProviderResponse
from services.kaipanla_snapshot_scheduler import KaipanlaSnapshotScheduler, SnapshotSchedulerSettings

class Repo:
    def __init__(self): self.types=set(); self.leases=[]
    def has_snapshot(self, d, snapshot_type='auction'): return snapshot_type in self.types
    def acquire_lease(self, name, owner, ttl, now=None): self.leases.append(name); return True
    def release_lease(self, name, owner): pass
    def prune_before(self, cutoff): return 0

class Service:
    def __init__(self, repo): self.repository=repo; self.calls=[]
    def get_open_date_status(self, d): return 'open'
    def capture_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        self.repository.types.add(kwargs['snapshot_type'])
        return ProviderResponse(data=[], meta={'snapshot_id':'id','snapshot_created':True,'record_count':1,'snapshot_type':kwargs['snapshot_type']})

def settings():
    return SnapshotSchedulerSettings(enabled=True, auction_hour=9, auction_minute=26, auction_second=5, post_open_hour=9, post_open_minute=31, post_open_second=0, window_seconds=120, poll_seconds=5, page_size=1000, max_pages=10, lease_seconds=300, retention_days=1095)

def test_scheduler_runs_each_type_in_its_own_window_and_lease():
    tz=ZoneInfo('Asia/Shanghai'); repo=Repo(); svc=Service(repo)
    scheduler=KaipanlaSnapshotScheduler(service=svc, repository=repo, settings=settings(), owner_id='worker')
    first=scheduler.run_once(now=datetime(2026,7,23,9,26,5,tzinfo=tz))
    second=scheduler.run_once(now=datetime(2026,7,23,9,31,0,tzinfo=tz))
    assert first['snapshot_type']=='auction' and second['snapshot_type']=='post_open'
    assert [c['snapshot_type'] for c in svc.calls] == ['auction','post_open']
    assert repo.leases == ['kaipanla_morning_bidding:20260723:auction','kaipanla_morning_bidding:20260723:post_open']
