# -*- coding: utf-8 -*-
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from tools.interface_tester import (
    _test_dates,
    build_sample_param_candidates,
    build_sample_params,
    get_last_completed_weekday,
)


class InterfaceTestParameterTests(unittest.TestCase):
    def test_etf_index_does_not_use_etf_code_as_index_code(self):
        self.assertEqual(build_sample_params("tushare", "etf_index"), {})
        candidates = build_sample_param_candidates("tushare", "etf_index")
        self.assertIn({"ts_code": "000300.SH"}, candidates)

    def test_st_uses_list_query_instead_of_normal_stock(self):
        self.assertEqual(build_sample_params("tushare", "st"), {})

    def test_event_financial_interfaces_do_not_pin_normal_stock(self):
        self.assertNotIn("ts_code", build_sample_params("tushare", "express"))
        self.assertNotIn("ts_code", build_sample_params("tushare", "forecast"))
        self.assertNotIn("ts_code", build_sample_params("tushare", "stk_holdertrade"))



    def test_rt_etf_k_uses_verified_sz_etf_and_bounded_fallbacks(self):
        self.assertEqual(
            build_sample_params("tushare", "rt_etf_k"),
            {"ts_code": "159919.SZ"},
        )
        candidates = build_sample_param_candidates("tushare", "rt_etf_k")
        self.assertEqual(
            candidates,
            [
                {"ts_code": "159919.SZ"},
                {"ts_code": "510300.SH"},
                {"ts_code": "510050.SH"},
            ],
        )

    def test_stock_company_acceptance_sample_limits_fields(self):
        params = build_sample_params("tushare", "stock_company")
        self.assertEqual(params["exchange"], "SZSE")
        self.assertIn("fields", params)
        self.assertIn("ts_code", params["fields"])

    def test_historical_interfaces_use_historical_dates(self):
        self.assertLess(build_sample_params("tushare", "stk_account")["end_date"], "20200101")
        self.assertLess(build_sample_params("tushare", "slb_sec")["trade_date"], "20240101")

    def test_before_market_close_uses_previous_completed_weekday(self):
        now = datetime(2026, 7, 20, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(get_last_completed_weekday(now).strftime("%Y%m%d"), "20260717")
        dates = _test_dates(now)
        self.assertEqual(dates["trade_date"], "20260717")
        self.assertEqual(dates["minute_start"], "2026-07-17 09:00:00")
        self.assertEqual(dates["minute_end"], "2026-07-17 15:30:00")

    def test_after_market_close_can_use_current_weekday(self):
        now = datetime(2026, 7, 20, 16, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(get_last_completed_weekday(now).strftime("%Y%m%d"), "20260720")
        self.assertEqual(_test_dates(now)["trade_date"], "20260720")

    def test_weekend_uses_previous_friday(self):
        now = datetime(2026, 7, 19, 18, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(get_last_completed_weekday(now).strftime("%Y%m%d"), "20260717")

    def test_daily_and_minute_samples_use_completed_day_but_realtime_stays_realtime(self):
        now = datetime(2026, 7, 20, 7, 30, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(
            build_sample_params("tushare", "stk_limit", now=now)["trade_date"],
            "20260717",
        )
        minute = build_sample_params("tushare", "stk_mins", now=now)
        self.assertEqual(minute["start_date"], "2026-07-17 09:00:00")
        self.assertEqual(minute["end_date"], "2026-07-17 15:30:00")
        self.assertEqual(
            build_sample_params("tushare", "rt_min", now=now),
            {"ts_code": "000001.SZ", "freq": "1MIN"},
        )


if __name__ == "__main__":
    unittest.main()
