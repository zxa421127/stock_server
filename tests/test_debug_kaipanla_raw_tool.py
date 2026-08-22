# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from tools.debug_kaipanla_raw import build_debug_summary


class DebugKaipanlaRawToolTests(unittest.TestCase):
    def test_summary_uses_status_errcode_instead_of_missing_ret(self):
        raw = {
            "status": 1,
            "errcode": "0",
            "day": "2026-07-20",
            "time": 1784554616,
            "info": [["002432", "九安医疗"]],
        }

        summary = build_debug_summary(
            raw=raw,
            error=None,
            dataframe_rows=1,
            public_params={"order": 1, "st": 20, "index": 0},
        )

        self.assertTrue(summary["业务成功"])
        self.assertEqual(summary["状态协议"], "status_errcode")
        self.assertEqual(summary["状态码"], "status=1;errcode=0")
        self.assertEqual(summary["原始info条数"], 1)
        self.assertEqual(summary["day"], "2026-07-20")
        self.assertIsNone(summary["ret"])

    def test_summary_reports_business_failure_even_when_info_exists(self):
        raw = {
            "status": 0,
            "errcode": "1002",
            "errmsg": "权限不足",
            "info": [["002432", "不应接受"]],
        }

        summary = build_debug_summary(
            raw=raw,
            error="权限不足",
            dataframe_rows=0,
            public_params={"order": 1, "st": 20, "index": 0},
        )

        self.assertFalse(summary["业务成功"])
        self.assertEqual(summary["业务消息"], "权限不足")
        self.assertEqual(summary["DataFrame行数"], 0)

    def test_summary_only_contains_public_request_parameters(self):
        public = {"order": 1, "st": 20, "index": 0, "pid_type": 0, "b_type": 4}
        summary = build_debug_summary(
            raw={"status": 1, "errcode": "0", "info": []},
            error=None,
            dataframe_rows=0,
            public_params=public,
        )
        self.assertEqual(summary["安全请求参数"], public)
        rendered = repr(summary)
        self.assertNotIn("Token", rendered)
        self.assertNotIn("UserID", rendered)
        self.assertNotIn("DeviceID", rendered)


if __name__ == "__main__":
    unittest.main()
