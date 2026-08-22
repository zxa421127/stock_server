from __future__ import annotations

import sqlite3
import unittest

from services.tushare_spec_monitor_repository import (
    TushareSpecMonitorRepository,
    create_tushare_spec_monitor_tables,
)


class TushareSpecMonitorRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        create_tushare_spec_monitor_tables(self.conn.cursor())
        self.conn.commit()
        self.repo = TushareSpecMonitorRepository(connection_factory=lambda: self.conn)

    def tearDown(self):
        self.conn.close()

    def test_run_snapshot_and_alert_lifecycle(self):
        run = self.repo.start_scan_run(trigger="manual", target_count=138, next_scheduled_at="2026-07-29 02:30:00")
        self.repo.upsert_snapshot(
            provider="tushare", api_name="ci_daily", official_url="https://tushare.pro/document/2?doc_id=308",
            raw_content_hash="raw1", semantic_spec_hash="sem1", parsed_spec={"api_name": "ci_daily"},
            source_format="markdown", fetched_at="2026-07-25 10:00:00", scan_run_id=run["id"],
        )
        alert = self.repo.upsert_change_alert(
            provider="tushare", api_name="ci_daily", title="中信行业指数行情",
            semantic_spec_hash="sem1", severity="blocking", diffs=[{"change_type": "input_added"}],
            scan_run_id=run["id"],
        )
        duplicate = self.repo.upsert_change_alert(
            provider="tushare", api_name="ci_daily", title="中信行业指数行情",
            semantic_spec_hash="sem1", severity="blocking", diffs=[{"change_type": "input_added"}],
            scan_run_id=run["id"],
        )
        self.assertEqual(alert["id"], duplicate["id"])
        self.assertEqual(len(self.repo.list_alerts(statuses=["new"])), 1)
        self.repo.mark_alerts_candidate([alert["id"]], "candidate-1")
        self.assertEqual(self.repo.get_alert(alert["id"])["status"], "candidate_ready")
        self.repo.mark_alerts_published([alert["id"]], "spec-1")
        self.repo.mark_alerts_verified([alert["id"]])
        self.assertEqual(self.repo.get_alert(alert["id"])["status"], "verified")
        self.repo.finish_scan_run(run["id"], status="success", success_count=1, failure_count=0, changed_count=1)
        self.assertEqual(self.repo.latest_scan_run()["status"], "success")


    def test_repository_commits_alert_updates_with_fresh_connections(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "monitor.db"
            opened_connections = []

            def factory():
                conn = sqlite3.connect(database)
                conn.row_factory = sqlite3.Row
                opened_connections.append(conn)
                return conn

            try:
                repo = TushareSpecMonitorRepository(connection_factory=factory)
                run = repo.start_scan_run(trigger="manual", target_count=1)
                alert = repo.upsert_change_alert(
                    provider="tushare", api_name="ci_daily", title="中信行业指数行情",
                    semantic_spec_hash="sem-fresh", severity="warning",
                    diffs=[{"change_type": "description_changed"}], scan_run_id=run["id"],
                )
                repo.mark_alerts_viewed([alert["id"]])
                self.assertEqual(repo.get_alert(alert["id"])["status"], "viewed")
            finally:
                for connection in opened_connections:
                    try:
                        connection.close()
                    except sqlite3.Error:
                        pass

    def test_verified_alert_is_reopened_when_same_official_contract_diff_reappears(self):
        run = self.repo.start_scan_run(trigger="manual", target_count=1)
        alert = self.repo.upsert_change_alert(
            provider="tushare", api_name="ci_daily", title="中信行业指数行情",
            semantic_spec_hash="sem-reopen", severity="warning",
            diffs=[{"change_type": "description_changed"}], scan_run_id=run["id"],
        )
        self.repo.mark_alerts_verified([alert["id"]])
        reopened = self.repo.upsert_change_alert(
            provider="tushare", api_name="ci_daily", title="中信行业指数行情",
            semantic_spec_hash="sem-reopen", severity="blocking",
            diffs=[{"change_type": "input_removed"}], scan_run_id=run["id"],
        )
        self.assertEqual(reopened["status"], "new")
        self.assertEqual(reopened["severity"], "blocking")

    def test_lease_prevents_duplicate_monitor(self):
        self.assertTrue(self.repo.acquire_lease("monitor", owner="worker-a", lease_seconds=60))
        self.assertFalse(self.repo.acquire_lease("monitor", owner="worker-b", lease_seconds=60))
        self.repo.release_lease("monitor", owner="worker-a")
        self.assertTrue(self.repo.acquire_lease("monitor", owner="worker-b", lease_seconds=60))


if __name__ == "__main__":
    unittest.main()
