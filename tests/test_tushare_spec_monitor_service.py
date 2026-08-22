from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.market_interface_spec_service import MarketInterfaceSpecService
from services.tushare_spec_monitor_repository import TushareSpecMonitorRepository, create_tushare_spec_monitor_tables
from services.tushare_spec_monitor_service import TushareSpecMonitorService
from services.tushare_spec_sync_service import TushareSpecSyncService


class FakeMonitorSync(TushareSpecSyncService):
    def __init__(self, spec_service, documents):
        super().__init__(spec_service)
        self.documents = documents

    def fetch_official_document(self, spec):
        return self.documents[spec["api_name"]]

    def fetch_and_parse_official_spec(self, spec):
        document = self.fetch_official_document(spec)
        from services.tushare_spec_sync_service import parse_tushare_official_document
        raw = parse_tushare_official_document(
            document["text"], document["url"], content_type=document.get("content_type", ""),
        )
        raw["api_name"] = spec["api_name"]
        raw["official_url"] = spec.get("official_url") or document["url"]
        raw["source_url"] = document["url"]
        return raw, document


class TushareSpecMonitorServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.specs = MarketInterfaceSpecService(Path(self.tempdir.name) / "specs")
        self.specs.ensure_seed_release()
        # Simulate a legacy sample-derived active contract so monitoring has a real change to detect.
        import json
        rows = self.specs.list_effective_specs()
        for row in rows:
            if row.get("provider") == "tushare" and row.get("api_name") == "ci_daily":
                row["title"] = "中信行业指数日行情"
                row["description"] = "项目样例规格"
                row["permission_text"] = ""
                row["limit_text"] = ""
                row["input_params"] = [item for item in row["input_params"] if item["name"] in {"start_date", "end_date"}]
                row["official_verified"] = False
                row["source_kind"] = "catalog_seed"
                break
        version = "legacy-ci-sample"
        release = self.specs.releases_dir / version
        release.mkdir(parents=True)
        (release / "effective_specs.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        (release / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs.current_file.write_text(json.dumps({"version": version}), encoding="utf-8")
        self.specs._cache_version = ""
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        create_tushare_spec_monitor_tables(self.conn.cursor())
        self.conn.commit()
        self.repo = TushareSpecMonitorRepository(connection_factory=lambda: self.conn)
        text = (Path(__file__).parent / "fixtures" / "tushare_docs" / "ci_daily_308.md").read_text(encoding="utf-8")
        self.documents = {"ci_daily": {"text": text, "url": "https://tushare.pro/wctapi/documents/308.md", "content_type": "text/markdown"}}

    def tearDown(self):
        self.conn.close()

    def test_scan_creates_change_alert_without_publishing(self):
        before = self.specs.current_version()
        service = TushareSpecMonitorService(
            spec_service=self.specs,
            repository=self.repo,
            sync_service=FakeMonitorSync(self.specs, self.documents),
        )
        result = service.scan(api_names=["ci_daily"], trigger="manual")
        self.assertEqual(result["changed_count"], 1)
        self.assertEqual(self.specs.current_version(), before)
        alerts = self.repo.list_alerts(statuses=["new"])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["api_name"], "ci_daily")
        self.assertTrue(any(d["change_type"] == "input_added" for d in alerts[0]["diffs"]))

    def test_sync_alerts_refetches_and_creates_candidate(self):
        service = TushareSpecMonitorService(
            spec_service=self.specs,
            repository=self.repo,
            sync_service=FakeMonitorSync(self.specs, self.documents),
        )
        service.scan(api_names=["ci_daily"], trigger="manual")
        alert = self.repo.list_alerts(statuses=["new"])[0]
        result = service.create_candidate_for_alerts([alert["id"]], candidate_version="candidate-ci")
        self.assertEqual(result["version"], "candidate-ci")
        self.assertEqual(self.repo.get_alert(alert["id"])["status"], "candidate_ready")
        candidate = self.specs.load_candidate("candidate-ci")
        self.assertEqual(len(candidate["specs"][0]["input_params"]), 4)

    def test_sync_requires_at_least_one_alert(self):
        service = TushareSpecMonitorService(
            spec_service=self.specs,
            repository=self.repo,
            sync_service=FakeMonitorSync(self.specs, self.documents),
        )
        with self.assertRaisesRegex(ValueError, "至少选择一个"):
            service.create_candidate_for_alerts([])
