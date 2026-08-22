# -*- coding: utf-8 -*-
"""Latest-available date fallback for selected Tushare interfaces.

The goal is to return the newest dataset that Tushare currently supports:

1. Query the requested/current Shanghai date first.
2. If Tushare has not published that date yet and returns an empty frame,
   walk backwards through a small, bounded set of weekdays.
3. Return the first non-empty result and expose the requested/actual date in
   response metadata so callers are never misled about data freshness.
4. Explicit historical queries keep exact-date semantics unless ``latest=1``
   (or an equivalent control flag) is supplied.

The fallback is deliberately bounded and the service layer applies short cache
TTL caps, so this improves availability without turning one website request
into an unbounded upstream scan.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd


RawQuery = Callable[[str, dict[str, Any]], tuple[pd.DataFrame, str | None]]

_CONTROL_KEYS = frozenset({"latest", "auto_latest", "fallback_latest"})
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class LatestAvailablePolicy:
    max_weekday_candidates: int
    cache_ttl_cap_seconds: int
    release_profile: str


LATEST_AVAILABLE_POLICIES: dict[str, LatestAvailablePolicy] = {
    # Previous trading-day official datasets.  The current date may legitimately
    # remain empty until the following morning.
    "etf_share_size": LatestAvailablePolicy(8, 300, "previous_trading_day"),
    "margin": LatestAvailablePolicy(8, 300, "previous_trading_day"),
    "margin_detail": LatestAvailablePolicy(8, 300, "previous_trading_day"),

    # Intraday/after-hours rankings.  Keep the cache short so a current-day
    # publication replaces the fallback quickly after Tushare updates it.
    "dc_hot": LatestAvailablePolicy(5, 60, "intraday_ranking"),
    "kpl_list": LatestAvailablePolicy(5, 60, "intraday_ranking"),
    "ths_hot": LatestAvailablePolicy(5, 60, "intraday_ranking"),

    # CCASS / southbound holding datasets can be delayed until the following
    # trading morning.  A slightly longer bounded lookback handles holidays.
    "ccass_hold": LatestAvailablePolicy(10, 600, "next_trading_morning"),
    "ccass_hold_detail": LatestAvailablePolicy(10, 600, "next_trading_morning"),
    "hk_hold": LatestAvailablePolicy(10, 600, "holding_disclosure"),
}


def is_latest_available_api(api_name: str) -> bool:
    return _normalize_api(api_name) in LATEST_AVAILABLE_POLICIES


def latest_cache_ttl_cap(api_name: str) -> int | None:
    policy = LATEST_AVAILABLE_POLICIES.get(_normalize_api(api_name))
    return policy.cache_ttl_cap_seconds if policy else None


def _normalize_api(api_name: str) -> str:
    return (api_name or "").strip().lower().replace("-", "_")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _china_today(now: datetime | None = None) -> date:
    if now is None:
        return datetime.now(_SHANGHAI_TZ).date()
    if now.tzinfo is None:
        return now.date()
    return now.astimezone(_SHANGHAI_TZ).date()


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _date_text(value: date) -> str:
    return value.strftime("%Y%m%d")


def _candidate_weekdays(start: date, count: int) -> list[str]:
    candidates: list[str] = []
    cursor = start
    while len(candidates) < count:
        if cursor.weekday() < 5:
            candidates.append(_date_text(cursor))
        cursor -= timedelta(days=1)
    return candidates


def _extract_actual_trade_date(df: pd.DataFrame, fallback: str) -> str:
    if df is not None and not df.empty and "trade_date" in df.columns:
        values = df["trade_date"].dropna().astype(str)
        values = values[values.str.fullmatch(r"\d{8}")]
        if not values.empty:
            return str(values.max())
    return fallback


def _strip_controls(params: Mapping[str, Any]) -> tuple[dict[str, Any], bool | None]:
    cleaned: dict[str, Any] = {}
    explicit: bool | None = None
    for key, value in dict(params or {}).items():
        if key in _CONTROL_KEYS:
            explicit = _as_bool(value)
            continue
        cleaned[key] = value
    return cleaned, explicit


def _latest_mode(
    api_name: str,
    params: Mapping[str, Any],
    *,
    today: date,
) -> tuple[dict[str, Any], bool, str | None]:
    cleaned, explicit = _strip_controls(params)
    if not is_latest_available_api(api_name):
        return cleaned, False, None

    requested = _parse_date(cleaned.get("trade_date"))
    requested_text = str(cleaned.get("trade_date") or "").strip() or None

    if explicit is False:
        return cleaned, False, requested_text
    if explicit is True:
        target = requested or today
        return cleaned, True, _date_text(target)

    # Historical ranges and explicit old dates must retain exact semantics.
    if requested is None:
        if cleaned.get("start_date") or cleaned.get("end_date"):
            return cleaned, False, None
        return cleaned, True, _date_text(today)
    if requested >= today:
        return cleaned, True, _date_text(requested)
    return cleaned, False, requested_text


def _base_meta(
    *,
    api_name: str,
    enabled: bool,
    requested_date: str | None,
    policy: LatestAvailablePolicy | None,
) -> dict[str, Any]:
    return {
        "latest_available_enabled": enabled,
        "requested_trade_date": requested_date,
        "actual_trade_date": None,
        "fallback_used": False,
        "data_freshness": "exact_request" if not enabled else "not_found",
        "fallback_attempt_count": 0,
        "fallback_candidate_dates": [],
        "release_profile": policy.release_profile if policy else "exact_request",
    }


def _call(raw_query: RawQuery, api_name: str, params: dict[str, Any]) -> tuple[pd.DataFrame, str | None]:
    df, error = raw_query(api_name, params)
    if df is None:
        df = pd.DataFrame()
    return df, error


def _query_standard_latest(
    raw_query: RawQuery,
    api_name: str,
    cleaned: dict[str, Any],
    requested_date: str,
    policy: LatestAvailablePolicy,
    *,
    today: date,
) -> tuple[pd.DataFrame, str | None, dict[str, Any]]:
    requested = _parse_date(requested_date) or today
    search_start = min(requested, today)
    candidates = _candidate_weekdays(search_start, policy.max_weekday_candidates)
    meta = _base_meta(
        api_name=api_name,
        enabled=True,
        requested_date=requested_date,
        policy=policy,
    )
    meta["fallback_candidate_dates"] = candidates

    last_df = pd.DataFrame()
    for index, candidate in enumerate(candidates, start=1):
        query_params = dict(cleaned)
        query_params.pop("start_date", None)
        query_params.pop("end_date", None)
        query_params["trade_date"] = candidate
        df, error = _call(raw_query, api_name, query_params)
        meta["fallback_attempt_count"] = index
        if error:
            meta["attempted_trade_date"] = candidate
            return df, error, meta
        last_df = df
        if not df.empty:
            actual = _extract_actual_trade_date(df, candidate)
            meta.update({
                "actual_trade_date": actual,
                "fallback_used": actual != requested_date,
                "data_freshness": "current_date" if actual == requested_date else "latest_available",
                "resolved_query_params": query_params,
            })
            return df, None, meta

    return last_df, None, meta


def _pick_ccass_identity(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if df is None or df.empty:
        return None, None
    for _, row in df.iterrows():
        ts_code = str(row.get("ts_code") or "").strip()
        trade_date = str(row.get("trade_date") or "").strip()
        if ts_code and trade_date:
            return ts_code, trade_date
    return None, None


def _query_ccass_detail_latest(
    raw_query: RawQuery,
    cleaned: dict[str, Any],
    requested_date: str,
    policy: LatestAvailablePolicy,
    *,
    today: date,
) -> tuple[pd.DataFrame, str | None, dict[str, Any]]:
    # When the caller supplies a concrete security, preserve it and walk dates.
    if cleaned.get("ts_code") or cleaned.get("hk_code"):
        return _query_standard_latest(
            raw_query,
            "ccass_hold_detail",
            cleaned,
            requested_date,
            policy,
            today=today,
        )

    requested = _parse_date(requested_date) or today
    search_start = min(requested, today)
    candidates = _candidate_weekdays(search_start, policy.max_weekday_candidates)
    meta = _base_meta(
        api_name="ccass_hold_detail",
        enabled=True,
        requested_date=requested_date,
        policy=policy,
    )
    meta["fallback_candidate_dates"] = candidates
    meta["reference_api"] = "ccass_hold"

    last_df = pd.DataFrame()
    for index, candidate in enumerate(candidates, start=1):
        summary_df, summary_error = _call(
            raw_query,
            "ccass_hold",
            {"trade_date": candidate, "fields": "trade_date,ts_code,name"},
        )
        meta["fallback_attempt_count"] = index
        if summary_error:
            meta["attempted_trade_date"] = candidate
            return summary_df, summary_error, meta
        ts_code, actual_summary_date = _pick_ccass_identity(summary_df)
        if not ts_code or not actual_summary_date:
            continue

        detail_params = dict(cleaned)
        detail_params.pop("start_date", None)
        detail_params.pop("end_date", None)
        detail_params.update({"ts_code": ts_code, "trade_date": actual_summary_date})
        detail_df, detail_error = _call(raw_query, "ccass_hold_detail", detail_params)
        if detail_error:
            return detail_df, detail_error, meta
        last_df = detail_df
        if not detail_df.empty:
            actual = _extract_actual_trade_date(detail_df, actual_summary_date)
            meta.update({
                "actual_trade_date": actual,
                "fallback_used": actual != requested_date,
                "data_freshness": "current_date" if actual == requested_date else "latest_available",
                "resolved_query_params": detail_params,
                "reference_ts_code": ts_code,
                "reference_trade_date": actual_summary_date,
            })
            return detail_df, None, meta

    return last_df, None, meta



def _query_hk_hold_latest(
    raw_query: RawQuery,
    cleaned: dict[str, Any],
    requested_date: str,
    policy: LatestAvailablePolicy,
    *,
    today: date,
) -> tuple[pd.DataFrame, str | None, dict[str, Any]]:
    exchange = str(cleaned.get("exchange") or "").strip().upper()
    if exchange not in {"SH", "SZ"}:
        return _query_standard_latest(
            raw_query,
            "hk_hold",
            cleaned,
            requested_date,
            policy,
            today=today,
        )

    # Northbound daily disclosure stopped in 2024 and is now quarterly.  A
    # bounded date-by-date scan would miss the latest supported observation, so
    # use one range request and keep only the newest returned disclosure date.
    requested = _parse_date(requested_date) or today
    end_day = min(requested, today)
    start_day = end_day - timedelta(days=550)
    query_params = dict(cleaned)
    query_params.pop("trade_date", None)
    query_params["start_date"] = _date_text(start_day)
    query_params["end_date"] = _date_text(end_day)

    meta = _base_meta(
        api_name="hk_hold",
        enabled=True,
        requested_date=requested_date,
        policy=policy,
    )
    meta.update({
        "fallback_attempt_count": 1,
        "fallback_candidate_dates": [f"{_date_text(start_day)}-{_date_text(end_day)}"],
        "range_lookup_used": True,
    })
    df, error = _call(raw_query, "hk_hold", query_params)
    if error or df.empty:
        return df, error, meta

    actual = _extract_actual_trade_date(df, "")
    if actual and "trade_date" in df.columns:
        mask = df["trade_date"].astype(str) == actual
        df = df.loc[mask].reset_index(drop=True)
    meta.update({
        "actual_trade_date": actual or None,
        "fallback_used": bool(actual and actual != requested_date),
        "data_freshness": "current_date" if actual == requested_date else "latest_available",
        "resolved_query_params": query_params,
    })
    return df, None, meta

def query_with_latest_available(
    api_name: str,
    params: Mapping[str, Any],
    raw_query: RawQuery,
    *,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, str | None, dict[str, Any]]:
    """Query one Tushare API with bounded latest-available fallback.

    ``raw_query`` receives ``(api_name, params_dict)`` and returns
    ``(DataFrame, error)``.  The returned metadata is safe to expose through the
    unified route's ``source`` object.
    """
    normalized = _normalize_api(api_name)
    policy = LATEST_AVAILABLE_POLICIES.get(normalized)
    today = _china_today(now)
    cleaned, enabled, requested_date = _latest_mode(normalized, params, today=today)

    if not enabled or policy is None:
        df, error = _call(raw_query, normalized, cleaned)
        meta = _base_meta(
            api_name=normalized,
            enabled=False,
            requested_date=requested_date,
            policy=policy,
        )
        if error is None and not df.empty:
            meta["actual_trade_date"] = _extract_actual_trade_date(
                df,
                requested_date or "",
            ) or None
            meta["data_freshness"] = "exact_request"
        return df, error, meta

    requested_date = requested_date or _date_text(today)
    if normalized == "ccass_hold_detail":
        return _query_ccass_detail_latest(
            raw_query,
            cleaned,
            requested_date,
            policy,
            today=today,
        )
    if normalized == "hk_hold":
        return _query_hk_hold_latest(
            raw_query,
            cleaned,
            requested_date,
            policy,
            today=today,
        )
    return _query_standard_latest(
        raw_query,
        normalized,
        cleaned,
        requested_date,
        policy,
        today=today,
    )
