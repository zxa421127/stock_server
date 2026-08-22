# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

import db_utils
from services.member_service import apply_subscription_action, create_or_get_user


class _DummyBitable:
    def _str_to_ms(self, _value):
        return 123456789


class FeishuSubscriptionFieldTests(unittest.TestCase):
    def _cleanup_test_database(self):
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
        self.addCleanup(self._cleanup_test_database)
        db_utils.DB_FILE = str(Path(self.tempdir.name) / "test.db")
        old_conn = getattr(db_utils._local, "conn", None)
        if old_conn is not None:
            old_conn.close()
        db_utils._local.conn = None
        db_utils._db_pragmas_initialized = False
        db_utils.init_db()
        user = create_or_get_user(username="feishu_test", phone="17700000000")
        self.user_id = int(user["id"])
        apply_subscription_action(self.user_id, "general_month", "open")
        apply_subscription_action(self.user_id, "special_month", "switch_scheduled", extra_days=3)

        fake_module = types.ModuleType("integrations.feishu.bitable")
        fake_module.get_bitable_manager = lambda: _DummyBitable()
        sys.modules["integrations.feishu.bitable"] = fake_module
        sys.modules.pop("services.feishu_sync_service", None)
        from services import feishu_sync_service
        self.sync = feishu_sync_service

    def tearDown(self):
        sys.modules.pop("services.feishu_sync_service", None)
        sys.modules.pop("integrations.feishu.bitable", None)


    def test_extended_fields_distinguish_current_and_scheduled_plan(self):
        rows = self.sync._get_local_member_rows(self.user_id)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["plan_code"], "general_month")
        self.assertEqual(row["scheduled_plan_code"], "special_month")

        old_flag = self.sync.config.FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED
        self.sync.config.FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED = True
        try:
            fields = self.sync._build_feishu_member_fields(row, _DummyBitable())
        finally:
            self.sync.config.FEISHU_EXTENDED_MEMBER_FIELDS_ENABLED = old_flag
        self.assertEqual(fields["授权码"], "")
        self.assertEqual(fields["套餐代码"], "general_month")
        self.assertEqual(fields["待生效套餐代码"], "special_month")
        self.assertEqual(fields["最近操作类型"], "到期后换套餐")
        self.assertEqual(fields["额外补偿天数"], 3)
        self.assertEqual(fields["待生效开始时间"], 123456789)
        self.assertEqual(fields["待生效截止时间"], 123456789)

    def test_legacy_feishu_plan_codes_map_to_current_six_plan_catalog(self):
        cases = {
            "history_month": "general_month",
            "history_quarter": "general_quarter",
            "history_year": "general_year",
            "realtime_month": "special_month",
            "realtime_quarter": "special_quarter",
            "realtime_year": "special_year",
            "developer_points_month": "general_month",
            "developer_full_month": "special_month",
        }
        for legacy_code, current_code in cases.items():
            with self.subTest(legacy_code=legacy_code):
                self.assertEqual(
                    self.sync.plan_code_from_feishu({"套餐代码": legacy_code}),
                    current_code,
                )

    def test_current_feishu_plan_code_is_kept(self):
        self.assertEqual(
            self.sync.plan_code_from_feishu({"套餐代码": "special_year"}),
            "special_year",
        )

    def test_token_log_fingerprint_never_exposes_token_or_prefix(self):
        token = "SK_STOCK_API_20260720_SUPER_SECRET_TOKEN"
        fingerprint = self.sync._token_log_fingerprint(token)
        self.assertEqual(len(fingerprint), 12)
        self.assertRegex(fingerprint, r"^[0-9a-f]{12}$")
        self.assertNotIn("SK_STOCK_API_", fingerprint)
        self.assertEqual(fingerprint, self.sync._token_log_fingerprint(token))
        self.assertNotEqual(
            fingerprint,
            self.sync._token_log_fingerprint(token + "_other"),
        )

        source = Path("services/feishu_sync_service.py").read_text(encoding="utf-8")
        self.assertNotIn("token[:18]", source)
        self.assertNotIn(" token=%s", source)


if __name__ == "__main__":
    unittest.main()
