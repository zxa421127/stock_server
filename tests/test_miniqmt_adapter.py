# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import pandas as pd

from integrations.market_data.miniqmt.adapter import full_tick_to_frame, market_data_to_frame


class MiniQmtAdapterTests(unittest.TestCase):
    def test_market_data_dict_is_flattened(self):
        payload = {"000001.SZ": pd.DataFrame([{"close": 10.0}])}
        df = market_data_to_frame(payload)
        self.assertEqual(df.loc[0, "symbol"], "000001.SZ")
        self.assertEqual(df.loc[0, "close"], 10.0)

    def test_full_tick_is_flattened(self):
        df = full_tick_to_frame({"000001.SZ": {"lastPrice": 10.1}})
        self.assertEqual(df.loc[0, "symbol"], "000001.SZ")
        self.assertEqual(df.loc[0, "lastPrice"], 10.1)


if __name__ == "__main__":
    unittest.main()
