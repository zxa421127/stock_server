# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import db_utils
from services.plan_catalog import LEGACY_PUBLIC_PLAN_MIGRATION
from tools.db.apply_two_tier_plans import main as apply_migration


class TwoTierPlanMigrationTests(unittest.TestCase):
    def _cleanup(self):
        conn = getattr(db_utils._local, "conn", None)
        if conn is not None:
            conn.close()
        db_utils._local.conn = None
        db_utils._db_pragmas_initialized = False
        db_utils.DB_FILE = self.old_db

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db = db_utils.DB_FILE
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._cleanup)
        db_utils.DB_FILE = str(Path(self.tempdir.name) / "migration.db")
        old_conn = getattr(db_utils._local, "conn", None)
        if old_conn is not None:
            old_conn.close()
        db_utils._local.conn = None
        db_utils._db_pragmas_initialized = False
        db_utils.init_db()

    def test_legacy_rows_are_mapped_before_old_plans_are_deleted(self):
        conn = db_utils.get_conn()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        expire = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            "INSERT INTO users (username,phone,status,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("legacy", "18812345678", "active", now, now),
        )
        user_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        # Simulate the previous built-in public plan catalog.
        old_plans = {
            "developer_points_month": ("research", "month", 30),
            "developer_full_month": ("research", "month", 30),
            "history_quarter": ("history", "quarter", 90),
            "realtime_year": ("realtime", "year", 365),
        }
        for code, (plan_type, duration_type, days) in old_plans.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO plans (
                    plan_code,plan_name,plan_type,duration_type,duration_days,
                    original_price_cent,sale_price_cent,quota_daily,quota_per_minute,
                    max_symbols_per_request,min_refresh_interval_sec,scopes,status,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    code, code, plan_type, duration_type, days, 100, 100, 1000,
                    1000, 100, 0, json.dumps(["legacy"]), "active", now, now,
                ),
            )

        conn.execute(
            """
            INSERT INTO subscriptions (
                user_id,plan_code,plan_type,start_time,expire_time,status,
                source_order_no,created_at,updated_at
            ) VALUES (?,?,?,?,?,'active',?,?,?)
            """,
            (user_id, "developer_points_month", "research", now, expire, "OLD-SUB", now, now),
        )
        conn.execute(
            """
            INSERT INTO manual_orders (
                order_no,user_id,plan_code,plan_type,duration_type,amount_cent,
                previous_plan_code,created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                "OLD-ORDER", user_id, "realtime_year", "realtime", "year",
                100, "history_quarter", now,
            ),
        )
        conn.commit()

        apply_migration()

        sub = conn.execute(
            "SELECT plan_code,plan_type,start_time,expire_time FROM subscriptions WHERE source_order_no='OLD-SUB'"
        ).fetchone()
        self.assertEqual(sub["plan_code"], "general_month")
        self.assertEqual(sub["plan_type"], "general")
        self.assertEqual(sub["start_time"], now)
        self.assertEqual(sub["expire_time"], expire)

        order = conn.execute(
            "SELECT plan_code,plan_type,duration_type,previous_plan_code FROM manual_orders WHERE order_no='OLD-ORDER'"
        ).fetchone()
        self.assertEqual(tuple(order), ("special_year", "special", "year", "general_quarter"))

        old_codes = sorted(LEGACY_PUBLIC_PLAN_MIGRATION)
        placeholders = ",".join("?" for _ in old_codes)
        old_count = conn.execute(
            f"SELECT COUNT(*) FROM plans WHERE plan_code IN ({placeholders})",
            old_codes,
        ).fetchone()[0]
        self.assertEqual(old_count, 0)

        public = db_utils.list_active_plans()
        self.assertEqual(
            [row["plan_code"] for row in public],
            [
                "general_month", "general_quarter", "general_year",
                "special_month", "special_quarter", "special_year",
            ],
        )


if __name__ == "__main__":
    unittest.main()
