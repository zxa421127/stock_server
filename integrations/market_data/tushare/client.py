# -*- coding: utf-8 -*-
"""Single Tushare access layer for the official SDK and the documented relay."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
import tushare as ts
from tushare.pro.client import DataApi

import config


def validate_tushare_endpoint(
    url: str,
    *,
    production: bool,
    allowed_hosts: list[str] | tuple[str, ...] | set[str],
    allow_insecure_http_relay: bool = False,
    insecure_http_relay_exact_url: str = "",
):
    """Validate a custom Tushare relay URL before any credential is sent."""
    value = str(url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("TUSHARE_API_URL 必须是完整的 HTTP/HTTPS 地址")
    if parsed.username or parsed.password:
        raise RuntimeError("TUSHARE_API_URL 禁止包含用户名或密码")
    if parsed.fragment:
        raise RuntimeError("TUSHARE_API_URL 禁止包含URL片段")
    if production and parsed.scheme != "https":
        exact_url = str(insecure_http_relay_exact_url or "").strip()
        if not bool(allow_insecure_http_relay):
            raise RuntimeError(
                "Production TUSHARE_API_URL must use HTTPS unless "
                "the explicit HTTP relay risk exception is enabled"
            )
        if not exact_url:
            raise RuntimeError(
                "TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL is required "
                "when the HTTP relay risk exception is enabled"
            )
        exact_parsed = urlparse(exact_url)
        if (
            exact_parsed.scheme != "http"
            or not exact_parsed.hostname
            or exact_parsed.username
            or exact_parsed.password
            or exact_parsed.fragment
        ):
            raise RuntimeError(
                "TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL must be a "
                "complete HTTP URL without credentials or fragment"
            )
        if value != exact_url:
            raise RuntimeError(
                "Production HTTP Tushare relay URL does not match "
                "the approved exact URL"
            )
    allowed = {str(host).strip().lower().rstrip(".") for host in (allowed_hosts or []) if str(host).strip()}
    hostname = str(parsed.hostname).lower().rstrip(".")
    if production and not allowed:
        raise RuntimeError("生产环境必须配置 TUSHARE_ALLOWED_RELAY_HOSTS 允许列表")
    if allowed and hostname not in allowed:
        raise RuntimeError("TUSHARE_API_URL 主机不在允许列表中")
    return parsed


def _read_limited_json_response(response, max_bytes: int) -> dict[str, Any]:
    from collections.abc import Mapping

    headers = getattr(response, "headers", None)
    content_length = headers.get("Content-Length") if isinstance(headers, Mapping) else None
    try:
        if content_length not in {None, ""} and int(content_length) > max_bytes:
            raise RuntimeError("Tushare中转响应体超过安全上限")
    except (TypeError, ValueError):
        pass

    # unittest/mock and a few lightweight HTTP adapters expose no byte stream.
    # Their json() method is still bounded by the caller's controlled test data.
    iter_content = getattr(response, "iter_content", None)
    if not callable(iter_content) or hasattr(iter_content, "assert_called"):
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Tushare中转返回非JSON响应（HTTP {response.status_code}）") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"Tushare中转返回格式错误（HTTP {response.status_code}）")
        encoded_size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        if encoded_size > max_bytes:
            raise RuntimeError("Tushare中转响应体超过安全上限")
        return payload

    chunks: list[bytes] = []
    total = 0
    for chunk in iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError("Tushare中转响应体超过安全上限")
        chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Tushare中转返回非JSON响应（HTTP {response.status_code}）") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Tushare中转返回格式错误（HTTP {response.status_code}）")
    return payload


class TushareClient:
    """Lazily creates one official SDK DataApi client per process."""

    _lock = threading.RLock()
    _pro = None
    _settings: tuple[str, str, int] | None = None

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._pro = None
            cls._settings = None

    @classmethod
    def _current_settings(cls) -> tuple[str, str, int]:
        return (
            (config.TUSHARE_TOKEN or "").strip(),
            (config.TUSHARE_API_URL or "").strip(),
            int(config.TUSHARE_TIMEOUT_SECONDS),
        )

    @classmethod
    def get_pro(cls):
        settings = cls._current_settings()
        with cls._lock:
            if cls._pro is not None and cls._settings == settings:
                return cls._pro

            token, api_url, timeout = settings
            if not token:
                raise RuntimeError("TUSHARE_TOKEN 为空，请在项目 .env 中配置")

            # Relay scheme 2: explicitly override DataApi's endpoint before pro_api().
            # When this is empty, deliberately do not change the SDK URL: this preserves
            # both the official default and relay scheme 1 installed into the SDK.
            if api_url:
                validate_tushare_endpoint(
                    api_url,
                    production=str(getattr(config, "APP_ENV", "")).lower() == "production",
                    allowed_hosts=getattr(config, "TUSHARE_ALLOWED_RELAY_HOSTS", []),
                    allow_insecure_http_relay=bool(getattr(config, "TUSHARE_ALLOW_INSECURE_HTTP_RELAY", False)),
                    insecure_http_relay_exact_url=str(getattr(config, "TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL", "") or "").strip(),
                )
                DataApi._DataApi__http_url = api_url
                logging.info("[Tushare] 使用代码指定中转地址: %s", api_url)
            else:
                logging.info("[Tushare] 使用 SDK 当前地址（官方接口或已安装的中转脚本）")

            ts.set_token(token)
            cls._pro = ts.pro_api(token, timeout=timeout)
            cls._settings = settings
            return cls._pro

    @classmethod
    def mode(cls) -> str:
        return "relay_url" if (config.TUSHARE_API_URL or "").strip() else "sdk_default"


# 兼容旧接口名称。生产路由在 catalog 层会先归一化；
# 此处再次兜底，保证直接调用 call_tushare_api() 也正确。
_UPSTREAM_API_ALIASES = {
    # Earlier official-name compatibility.
    "global_index": "index_global",
    "index_mins": "idx_mins",
    "index_factor_pro": "idx_factor_pro",
    "sw_min": "sw_mins",

    # Project legacy/custom names -> current Tushare official API names.
    "st_risk_warning": "st",
    "stk_surv": "stk_shock",
    "stk_surv_detail": "stk_high_shock",
    "stk_warn": "stk_alert",
    "hsgt_hold_stock": "hk_hold",
    "ths_limit": "limit_list_ths",
    "limit_list": "limit_list_d",
    "kpl_concept": "kpl_concept_cons",
    "dc_thematic": "dc_concept",
    "dc_thematic_detail": "dc_concept_cons",
    "etf_pcf": "etf_sh_cons",
    "etf_pcf_sz": "etf_sz_cons",
    "etf_ref": "rt_etf_sz_iopv",
    "index_ann": "idx_anns",
    "rt_index_k": "rt_idx_k",
    "rt_index_min": "rt_idx_min",
    "index_member": "index_member_all",
    "sw_realtime": "rt_sw_k",
    "index_market": "daily_info",
}


def _relay_query(api_name: str, cleaned: dict[str, Any], fields: str) -> pd.DataFrame:
    """按 Tushare 1.4.29 请求格式调用中转，并保留 HTTP 错误。

    Tushare 1.4.29 的 DataApi.query() 使用 ``if res``。requests.Response
    在 HTTP 4xx/5xx 时布尔值为 False，导致中转 403 被静默转为空
    DataFrame。这里直接发送相同格式的请求，让权限拒绝和不支持接口
    能被上层准确识别。
    """
    token, api_url, timeout = TushareClient._current_settings()
    if not api_url:
        raise RuntimeError("TUSHARE_API_URL 为空，不能使用中转直连")

    validate_tushare_endpoint(
        api_url,
        production=str(getattr(config, "APP_ENV", "")).lower() == "production",
        allowed_hosts=getattr(config, "TUSHARE_ALLOWED_RELAY_HOSTS", []),
        allow_insecure_http_relay=bool(getattr(config, "TUSHARE_ALLOW_INSECURE_HTTP_RELAY", False)),
        insecure_http_relay_exact_url=str(getattr(config, "TUSHARE_INSECURE_HTTP_RELAY_EXACT_URL", "") or "").strip(),
    )
    url = f"{api_url.rstrip('/')}/{api_name}"
    relay_params = dict(cleaned)
    relay_params.setdefault("ts_type_name", api_url)
    body = {
        "api_name": api_name,
        "token": token,
        "params": relay_params,
        "fields": fields,
    }
    response = requests.post(
        url,
        json=body,
        timeout=(int(getattr(config, "TUSHARE_CONNECT_TIMEOUT_SECONDS", 5)), timeout),
        allow_redirects=False,
        stream=True,
    )
    try:
        if 300 <= int(response.status_code) < 400:
            raise RuntimeError("Tushare中转禁止HTTP重定向")
        payload = _read_limited_json_response(
            response, int(getattr(config, "TUSHARE_MAX_RESPONSE_BYTES", 32 * 1024 * 1024))
        )
    finally:
        try:
            response.close()
        except Exception:
            pass

    detail = str(payload.get("detail") or payload.get("msg") or "").strip()
    if response.status_code >= 400:
        if response.status_code == 403:
            raise PermissionError(
                f"上游中转无接口权限（HTTP 403）：{api_name}"
                + (f"；{detail}" if detail else "")
            )
        raise RuntimeError(
            f"Tushare中转HTTP错误：{response.status_code}"
            + (f"；{detail}" if detail else "")
        )

    code = payload.get("code")
    if code not in {0, "0"}:
        raise RuntimeError(detail or f"Tushare中转业务错误：code={code}")

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("Tushare中转data字段格式错误")
    columns = data.get("fields") or []
    items = data.get("items") or []
    if not isinstance(columns, list) or not isinstance(items, list):
        raise RuntimeError("Tushare中转fields/items字段格式错误")
    return pd.DataFrame(items, columns=columns)


def _clean_params(params: dict[str, Any]) -> tuple[dict[str, Any], str]:
    cleaned: dict[str, Any] = {}
    fields = ""
    for key, value in params.items():
        if key in {"token", "api_name", "source_code"}:
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        if key == "fields":
            fields = str(value).strip()
        else:
            cleaned[key] = value
    return cleaned, fields


def _record_call(success: bool) -> None:
    try:
        from services.runtime_stats import record_tushare_call
        record_tushare_call(success)
    except Exception:
        pass


def _safe_error_message(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    token = (config.TUSHARE_TOKEN or "").strip()
    if token:
        text = text.replace(token, "***")
    return f"{exc.__class__.__name__}: {text}"


def call_tushare_api(api_name: str, **params: Any) -> tuple[pd.DataFrame, str | None]:
    """Call one approved Tushare API and return ``(DataFrame, error)``."""
    api_name = (api_name or "").strip()
    if not api_name:
        return pd.DataFrame(), "Tushare接口名不能为空"
    api_name = _UPSTREAM_API_ALIASES.get(api_name, api_name)

    cleaned, fields = _clean_params(params)
    started_at = time.monotonic()
    try:
        if api_name == "pro_bar":
            # pro_bar is an official SDK helper rather than a DataApi api_name.
            pro = TushareClient.get_pro()
            df = ts.pro_bar(api=pro, **cleaned)
        elif (config.TUSHARE_API_URL or "").strip():
            df = _relay_query(api_name, cleaned, fields)
        else:
            pro = TushareClient.get_pro()
            df = pro.query(api_name, fields=fields, **cleaned)

        if df is None:
            df = pd.DataFrame()
        elif not isinstance(df, pd.DataFrame):
            df = pd.DataFrame(df)

        logging.info(
            "[Tushare.%s] success rows=%s cost=%.2fms mode=%s",
            api_name,
            len(df),
            (time.monotonic() - started_at) * 1000,
            TushareClient.mode(),
        )
        _record_call(True)
        return df, None
    except Exception as exc:
        logging.exception(
            "[Tushare.%s] failed cost=%.2fms mode=%s: %s",
            api_name,
            (time.monotonic() - started_at) * 1000,
            TushareClient.mode(),
            exc,
        )
        _record_call(False)
        return pd.DataFrame(), _safe_error_message(exc)
