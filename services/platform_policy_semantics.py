# -*- coding: utf-8 -*-
"""Fail-closed semantic validation for settings/platform_policy.json."""

from __future__ import annotations

import re
from typing import Any

CONFIG_RULES = {'ADMIN_API_TEST_CLEANUP_HOUR': ('int', 0, 23),
 'ADMIN_API_TEST_DISK_CRITICAL_PERCENT': ('int', 1, 100),
 'ADMIN_API_TEST_DISK_WARNING_PERCENT': ('int', 1, 99),
 'ADMIN_API_TEST_MAX_CONCURRENT_BATCHES': ('int', 1, 4),
 'ADMIN_API_TEST_MAX_CONCURRENT_ITEMS': ('int', 1, 8),
 'ADMIN_API_TEST_MAX_PREVIEW_PAGE_SIZE': ('int', 1, 5000),
 'ADMIN_API_TEST_MAX_RESULT_BYTES': ('int', 1048576, 10737418240),
 'ADMIN_API_TEST_OFFICIAL_SYNC_DELAY_MS': ('int', 0, 10000),
 'ADMIN_API_TEST_OFFICIAL_SYNC_RETRIES': ('int', 0, 5),
 'ADMIN_API_TEST_OFFICIAL_SYNC_TIMEOUT_SECONDS': ('int', 5, 300),
 'ADMIN_API_TEST_PREVIEW_PAGE_SIZE': ('int', 1, 1000),
 'ADMIN_API_TEST_RETENTION_DAYS': ('int', 1, 36500),
 'ADMIN_CAPTCHA_TTL_SECONDS': ('int', 30, 1800),
 'API_ACCESS_LOG_RETENTION_DAYS': ('int', 0, 36500),
 'API_DOC_STATUS_FILE_SCAN_SECONDS': ('int', 1, 3600),
 'API_DOC_STATUS_REFRESH_INTERVAL_SECONDS': ('int', 3600, 604800),
 'API_DOC_STATUS_STARTUP_DELAY_SECONDS': ('int', 10, 7200),
 'API_DOC_STATUS_SUBPROCESS_TIMEOUT_SECONDS': ('int', 300, 21600),
 'API_KEY_TOUCH_INTERVAL_SECONDS': ('int', 0, 86400),
 'API_MAX_DATAFRAME_BYTES': ('int', 1024, 2147483648),
 'API_MAX_RESPONSE_BYTES': ('int', 1024, 1073741824),
 'API_MAX_RESPONSE_ROWS': ('int', 1, 1000000),
 'API_MAX_RESPONSE_ROWS_OVERRIDES': ('int_map', 1, 1000000),
 'AUDIT_CSV_EXPORT_MAX_ROWS': ('int', 1, 1000000),
 'AUDIT_SPOOL_BATCH_SIZE': ('int', 1, 5000),
 'AUDIT_SPOOL_FLUSH_INTERVAL_SECONDS': ('int', 1, 60),
 'AUDIT_SPOOL_MAX_RETRIES': ('int', 1, 100),
 'AUDIT_SPOOL_SYNCHRONOUS': ('enum', ('OFF', 'NORMAL', 'FULL', 'EXTRA', '0', '1', '2', '3')),
 'BIDDING_SYNC_COUNT': ('int', 10000, 10000),
 'CONTACT_CODE_TTL_SECONDS': ('int', 60, 1800),
 'DEFAULT_REQUESTS_PER_MINUTE': ('int', 1, 100000),
 'GLOBAL_REQUESTS_PER_SECOND': ('int', 0, 100000),
 'KAIPANLA_SNAPSHOT_LEASE_SECONDS': ('int', 30, 3600),
 'KAIPANLA_SNAPSHOT_WINDOW_SECONDS': ('int', 30, 1800),
 'MARKET_DATA_BACKGROUND_REFRESH_APIS': ('str_list',),
 'MARKET_DATA_BACKGROUND_REFRESH_WORKERS': ('int', 1, 8),
 'MARKET_DATA_CACHE_ENABLED': ('bool',),
 'MARKET_DATA_CACHE_EXCLUDE_APIS': ('str_list',),
 'MARKET_DATA_CACHE_MAX_ITEMS': ('int', 10, 100000),
 'MARKET_DATA_CACHE_MAX_ITEM_BYTES': ('int', 1024, 2147483648),
 'MARKET_DATA_CACHE_MAX_ROWS_PER_ITEM': ('int', 1, 10000000),
 'MARKET_DATA_CACHE_MAX_TOTAL_BYTES': ('int', 1024, 8589934592),
 'MARKET_DATA_CACHE_TTL_OVERRIDES': ('int_map', 0, 604800),
 'MARKET_DATA_CACHE_TTL_SECONDS': ('int', 1, 86400),
 'MARKET_DATA_EMPTY_CACHE_TTL_SECONDS': ('int', 0, 3600),
 'MARKET_DATA_PREWARM_APIS': ('str_list',),
 'MARKET_DATA_PREWARM_DELAY_SECONDS': ('int', 0, 300),
 'MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES': ('int', 1024, 1073741824),
 'MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES': ('int', 1024, 2147483648),
 'MARKET_DATA_REFRESH_AHEAD_SECONDS': ('int', 0, 3600),
 'MARKET_DATA_STALE_IF_ERROR_APIS': ('str_list',),
 'MARKET_DATA_STALE_IF_ERROR_SECONDS': ('int', 0, 2592000),
 'MARKET_QUERY_CONCURRENCY_RETRY_AFTER_SECONDS': ('int', 1, 60),
 'MARKET_QUERY_DATE_SPAN_OVERRIDES': ('int_map', 1, 36500),
 'MARKET_QUERY_DEFAULT_MAX_DATE_SPAN_DAYS': ('int', 1, 36500),
 'MARKET_QUERY_FINANCIAL_MAX_DATE_SPAN_DAYS': ('int', 1, 36500),
 'MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_TOKEN': ('int', 0, 1000),
 'MARKET_QUERY_GENERAL_MAX_CONCURRENT_PER_USER': ('int', 0, 1000),
 'MARKET_QUERY_INTRADAY_MAX_DATE_SPAN_DAYS': ('int', 1, 3660),
 'MARKET_QUERY_LEASE_TTL_SECONDS': ('int', 5, 3600),
 'MARKET_QUERY_MAX_CONCURRENT_GLOBAL': ('int', 0, 100000),
 'MARKET_QUERY_MAX_CONCURRENT_PER_TOKEN': ('int', 0, 1000),
 'MARKET_QUERY_MAX_CONCURRENT_PER_USER': ('int', 0, 1000),
 'MARKET_QUERY_MAX_FIELDS': ('int', 1, 1000),
 'MARKET_QUERY_MAX_PARAMS': ('int', 1, 500),
 'MARKET_QUERY_MAX_PARAM_KEY_LENGTH': ('int', 1, 256),
 'MARKET_QUERY_MAX_PARAM_VALUE_LENGTH': ('int', 16, 1048576),
 'MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_TOKEN': ('int', 0, 1000),
 'MARKET_QUERY_SPECIAL_MAX_CONCURRENT_PER_USER': ('int', 0, 1000),
 'MAX_REQUEST_BODY_BYTES': ('int', 1024, 104857600),
 'MIN_REQUESTS_PER_MINUTE': ('int', 1, 100000),
 'REGISTRATION_CAPTCHA_TTL_SECONDS': ('int', 30, 1800),
 'SERVER_THREADS': ('int', 1, 256),
 'TUSHARE_SPEC_MONITOR_HOUR': ('int', 0, 23),
 'TUSHARE_SPEC_MONITOR_LEASE_SECONDS': ('int', 300, 86400),
 'TUSHARE_SPEC_MONITOR_MINUTE': ('int', 0, 59),
 'TUSHARE_SPEC_MONITOR_TIMEZONE': ('timezone',),
 'TUSHARE_SPEC_MONITOR_WEEKDAYS': ('weekdays',),
 'USAGE_LOG_QUEUE_SIZE': ('int', 100, 1000000),
 'USER_PASSWORD_MIN_LENGTH': ('int', 8, 128),
 'WAITRESS_CHANNEL_TIMEOUT': ('int', 10, 600),
 'WAITRESS_CONNECTION_LIMIT': ('int', 10, 10000)}

_ALLOWED_WEEKDAYS = frozenset(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))
_TIMEZONE_RE = re.compile(r"^(?:UTC|[A-Za-z0-9._+-]+(?:/[A-Za-z0-9._+-]+)+)$")


def _fail(message: str) -> None:
    raise RuntimeError("invalid platform policy: " + message)


def _require_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    extra = actual - expected
    missing = expected - actual
    if extra or missing:
        _fail(
            label
            + " keys mismatch"
            + (" extra=" + ",".join(sorted(extra)) if extra else "")
            + (" missing=" + ",".join(sorted(missing)) if missing else "")
        )


def _require_int(value: Any, low: int, high: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(label + " must be an integer")
    if value < low or value > high:
        _fail(label + f" must be between {low} and {high}")
    return value


def _require_text(value: Any, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        _fail(label + " must be a string")
    text = value.strip()
    if not text or len(text) > maximum:
        _fail(label + " must be a non-empty bounded string")
    return text


def _validate_string_list(value: Any, label: str) -> None:
    if not isinstance(value, list) or len(value) > 512:
        _fail(label + " must be a list")
    normalized = []
    for item in value:
        normalized.append(_require_text(item, label + " item", maximum=128))
    if len(normalized) != len(set(normalized)):
        _fail(label + " contains duplicate items")


def _validate_int_map(value: Any, low: int, high: int, label: str) -> None:
    if not isinstance(value, dict) or len(value) > 512:
        _fail(label + " must be an object")
    for raw_key, raw_value in value.items():
        _require_text(raw_key, label + " key", maximum=128)
        _require_int(raw_value, low, high, label + "." + str(raw_key))


def validate_policy_shape(policy: dict[str, Any]) -> None:
    if not isinstance(policy, dict):
        _fail("root must be an object")
    _require_exact_keys(
        policy,
        {"schema_version", "config", "waitress", "plans"},
        "root",
    )
    schema = policy.get("schema_version")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema != 1:
        _fail("schema_version must be integer 1")


def validate_config_values(values: dict[str, Any]) -> None:
    if not isinstance(values, dict):
        _fail("config must be an object")
    _require_exact_keys(values, set(CONFIG_RULES), "config")

    for key, rule in CONFIG_RULES.items():
        value = values[key]
        kind = rule[0]

        if kind == "int":
            _require_int(value, int(rule[1]), int(rule[2]), "config." + key)

        elif kind == "bool":
            if not isinstance(value, bool):
                _fail("config." + key + " must be a boolean")

        elif kind == "str_list":
            _validate_string_list(value, "config." + key)

        elif kind == "int_map":
            _validate_int_map(
                value,
                int(rule[1]),
                int(rule[2]),
                "config." + key,
            )

        elif kind == "enum":
            text = _require_text(value, "config." + key, maximum=32).upper()
            if text not in set(rule[1]):
                _fail("config." + key + " has an unsupported value")

        elif kind == "timezone":
            text = _require_text(value, "config." + key, maximum=64)
            if not _TIMEZONE_RE.fullmatch(text):
                _fail("config." + key + " has an invalid timezone shape")

        elif kind == "weekdays":
            text = _require_text(value, "config." + key, maximum=64)
            parts = [part.strip().lower() for part in text.split(",") if part.strip()]
            if not parts or len(parts) != len(set(parts)):
                _fail("config." + key + " has duplicate/empty weekdays")
            if any(part not in _ALLOWED_WEEKDAYS for part in parts):
                _fail("config." + key + " has an invalid weekday")

        else:
            _fail("unknown rule kind for " + key)

    if values["ADMIN_API_TEST_DISK_WARNING_PERCENT"] >= values["ADMIN_API_TEST_DISK_CRITICAL_PERCENT"]:
        _fail("disk warning percent must be lower than critical percent")

    if values["ADMIN_API_TEST_PREVIEW_PAGE_SIZE"] > values["ADMIN_API_TEST_MAX_PREVIEW_PAGE_SIZE"]:
        _fail("preview page size exceeds maximum preview page size")

    if values["MIN_REQUESTS_PER_MINUTE"] > values["DEFAULT_REQUESTS_PER_MINUTE"]:
        _fail("minimum requests per minute exceeds default requests per minute")

    if values["MARKET_DATA_CACHE_MAX_ITEM_BYTES"] > values["MARKET_DATA_CACHE_MAX_TOTAL_BYTES"]:
        _fail("cache max item bytes exceeds total cache bytes")

    if values["MARKET_DATA_REDIS_MAX_COMPRESSED_BYTES"] > values["MARKET_DATA_REDIS_MAX_DECOMPRESSED_BYTES"]:
        _fail("redis compressed byte limit exceeds decompressed byte limit")


def validate_waitress_section(section: dict[str, Any]) -> None:
    if not isinstance(section, dict):
        _fail("waitress must be an object")
    _require_exact_keys(section, {"backlog"}, "waitress")
    _require_int(section["backlog"], 1, 100000, "waitress.backlog")


def _validate_scopes(value: Any, label: str) -> None:
    if not isinstance(value, list) or not value or len(value) > 512:
        _fail(label + " must be a non-empty list")
    normalized = []
    for item in value:
        normalized.append(_require_text(item, label + " item", maximum=256))
    if len(normalized) != len(set(normalized)):
        _fail(label + " contains duplicate scopes")


def _validate_public_shared(shared: dict[str, Any], family: str) -> None:
    expected = {
        "quota_daily",
        "quota_per_minute",
        "max_symbols_per_request",
        "min_refresh_interval_sec",
        "scopes",
        "public",
    }
    _require_exact_keys(shared, expected, "plans." + family + ".shared")
    if shared["public"] is not True:
        _fail("plans." + family + ".shared.public must be true")
    _require_int(shared["quota_daily"], 1, 1_000_000_000, "plans." + family + ".quota_daily")
    _require_int(shared["quota_per_minute"], 1, 1_000_000, "plans." + family + ".quota_per_minute")
    _require_int(shared["max_symbols_per_request"], 1, 1_000_000, "plans." + family + ".max_symbols_per_request")
    _require_int(shared["min_refresh_interval_sec"], 0, 86400, "plans." + family + ".min_refresh_interval_sec")
    _validate_scopes(shared["scopes"], "plans." + family + ".scopes")


def _validate_public_variants(variants: Any, family: str) -> None:
    if not isinstance(variants, list) or len(variants) != 3:
        _fail("plans." + family + ".variants must contain exactly three entries")
    expected_fields = {
        "plan_code",
        "plan_name",
        "duration_type",
        "duration_days",
        "original_price_cent",
        "sale_price_cent",
    }
    seen = set()
    for variant in variants:
        if not isinstance(variant, dict):
            _fail("plans." + family + " variant must be an object")
        _require_exact_keys(variant, expected_fields, "plans." + family + " variant")
        duration = _require_text(variant["duration_type"], "duration_type", maximum=16).lower()
        if duration not in {"month", "quarter", "year"}:
            _fail("plans." + family + " duration_type invalid")
        if duration in seen:
            _fail("plans." + family + " duration_type duplicate")
        seen.add(duration)
        code = _require_text(variant["plan_code"], "plan_code", maximum=64)
        if code != family + "_" + duration:
            _fail("plans." + family + " plan_code does not match family/duration")
        _require_text(variant["plan_name"], "plan_name", maximum=256)
        _require_int(variant["duration_days"], 1, 36500, "duration_days")
        original = _require_int(variant["original_price_cent"], 0, 1_000_000_000, "original_price_cent")
        sale = _require_int(variant["sale_price_cent"], 0, 1_000_000_000, "sale_price_cent")
        if sale > original:
            _fail("sale_price_cent exceeds original_price_cent")
    if seen != {"month", "quarter", "year"}:
        _fail("plans." + family + " duration set invalid")


def _validate_admin(admin: dict[str, Any]) -> None:
    expected = {
        "plan_code",
        "plan_name",
        "plan_type",
        "duration_type",
        "duration_days",
        "original_price_cent",
        "sale_price_cent",
        "quota_daily",
        "quota_per_minute",
        "max_symbols_per_request",
        "min_refresh_interval_sec",
        "scopes",
        "public",
    }
    _require_exact_keys(admin, expected, "plans.admin")
    if admin["plan_code"] != "admin_internal":
        _fail("admin plan_code invalid")
    if str(admin["plan_type"]).lower() != "admin":
        _fail("admin plan_type invalid")
    if str(admin["duration_type"]).lower() != "internal":
        _fail("admin duration_type invalid")
    if admin["public"] is not False:
        _fail("admin public must be false")
    _require_text(admin["plan_name"], "plans.admin.plan_name", maximum=256)
    _require_int(admin["duration_days"], 1, 365000, "plans.admin.duration_days")
    _require_int(admin["original_price_cent"], 0, 1_000_000_000, "plans.admin.original_price_cent")
    _require_int(admin["sale_price_cent"], 0, 1_000_000_000, "plans.admin.sale_price_cent")
    _require_int(admin["quota_daily"], 0, 1_000_000_000, "plans.admin.quota_daily")
    _require_int(admin["quota_per_minute"], 0, 1_000_000, "plans.admin.quota_per_minute")
    _require_int(admin["max_symbols_per_request"], 1, 1_000_000, "plans.admin.max_symbols_per_request")
    _require_int(admin["min_refresh_interval_sec"], 0, 86400, "plans.admin.min_refresh_interval_sec")
    _validate_scopes(admin["scopes"], "plans.admin.scopes")


def validate_plan_policy(plans: dict[str, Any]) -> None:
    if not isinstance(plans, dict):
        _fail("plans must be an object")
    _require_exact_keys(plans, {"general", "special", "admin"}, "plans")

    for family in ("general", "special"):
        section = plans[family]
        if not isinstance(section, dict):
            _fail("plans." + family + " must be an object")
        _require_exact_keys(section, {"shared", "variants"}, "plans." + family)
        if not isinstance(section["shared"], dict):
            _fail("plans." + family + ".shared must be an object")
        _validate_public_shared(section["shared"], family)
        _validate_public_variants(section["variants"], family)

    admin = plans["admin"]
    if not isinstance(admin, dict):
        _fail("plans.admin must be an object")
    _validate_admin(admin)
