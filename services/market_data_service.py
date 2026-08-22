# -*- coding: utf-8 -*-
"""Provider-neutral market-data orchestration, caching and request coalescing.

Key properties:
- per-interface TTL overrides;
- short caching for empty results;
- stale-if-error for explicitly safe/static interfaces;
- bounded background refresh for slow interfaces such as ``stock_company``;
- an admin-only bypass mode can force a real upstream call for acceptance tests.
"""
from __future__ import annotations

import atexit
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

import config
from integrations.market_data.registry import get_provider_registry
from integrations.market_data.tushare.latest_available import latest_cache_ttl_cap
from services.keyed_lock import keyed_lock
from services.market_data_cache import (
    CacheLookup,
    build_cache_key,
    get_cached_entry,
    is_cache_enabled_for,
    set_cached_dataframe,
)


@dataclass(slots=True)
class MarketDataResult:
    provider: str
    data_type: str
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None
    cache_hit: bool = False
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CachePolicy:
    enabled: bool
    ttl_seconds: int
    empty_ttl_seconds: int
    stale_if_error_seconds: int
    background_refresh: bool
    refresh_ahead_seconds: int


_refresh_executor = ThreadPoolExecutor(
    max_workers=int(getattr(config, "MARKET_DATA_BACKGROUND_REFRESH_WORKERS", 2) or 2),
    thread_name_prefix="market-cache-refresh",
)
_refresh_guard = threading.RLock()
_refresh_inflight: set[str] = set()
_prewarm_started = False
_shutdown = False


def list_providers(*, include_health: bool = False) -> list[dict[str, Any]]:
    rows = []
    for provider in get_provider_registry().list():
        row = {
            "code": provider.code,
            "name": provider.display_name,
            "catalog_size": len(provider.catalog()),
        }
        if include_health:
            row["health"] = provider.health_check()
        rows.append(row)
    return sorted(rows, key=lambda item: item["code"])


def get_provider_catalog(provider_code: str) -> list[dict[str, Any]]:
    return get_provider_registry().get(provider_code).catalog()


def get_provider_health(provider_code: str) -> dict[str, Any]:
    provider = get_provider_registry().get(provider_code)
    return {"code": provider.code, "name": provider.display_name, **provider.health_check()}


def scope_for(provider_code: str, data_type: str) -> str:
    try:
        provider = get_provider_registry().get(provider_code)
    except KeyError:
        return "market:read"
    return provider.scope_for(data_type)


def cache_policy_for(provider_code: str, data_type: str, *, realtime: bool) -> CachePolicy:
    normalized = (data_type or "").strip().lower().replace("-", "_")
    enabled = is_cache_enabled_for(normalized, realtime=realtime)
    if realtime:
        ttl = int(getattr(config, "REALTIME_CACHE_TTL_SECONDS", 0) or 0)
    else:
        overrides = dict(getattr(config, "MARKET_DATA_CACHE_TTL_OVERRIDES", {}) or {})
        ttl = int(overrides.get(normalized, getattr(config, "MARKET_DATA_CACHE_TTL_SECONDS", 300)) or 0)

    # Latest-available fallbacks must recheck the current trading date quickly.
    # A short hard cap prevents yesterday's fallback from lingering after
    # Tushare publishes today's official data, even when .env has a longer
    # generic TTL override.
    latest_ttl_cap = latest_cache_ttl_cap(normalized) if provider_code == "tushare" else None
    if latest_ttl_cap is not None and ttl > 0:
        ttl = min(ttl, latest_ttl_cap)

    empty_ttl = int(getattr(config, "MARKET_DATA_EMPTY_CACHE_TTL_SECONDS", 45) or 0)
    stale_apis = set(getattr(config, "MARKET_DATA_STALE_IF_ERROR_APIS", []) or [])
    stale_seconds = (
        int(getattr(config, "MARKET_DATA_STALE_IF_ERROR_SECONDS", 0) or 0)
        if normalized in stale_apis and not realtime
        else 0
    )
    background_apis = set(getattr(config, "MARKET_DATA_BACKGROUND_REFRESH_APIS", []) or [])
    background_refresh = bool(
        enabled
        and stale_seconds > 0
        and normalized in background_apis
        and getattr(config, "MARKET_DATA_BACKGROUND_REFRESH_ENABLED", True)
    )
    return CachePolicy(
        enabled=bool(enabled and ttl > 0),
        ttl_seconds=max(0, ttl),
        empty_ttl_seconds=max(0, empty_ttl),
        stale_if_error_seconds=max(0, stale_seconds),
        background_refresh=background_refresh,
        refresh_ahead_seconds=max(0, int(getattr(config, "MARKET_DATA_REFRESH_AHEAD_SECONDS", 60) or 0)),
    )


def _lookup_meta(lookup: CacheLookup, policy: CachePolicy, **extra: Any) -> dict[str, Any]:
    meta = {
        "cache_source": lookup.source,
        "cache_stale": lookup.stale,
        "cache_age_seconds": round(lookup.age_seconds, 3),
        "cache_expires_in_seconds": round(lookup.expires_in_seconds, 3),
        "cache_stale_remaining_seconds": round(lookup.stale_remaining_seconds, 3),
        "cache_ttl_seconds": policy.ttl_seconds,
    }
    meta.update(extra)
    return meta


def _set_success_cache(
    cache_key: str,
    data: pd.DataFrame,
    policy: CachePolicy,
) -> None:
    if not policy.enabled:
        return
    if data is None or data.empty:
        if policy.empty_ttl_seconds > 0:
            set_cached_dataframe(
                cache_key,
                pd.DataFrame() if data is None else data,
                ttl_seconds=policy.empty_ttl_seconds,
                stale_if_error_seconds=0,
            )
        return
    set_cached_dataframe(
        cache_key,
        data,
        ttl_seconds=policy.ttl_seconds,
        stale_if_error_seconds=policy.stale_if_error_seconds,
    )


def _background_refresh(
    *,
    cache_key: str,
    provider_code: str,
    data_type: str,
    params: dict[str, Any],
    policy: CachePolicy,
) -> None:
    try:
        provider = get_provider_registry().get(provider_code)
        started = time.perf_counter()
        response = provider.query(data_type, params)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if response.error:
            logging.warning(
                "[后台刷新] %s.%s 失败，保留旧缓存 cost=%.1fms error=%s",
                provider_code,
                data_type,
                elapsed_ms,
                response.error,
            )
            return
        if response.data is None or response.data.empty:
            logging.warning(
                "[后台刷新] %s.%s 返回空数据，保留旧缓存 cost=%.1fms",
                provider_code,
                data_type,
                elapsed_ms,
            )
            return
        _set_success_cache(cache_key, response.data, policy)
        logging.info(
            "[后台刷新] %s.%s 完成 rows=%s cost=%.1fms",
            provider_code,
            data_type,
            len(response.data),
            elapsed_ms,
        )
    except Exception:
        logging.exception("[后台刷新] %s.%s 异常，保留旧缓存", provider_code, data_type)
    finally:
        with _refresh_guard:
            _refresh_inflight.discard(cache_key)


def _schedule_background_refresh(
    *,
    cache_key: str,
    provider_code: str,
    data_type: str,
    params: dict[str, Any],
    policy: CachePolicy,
) -> bool:
    global _shutdown
    if _shutdown or not policy.background_refresh:
        return False
    with _refresh_guard:
        if cache_key in _refresh_inflight:
            return False
        _refresh_inflight.add(cache_key)
    try:
        _refresh_executor.submit(
            _background_refresh,
            cache_key=cache_key,
            provider_code=provider_code,
            data_type=data_type,
            params=dict(params),
            policy=policy,
        )
        return True
    except RuntimeError:
        with _refresh_guard:
            _refresh_inflight.discard(cache_key)
        return False


def _cached_result(
    provider_code: str,
    data_type: str,
    lookup: CacheLookup,
    policy: CachePolicy,
    **meta: Any,
) -> MarketDataResult:
    return MarketDataResult(
        provider=provider_code,
        data_type=data_type,
        data=lookup.data,
        cache_hit=True,
        meta=_lookup_meta(lookup, policy, **meta),
    )


def query_market_data(
    provider_code: str,
    data_type: str,
    params: dict[str, Any],
    *,
    bypass_cache: bool = False,
) -> MarketDataResult:
    provider = get_provider_registry().get(provider_code)
    normalized_type = provider.normalize_data_type(data_type)
    normalized_params = dict(params or {})
    realtime = provider.is_realtime(normalized_type)
    policy = cache_policy_for(provider.code, normalized_type, realtime=realtime)
    cache_key = build_cache_key(provider.code, normalized_type, normalized_params)

    if policy.enabled and not bypass_cache:
        fresh = get_cached_entry(cache_key, allow_stale=False)
        if fresh is not None:
            refresh_scheduled = False
            if (
                policy.background_refresh
                and fresh.expires_in_seconds <= policy.refresh_ahead_seconds
            ):
                refresh_scheduled = _schedule_background_refresh(
                    cache_key=cache_key,
                    provider_code=provider.code,
                    data_type=normalized_type,
                    params=normalized_params,
                    policy=policy,
                )
            return _cached_result(
                provider.code,
                normalized_type,
                fresh,
                policy,
                background_refresh_scheduled=refresh_scheduled,
            )

        # Slow/static interfaces return stale data immediately and refresh in a
        # bounded background pool.  The request thread is never held for 60 s.
        if policy.background_refresh:
            stale = get_cached_entry(cache_key, allow_stale=True)
            if stale is not None and stale.stale and not stale.data.empty:
                scheduled = _schedule_background_refresh(
                    cache_key=cache_key,
                    provider_code=provider.code,
                    data_type=normalized_type,
                    params=normalized_params,
                    policy=policy,
                )
                return _cached_result(
                    provider.code,
                    normalized_type,
                    stale,
                    policy,
                    background_refresh_scheduled=scheduled,
                    stale_reason="background_refresh",
                )

    # Collapse simultaneous identical requests to one upstream call per process.
    with keyed_lock(cache_key):
        if policy.enabled and not bypass_cache:
            fresh = get_cached_entry(cache_key, allow_stale=False)
            if fresh is not None:
                return _cached_result(provider.code, normalized_type, fresh, policy)

        existing_before = (
            get_cached_entry(cache_key, allow_stale=True)
            if policy.enabled and policy.stale_if_error_seconds > 0
            else None
        )
        stale_before = None if bypass_cache else existing_before
        started = time.perf_counter()
        response = provider.query(normalized_type, normalized_params)
        upstream_elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        provider_meta = dict(response.meta or {})
        provider_meta.update({
            "cache_bypassed": bool(bypass_cache),
            "cache_ttl_seconds": policy.ttl_seconds,
            "empty_cache_ttl_seconds": policy.empty_ttl_seconds,
            "upstream_elapsed_ms": upstream_elapsed_ms,
        })

        if response.error is None:
            data = response.data if response.data is not None else pd.DataFrame()
            if data.empty and existing_before is not None and not existing_before.data.empty:
                # Never overwrite a known-good static cache with an unexpected
                # empty refresh.  Normal production requests may use the stale
                # value; admin bypass tests still receive the real empty result.
                if not bypass_cache:
                    return _cached_result(
                        provider.code,
                        normalized_type,
                        existing_before,
                        policy,
                        stale_reason="upstream_empty",
                        upstream_empty=True,
                        **provider_meta,
                    )
                provider_meta["cache_preserved"] = True
            else:
                _set_success_cache(cache_key, data, policy)
            return MarketDataResult(
                provider=provider.code,
                data_type=normalized_type,
                data=data,
                error=None,
                cache_hit=False,
                meta=provider_meta,
            )

        if stale_before is not None and not stale_before.data.empty:
            # Safe/static interfaces stay available when the relay is slow or
            # temporarily unavailable.  The error is surfaced as metadata.
            return _cached_result(
                provider.code,
                normalized_type,
                stale_before,
                policy,
                stale_reason="upstream_error",
                upstream_error=response.error,
                **provider_meta,
            )

        return MarketDataResult(
            provider=provider.code,
            data_type=normalized_type,
            data=response.data,
            error=response.error,
            cache_hit=False,
            meta=provider_meta,
        )


def _prewarm_requests() -> list[tuple[str, str, dict[str, Any]]]:
    requested = set(getattr(config, "MARKET_DATA_PREWARM_APIS", []) or [])
    today = date.today()
    requests: list[tuple[str, str, dict[str, Any]]] = []
    if "stock_company" in requested:
        requests.extend([
            ("tushare", "stock_company", {"exchange": "SZSE"}),
            ("tushare", "stock_company", {"exchange": "SSE"}),
        ])
    if "stock_basic" in requested:
        requests.append(("tushare", "stock_basic", {"list_status": "L"}))
    if "trade_cal" in requested:
        requests.append((
            "tushare",
            "trade_cal",
            {
                "exchange": "SSE",
                "start_date": (today - timedelta(days=30)).strftime("%Y%m%d"),
                "end_date": (today + timedelta(days=365)).strftime("%Y%m%d"),
            },
        ))
    return requests


def _run_prewarm() -> None:
    delay = int(getattr(config, "MARKET_DATA_PREWARM_DELAY_SECONDS", 3) or 0)
    if delay > 0:
        time.sleep(delay)
    for provider_code, api_name, params in _prewarm_requests():
        if _shutdown:
            return
        try:
            result = query_market_data(provider_code, api_name, params)
            if result.error:
                logging.warning("[缓存预热] %s.%s 失败: %s", provider_code, api_name, result.error)
            else:
                logging.info(
                    "[缓存预热] %s.%s rows=%s cache_hit=%s stale=%s",
                    provider_code,
                    api_name,
                    len(result.data),
                    result.cache_hit,
                    bool(result.meta.get("cache_stale")),
                )
        except Exception:
            logging.exception("[缓存预热] %s.%s 异常", provider_code, api_name)


def start_market_data_background_services() -> None:
    global _prewarm_started
    if (
        not _prewarm_started
        and getattr(config, "MARKET_DATA_PREWARM_ENABLED", True)
        and getattr(config, "MARKET_DATA_CACHE_ENABLED", True)
    ):
        _prewarm_started = True
        thread = threading.Thread(target=_run_prewarm, name="market-cache-prewarm", daemon=True)
        thread.start()

    if getattr(config, "KAIPANLA_SNAPSHOT_IN_PROCESS", True):
        try:
            from services.kaipanla_snapshot_scheduler import start_kaipanla_snapshot_scheduler
            start_kaipanla_snapshot_scheduler()
        except Exception:
            logging.exception("[开盘啦快照] 调度器启动失败")
    elif getattr(config, "KAIPANLA_SNAPSHOT_ENABLED", False):
        logging.info("[开盘啦快照] Web进程内调度已关闭，请单独运行 python -m tools.kaipanla_snapshot_worker")


def stop_market_data_background_services() -> None:
    global _shutdown
    _shutdown = True
    try:
        from services.kaipanla_snapshot_scheduler import stop_kaipanla_snapshot_scheduler
        stop_kaipanla_snapshot_scheduler()
    except Exception:
        logging.exception("[开盘啦快照] 调度器停止失败")
    _refresh_executor.shutdown(wait=False, cancel_futures=True)


atexit.register(stop_market_data_background_services)
