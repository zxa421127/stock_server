# -*- coding: utf-8 -*-
"""Execute one administrator market-interface test and archive the full result."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from services.admin_api_test_repository import AdminApiTestRepository
from services.admin_api_test_storage import AdminApiTestStorage, ResultTooLargeError
from services.market_data_service import MarketDataResult, query_market_data
from services.market_interface_spec_service import MarketInterfaceSpecService, get_market_interface_spec_service


_SENSITIVE_KEYS = {
    "token", "api_token", "tushare_token", "kaipanla_token", "password",
    "csrf_token", "cookie", "session", "secret", "api_key", "authorization",
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_records(frame: pd.DataFrame | None) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return json.loads(frame.to_json(orient="records", date_format="iso", force_ascii=False))


def _redact(value: Any, *, key: str = "") -> Any:
    if key.strip().lower() in _SENSITIVE_KEYS:
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _actual_type(values: list[Any]) -> str:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return "unknown"
    kinds = set()
    for value in non_null:
        if isinstance(value, bool):
            kinds.add("boolean")
        elif isinstance(value, int):
            kinds.add("integer")
        elif isinstance(value, float):
            kinds.add("number")
        elif isinstance(value, dict):
            kinds.add("object")
        elif isinstance(value, list):
            kinds.add("array")
        else:
            kinds.add("string")
    if kinds <= {"integer", "number"}:
        return "number" if "number" in kinds else "integer"
    return next(iter(kinds)) if len(kinds) == 1 else "mixed"


def _compatible(expected: str, actual: str) -> bool:
    expected = (expected or "unknown").lower()
    actual = (actual or "unknown").lower()
    if expected in {"unknown", "none", ""} or actual == "unknown":
        return True
    if expected == actual:
        return True
    return expected in {"integer", "number"} and actual in {"integer", "number"}


class AdminMarketTestService:
    def __init__(
        self,
        repository: AdminApiTestRepository | None = None,
        spec_service: MarketInterfaceSpecService | None = None,
        storage: AdminApiTestStorage | None = None,
        *,
        query_func: Callable[..., MarketDataResult] | None = None,
    ):
        self.repository = repository or AdminApiTestRepository()
        self.spec_service = spec_service or get_market_interface_spec_service()
        self.storage = storage or AdminApiTestStorage()
        self.query_func = query_func or query_market_data

    def run_item(self, item_id: int) -> dict[str, Any]:
        item = self.repository.get_item(item_id)
        if not item:
            raise KeyError(f"测试项目不存在：{item_id}")
        started_at = _now()
        started = time.perf_counter()
        try:
            self.repository.update_item(
                item_id, status="running", started_at=started_at,
                error_code="", error_message="",
            )
            return self._run_item(item, started=started, started_at=started_at)
        except Exception as exc:
            logging.exception(
                "管理员接口测试未处理异常: item_id=%s provider=%s api=%s",
                item_id, item.get("provider"), item.get("api_name"),
            )
            return self._finish_unhandled_error(item, exc, started, started_at)

    def _run_item(
        self, item: dict[str, Any], *, started: float, started_at: str,
    ) -> dict[str, Any]:
        spec = self.spec_service.get_effective_spec(item["provider"], item["api_name"])
        if not spec:
            return self._finish_error(item, "unsupported", 404, "未找到接口规格", started, started_at)

        raw_params = dict(item.get("params") or {})
        output_fields = self.spec_service.all_output_field_names(item["provider"], item["api_name"])
        try:
            validated = self.spec_service.validate_params(item["provider"], item["api_name"], raw_params)
        except (ValueError, KeyError) as exc:
            return self._finish_error(item, "invalid_params", 400, str(exc), started, started_at, request_params=raw_params)

        query_params = dict(validated)
        if item["provider"] == "tushare" and output_fields:
            query_params["fields"] = ",".join(output_fields)
        bypass_cache = item.get("mode") == "upstream"
        request_payload = {
            "provider": item["provider"],
            "api_name": item["api_name"],
            "mode": item.get("mode") or "upstream",
            "params": _redact(query_params),
            "output_fields": output_fields,
            "spec_version": item.get("spec_version") or self.spec_service.current_version(),
            "spec_hash": item.get("spec_hash") or spec.get("spec_hash"),
            "started_at": started_at,
        }
        try:
            result = self.query_func(
                item["provider"], item["api_name"], query_params,
                bypass_cache=bypass_cache,
            )
        except TimeoutError as exc:
            return self._finish_error(item, "timeout", 504, str(exc) or "上游调用超时", started, started_at, request_params=query_params)
        except KeyError as exc:
            return self._finish_error(item, "unsupported", 404, str(exc), started, started_at, request_params=query_params)
        except ValueError as exc:
            return self._finish_error(item, "invalid_params", 400, str(exc), started, started_at, request_params=query_params)
        except Exception as exc:
            text = str(exc)
            status = "timeout" if "timeout" in text.lower() or "超时" in text else "internal_error"
            code = 504 if status == "timeout" else 500
            return self._finish_error(item, status, code, text or exc.__class__.__name__, started, started_at, request_params=query_params)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        if result.error:
            status, http_status = self._classify_error(result.error, result.meta)
            response = self._error_envelope(item, result.error, http_status, result.meta)
            schema_report = self._schema_report(spec, [], output_fields)
            request_payload["finished_at"] = _now()
            return self._store_and_finish(
                item, status=status, http_status=http_status, error_code=status,
                error_message=result.error, elapsed_ms=elapsed_ms,
                request_payload=request_payload, response_payload=response,
                schema_report=schema_report, result=result,
            )

        records = _safe_records(result.data)
        schema_report = self._schema_report(spec, records, output_fields)
        fallback_used = bool(result.meta.get("fallback_used"))
        if schema_report["status"] == "mismatch":
            status = "schema_mismatch"
        elif fallback_used:
            status = "success_fallback"
        elif records:
            status = "success_data"
        else:
            status = "success_empty"
        response = self._success_envelope(item, result, records)
        request_payload["finished_at"] = _now()
        return self._store_and_finish(
            item, status=status, http_status=200,
            error_code="schema_mismatch" if status == "schema_mismatch" else "",
            error_message="请求的输出字段未完整返回" if status == "schema_mismatch" else "",
            elapsed_ms=elapsed_ms, request_payload=request_payload,
            response_payload=response, schema_report=schema_report, result=result,
        )

    @staticmethod
    def _classify_error(message: str, meta: dict[str, Any]) -> tuple[str, int]:
        text = (message or "").lower()
        http_status = int((meta or {}).get("http_status") or 502)
        if any(word in text for word in ("权限", "积分", "permission", "无权", "没有接口访问")):
            return "permission_denied", 403
        if any(word in text for word in ("scope", "套餐")):
            return "scope_denied", 403
        if any(word in text for word in ("timeout", "timed out", "超时")):
            return "timeout", 504
        if any(word in text for word in ("未开放", "不支持", "unsupported", "not found")):
            return "unsupported", 404
        if any(word in text for word in ("参数", "invalid", "格式")):
            return "invalid_params", 400
        return "upstream_error", http_status

    @staticmethod
    def _success_envelope(item: dict[str, Any], result: MarketDataResult, records: list[dict[str, Any]]) -> dict[str, Any]:
        meta = dict(result.meta or {})
        fallback = bool(meta.get("fallback_used"))
        return {
            "success": True,
            "code": 200,
            "provider": result.provider,
            "data_type": result.data_type,
            "source": {
                "provider": result.provider,
                "cache_hit": bool(result.cache_hit),
                "cache_bypassed": item.get("mode") == "upstream",
                **meta,
            },
            "freshness": {
                "requested_trade_date": meta.get("requested_trade_date"),
                "actual_trade_date": meta.get("actual_trade_date"),
                "fallback_used": fallback,
                "data_freshness": meta.get("data_freshness"),
                "fallback_attempt_count": meta.get("fallback_attempt_count", 0),
            },
            "snapshot": {
                "snapshot_id": meta.get("snapshot_id"),
                "snapshot_type": meta.get("snapshot_type"),
                "snapshot_time": meta.get("snapshot_time"),
                "payload_hash": meta.get("payload_hash"),
            },
            "quality": {
                "data_quality": meta.get("data_quality"),
                "schema_version": meta.get("schema_version"),
                "warning": meta.get("warning"),
            },
            "count": len(records),
            "data": records,
            "msg": f"管理员测试成功，共{len(records)}条" + ("；使用最近可用日期回退" if fallback else ""),
        }

    @staticmethod
    def _error_envelope(item: dict[str, Any], message: str, http_status: int, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "success": False,
            "code": int(http_status),
            "provider": item.get("provider"),
            "data_type": item.get("api_name"),
            "source": dict(meta or {}),
            "data": [],
            "msg": message,
        }

    @staticmethod
    def _schema_report(spec: dict[str, Any], records: list[dict[str, Any]], requested_fields: list[str]) -> dict[str, Any]:
        expected_rows = {row["name"]: row for row in spec.get("output_fields", [])}
        expected_fields = requested_fields or list(expected_rows)
        returned_fields: list[str] = []
        for record in records:
            for key in record:
                if key not in returned_fields:
                    returned_fields.append(key)
        missing = [name for name in expected_fields if records and name not in returned_fields]
        unexpected = [name for name in returned_fields if expected_rows and name not in expected_rows]
        type_mismatches = []
        null_statistics = {}
        field_details = []
        for name in returned_fields:
            values = [record.get(name) for record in records]
            actual = _actual_type(values)
            expected = str(expected_rows.get(name, {}).get("normalized_type") or "unknown")
            nulls = sum(value is None for value in values)
            null_statistics[name] = nulls
            matched = _compatible(expected, actual)
            if not matched:
                type_mismatches.append({"field": name, "expected": expected, "actual": actual})
            field_details.append({
                "field": name,
                "official_type": expected_rows.get(name, {}).get("official_type"),
                "expected_type": expected,
                "actual_type": actual,
                "description": expected_rows.get(name, {}).get("description", ""),
                "null_count": nulls,
                "matched": matched,
            })
        mismatch = bool(missing or type_mismatches)
        return {
            "status": "mismatch" if mismatch else "matched",
            "expected_fields": expected_fields,
            "returned_fields": returned_fields,
            "missing_requested_fields": missing,
            "unexpected_fields": unexpected,
            "type_mismatches": type_mismatches,
            "null_statistics": null_statistics,
            "field_details": field_details,
        }

    def _finish_unhandled_error(
        self, item: dict[str, Any], exc: Exception, started: float, started_at: str,
    ) -> dict[str, Any]:
        detail = str(exc).strip()
        message = f"{exc.__class__.__name__}: {detail}" if detail else exc.__class__.__name__
        try:
            spec = self.spec_service.get_effective_spec(
                item["provider"], item["api_name"]
            ) or {}
            output_fields = self.spec_service.all_output_field_names(
                item["provider"], item["api_name"]
            )
            schema_report = self._schema_report(spec, [], output_fields)
        except Exception as spec_exc:
            output_fields = list(item.get("fields") or [])
            schema_report = {
                "status": "diagnostic_error",
                "expected_fields": output_fields,
                "returned_fields": [],
                "message": f"规格诊断失败：{spec_exc.__class__.__name__}: {spec_exc}",
            }
        request_payload = {
            "provider": item.get("provider"),
            "api_name": item.get("api_name"),
            "mode": item.get("mode"),
            "params": _redact(item.get("params") or {}),
            "output_fields": output_fields,
            "started_at": started_at,
            "finished_at": _now(),
            "spec_version": item.get("spec_version"),
            "spec_hash": item.get("spec_hash"),
            "diagnostic": {"exception_type": exc.__class__.__name__},
        }
        response = self._error_envelope(item, message, 500)
        return self._store_and_finish(
            item, status="internal_error", http_status=500,
            error_code="internal_error", error_message=message,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 3),
            request_payload=request_payload, response_payload=response,
            schema_report=schema_report, result=None,
        )

    def _finish_error(
        self, item: dict[str, Any], status: str, http_status: int, message: str,
        started: float, started_at: str, *, request_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        response = self._error_envelope(item, message, http_status)
        spec = self.spec_service.get_effective_spec(item["provider"], item["api_name"]) or {}
        output_fields = self.spec_service.all_output_field_names(item["provider"], item["api_name"])
        schema_report = self._schema_report(spec, [], output_fields)
        request_payload = {
            "provider": item["provider"], "api_name": item["api_name"],
            "mode": item.get("mode"), "params": _redact(request_params or item.get("params") or {}),
            "output_fields": output_fields, "started_at": started_at,
            "finished_at": _now(), "spec_version": item.get("spec_version"), "spec_hash": item.get("spec_hash"),
        }
        return self._store_and_finish(
            item, status=status, http_status=http_status, error_code=status,
            error_message=message, elapsed_ms=elapsed_ms, request_payload=request_payload,
            response_payload=response, schema_report=schema_report, result=None,
        )

    def _store_and_finish(
        self, item: dict[str, Any], *, status: str, http_status: int,
        error_code: str, error_message: str, elapsed_ms: float,
        request_payload: dict[str, Any], response_payload: dict[str, Any],
        schema_report: dict[str, Any], result: MarketDataResult | None,
    ) -> dict[str, Any]:
        try:
            stored = self.storage.store_result(
                batch_id=item["batch_id"], item_id=item["id"], provider=item["provider"], api_name=item["api_name"],
                request_payload=request_payload, response_payload=response_payload, schema_report=schema_report,
            )
        except ResultTooLargeError as exc:
            status = "result_too_large"
            http_status = 413
            error_code = status
            error_message = str(exc)
            stored = {"result_dir": str(self.storage.item_dir(item["batch_id"], item["id"], item["provider"], item["api_name"]))}
        except Exception as exc:
            detail = str(exc).strip()
            storage_message = (
                f"结果文件写入失败（原状态：{status}）：{exc.__class__.__name__}"
                + (f": {detail}" if detail else "")
            )
            logging.exception(
                "管理员接口测试结果写入失败: item_id=%s batch=%s",
                item.get("id"), item.get("batch_id"),
            )
            updated = self.repository.update_item(
                item["id"], status="storage_error", http_status=500,
                row_count=0, column_count=0, elapsed_ms=elapsed_ms,
                cache_hit=bool(result.cache_hit) if result else False,
                fallback_used=False, actual_trade_date="",
                error_code="storage_error", error_message=storage_message,
                finished_at=_now(),
            )
            self.repository.add_event(
                item["batch_id"], "item_storage_error",
                {
                    "status": "storage_error",
                    "exception_type": exc.__class__.__name__,
                    "error": detail or exc.__class__.__name__,
                    "original_status": status,
                },
                item_id=item["id"],
            )
            self.repository.recalculate_batch_counts(item["batch_id"])
            return updated or {}
        meta = dict((result.meta if result else {}) or {})
        stored_fields = dict(stored)
        row_count = int(stored_fields.pop("row_count", len(response_payload.get("data") or [])) or 0)
        column_count = int(stored_fields.pop("column_count", 0) or 0)
        stored_fields.pop("result_uncompressed_size_bytes", None)
        updated = self.repository.update_item(
            item["id"], status=status, http_status=http_status,
            row_count=row_count, column_count=column_count, elapsed_ms=elapsed_ms,
            cache_hit=bool(result.cache_hit) if result else False,
            fallback_used=bool(meta.get("fallback_used")),
            actual_trade_date=str(meta.get("actual_trade_date") or ""),
            error_code=error_code, error_message=error_message,
            finished_at=_now(), **stored_fields,
        )
        self.repository.add_event(
            item["batch_id"], "item_finished",
            {"status": status, "http_status": http_status, "row_count": updated.get("row_count"), "elapsed_ms": elapsed_ms},
            item_id=item["id"],
        )
        self.repository.recalculate_batch_counts(item["batch_id"])
        return updated or {}
