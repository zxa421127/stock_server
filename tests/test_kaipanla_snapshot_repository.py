# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sqlite3, tempfile, unittest
from datetime import datetime, timezone
from services.kaipanla_snapshot_repository import KaipanlaSnapshotRepository


class KaipanlaSnapshotRepositoryTests(unittest.TestCase):
    def setUp(self):
        handle,self.db_path=tempfile.mkstemp(suffix='.db'); os.close(handle)
        self.conn=sqlite3.connect(self.db_path,timeout=5,check_same_thread=False); self.conn.row_factory=sqlite3.Row
        self.repo=KaipanlaSnapshotRepository(connection_factory=lambda:self.conn)
    def tearDown(self):
        self.conn.close()
        try: os.remove(self.db_path)
        except FileNotFoundError: pass
    def _save(self,trade_date='20260717',snapshot_time='2026-07-17 09:26:05',snapshot_type='auction',value=1):
        return self.repo.save_snapshot(trade_date=trade_date,snapshot_time=snapshot_time,snapshot_type=snapshot_type,source_params={'st':1000},raw_payload={'pages':[{'ret':0,'info':[['000001',value]]}]},normalized_data=[{'ts_code':'000001.SZ','name':'平安银行','auction_match_amount':value}],data_quality='complete')
    def test_compressed_round_trip_injects_snapshot_identity_into_all_rows(self):
        saved=self._save(); loaded=self.repo.get_snapshot('20260717','auction')
        self.assertTrue(saved.created); self.assertEqual(loaded.snapshot_id,saved.snapshot.snapshot_id)
        self.assertEqual(loaded.normalized_data[0]['snapshot_type'],'auction')
        self.assertEqual(loaded.normalized_data[0]['snapshot_id'],loaded.snapshot_id)
        self.assertEqual(len(loaded.payload_hash),64)
    def test_same_date_same_type_is_deduplicated_even_if_payload_changes(self):
        first=self._save(value=1); second=self._save(snapshot_time='2026-07-17 09:26:35',value=2)
        self.assertTrue(first.created); self.assertFalse(second.created); self.assertEqual(first.snapshot.snapshot_id,second.snapshot.snapshot_id)
    def test_same_date_different_types_are_both_saved(self):
        auction=self._save(value=1); post=self._save(snapshot_time='2026-07-17 09:31:00',snapshot_type='post_open',value=2)
        self.assertTrue(auction.created); self.assertTrue(post.created)
        self.assertNotEqual(auction.snapshot.snapshot_id,post.snapshot.snapshot_id)
    def test_latest_lookup_is_bounded_and_type_aware(self):
        self._save('20260716','2026-07-16 09:26:05','auction')
        self._save('20260718','2026-07-18 09:31:00','post_open')
        self.assertEqual(self.repo.get_latest_snapshot('20260717','auction').trade_date,'20260716')
        self.assertIsNone(self.repo.get_latest_snapshot('20260717','post_open'))
    def test_database_lease_is_exclusive_per_name(self):
        now=datetime(2026,7,17,1,26,tzinfo=timezone.utc)
        self.assertTrue(self.repo.acquire_lease('daily:auction','a',60,now=now))
        self.assertFalse(self.repo.acquire_lease('daily:auction','b',60,now=now))
        self.assertTrue(self.repo.acquire_lease('daily:post_open','b',60,now=now))


if __name__=='__main__': unittest.main()
