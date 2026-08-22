# -*- coding: utf-8 -*-
from __future__ import annotations
import sqlite3

from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository
from tools.migrate_kaipanla_snapshots_v2 import migrate_repository


def test_old_snapshot_is_restored_from_raw_payload_without_modifying_raw(tmp_path):
    path=tmp_path/'migration.db'
    def factory():
        conn=sqlite3.connect(path,check_same_thread=False); conn.row_factory=sqlite3.Row; return conn
    repo=KaipanlaSnapshotRepository(factory)
    raw={"pages":[{"index":0,"response":{"ret":0,"info":[["600895","张江高科",35.15,3.47,1180010068,10.01,116352228,0.76,225834380,20927200,225834384,"光刻机、创投",27898674312,238939100,1318790483,-1079851383,"4连板"]]}}]}
    old=[{"股票代码":"600895","auction_net_amount":238939100,"auction_buy_amount":1318790483,"auction_sell_amount":1079851383}]
    saved=repo.save_snapshot(trade_date='20260714',snapshot_time='2026-07-14 09:26:05',source_params={},raw_payload=raw,normalized_data=old,schema_version='kaipanla_bidding.v1')
    before=repo.get_by_id(saved.snapshot.snapshot_id).raw_payload
    dry=migrate_repository(repo,apply=False,backup_path=None)
    assert dry['would_migrate']==1
    assert repo.get_by_id(saved.snapshot.snapshot_id).schema_version=='kaipanla_bidding.v1'
    report=migrate_repository(repo,apply=True,backup_path=str(tmp_path/'backup.db'))
    loaded=repo.get_by_id(saved.snapshot.snapshot_id)
    assert report['migrated']==1
    assert loaded.raw_payload==before
    assert loaded.schema_version=='kaipanla_bidding.v2'
    row=loaded.normalized_data[0]
    assert row['auction_match_amount']==225834384
    assert row['auction_net_amount']==116352228
    assert row['main_net_amount']==238939100
    assert row['main_buy_amount']==1318790483
    assert row['main_sell_amount']==1079851383
    assert row['snapshot_type']=='auction'
    for removed in ('10','13','14','15','auction_buy_amount','auction_sell_amount','main_sell_amount_signed'):
        assert removed not in row
    again=migrate_repository(repo,apply=True,backup_path=str(tmp_path/'backup2.db'))
    assert again['migrated']==0
