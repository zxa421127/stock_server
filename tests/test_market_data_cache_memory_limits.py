from __future__ import annotations

import zlib

import pandas as pd
import pytest

from services.market_data_cache import (
    CachePayloadTooLarge,
    TTLDataFrameCache,
    dataframe_memory_bytes,
    deserialize_cache_item,
)


def test_local_cache_skips_item_larger_than_item_budget():
    frame = pd.DataFrame([{"value": "x" * 1000}])
    cache = TTLDataFrameCache(max_items=10, max_item_bytes=100, max_total_bytes=10_000)
    assert cache.set("large", frame, 30) is False
    assert cache.get("large") is None
    assert cache.stats()["skipped_oversize"] == 1


def test_local_cache_evicts_oldest_items_to_meet_total_byte_budget():
    first = pd.DataFrame([{"value": "a" * 100}])
    second = pd.DataFrame([{"value": "b" * 100}])
    size = max(dataframe_memory_bytes(first), dataframe_memory_bytes(second))
    cache = TTLDataFrameCache(max_items=10, max_item_bytes=size * 2, max_total_bytes=size + size // 2)
    assert cache.set("first", first, 30) is True
    assert cache.set("second", second, 30) is True
    assert cache.get("first") is None
    assert cache.get("second") is not None
    assert cache.stats()["total_bytes"] <= cache.stats()["max_total_bytes"]


def test_bounded_decompression_rejects_oversized_payload():
    payload = zlib.compress(b"x" * 10_000)
    with pytest.raises(CachePayloadTooLarge):
        deserialize_cache_item(payload, max_compressed_bytes=1024, max_decompressed_bytes=100)
