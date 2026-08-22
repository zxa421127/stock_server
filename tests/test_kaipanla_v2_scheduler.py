# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from services.kaipanla_snapshot_scheduler import KaipanlaSnapshotScheduler, SnapshotSchedulerSettings


class Repo:
    def __init__(self): self.existing=set(); self.leases=[]
    def has_snapshot(self,d,t='auction'): return (d,t) in self.existing
    def acquire_lease(self,name,owner,ttl,now=None): self.leases.append((name,owner)); return True
    def release_lease(self,name,owner): pass
    def prune_before(self,cutoff): return 0


class Service:
    def __init__(self,repo): self.repository=repo; self.calls=[]
    def get_open_date_status(self,d): return 'open'
    def capture_snapshot(self,**kwargs):
        self.calls.append(kwargs)
        return type('R',(),{'error':None,'data':[],'meta':{'snapshot_id':'x','snapshot_created':True,'record_count':1}})()


def settings():
    return SnapshotSchedulerSettings(True,9,26,5,9,31,0,120,5,1000,10,300,1095)


def test_scheduler_triggers_each_snapshot_in_its_own_window_and_lease():
    repo=Repo(); svc=Service(repo); sched=KaipanlaSnapshotScheduler(service=svc,repository=repo,settings=settings(),owner_id='worker'); tz=ZoneInfo('Asia/Shanghai')
    assert sched.run_once(now=datetime(2026,7,14,9,26,4,tzinfo=tz))['status']=='outside_window'
    first=sched.run_once(now=datetime(2026,7,14,9,26,5,tzinfo=tz))
    second=sched.run_once(now=datetime(2026,7,14,9,31,0,tzinfo=tz))
    assert first['snapshot_type']=='auction' and second['snapshot_type']=='post_open'
    assert [call['snapshot_type'] for call in svc.calls]==['auction','post_open']
    assert {name for name,_ in repo.leases}=={'kaipanla_morning_bidding:20260714:auction','kaipanla_morning_bidding:20260714:post_open'}
