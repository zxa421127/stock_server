# -*- coding: utf-8 -*-
"""开盘啦（龙虎榜VIP）上游请求封装。"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional, Tuple
from urllib.parse import parse_qs, urlencode

import pandas as pd
import requests

from config import KAIPANLA_DEVICE_ID
from services.runtime_stats import record_kaipanla_call

BASE_URL = "https://apphwhq.longhuvip.com/w1/api/index.php"
DEFAULT_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 14; V2178A Build/UP1A.231005.007)",
}


@dataclass(frozen=True, slots=True)
class KaipanlaBusinessStatus:
    """Normalized business status for multiple Kaipanla response schemas."""

    success: bool
    protocol: str
    code: str
    message: str | None = None


def _normalized_code(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value).strip()


def _message_from_payload(data: dict[str, Any]) -> str | None:
    for key in ("msg", "message", "errmsg", "err_msg", "error"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def evaluate_kaipanla_business_status(data: Any) -> KaipanlaBusinessStatus:
    """Evaluate Kaipanla business success without depending on one schema only.

    Known schemas:
    - legacy: ``ret=0`` with optional ``msg``
    - current: ``status=1`` and ``errcode=0``
    - compatibility fallback: a list payload under a known data key
    """
    if not isinstance(data, dict):
        return KaipanlaBusinessStatus(
            success=False,
            protocol="invalid_payload",
            code=type(data).__name__,
            message="开盘啦返回内容不是JSON对象",
        )

    message = _message_from_payload(data)
    if "ret" in data:
        ret = _normalized_code(data.get("ret"))
        success = ret == "0"
        return KaipanlaBusinessStatus(
            success=success,
            protocol="ret",
            code=f"ret={ret or '<empty>'}",
            message=message,
        )

    if "errcode" in data or "status" in data:
        errcode_present = "errcode" in data
        status_present = "status" in data
        errcode = _normalized_code(data.get("errcode"))
        status = _normalized_code(data.get("status"))
        errcode_ok = not errcode_present or errcode == "0"
        status_ok = not status_present or status.lower() in {"1", "true"}
        success = errcode_ok and status_ok
        return KaipanlaBusinessStatus(
            success=success,
            protocol="status_errcode",
            code=(
                f"status={status or '<missing>'};"
                f"errcode={errcode or '<missing>'}"
            ),
            message=message,
        )

    for key in ("info", "list", "data", "Data"):
        if isinstance(data.get(key), list):
            return KaipanlaBusinessStatus(
                success=True,
                protocol="implicit_list",
                code=f"list_key={key}",
                message=message,
            )

    return KaipanlaBusinessStatus(
        success=False,
        protocol="unknown",
        code="no_status_or_list",
        message=message or "开盘啦返回中缺少可识别的业务状态和数据列表",
    )


def _safe_error_text(value: object, params: dict | None = None) -> str:
    text = str(value)
    secrets = [KAIPANLA_DEVICE_ID]
    if params:
        secrets.extend(str(params.get(key) or "") for key in ("Token", "UserID", "DeviceID"))
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _extract_dataframe(data: Any) -> pd.DataFrame:
    list_data = None
    if isinstance(data, dict):
        for key in ("info", "list", "data", "Data"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                list_data = candidate
                break
    if list_data is not None:
        return pd.DataFrame(list_data)
    return pd.DataFrame([data]) if isinstance(data, dict) else pd.DataFrame()


def _call_kaipanla_api_internal(
    api_path: str,
    params: dict | None = None,
    method: str = "POST",
) -> tuple[pd.DataFrame, Any | None, Optional[str]]:
    start_time = time.time()
    final_params: dict[str, Any] = {}
    try:
        if not KAIPANLA_DEVICE_ID:
            return pd.DataFrame(), None, "KAIPANLA_DEVICE_ID 未配置"

        default_params = {
            "PhoneOSNew": "1",
            "DeviceID": KAIPANLA_DEVICE_ID,
            "VerSion": "5.20.0.2",
            "apiv": "w41",
        }
        path_params = {key: values[0] for key, values in parse_qs(api_path).items()}
        final_params.update(default_params)
        final_params.update(path_params)
        final_params.update(params or {})
        url = f"{BASE_URL}?{urlencode(final_params)}"
        api_name = path_params.get("a", "unknown")
        logging.info("[开盘啦.%s] 开始调用 | 方法:%s", api_name, method)

        if method.upper() == "POST":
            response = requests.post(url, headers=DEFAULT_HEADERS, timeout=10)
        else:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        cost_time = round((time.time() - start_time) * 1000, 2)

        business_status = evaluate_kaipanla_business_status(data)
        info_list = data.get("info", []) if isinstance(data, dict) else []
        info_count = len(info_list) if isinstance(info_list, list) else "N/A"
        logging.info(
            "[开盘啦.%s] 业务状态: protocol=%s code=%s info数量=%s",
            api_name,
            business_status.protocol,
            business_status.code,
            info_count,
        )
        if not business_status.success:
            error_msg = business_status.message or f"开盘啦业务状态失败：{business_status.code}"
            safe_error = _safe_error_text(error_msg, final_params or params)
            logging.error(
                "[开盘啦.%s] 调用失败 | 耗时:%sms | protocol=%s | code=%s | 错误:%s",
                api_name,
                cost_time,
                business_status.protocol,
                business_status.code,
                safe_error,
            )
            record_kaipanla_call(False)
            return pd.DataFrame(), data, safe_error

        df = _extract_dataframe(data)
        if df.empty:
            logging.warning("[开盘啦.%s] 调用成功但无数据列表 | 耗时:%sms", api_name, cost_time)
        else:
            logging.info("[开盘啦.%s] 调用成功 | 耗时:%sms | 返回%s条数据", api_name, cost_time, len(df))
        record_kaipanla_call(True)
        return df, data, None

    except requests.exceptions.Timeout:
        cost_time = round((time.time() - start_time) * 1000, 2)
        logging.error("[开盘啦] 请求超时 | 耗时:%sms", cost_time)
        record_kaipanla_call(False)
        return pd.DataFrame(), None, "请求超时"
    except requests.exceptions.RequestException as exc:
        cost_time = round((time.time() - start_time) * 1000, 2)
        safe_error = _safe_error_text(exc, final_params or params)
        logging.error("[开盘啦] 请求失败 | 耗时:%sms | 错误:%s", cost_time, safe_error)
        record_kaipanla_call(False)
        return pd.DataFrame(), None, f"请求失败: {safe_error}"
    except Exception as exc:
        cost_time = round((time.time() - start_time) * 1000, 2)
        safe_error = _safe_error_text(exc, final_params or params)
        logging.error("[开盘啦] 未知错误 | 耗时:%sms | 错误:%s", cost_time, safe_error)
        record_kaipanla_call(False)
        return pd.DataFrame(), None, f"未知错误: {safe_error}"


def call_kaipanla_api(
    api_path: str,
    params: dict = None,
    method: str = "POST",
) -> Tuple[pd.DataFrame, Optional[str]]:
    """Backward-compatible call returning only DataFrame and error."""
    df, _raw, error = _call_kaipanla_api_internal(api_path, params=params, method=method)
    return df, error


def call_kaipanla_api_with_raw(
    api_path: str,
    params: dict = None,
    method: str = "POST",
) -> tuple[pd.DataFrame, Any | None, Optional[str]]:
    """Call Kaipanla and also return the exact decoded JSON payload."""
    return _call_kaipanla_api_internal(api_path, params=params, method=method)
