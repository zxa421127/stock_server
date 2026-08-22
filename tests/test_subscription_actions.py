# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import db_utils
from services.member_service import (
    apply_subscription_action,
    cancel_scheduled_subscription,
    create_or_get_user,
)


class SubscriptionActionTests(unittest.TestCase):
    def _cleanup_test_database(self):
        # Windows must release the SQLite handle before TemporaryDirectory
        # removes test.db, otherwise cleanup can fail with WinError 32.
        db_utils.close_thread_connection()
        db_utils._db_pragmas_initialized = False
        db_utils.DB_FILE = self.old_db

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.old_db = db_utils.DB_FILE
        self.addCleanup(self.tempdir.cleanup)
        self.addCleanup(self._cleanup_test_database)
        db_utils.DB_FILE = str(Path(self.tempdir.name) / "test.db")
        db_utils.close_thread_connection()
        db_utils._db_pragmas_initialized = False
        db_utils.init_db()
        self.user = create_or_get_user(username="member_test", phone="18800000000")
        self.user_id = int(self.user["id"])

    def tearDown(self):
        pass


    def test_open_and_renew_do_not_create_two_active_rows(self):
        first = apply_subscription_action(self.user_id, "general_month", "open")
        renewed = apply_subscription_action(self.user_id, "general_month", "renew")
        self.assertEqual(first["subscription_id"], renewed["subscription_id"])
        conn = db_utils.get_conn()
        active = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE user_id=? AND status='active'",
            (self.user_id,),
        ).fetchone()[0]
        orders = conn.execute(
            "SELECT operation_type FROM manual_orders WHERE user_id=? ORDER BY id",
            (self.user_id,),
        ).fetchall()
        self.assertEqual(active, 1)
        self.assertEqual([row[0] for row in orders], ["open", "renew"])

    def test_renew_rejects_different_plan(self):
        apply_subscription_action(self.user_id, "general_month", "open")
        with self.assertRaises(ValueError):
            apply_subscription_action(self.user_id, "special_month", "renew")

    def test_immediate_switch_replaces_current(self):
        old = apply_subscription_action(self.user_id, "general_month", "open")
        new = apply_subscription_action(self.user_id, "special_month", "switch_now", extra_days=2)
        conn = db_utils.get_conn()
        old_row = conn.execute("SELECT status,ended_reason FROM subscriptions WHERE id=?", (old["subscription_id"],)).fetchone()
        current = db_utils.get_active_subscription(self.user_id)
        self.assertEqual(tuple(old_row), ("replaced", "switch_now"))
        self.assertEqual(current["id"], new["subscription_id"])
        self.assertEqual(current["plan_code"], "special_month")

    def test_scheduled_switch_and_cancel(self):
        apply_subscription_action(self.user_id, "special_month", "open")
        queued = apply_subscription_action(self.user_id, "general_month", "switch_scheduled")
        scheduled = db_utils.get_scheduled_subscriptions(self.user_id)
        self.assertEqual([row["id"] for row in scheduled], [queued["subscription_id"]])
        cancel_scheduled_subscription(self.user_id, queued["subscription_id"], operator_name="admin")
        self.assertEqual(db_utils.get_scheduled_subscriptions(self.user_id), [])
        status = db_utils.get_conn().execute(
            "SELECT status FROM subscriptions WHERE id=?", (queued["subscription_id"],)
        ).fetchone()[0]
        self.assertEqual(status, "cancelled")

    def test_renew_moves_scheduled_queue_forward(self):
        apply_subscription_action(self.user_id, "general_month", "open")
        queued = apply_subscription_action(self.user_id, "special_month", "switch_scheduled")
        before = db_utils.get_conn().execute(
            "SELECT start_time,expire_time FROM subscriptions WHERE id=?",
            (queued["subscription_id"],),
        ).fetchone()
        apply_subscription_action(self.user_id, "general_month", "renew")
        after = db_utils.get_conn().execute(
            "SELECT start_time,expire_time FROM subscriptions WHERE id=?",
            (queued["subscription_id"],),
        ).fetchone()
        self.assertGreater(after["start_time"], before["start_time"])
        self.assertGreater(after["expire_time"], before["expire_time"])

    def test_immediate_switch_can_preserve_and_rebase_queue(self):
        apply_subscription_action(self.user_id, "general_month", "open")
        queued = apply_subscription_action(self.user_id, "special_year", "switch_scheduled")
        switched = apply_subscription_action(
            self.user_id, "special_month", "switch_now", cancel_scheduled=False
        )
        queued_row = db_utils.get_conn().execute(
            "SELECT status,start_time FROM subscriptions WHERE id=?",
            (queued["subscription_id"],),
        ).fetchone()
        self.assertEqual(queued_row["status"], "scheduled")
        self.assertEqual(queued_row["start_time"], switched["expire_time"])

    def test_due_scheduled_subscription_is_promoted(self):
        apply_subscription_action(self.user_id, "general_month", "open")
        queued = apply_subscription_action(self.user_id, "special_month", "switch_scheduled")
        conn = db_utils.get_conn()
        conn.execute(
            "UPDATE subscriptions SET expire_time='2000-01-01 00:00:00' WHERE user_id=? AND status='active'",
            (self.user_id,),
        )
        conn.execute(
            "UPDATE subscriptions SET start_time='2000-01-02 00:00:00',expire_time='2126-01-01 00:00:00' WHERE id=?",
            (queued["subscription_id"],),
        )
        conn.commit()
        current = db_utils.get_active_subscription(self.user_id)
        self.assertEqual(current["id"], queued["subscription_id"])
        self.assertEqual(current["plan_code"], "special_month")

    def test_initial_open_rejects_existing_queue(self):
        apply_subscription_action(self.user_id, "general_month", "open")
        apply_subscription_action(self.user_id, "special_month", "switch_scheduled")
        with self.assertRaises(ValueError):
            apply_subscription_action(self.user_id, "general_month", "open")


if __name__ == "__main__":
    unittest.main()
