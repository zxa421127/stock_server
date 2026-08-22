# -*- coding: utf-8 -*-
"""开盘啦早盘集合竞价接口；保留所有原始数组列。"""
from __future__ import annotations

from typing import Any
import pandas as pd
import config
from . import call_kaipanla_api, call_kaipanla_api_with_raw

BIDDING_FIELD_MAPPING = {
    0: "股票代码", 1: "股票名称", 2: "当前价格", 3: "实时涨幅",
    4: "涨停委买额", 5: "竞价涨幅", 6: "竞价净额", 7: "竞价换手",
    8: "竞价成交额", 9: "20分后涨停委买", 10: "竞价匹配额",
    11: "板块", 12: "实际流通", 13: "主力净额", 14: "主力买入",
    15: "主力卖出额原始值", 16: "连板",
}


def _build_request_params(order=1, st=200, index=0, pid_type=0, b_type=4, user_id=None, token=None):
    user_id = user_id or config.KAIPANLA_USER_ID
    token = token or config.KAIPANLA_TOKEN
    params = {"Order":order,"a":"MorningBiddingList","st":st,"c":"HomeDingPan","Index":index,"PidType":pid_type,"Type":b_type}
    if user_id: params["UserID"] = user_id
    if token: params["Token"] = token
    return params


def _map_bidding_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Duplicate semantic aliases while preserving raw numeric keys as strings."""
    result = df.copy()
    result.columns = [str(c) if isinstance(c, int) or str(c).isdigit() else c for c in result.columns]
    for index, name in BIDDING_FIELD_MAPPING.items():
        raw = str(index)
        if raw not in result.columns:
            result[raw] = None
        if name not in result.columns:
            result[name] = result[raw]
        else:
            result[name] = result[name].where(result[name].notna(), result[raw])
    return result


def get_morning_bidding_page_raw(
    order: int = 1, st: int = 200, index: int = 0, pid_type: int = 0, b_type: int = 4,
    user_id: str | None = None, token: str | None = None,
) -> tuple[pd.DataFrame, Any | None, str | None, dict[str, Any]]:
    params = _build_request_params(order, st, index, pid_type, b_type, user_id, token)
    path = "&".join(f"{k}={v}" for k, v in params.items())
    df, raw, error = call_kaipanla_api_with_raw(path)
    if error is None and df is not None and not df.empty:
        df = _map_bidding_fields(df)
    public = {"order":order,"st":st,"index":index,"pid_type":pid_type,"b_type":b_type}
    return df, raw, error, public


def get_morning_bidding(
    order: int = 1, st: int = 200, index: int = 0, pid_type: int = 0, b_type: int = 4,
    user_id: str | None = None, token: str | None = None,
) -> tuple[pd.DataFrame, str | None]:
    params = _build_request_params(order, st, index, pid_type, b_type, user_id, token)
    path = "&".join(f"{k}={v}" for k, v in params.items())
    df, error = call_kaipanla_api(path)
    if error is None and df is not None and not df.empty:
        df = _map_bidding_fields(df)
    return df, error
