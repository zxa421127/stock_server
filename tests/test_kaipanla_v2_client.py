# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import pandas as pd

from integrations.market_data.kaipanla.client import KaipanlaClient


class KaipanlaBiddingClientTests(unittest.TestCase):
    def test_collects_pages_until_short_page_and_deduplicates_codes(self):
        calls: list[int] = []
        pages = {
            0: pd.DataFrame([["000001", "A"], ["000002", "B"]]),
            1: pd.DataFrame([["000002", "B2"], ["000003", "C"]]),
            2: pd.DataFrame([["000004", "D"]]),
        }

        def fetch_page(**kwargs):
            index = kwargs["index"]
            calls.append(index)
            frame = pages[index]
            return frame, {"ret": 0, "info": frame.values.tolist()}, None, kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=2, max_pages=10)

        self.assertIsNone(result.error)
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(result.data[0].tolist(), ["000001", "000002", "000003", "000004"])
        self.assertEqual(len(result.raw_pages), 3)
        self.assertEqual(result.params["st"], 2)

    def test_detects_offset_style_indexing_from_high_page_overlap(self):
        calls: list[int] = []
        pages = {
            0: pd.DataFrame([[f"{i:06d}", f"N{i}"] for i in range(1, 6)]),
            1: pd.DataFrame([[f"{i:06d}", f"N{i}"] for i in range(2, 7)]),
            5: pd.DataFrame([[f"{i:06d}", f"N{i}"] for i in range(6, 11)]),
            10: pd.DataFrame([["000011", "N11"]]),
        }

        def fetch_page(**kwargs):
            index = kwargs["index"]
            calls.append(index)
            frame = pages[index]
            return frame, {"ret": 0, "info": frame.values.tolist()}, None, kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=5, max_pages=10)

        self.assertIsNone(result.error)
        self.assertEqual(calls, [0, 1, 5, 10])
        self.assertEqual(len(result.data), 11)
        self.assertEqual(result.params["index_mode"], "offset")


    def test_probes_second_page_when_upstream_caps_requested_page_size(self):
        calls: list[int] = []
        pages = {
            0: pd.DataFrame([["000001", "A"], ["000002", "B"]]),
            1: pd.DataFrame([["000003", "C"]]),
        }

        def fetch_page(**kwargs):
            index = kwargs["index"]
            calls.append(index)
            frame = pages.get(index, pd.DataFrame())
            return frame, {"ret": 0, "info": frame.values.tolist()}, None, kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=5, max_pages=10)

        self.assertEqual(calls, [0, 1])
        self.assertEqual(result.data[0].tolist(), ["000001", "000002", "000003"])

    def test_stops_when_index_is_ignored_even_if_values_change(self):
        calls: list[int] = []

        def fetch_page(**kwargs):
            index = kwargs["index"]
            calls.append(index)
            frame = pd.DataFrame([["000001", f"A-{index}"], ["000002", f"B-{index}"]])
            return frame, {"ret": 0, "info": frame.values.tolist()}, None, kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=2, max_pages=10)

        self.assertEqual(calls, [0, 1])
        self.assertEqual(len(result.data), 2)


    def test_stops_when_upstream_repeats_the_same_full_page(self):
        calls: list[int] = []
        page = pd.DataFrame([["000001", "A"], ["000002", "B"]])

        def fetch_page(**kwargs):
            calls.append(kwargs["index"])
            return page.copy(), {"ret": 0, "info": page.values.tolist()}, None, kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=2, max_pages=10)

        self.assertIsNone(result.error)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(len(result.data), 2)

    def test_any_page_error_prevents_partial_snapshot_success(self):
        first = pd.DataFrame([["000001", "A"], ["000002", "B"]])

        def fetch_page(**kwargs):
            if kwargs["index"] == 0:
                return first, {"ret": 0, "info": first.values.tolist()}, None, kwargs
            return pd.DataFrame(), None, "upstream failed", kwargs

        result = KaipanlaClient(fetch_page=fetch_page).fetch_all(page_size=2, max_pages=3)

        self.assertEqual(result.error, "upstream failed")
        self.assertEqual(len(result.data), 2)
        self.assertEqual(len(result.raw_pages), 1)


if __name__ == "__main__":
    unittest.main()
