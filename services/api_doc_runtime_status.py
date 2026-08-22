# -*- coding: utf-8 -*-
"""Runtime health model for the public API documentation page.

The generated API catalog describes the interface contract.  Actual health is
read from the newest *valid* full-interface acceptance report under
``data/auto_test_results``.  A failed discovery run that produced zero
interfaces is deliberately ignored so it cannot overwrite the last good status.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any

import config

_REPORT_GLOB = "全部真实数据接口_*.json"
_REPORT_STAMP_RE = re.compile(r"全部真实数据接口_(\d{8}_\d{6})\.json$")
_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, Any] = {
    "checked_monotonic": 0.0,
    "result_dir": "",
    "latest_mtime_ns": -1,
    "snapshot": None,
}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _yes(value: Any) -> bool:
    return str(value or "").strip().lower() in {"是", "yes", "true", "1", "y"}


def _normalize_provider(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_api_name(value: Any) -> str:
    return str(value or "").strip().strip("/").lower().replace("-", "_")


def endpoint_identity_from_path(path: str) -> tuple[str, str]:
    """Return ``(provider, api_name)`` from a platform market-data path.

    Nested APIs are preserved, e.g. ``morning_bidding/history``.
    """
    clean = str(path or "").split("?", 1)[0]
    parts = [part for part in clean.split("/") if part]
    try:
        market_index = parts.index("market")
    except ValueError:
        return "", ""
    if len(parts) <= market_index + 2:
        return "", ""
    provider = _normalize_provider(parts[market_index + 1])
    api_name = _normalize_api_name("/".join(parts[market_index + 2 :]))
    return provider, api_name


def endpoint_key(provider: Any, api_name: Any) -> str:
    provider_text = _normalize_provider(provider)
    api_text = _normalize_api_name(api_name)
    if not provider_text or not api_text:
        return ""
    return f"{provider_text}.{api_text}"


def _status_from_row(row: dict[str, Any]) -> dict[str, Any]:
    has_data = _yes(row.get("是否取得数据"))
    callable_ok = _yes(row.get("接口是否可调用"))
    fallback_used = bool(row.get("是否回退最近数据"))
    problem = str(row.get("问题分类") or "").strip()
    verdict = str(row.get("结论") or "").strip()

    if has_data and fallback_used:
        status_key = "fallback"
        status_label = "回退取得数据"
    elif has_data:
        status_key = "healthy"
        status_label = "实测正常"
    elif callable_ok:
        status_key = "callable_empty"
        status_label = "可调用但无匹配数据"
    else:
        problem_map = {
            "中转路由未配置": "upstream_route_missing",
            "中转Token未开通": "upstream_permission",
            "中转明确不支持": "upstream_unsupported",
            "中转临时故障": "upstream_temporary",
            "中转或上游性能": "upstream_performance",
            "中转或上游异常": "upstream_error",
            "网站账户权限": "account_permission",
            "网站限流": "rate_limited",
            "网络或服务器异常": "network_error",
        }
        status_key = problem_map.get(problem, "uncallable")
        status_label = problem or verdict or "真正不可调用"

    return {
        "status_key": status_key,
        "status_label": status_label,
        "has_data": has_data,
        "callable": callable_ok,
        "fallback_used": fallback_used,
        "verdict": verdict,
        "problem_category": problem,
        "http_status": row.get("HTTP状态"),
        "data_count": _as_int(row.get("数据条数")),
        "data_freshness": str(row.get("数据新鲜度") or "").strip(),
        "requested_trade_date": row.get("请求交易日"),
        "actual_trade_date": row.get("实际数据日期"),
        "message": str(row.get("消息") or "").strip(),
        "elapsed_ms": row.get("总耗时毫秒"),
        "upstream_elapsed_ms": row.get("上游耗时毫秒"),
        "lifecycle": str(row.get("接口生命周期") or "active").strip(),
        "test_note": str(row.get("测试说明") or "").strip(),
    }


def _report_datetime(path: Path, payload: dict[str, Any]) -> datetime:
    explicit = str(payload.get("生成时间") or "").strip()
    if explicit:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(explicit[:19], fmt)
            except ValueError:
                continue
    match = _REPORT_STAMP_RE.search(path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def _empty_snapshot(*, invalid_reports: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "valid": False,
        "report_path": "",
        "report_name": "",
        "report_time": "",
        "report_age_seconds": None,
        "total_count": 0,
        "coverage_count": 0,
        "callable_count": 0,
        "data_count": 0,
        "direct_count": 0,
        "fallback_count": 0,
        "callable_empty_count": 0,
        "uncallable_count": 0,
        "problem_counts": {},
        "status_counts": {},
        "endpoints": {},
        "invalid_reports": invalid_reports or [],
    }


def _validate_payload(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "报告不是JSON对象"
    total = _as_int(payload.get("总接口数"), -1)
    rows = payload.get("结果")
    if total <= 0:
        return False, "总接口数必须大于0"
    if not isinstance(rows, list):
        return False, "结果字段不是列表"
    if len(rows) != total:
        return False, f"结果数量{len(rows)}与总接口数{total}不一致"
    keys = {
        endpoint_key(row.get("数据来源"), row.get("接口"))
        for row in rows
        if isinstance(row, dict)
    }
    keys.discard("")
    if not keys:
        return False, "没有可识别的provider.api_name"
    return True, ""


def _build_snapshot(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("结果") or []
    endpoints: dict[str, dict[str, Any]] = {}
    status_counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = endpoint_key(row.get("数据来源"), row.get("接口"))
        if not key:
            continue
        status = _status_from_row(row)
        status["provider"] = _normalize_provider(row.get("数据来源"))
        status["api_name"] = _normalize_api_name(row.get("接口"))
        endpoints[key] = status
        status_counts[status["status_key"]] = status_counts.get(status["status_key"], 0) + 1

    report_dt = _report_datetime(path, payload)
    age = max((datetime.now() - report_dt).total_seconds(), 0.0)
    total = _as_int(payload.get("总接口数"), len(rows))
    callable_count = _as_int(
        payload.get("可调用接口数"),
        sum(1 for item in endpoints.values() if item["callable"]),
    )
    data_count = _as_int(
        payload.get("取得数据接口数"),
        sum(1 for item in endpoints.values() if item["has_data"]),
    )
    fallback_count = _as_int(
        payload.get("回退最近可用日期后取得数据接口数"),
        sum(1 for item in endpoints.values() if item["fallback_used"] and item["has_data"]),
    )
    direct_count = _as_int(
        payload.get("当前日期或原请求直接取得数据接口数"),
        max(data_count - fallback_count, 0),
    )
    uncallable_count = _as_int(payload.get("不可调用接口数"), max(total - callable_count, 0))
    callable_empty_count = max(callable_count - data_count, 0)

    return {
        "valid": True,
        "report_path": str(path),
        "report_name": path.name,
        "report_time": report_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "report_age_seconds": age,
        "report_version": payload.get("报告版本") or 1,
        "test_address": payload.get("测试地址") or "",
        "test_mode": payload.get("测试模式") or "",
        "total_count": total,
        "coverage_count": len(endpoints),
        "callable_count": callable_count,
        "data_count": data_count,
        "direct_count": direct_count,
        "fallback_count": fallback_count,
        "callable_empty_count": callable_empty_count,
        "uncallable_count": uncallable_count,
        "problem_counts": dict(payload.get("问题分类统计") or {}),
        "status_counts": status_counts,
        "endpoints": endpoints,
        "invalid_reports": [],
    }


def load_latest_runtime_report(
    *,
    result_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Load the newest valid full-interface report, skipping broken zero runs."""
    directory = Path(result_dir or (Path(config.DATA_DIR) / "auto_test_results"))
    if not directory.exists():
        return _empty_snapshot()

    candidates = sorted(
        directory.glob(_REPORT_GLOB),
        key=lambda item: (item.stat().st_mtime_ns, item.name),
        reverse=True,
    )
    invalid_reports: list[dict[str, str]] = []
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            invalid_reports.append({"name": path.name, "reason": f"读取失败：{exc}"})
            continue
        valid, reason = _validate_payload(payload)
        if not valid:
            invalid_reports.append({"name": path.name, "reason": reason})
            continue
        snapshot = _build_snapshot(path, payload)
        snapshot["invalid_reports"] = invalid_reports
        return snapshot
    return _empty_snapshot(invalid_reports=invalid_reports)


def get_runtime_status_snapshot(
    *,
    force: bool = False,
    result_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Return a cached runtime snapshot and rescan report files periodically."""
    directory = Path(result_dir or (Path(config.DATA_DIR) / "auto_test_results"))
    scan_seconds = max(int(getattr(config, "API_DOC_STATUS_FILE_SCAN_SECONDS", 60) or 60), 1)
    now_mono = time.monotonic()
    directory_key = str(directory.resolve())
    latest_mtime_ns = -1
    if directory.exists():
        try:
            latest_mtime_ns = max(
                (path.stat().st_mtime_ns for path in directory.glob(_REPORT_GLOB)),
                default=-1,
            )
        except OSError:
            latest_mtime_ns = -1

    with _CACHE_LOCK:
        cached = _CACHE.get("snapshot")
        cache_fresh = (
            not force
            and cached is not None
            and _CACHE.get("result_dir") == directory_key
            and _CACHE.get("latest_mtime_ns") == latest_mtime_ns
            and now_mono - float(_CACHE.get("checked_monotonic") or 0.0) < scan_seconds
        )
        if cache_fresh:
            return cached

        snapshot = load_latest_runtime_report(result_dir=directory)
        _CACHE.update({
            "checked_monotonic": now_mono,
            "result_dir": directory_key,
            "latest_mtime_ns": latest_mtime_ns,
            "snapshot": snapshot,
        })
        if snapshot.get("invalid_reports"):
            logging.warning(
                "[API文档状态] 已忽略无效测试报告: %s",
                snapshot.get("invalid_reports"),
            )
        return snapshot


def runtime_status_for_path(path: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any] | None:
    provider, api_name = endpoint_identity_from_path(path)
    if not provider or not api_name:
        return None
    data = snapshot if snapshot is not None else get_runtime_status_snapshot()
    return (data.get("endpoints") or {}).get(endpoint_key(provider, api_name))


def runtime_report_is_stale(snapshot: dict[str, Any], *, max_age_seconds: int | None = None) -> bool:
    if not snapshot.get("valid"):
        return True
    age = snapshot.get("report_age_seconds")
    if age is None:
        return True
    threshold = int(
        max_age_seconds
        if max_age_seconds is not None
        else getattr(config, "API_DOC_STATUS_REFRESH_INTERVAL_SECONDS", 43200)
    )
    return float(age) > max(threshold, 1)
