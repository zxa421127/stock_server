# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from services import market_data_service


class KaipanlaSnapshotStartupTests(unittest.TestCase):
    def test_web_process_can_disable_in_process_snapshot_scheduler(self):
        with patch.object(market_data_service.config, "MARKET_DATA_PREWARM_ENABLED", False), \
             patch.object(market_data_service.config, "KAIPANLA_SNAPSHOT_IN_PROCESS", False, create=True), \
             patch(
                 "services.kaipanla_snapshot_scheduler.start_kaipanla_snapshot_scheduler"
             ) as start_scheduler:
            market_data_service.start_market_data_background_services()

        start_scheduler.assert_not_called()

    def test_env_example_keeps_snapshot_disabled_by_default_and_documents_all_settings(self):
        text = Path(".env.example").read_text(encoding="utf-8")
        self.assertIn("KAIPANLA_SNAPSHOT_ENABLED=False", text)
        for name in (
            "KAIPANLA_SNAPSHOT_IN_PROCESS",
            "KAIPANLA_AUCTION_SNAPSHOT_HOUR",
            "KAIPANLA_AUCTION_SNAPSHOT_MINUTE",
            "KAIPANLA_AUCTION_SNAPSHOT_SECOND",
            "KAIPANLA_POST_OPEN_SNAPSHOT_HOUR",
            "KAIPANLA_POST_OPEN_SNAPSHOT_MINUTE",
            "KAIPANLA_POST_OPEN_SNAPSHOT_SECOND",
            "KAIPANLA_SNAPSHOT_WINDOW_SECONDS",
            "KAIPANLA_SNAPSHOT_POLL_SECONDS",
            "KAIPANLA_SNAPSHOT_PAGE_SIZE",
            "KAIPANLA_SNAPSHOT_MAX_PAGES",
            "KAIPANLA_SNAPSHOT_LEASE_SECONDS",
            "KAIPANLA_SNAPSHOT_RETENTION_DAYS",
        ):
            self.assertIn(f"{name}=", text)


if __name__ == "__main__":
    unittest.main()
