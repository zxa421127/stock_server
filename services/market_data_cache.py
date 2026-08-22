# -*- coding: utf-8 -*-
"""Bounded hybrid DataFrame cache with fresh/stale windows."""
from __future__ import annotations

import json
import logging
import threading
import time
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from typing import Any

import pandas as pd

import config
from services.redis_backend import get_redis, redis_key


class CachePayloadTooLarge(ValueError):
    """Raised when a cache payload exceeds configured memory limits."""


@dataclass(slots=True)
class CacheLookup:
    data: pd.DataFrame
    source: str
    stale: bool
    age_seconds: float
    expires_in_seconds: float
    stale_remaining_seconds: float


@dataclass(slots=True)
class _CacheItem:
    cached_at: float
    fresh_until: float
    stale_until: float
    data: pd.DataFrame
    size_bytes: int


def dataframe_memory_bytes(df: pd.DataFrame | None) -> int:
    if df is None:
        return 0
    try:
        return int(df.memory_usage(index=True, deep=True).sum())
    except Exception:
        # Conservative fallback for unusual extension dtypes.
        return int(df.memory_usage(index=True).sum())


class TTLDataFrameCache:
    """Thread-safe byte-aware LRU cache retaining stale fallback values."""

    def __init__(
        self,
        max_items: int = 1000,
        *,
        max_item_bytes: int | None = None,
        max_total_bytes: int | None = None,
    ):
        self.max_items = max(1, int(max_items or 1000))
        self.max_item_bytes = max(1, int(max_item_bytes or 64 * 1024 * 1024))
        self.max_total_bytes = max(1, int(max_total_bytes or 512 * 1024 * 1024))
        self._lock = threading.RLock()
        self._data: OrderedDict[str, _CacheItem] = OrderedDict()
        self._total_bytes = 0
        self.hits = 0
        self.stale_hits = 0
        self.misses = 0
        self.skipped_oversize = 0
        self.evictions = 0

    def _remove_unlocked(self, key: str) -> _CacheItem | None:
        item = self._data.pop(key, None)
        if item is not None:
            self._total_bytes = max(0, self._total_bytes - item.size_bytes)
        return item

    def lookup(self, key: str, *, allow_stale: bool = False) -> CacheLookup | None:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                self.misses += 1
                return None
            if item.stale_until <= now:
                self._remove_unlocked(key)
                self.misses += 1
                return None

            stale = item.fresh_until <= now
            if stale and not allow_stale:
                self.misses += 1
                return None

            self._data.move_to_end(key)
            if stale:
                self.stale_hits += 1
            else:
                self.hits += 1
            return CacheLookup(
                data=item.data.copy(deep=True),
                source="local",
                stale=stale,
                age_seconds=max(0.0, now - item.cached_at),
                expires_in_seconds=item.fresh_until - now,
                stale_remaining_seconds=max(0.0, item.stale_until - now),
            )

    def get(self, key: str) -> pd.DataFrame | None:
        lookup = self.lookup(key, allow_stale=False)
        return None if lookup is None else lookup.data

    def set(
        self,
        key: str,
        df: pd.DataFrame,
        ttl_seconds: int,
        *,
        stale_if_error_seconds: int = 0,
        cached_at: float | None = None,
        fresh_until: float | None = None,
        stale_until: float | None = None,
    ) -> bool:
        if df is None:
            return False
        item_size = dataframe_memory_bytes(df)
        if item_size > self.max_item_bytes or item_size > self.max_total_bytes:
            with self._lock:
                self.skipped_oversize += 1
            return False
        now = time.time()
        ttl_seconds = max(1, int(ttl_seconds or 1))
        stale_if_error_seconds = max(0, int(stale_if_error_seconds or 0))
        cached_at = float(cached_at if cached_at is not None else now)
        fresh_until = float(fresh_until if fresh_until is not None else cached_at + ttl_seconds)
        stale_until = float(stale_until if stale_until is not None else fresh_until + stale_if_error_seconds)
        stale_until = max(stale_until, fresh_until)
        item = _CacheItem(
            cached_at=cached_at,
            fresh_until=fresh_until,
            stale_until=stale_until,
            data=df.copy(deep=True),
            size_bytes=item_size,
        )
        with self._lock:
            self._remove_unlocked(key)
            self._data[key] = item
            self._total_bytes += item_size
            self._data.move_to_end(key)
            while len(self._data) > self.max_items or self._total_bytes > self.max_total_bytes:
                oldest_key = next(iter(self._data))
                self._remove_unlocked(oldest_key)
                self.evictions += 1
        return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._total_bytes = 0

    def stats(self) -> dict[str, int]:
        now = time.time()
        with self._lock:
            dead = [key for key, item in self._data.items() if item.stale_until <= now]
            for key in dead:
                self._remove_unlocked(key)
            fresh_items = sum(item.fresh_until > now for item in self._data.values())
            stale_items = len(self._data) - fresh_items
            return {
                "items": len(self._data),
                "fresh_items": fresh_items,
                "stale_items": stale_items,
                "max_items": self.max_items,
                "total_bytes": self._total_bytes,
                "max_item_bytes": self.max_item_bytes,
                "max_total_bytes": self.max_total_bytes,
                "hits": self.hits,
                "stale_hits": self.stale_hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "skipped_oversize": self.skipped_oversize,
            }


_cache = TTLDataFrameCache(
    getattr(config, "MARKET_DATA_CACHE_MAX_ITEMS", 5000),
    max_item_bytes=getattr(config, "MARKET_DATA_CACHE_MAX_ITEM_BYTES", 64 * 1024 * 1024),
    max_total_bytes=getattr(config, "MARKET_DATA_CACHE_MAX_TOTAL_BYTES", 512 * 1024 * 1024),
)


def _safe_json_default(value: Any):
    return str(value)


def build_cache_key(source_code: str, data_type: str, params: dict[str, Any]) -> str:
    payload = {"source_code": source_code, "data_type": data_type, "params": params or {}}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=_safe_json_default)
    return sha256(raw.encode("utf-8")).hexdigest()


def is_cache_enabled_for(data_type: str, *, realtime: bool = False) -> bool:
    if not getattr(config, "MARKET_DATA_CACHE_ENABLED", True):
        return False
    excluded = set(getattr(config, "MARKET_DATA_CACHE_EXCLUDE_APIS", []) or [])
    if (data_type or "").strip() in excluded:
        return False
    if realtime and int(getattr(config, "REALTIME_CACHE_TTL_SECONDS", 0) or 0) <= 0:
        return False
    return True


def serialize_cache_item(
    df: pd.DataFrame,
    *,
    cached_at: float,
    fresh_until: float,
    stale_until: float,
    max_compressed_bytes: int | None = None,
    max_decompressed_bytes: int | None = None,
) -> bytes:
    max_compressed = int(max_compressed_bytes or getattr(config, "MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES", 32 * 1024 * 1024))
    max_decompressed = int(max_decompressed_bytes or getattr(config, "MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES", 128 * 1024 * 1024))
    envelope = {
        "version": 2,
        "cached_at": cached_at,
        "fresh_until": fresh_until,
        "stale_until": stale_until,
        "table": df.to_json(orient="table", date_format="iso", force_ascii=False),
    }
    raw = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > max_decompressed:
        raise CachePayloadTooLarge(f"cache payload expands to {len(raw)} bytes")
    payload = zlib.compress(raw, level=3)
    if len(payload) > max_compressed:
        raise CachePayloadTooLarge(f"compressed cache payload is {len(payload)} bytes")
    return payload


def _bounded_decompress(payload: bytes, max_output_bytes: int) -> bytes:
    inflater = zlib.decompressobj()
    raw = inflater.decompress(payload, max_output_bytes + 1)
    if len(raw) > max_output_bytes or inflater.unconsumed_tail:
        raise CachePayloadTooLarge("decompressed cache payload exceeds limit")
    tail = inflater.flush(max(1, max_output_bytes + 1 - len(raw)))
    raw += tail
    if len(raw) > max_output_bytes or not inflater.eof:
        raise CachePayloadTooLarge("decompressed cache payload exceeds limit")
    return raw


def deserialize_cache_item(
    payload: bytes,
    *,
    max_compressed_bytes: int | None = None,
    max_decompressed_bytes: int | None = None,
) -> tuple[pd.DataFrame, float, float, float]:
    max_compressed = int(max_compressed_bytes or getattr(config, "MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES", 32 * 1024 * 1024))
    max_decompressed = int(max_decompressed_bytes or getattr(config, "MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES", 128 * 1024 * 1024))
    if len(payload) > max_compressed:
        raise CachePayloadTooLarge("compressed cache payload exceeds limit")
    raw_bytes = _bounded_decompress(payload, max_decompressed)
    raw = raw_bytes.decode("utf-8")
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        now = time.time()
        ttl = int(getattr(config, "LOCAL_CACHE_PROMOTION_TTL_SECONDS", 15) or 15)
        frame = pd.read_json(StringIO(raw), orient="table")
        if dataframe_memory_bytes(frame) > int(getattr(config, "MARKET_DATA_CACHE_MAX_ITEM_BYTES", 64 * 1024 * 1024)):
            raise CachePayloadTooLarge("decoded DataFrame exceeds cache item limit")
        return frame, now, now + ttl, now + ttl

    if isinstance(envelope, dict) and envelope.get("version") == 2:
        frame = pd.read_json(StringIO(str(envelope.get("table") or "{}")), orient="table")
        if dataframe_memory_bytes(frame) > int(getattr(config, "MARKET_DATA_CACHE_MAX_ITEM_BYTES", 64 * 1024 * 1024)):
            raise CachePayloadTooLarge("decoded DataFrame exceeds cache item limit")
        return (
            frame,
            float(envelope.get("cached_at") or time.time()),
            float(envelope.get("fresh_until") or time.time()),
            float(envelope.get("stale_until") or time.time()),
        )

    now = time.time()
    ttl = int(getattr(config, "LOCAL_CACHE_PROMOTION_TTL_SECONDS", 15) or 15)
    frame = pd.read_json(StringIO(raw), orient="table")
    if dataframe_memory_bytes(frame) > int(getattr(config, "MARKET_DATA_CACHE_MAX_ITEM_BYTES", 64 * 1024 * 1024)):
        raise CachePayloadTooLarge("decoded DataFrame exceeds cache item limit")
    return frame, now, now + ttl, now + ttl


# Backward-compatible private aliases used by older callers/tests.
_serialize_cache_item = serialize_cache_item
_deserialize_cache_item = deserialize_cache_item


def get_cached_entry(key: str, *, allow_stale: bool = False) -> CacheLookup | None:
    local = _cache.lookup(key, allow_stale=allow_stale)
    if local is not None:
        return local

    client = get_redis()
    if client is None:
        return None
    redis_cache_key = redis_key("cache", key)
    try:
        payload = client.get(redis_cache_key)
        if not payload:
            return None
        df, cached_at, fresh_until, stale_until = deserialize_cache_item(payload)
        now = time.time()
        stale = fresh_until <= now
        if stale_until <= now or (stale and not allow_stale):
            return None
        _cache.set(
            key,
            df,
            max(1, int(fresh_until - cached_at)),
            stale_if_error_seconds=max(0, int(stale_until - fresh_until)),
            cached_at=cached_at,
            fresh_until=fresh_until,
            stale_until=stale_until,
        )
        return CacheLookup(
            data=df.copy(deep=True),
            source="redis",
            stale=stale,
            age_seconds=max(0.0, now - cached_at),
            expires_in_seconds=fresh_until - now,
            stale_remaining_seconds=max(0.0, stale_until - now),
        )
    except CachePayloadTooLarge as exc:
        logging.warning("[缓存] 丢弃超限 Redis 缓存项: %s", exc)
        try:
            client.delete(redis_cache_key)
        except Exception:
            pass
        return None
    except Exception as exc:
        logging.warning("[缓存] Redis读取失败，使用本地缓存降级: %s", exc)
        return None


def get_cached_dataframe(key: str) -> pd.DataFrame | None:
    lookup = get_cached_entry(key, allow_stale=False)
    return None if lookup is None else lookup.data


def set_cached_dataframe(
    key: str,
    df: pd.DataFrame,
    ttl_seconds: int | None = None,
    *,
    stale_if_error_seconds: int = 0,
) -> bool:
    if df is None:
        return False
    max_rows = int(getattr(config, "MARKET_DATA_CACHE_MAX_ROWS_PER_ITEM", 100_000) or 100_000)
    if len(df) > max_rows:
        logging.info("[缓存] 跳过超行数缓存项 rows=%s limit=%s", len(df), max_rows)
        return False
    ttl = int(ttl_seconds or getattr(config, "MARKET_DATA_CACHE_TTL_SECONDS", 300) or 300)
    ttl = max(1, ttl)
    stale_seconds = max(0, int(stale_if_error_seconds or 0))
    cached_at = time.time()
    fresh_until = cached_at + ttl
    stale_until = fresh_until + stale_seconds
    local_saved = _cache.set(
        key,
        df,
        ttl,
        stale_if_error_seconds=stale_seconds,
        cached_at=cached_at,
        fresh_until=fresh_until,
        stale_until=stale_until,
    )
    if not local_saved:
        return False
    client = get_redis()
    if client is None:
        return True
    try:
        payload = serialize_cache_item(
            df,
            cached_at=cached_at,
            fresh_until=fresh_until,
            stale_until=stale_until,
        )
        client.set(redis_key("cache", key), payload, ex=max(1, ttl + stale_seconds))
    except CachePayloadTooLarge as exc:
        logging.info("[缓存] 跳过超限 Redis 缓存项: %s", exc)
    except Exception as exc:
        logging.warning("[缓存] Redis写入失败，仅保留本地缓存: %s", exc)
    return True


def cache_stats() -> dict[str, Any]:
    stats: dict[str, Any] = {
        "local": _cache.stats(),
        "redis": {"enabled": False},
        "policy": {
            "default_ttl_seconds": int(getattr(config, "MARKET_DATA_CACHE_TTL_SECONDS", 300) or 300),
            "empty_ttl_seconds": int(getattr(config, "MARKET_DATA_EMPTY_CACHE_TTL_SECONDS", 45) or 0),
            "stale_if_error_seconds": int(getattr(config, "MARKET_DATA_STALE_IF_ERROR_SECONDS", 0) or 0),
            "max_rows_per_item": int(getattr(config, "MARKET_DATA_CACHE_MAX_ROWS_PER_ITEM", 100_000) or 100_000),
            "redis_max_compressed_bytes": int(getattr(config, "MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES", 32 * 1024 * 1024)),
            "redis_max_decompressed_bytes": int(getattr(config, "MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES", 128 * 1024 * 1024)),
            "ttl_overrides": dict(getattr(config, "MARKET_DATA_CACHE_TTL_OVERRIDES", {}) or {}),
            "background_refresh_apis": list(getattr(config, "MARKET_DATA_BACKGROUND_REFRESH_APIS", []) or []),
        },
    }
    client = get_redis()
    if client is not None:
        stats["redis"] = {"enabled": True, "connected": True}
    return stats


def clear_cache() -> None:
    _cache.clear()
    client = get_redis()
    if client is None:
        return
    try:
        pattern = redis_key("cache", "*")
        batch: list[bytes] = []
        for key in client.scan_iter(match=pattern, count=500):
            batch.append(key)
            if len(batch) >= 500:
                client.delete(*batch)
                batch.clear()
        if batch:
            client.delete(*batch)
    except Exception as exc:
        logging.warning("[缓存] Redis清理失败: %s", exc)
