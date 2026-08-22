# -*- coding: utf-8 -*-
"""Normalize Kaipanla raw bidding rows into the public v2 business schema."""
from __future__ import annotations

import logging
import math
import re
from typing import Any

import pandas as pd

from integrations.market_data.kaipanla.schema import (
    SCHEMA_VERSION,
    SNAPSHOT_TYPES,
    STANDARD_BIDDING_COLUMNS,
)

_CODE_RE = re.compile(r"(?P<symbol>\d{6})")


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _text(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return None if not text or text.lower() in {"nan", "none", "null", "<na>"} else text


def _number(
    value: Any,
    *,
    field_name: str = "",
    stock_code: str | None = None,
) -> float | int | None:
    if _is_missing(value) or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        logging.warning(
            "[开盘啦竞价] 字段数值转换失败: field=%s stock_code=%s value_type=%s",
            field_name or "unknown",
            stock_code or "",
            type(value).__name__,
        )
        return None
    if not math.isfinite(number):
        logging.warning(
            "[开盘啦竞价] 字段数值转换失败: field=%s stock_code=%s reason=non_finite",
            field_name or "unknown",
            stock_code or "",
        )
        return None
    return int(number) if number.is_integer() else number


def _first(row: pd.Series, *names: Any) -> Any:
    for name in names:
        if name in row.index and not _is_missing(row[name]) and str(row[name]).strip() != "":
            return row[name]
    return None


def _symbol(value: Any) -> str | None:
    text = _text(value)
    match = _CODE_RE.search(text or "")
    return match.group("symbol") if match else None


def _guess_ts_code(symbol: str | None) -> str | None:
    if not symbol:
        return None
    suffix = (
        "BJ"
        if symbol.startswith(("4", "8", "9"))
        else "SH"
        if symbol.startswith(("5", "6", "7"))
        else "SZ"
    )
    return f"{symbol}.{suffix}"


def parse_limit_up_days(value: Any) -> int | None:
    text = _text(value)
    if not text:
        return None
    if "首板" in text:
        return 1
    match = re.search(r"(\d+)天(\d+)板", text)
    if match:
        return int(match.group(2))
    match = re.search(r"(?:昨)?(\d+)连板", text)
    if match:
        return int(match.group(1))
    return int(text) if text.isdigit() else None


def _records_by_symbol(df: pd.DataFrame | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        symbol = _symbol(_first(row, "symbol", "ts_code", "code", "股票代码"))
        if symbol:
            result[symbol] = row.to_dict()
    return result


def _coalesce_record(record: dict[str, Any] | None, *keys: str) -> Any:
    record = record or {}
    for key in keys:
        if key in record and not _is_missing(record[key]) and str(record[key]).strip() != "":
            return record[key]
    return None


def _validate_snapshot_type(value: Any) -> str:
    text = str(value or "auction").strip().lower()
    if text not in SNAPSHOT_TYPES:
        raise ValueError("snapshot_type 只允许 auction、post_open 或 close")
    return text


def _log_main_relation(
    net: float | int | None,
    buy: float | int | None,
    sell_amount: float | int | None,
    *,
    stock_code: str | None,
) -> None:
    if net is None or buy is None or sell_amount is None:
        return
    tolerance = max(1.0, abs(net) * 1e-6, abs(buy) * 1e-6, abs(sell_amount) * 1e-6)
    if abs(net - (buy - sell_amount)) > tolerance:
        logging.warning(
            "[开盘啦竞价] 主力资金关系校验失败: stock_code=%s net=%s buy=%s sell_amount=%s",
            stock_code or "",
            net,
            buy,
            sell_amount,
        )


def normalize_kaipanla_bidding(
    raw_df: pd.DataFrame | None,
    *,
    trade_date: str | None = None,
    snapshot_type: str = "auction",
    snapshot_time: str | None = None,
    snapshot_id: str | None = None,
    stock_basic_df: pd.DataFrame | None = None,
    bak_basic_df: pd.DataFrame | None = None,
    historical: bool = False,
    source_provider: str = "kaipanla",
    source_api: str = "morning_bidding",
    data_quality: str = "complete",
) -> pd.DataFrame:
    """Return only formal business fields; raw evidence remains in raw_payload."""
    snapshot_type = _validate_snapshot_type(snapshot_type)
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=STANDARD_BIDDING_COLUMNS)

    raw = raw_df.copy()
    raw.columns = [str(column) if isinstance(column, int) or str(column).isdigit() else column for column in raw.columns]
    stock_map = _records_by_symbol(stock_basic_df)
    bak_map = _records_by_symbol(bak_basic_df)
    rows: list[dict[str, Any]] = []

    for _, input_row in raw.iterrows():
        symbol = _symbol(_first(input_row, "股票代码", "0", "ts_code", "symbol"))
        stock = stock_map.get(symbol or "", {})
        bak = bak_map.get(symbol or "", {})
        stock_ts = _text(_coalesce_record(stock, "ts_code"))
        bak_ts = _text(_coalesce_record(bak, "ts_code"))
        ts_code = stock_ts or bak_ts or _text(_first(input_row, "ts_code")) or _guess_ts_code(symbol)

        kpl_name = _text(_first(input_row, "股票名称", "1"))
        stock_name = _text(_coalesce_record(stock, "name"))
        bak_name = _text(_coalesce_record(bak, "name"))
        name = kpl_name or (bak_name if historical else None) or stock_name
        industry = _text(_coalesce_record(stock, "industry")) or _text(_coalesce_record(bak, "industry"))

        auction_price = _number(
            _first(input_row, "当前价格", "2", "price", "auction_price"),
            field_name="2/当前价格",
            stock_code=symbol,
        )
        realtime_pct = _number(
            _first(input_row, "实时涨幅", "3", "realtime_pct"),
            field_name="3/实时涨幅",
            stock_code=symbol,
        )
        limit_buy_amount = _number(
            _first(input_row, "涨停委买额", "4", "limit_buy_amount"),
            field_name="4/涨停委买额",
            stock_code=symbol,
        )
        auction_pct = _number(
            _first(input_row, "竞价涨幅", "5", "pct_chg", "auction_pct"),
            field_name="5/竞价涨幅",
            stock_code=symbol,
        )
        auction_net_amount = _number(
            _first(input_row, "竞价净额", "6", "auction_net_amount"),
            field_name="6/竞价净额",
            stock_code=symbol,
        )
        auction_turnover = _number(
            _first(input_row, "竞价换手", "7", "turnover_rate", "auction_turnover"),
            field_name="7/竞价换手",
            stock_code=symbol,
        )
        auction_amount = _number(
            _first(input_row, "竞价成交额", "8", "amount", "auction_amount"),
            field_name="8/竞价成交额",
            stock_code=symbol,
        )
        limit_buy_after = _number(
            _first(input_row, "20分后涨停委买", "9", "limit_buy_amount_after_0920"),
            field_name="9/20分后涨停委买",
            stock_code=symbol,
        )
        auction_match_amount = _number(
            _first(input_row, "竞价匹配额", "10", "auction_match_amount"),
            field_name="10/竞价匹配额",
            stock_code=symbol,
        )
        float_market_value = _number(
            _first(input_row, "实际流通", "12", "float_market_value"),
            field_name="12/实际流通",
            stock_code=symbol,
        )
        main_net_amount = _number(
            _first(input_row, "主力净额", "13", "main_net_amount"),
            field_name="13/主力净额",
            stock_code=symbol,
        )
        main_buy_amount = _number(
            _first(input_row, "主力买入", "14", "main_buy_amount"),
            field_name="14/主力买入",
            stock_code=symbol,
        )
        signed_sell = _number(
            _first(input_row, "主力卖出额原始值", "15", "main_sell_amount"),
            field_name="15/主力卖出额",
            stock_code=symbol,
        )
        main_sell_amount = abs(signed_sell) if signed_sell is not None else None
        _log_main_relation(
            main_net_amount,
            main_buy_amount,
            main_sell_amount,
            stock_code=symbol,
        )

        pre_close = _number(
            _first(input_row, "pre_close", "昨收", "昨收价"),
            field_name="昨收",
            stock_code=symbol,
        )
        if auction_pct is None and auction_price is not None and pre_close and pre_close > 0:
            auction_pct = (auction_price / pre_close - 1) * 100

        sector = _text(_first(input_row, "板块", "11", "sector"))
        limit_text = _text(_first(input_row, "连板", "16"))
        limit_up_days = parse_limit_up_days(limit_text)

        row = {
            "股票代码": symbol,
            "股票名称": name,
            "当前价格": auction_price,
            "实时涨幅": realtime_pct,
            "竞价涨幅": auction_pct,
            "涨停委买额": limit_buy_amount,
            "20分后涨停委买": limit_buy_after,
            "竞价匹配额": auction_match_amount,
            "竞价成交额": auction_amount,
            "竞价净额": auction_net_amount,
            "竞价换手": auction_turnover,
            "主力净额": main_net_amount,
            "主力买入": main_buy_amount,
            "主力卖出额": main_sell_amount,
            "实际流通": float_market_value,
            "板块": sector,
            "行业": industry,
            "连板": limit_text,
            "连板高度": limit_up_days,
            "ts_code": ts_code,
            "name": name,
            "trade_date": trade_date or _text(_first(input_row, "trade_date")),
            "snapshot_type": snapshot_type,
            "snapshot_time": snapshot_time,
            "snapshot_id": snapshot_id,
            "auction_price": auction_price,
            "auction_pct": auction_pct,
            "realtime_pct": realtime_pct,
            "limit_buy_amount": limit_buy_amount,
            "limit_buy_amount_after_0920": limit_buy_after,
            "auction_net_amount": auction_net_amount,
            "auction_match_amount": auction_match_amount,
            "auction_amount": auction_amount,
            "auction_turnover": auction_turnover,
            "main_net_amount": main_net_amount,
            "main_buy_amount": main_buy_amount,
            "main_sell_amount": main_sell_amount,
            "float_market_value": float_market_value,
            "sector": sector,
            "limit_up_days": limit_up_days,
            "source_provider": source_provider,
            "source_api": source_api,
            "data_quality": data_quality,
            "schema_version": SCHEMA_VERSION,
        }
        rows.append(row)

    return pd.DataFrame(rows, columns=STANDARD_BIDDING_COLUMNS)
