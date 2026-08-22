# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from integrations import kaipanla


class KaipanlaBusinessStatusTests(unittest.TestCase):
    def test_ret_protocol_accepts_numeric_and_string_zero(self):
        for value in (0, "0"):
            with self.subTest(value=value):
                status = kaipanla.evaluate_kaipanla_business_status({"ret": value, "info": [["000001"]]})
                self.assertTrue(status.success)
                self.assertEqual(status.protocol, "ret")

    def test_ret_protocol_rejects_nonzero_and_uses_message(self):
        status = kaipanla.evaluate_kaipanla_business_status({"ret": 1001, "msg": "登录失效", "info": [["000001"]]})
        self.assertFalse(status.success)
        self.assertEqual(status.protocol, "ret")
        self.assertEqual(status.message, "登录失效")

    def test_status_errcode_protocol_accepts_real_payload_shape(self):
        status = kaipanla.evaluate_kaipanla_business_status(
            {"status": 1, "errcode": "0", "day": "2026-07-20", "info": [["000001"]]}
        )
        self.assertTrue(status.success)
        self.assertEqual(status.protocol, "status_errcode")
        self.assertIn("status=1", status.code)
        self.assertIn("errcode=0", status.code)

    def test_status_errcode_protocol_rejects_failed_status_even_with_info(self):
        status = kaipanla.evaluate_kaipanla_business_status(
            {"status": 0, "errcode": "0", "message": "状态失败", "info": [["000001"]]}
        )
        self.assertFalse(status.success)
        self.assertEqual(status.message, "状态失败")

    def test_status_errcode_protocol_rejects_nonzero_errcode(self):
        status = kaipanla.evaluate_kaipanla_business_status(
            {"status": 1, "errcode": "1002", "errmsg": "权限不足", "info": [["000001"]]}
        )
        self.assertFalse(status.success)
        self.assertEqual(status.message, "权限不足")

    def test_implicit_list_payload_remains_backward_compatible(self):
        status = kaipanla.evaluate_kaipanla_business_status({"info": [["000001"]]})
        self.assertTrue(status.success)
        self.assertEqual(status.protocol, "implicit_list")

    @patch.object(kaipanla, "KAIPANLA_DEVICE_ID", "device-for-test")
    @patch.object(kaipanla, "record_kaipanla_call")
    @patch.object(kaipanla.requests, "post")
    def test_failed_business_status_never_becomes_dataframe(self, post: Mock, record_call: Mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "status": 0,
            "errcode": "1002",
            "errmsg": "权限不足",
            "info": [["000001", "不应进入DataFrame"]],
        }
        post.return_value = response

        frame, raw, error = kaipanla.call_kaipanla_api_with_raw("a=MorningBiddingList")

        self.assertIsInstance(frame, pd.DataFrame)
        self.assertTrue(frame.empty)
        self.assertEqual(raw["errcode"], "1002")
        self.assertEqual(error, "权限不足")
        record_call.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
