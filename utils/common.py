# -*- coding: utf-8 -*-
"""Small shared response and DataFrame conversion helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import jsonify


def _convert_keys_to_str(data: Any):
    """Recursively convert mapping keys to strings for safe JSON encoding."""
    if isinstance(data, dict):
        return {str(key): _convert_keys_to_str(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_convert_keys_to_str(item) for item in data]
    return data


def get_today_date() -> str:
    return datetime.now().strftime("%Y%m%d")


def df_to_list(df) -> list[dict]:
    if df is None or getattr(df, "empty", True):
        return []
    return _convert_keys_to_str(df.to_dict("records"))


def make_resp(success: bool, data=None, msg: str = ""):
    safe_data = _convert_keys_to_str(data) if data is not None else []
    return jsonify({"success": success, "data": safe_data, "msg": msg})
