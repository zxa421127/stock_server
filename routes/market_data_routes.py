# -*- coding: utf-8 -*-
"""Provider-neutral market-data API routes."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import uuid

import config

import pandas as pd
from flask import Blueprint, g, jsonify, request

from middleware.auth import require_scope
from services.market_data_cache import cache_stats, clear_cache
from services.market_query_security import (
    QuerySecurityError,
    enforce_refresh_interval,
    request_lease,
    validate_market_query,
)
from services.audit_service import record_operation
from services.market_data_service import (
    get_provider_catalog,
    get_provider_health,
    list_providers,
    query_market_data,
    scope_for,
)

market_data_bp = Blueprint("market_data", __name__)


class ResponseLimitExceeded(ValueError):
    def __init__(self, reason: str, actual: int, limit: int):
        super().__init__(f"response {reason} limit exceeded: {actual}>{limit}")
        self.reason = reason
        self.actual = int(actual)
        self.limit = int(limit)


def response_row_limit_for(provider_code: str, data_type: str) -> int:
    """Return an interface-specific row cap without weakening the global default."""
    default_limit = int(getattr(config, "API_MAX_RESPONSE_ROWS", 5000))
    overrides = dict(getattr(config, "API_MAX_RESPONSE_ROWS_OVERRIDES", {}) or {})
    provider = str(provider_code or "").strip().lower().replace("-", "_")
    normalized = (
        str(data_type or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
    )
    key = f"{provider}.{normalized}"
    if key in overrides:
        return max(1, int(overrides[key]))
    return max(1, default_limit)


def enforce_response_limits(records: list[dict], *, max_rows: int, max_bytes: int) -> None:
    if len(records) > int(max_rows):
        raise ResponseLimitExceeded("rows", len(records), int(max_rows))
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    if len(encoded) > int(max_bytes):
        raise ResponseLimitExceeded("bytes", len(encoded), int(max_bytes))


def enforce_dataframe_limits(df: pd.DataFrame, *, max_rows: int, max_bytes: int) -> None:
    """Reject oversized frames before expensive JSON materialization."""
    if df is None:
        return
    if len(df) > int(max_rows):
        raise ResponseLimitExceeded("rows", len(df), int(max_rows))
    try:
        actual_bytes = int(df.memory_usage(index=True, deep=True).sum())
    except Exception:
        actual_bytes = int(df.memory_usage(index=True).sum())
    if actual_bytes > int(max_bytes):
        raise ResponseLimitExceeded("dataframe_bytes", actual_bytes, int(max_bytes))



def _safe_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))


def _collect_params() -> dict:
    params: dict = {}
    if request.method == "GET":
        params.update(request.args.to_dict(flat=True))
    elif request.is_json:
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict):
            params.update(body.get("params") if isinstance(body.get("params"), dict) else body)
    else:
        params.update(request.form.to_dict(flat=True))
        params.update(request.args.to_dict(flat=True))
    for key in (
        "token",
        "api_name",
        "source_code",
        "api_url",
        "provider",
        "bypass_cache",
        "cache_mode",
    ):
        params.pop(key, None)
    return params

# C6A03R2_MANDATORY_GENERIC_PAGINATION_V1
def _pagination_query_fingerprint(
    provider_code: str,
    data_type: str,
    params: dict,
) -> str:
    normalized_type = (
        str(data_type or "")
        .strip()
        .lower()
        .replace("-", "_")
        .replace("/", "_")
    )
    payload = {
        "provider": str(provider_code or "").strip().lower().replace("-", "_"),
        "data_type": normalized_type,
        "params": dict(params or {}),
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

# C6A03R3_SIGNED_CURSOR_HMAC_SHA256_V2
def _pagination_cursor_signing_key() -> bytes:
    raw_secret = getattr(
        config,
        "API_PAGINATION_CURSOR_SECRET",
        None,
    )
    if raw_secret in (None, ""):
        raw_secret = getattr(config, "SECRET_KEY", None)

    if raw_secret in (None, ""):
        raise RuntimeError(
            "pagination cursor signing secret is not configured"
        )

    secret_bytes = str(raw_secret).encode("utf-8")
    domain = b"stock-server:market-data:pagination-cursor:v2"

    # Domain separation prevents direct cross-protocol reuse of SECRET_KEY.
    return hmac.new(
        secret_bytes,
        domain,
        hashlib.sha256,
    ).digest()



class PublicValidationError(ValueError):
    """Validation error whose message is approved for public responses."""


def _decode_pagination_cursor(value: str) -> dict:
    text = str(value or "").strip()
    if not text:
        raise PublicValidationError("cursor不能为空")
    if len(text) > 2048:
        raise PublicValidationError("cursor过长")

    parts = text.split(".")
    if len(parts) != 2:
        raise PublicValidationError("cursor签名格式无效")

    payload_token, signature_token = parts
    if not payload_token or not signature_token:
        raise PublicValidationError("cursor签名格式无效")

    try:
        payload_padding = "=" * (-len(payload_token) % 4)
        payload_raw = base64.urlsafe_b64decode(
            (payload_token + payload_padding).encode("ascii")
        )

        signature_padding = "=" * (-len(signature_token) % 4)
        supplied_signature = base64.urlsafe_b64decode(
            (signature_token + signature_padding).encode("ascii")
        )
    except Exception as exc:
        raise PublicValidationError("cursor格式无效") from exc

    expected_signature = hmac.new(
        _pagination_cursor_signing_key(),
        payload_raw,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(
        supplied_signature,
        expected_signature,
    ):
        raise PublicValidationError("cursor签名无效")

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:
        raise PublicValidationError("cursor内容无效") from exc

    if not isinstance(payload, dict) or payload.get("v") != 2:
        raise PublicValidationError("cursor版本无效")

    try:
        offset = int(payload.get("offset"))
        page_size = int(payload.get("page_size"))
    except (TypeError, ValueError) as exc:
        raise PublicValidationError("cursor分页位置无效") from exc

    fingerprint = str(payload.get("fp") or "")
    if offset < 0 or page_size < 1:
        raise PublicValidationError("cursor分页位置无效")
    if len(fingerprint) != 64:
        raise PublicValidationError("cursor查询指纹无效")
    try:
        bytes.fromhex(fingerprint)
    except ValueError as exc:
        raise PublicValidationError("cursor查询指纹无效") from exc

    return {
        "offset": offset,
        "page_size": page_size,
        "fingerprint": fingerprint,
    }


def _encode_pagination_cursor(
    offset: int,
    page_size: int,
    fingerprint: str,
) -> str:
    payload = {
        "v": 2,
        "offset": int(offset),
        "page_size": int(page_size),
        "fp": str(fingerprint),
    }
    payload_raw = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    signature = hmac.new(
        _pagination_cursor_signing_key(),
        payload_raw,
        hashlib.sha256,
    ).digest()

    payload_token = base64.urlsafe_b64encode(
        payload_raw
    ).decode("ascii").rstrip("=")

    signature_token = base64.urlsafe_b64encode(
        signature
    ).decode("ascii").rstrip("=")

    return payload_token + "." + signature_token


def _extract_pagination_controls(
    raw_params: dict,
    provider_code: str,
    data_type: str,
) -> dict:
    raw_page_size = raw_params.pop("page_size", None)
    raw_cursor = raw_params.pop("cursor", None)

    response_cap = response_row_limit_for(provider_code, data_type)
    configured_max_page_size = int(
        getattr(config, "API_MAX_PAGE_SIZE", 2000) or 2000
    )
    max_page_size = min(
        response_cap,
        max(1, configured_max_page_size),
    )

    default_page_size = int(
        getattr(config, "API_DEFAULT_PAGE_SIZE", 1000) or 1000
    )
    default_page_size = max(
        1,
        min(default_page_size, max_page_size),
    )

    cursor_payload = (
        _decode_pagination_cursor(raw_cursor)
        if raw_cursor not in (None, "")
        else None
    )

    if raw_page_size not in (None, ""):
        if isinstance(raw_page_size, bool):
            raise PublicValidationError("page_size必须是整数")
        try:
            page_size = int(raw_page_size)
        except (TypeError, ValueError) as exc:
            raise PublicValidationError("page_size必须是整数") from exc
    elif cursor_payload is not None:
        page_size = int(cursor_payload["page_size"])
    else:
        page_size = default_page_size

    if page_size < 1:
        raise PublicValidationError("page_size必须大于0")
    if page_size > max_page_size:
        raise PublicValidationError(f"page_size超过单页上限{max_page_size}")

    if (
        cursor_payload is not None
        and raw_page_size not in (None, "")
        and int(cursor_payload["page_size"]) != page_size
    ):
        raise PublicValidationError("page_size与cursor不一致")

    return {
        "page_size": page_size,
        "offset": int(cursor_payload["offset"]) if cursor_payload else 0,
        "fingerprint": None,
        "cursor_payload": cursor_payload,
    }


def _bind_pagination_to_query(
    pagination: dict,
    provider_code: str,
    data_type: str,
    params: dict,
) -> dict:
    fingerprint = _pagination_query_fingerprint(
        provider_code,
        data_type,
        params,
    )
    cursor_payload = pagination.get("cursor_payload")
    if (
        cursor_payload is not None
        and str(cursor_payload.get("fingerprint")) != fingerprint
    ):
        raise PublicValidationError("cursor与当前查询条件不匹配")

    pagination["fingerprint"] = fingerprint
    return pagination


def _paginate_dataframe(
    df: pd.DataFrame | None,
    pagination: dict,
) -> tuple[pd.DataFrame, dict]:
    if df is None:
        df = pd.DataFrame()

    total_rows = len(df)
    offset = int(pagination["offset"])
    page_size = int(pagination["page_size"])

    if offset > total_rows:
        raise PublicValidationError("cursor已超出当前结果范围")

    end = min(total_rows, offset + page_size)
    page_df = df.iloc[offset:end].copy()
    has_more = end < total_rows
    next_cursor = (
        _encode_pagination_cursor(
            end,
            page_size,
            str(pagination["fingerprint"]),
        )
        if has_more
        else None
    )

    return page_df, {
        "page_size": page_size,
        "returned": len(page_df),
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def _scope_resolver(provider_code: str, data_type: str = "") -> str:
    return scope_for(provider_code, data_type)


def _query_response(provider_code: str, data_type: str, *, bypass_cache: bool = False):
    try:
        raw_params = _collect_params()
        pagination = _extract_pagination_controls(
            raw_params,
            provider_code,
            data_type,
        )
        plan = dict(getattr(g, "current_plan", {}) or {})
        user = dict(getattr(g, "current_user", {}) or {})
        params = validate_market_query(provider_code, data_type, raw_params, plan)
        pagination = _bind_pagination_to_query(
            pagination,
            provider_code,
            data_type,
            params,
        )
        enforce_refresh_interval(
            int(user.get("id") or 0),
            int(user.get("api_key_id") or 0),
            provider_code,
            data_type,
            plan,
        )
        with request_lease(
            int(user.get("id") or 0),
            int(user.get("api_key_id") or 0),
            plan,
        ):
            result = query_market_data(
                provider_code,
                data_type,
                params,
                bypass_cache=bypass_cache,
            )

            source = {
                "provider": result.provider,
                "cache_hit": result.cache_hit,
                "cache_bypassed": bool(bypass_cache),
                **result.meta,
            }
            if result.error:
                status = int(result.meta.get("http_status") or 502)
                if status < 400 or status > 599:
                    status = 502
                event_id = uuid.uuid4().hex
                logging.error(
                    "[行情上游错误] event_id=%s provider=%s data_type=%s status=%s detail=%s",
                    event_id,
                    result.provider,
                    result.data_type,
                    status,
                    result.error,
                )
                safe_source = {
                    "provider": result.provider,
                    "cache_hit": result.cache_hit,
                    "cache_bypassed": bool(bypass_cache),
                }
                return jsonify({
                    "success": False,
                    "code": status,
                    "error_code": "upstream_unavailable",
                    "event_id": event_id,
                    "provider": result.provider,
                    "data_type": result.data_type,
                    "source": safe_source,
                    "items": [],
                    "msg": "上游数据服务暂时不可用",
                }), status

            try:
                response_row_limit = response_row_limit_for(provider_code, data_type)

                # Phase 1 preserves the existing full-result row cap.
                # Pagination bounds each HTTP response but does not yet
                # increase the maximum logical query result.
                enforce_dataframe_limits(
                    result.data,
                    max_rows=response_row_limit,
                    max_bytes=int(
                        getattr(config, "API_MAX_DATAFRAME_BYTES", 64 * 1024 * 1024)
                    ),
                )

                page_df, pagination_meta = _paginate_dataframe(
                    result.data,
                    pagination,
                )
                records = _safe_records(page_df)
                enforce_response_limits(
                    records,
                    max_rows=int(pagination_meta["page_size"]),
                    max_bytes=int(
                        getattr(config, "API_MAX_RESPONSE_BYTES", 20 * 1024 * 1024)
                    ),
                )
            except ResponseLimitExceeded as exc:
                if exc.reason == "rows":
                    message = (
                        f"结果共{exc.actual}行，超过单次响应上限{exc.limit}行，"
                        "请按日期或证券代码分段查询并合并结果"
                    )
                elif exc.reason == "dataframe_bytes":
                    message = (
                        f"结果在序列化前占用约{exc.actual}字节，"
                        f"超过内存安全上限{exc.limit}字节，请缩小查询范围"
                    )
                else:
                    message = (
                        f"结果序列化后约{exc.actual}字节，"
                        f"超过单次响应上限{exc.limit}字节，请缩小查询范围"
                    )
                return jsonify({
                    "success": False,
                    "code": 413,
                    "provider": result.provider,
                    "data_type": result.data_type,
                    "items": [],
                    "msg": message,
                    "limit": {
                        "reason": exc.reason,
                        "actual": exc.actual,
                        "maximum": exc.limit,
                    },
                }), 413

            requested_trade_date = result.meta.get("requested_trade_date")
            actual_trade_date = result.meta.get("actual_trade_date")
            fallback_used = bool(result.meta.get("fallback_used"))
            freshness = {
                "requested_trade_date": requested_trade_date,
                "actual_trade_date": actual_trade_date,
                "fallback_used": fallback_used,
                "data_freshness": result.meta.get("data_freshness"),
                "fallback_attempt_count": result.meta.get("fallback_attempt_count", 0),
            }
            source_provider = str(result.meta.get("source_provider") or "")
            is_kaipanla_history = (
                provider_code == "kaipanla"
                and data_type.strip().lower().replace("-", "_").replace("/", "_")
                in {"morning_bidding_history", "bidding_history"}
            )
            if is_kaipanla_history and source_provider == "tushare":
                warning = result.meta.get("warning") or "开盘啦特有竞价字段无法还原"
                msg = f"获取成功，本页{len(records)}条；已降级为 Tushare 部分数据；{warning}"
            elif is_kaipanla_history and source_provider == "kaipanla_snapshot":
                if fallback_used and actual_trade_date:
                    msg = (
                        f"获取成功，本页{len(records)}条；未找到指定日期的开盘啦历史快照，"
                        f"已返回不晚于{requested_trade_date}的最近快照（{actual_trade_date}）"
                    )
                else:
                    msg = f"获取成功，本页{len(records)}条；已返回开盘啦历史快照"
            elif fallback_used and actual_trade_date:
                msg = (
                    f"获取成功，本页{len(records)}条；请求日期{requested_trade_date or '当前日期'}"
                    f"尚未发布，已返回最近可用日期{actual_trade_date}的数据"
                )
            elif result.meta.get("latest_available_enabled") and actual_trade_date:
                msg = f"获取成功，本页{len(records)}条；当前支持的最新数据日期为{actual_trade_date}"
            else:
                msg = f"获取成功，本页{len(records)}条"

            snapshot = {
                "snapshot_id": result.meta.get("snapshot_id"),
                "snapshot_type": result.meta.get("snapshot_type"),
                "snapshot_time": result.meta.get("snapshot_time"),
                "payload_hash": result.meta.get("payload_hash"),
            }
            quality = {
                "data_quality": result.meta.get("data_quality"),
                "schema_version": result.meta.get("schema_version"),
                "warning": result.meta.get("warning"),
            }
            # jsonify performs the final response serialization while the lease is
            # still held, so expensive DataFrame->records->JSON work is bounded.
            return jsonify({
                "success": True,
                "code": 200,
                "provider": result.provider,
                "data_type": result.data_type,
                "items": records,
                "pagination": pagination_meta,
                "source": source,
                "freshness": freshness,
                "snapshot": snapshot,
                "quality": quality,
                "msg": msg,
            })
    except QuerySecurityError as exc:
        response = jsonify({
            "success": False,
            "code": exc.status_code,
            "items": [],
            "error_code": exc.reason,
            "msg": str(exc),
        })
        if exc.status_code == 429 and exc.retry_after:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response, exc.status_code
    except PublicValidationError as exc:
        return jsonify({
            "success": False,
            "code": 400,
            "items": [],
            "msg": str(exc),
        }), 400
    except KeyError:
        return jsonify({
            "success": False,
            "code": 404,
            "items": [],
            "msg": "请求资源不存在",
        }), 404
    except ValueError:
        return jsonify({
            "success": False,
            "code": 400,
            "items": [],
            "msg": "请求参数无效",
        }), 400


@market_data_bp.get("/providers")
@require_scope("tushare:read")
def providers():
    include_health = request.args.get("health") in {"1", "true", "True"}
    return jsonify({
        "success": True,
        "code": 200,
        "data": list_providers(include_health=include_health),
        "msg": "数据源列表",
    })


@market_data_bp.get("/cache/stats")
@require_scope("admin:sync")
def market_cache_stats():
    """Return provider-neutral market-data cache statistics and policy."""
    return jsonify({"success": True, "code": 200, "data": cache_stats(), "msg": "缓存状态"})


@market_data_bp.post("/cache/clear")
@require_scope("admin:sync")
def market_cache_clear():
    """Clear all market-data caches through the unified route."""
    actor = dict(getattr(g, "current_user", {}) or {})
    try:
        before = cache_stats()
        clear_cache()
        after = cache_stats()
        record_operation(
            actor_type="admin", actor_id=actor.get("id"),
            actor_name=str(actor.get("username") or "admin-api"), target_user=None,
            action_category="system_maintenance", action_code="admin.cache_clear",
            action_name="清空行情缓存", success=True, status_code=200,
            before_data=before, after_data=after, request_data={"scope": "all"},
        )
        return jsonify({"success": True, "code": 200, "data": after, "msg": "缓存已清空"})
    except Exception as exc:
        record_operation(
            actor_type="admin", actor_id=actor.get("id"),
            actor_name=str(actor.get("username") or "admin-api"), target_user=None,
            action_category="system_maintenance", action_code="admin.cache_clear",
            action_name="清空行情缓存", success=False, status_code=500,
            error_code="cache_clear_failed", error_message=str(exc),
            request_data={"scope": "all"},
        )
        raise


@market_data_bp.route("/cache/query/<provider_code>/<path:data_type>", methods=["GET", "POST"])
@require_scope("admin:sync")
def query_provider_without_cache(provider_code: str, data_type: str):
    """Admin-only acceptance-test route that forces a real upstream call.

    Production users continue to use the normal cached route.  A successful
    fresh result is still written into the cache, so running the test does not
    leave the website cold.
    """
    return _query_response(provider_code, data_type, bypass_cache=True)


@market_data_bp.get("/<provider_code>/catalog")
@require_scope(_scope_resolver)
def provider_catalog(provider_code: str):
    try:
        rows = get_provider_catalog(provider_code)
    except KeyError as exc:
        return jsonify({"success": False, "code": 404, "data": [], "msg": str(exc)}), 404
    return jsonify({"success": True, "code": 200, "count": len(rows), "data": rows, "msg": "数据源接口目录"})


@market_data_bp.get("/<provider_code>/health")
@require_scope(_scope_resolver)
def provider_health(provider_code: str):
    try:
        data = get_provider_health(provider_code)
    except KeyError as exc:
        return jsonify({"success": False, "code": 404, "data": {}, "msg": str(exc)}), 404
    status = 200 if data.get("available") else 503
    return jsonify({
        "success": status == 200,
        "code": status,
        "data": data,
        "msg": "数据源正常" if status == 200 else "数据源不可用",
    }), status


@market_data_bp.route("/<provider_code>/<path:data_type>", methods=["GET", "POST"])
@require_scope(_scope_resolver)
def query_provider(provider_code: str, data_type: str):
    return _query_response(provider_code, data_type, bypass_cache=False)
