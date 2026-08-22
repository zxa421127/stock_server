# -*- coding: utf-8 -*-
"""MiniQMT/XtQuant market-data provider.

Only read-only market-data operations are exposed here. Trading is intentionally
kept out of this server layer.
"""
from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

import config
from integrations.market_data.base import MarketDataProvider, ProviderResponse
from integrations.market_data.miniqmt.adapter import full_tick_to_frame, market_data_to_frame
from integrations.market_data.miniqmt.client import MiniQmtClient


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


class MiniQmtProvider(MarketDataProvider):
    code = "miniqmt"
    display_name = "MiniQMT / XtQuant"
    _PERIOD_ALIASES = {
        "daily": "1d",
        "day": "1d",
        "minute": "1m",
        "min": "1m",
        "tick": "tick",
    }

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"provider": self.code, "api_name": "history", "title": "历史行情", "realtime": False},
            {"provider": self.code, "api_name": "quote", "title": "最新行情快照", "realtime": True},
            {"provider": self.code, "api_name": "download_history", "title": "增量下载历史行情", "realtime": False},
        ]

    def health_check(self) -> dict[str, Any]:
        result = MiniQmtClient.health()
        result["enabled"] = bool(getattr(config, "MINIQMT_ENABLED", False))
        return result

    @staticmethod
    def _symbols(params: Mapping[str, Any]) -> list[str]:
        raw = params.get("symbols") or params.get("symbol") or params.get("stock_list") or []
        if isinstance(raw, str):
            symbols = [item.strip() for item in raw.split(",") if item.strip()]
        else:
            symbols = [str(item).strip() for item in raw if str(item).strip()]
        max_symbols = MiniQmtClient.max_symbols()
        if not symbols:
            raise ValueError("MiniQMT请求必须提供 symbol 或 symbols")
        if len(symbols) > max_symbols:
            raise ValueError(f"单次最多允许 {max_symbols} 个证券代码")
        return symbols

    def query(self, data_type: str, params: Mapping[str, Any]) -> ProviderResponse:
        normalized = self.normalize_data_type(data_type)
        try:
            symbols = self._symbols(params)
            if normalized in {"quote", "full_tick", "realtime"}:
                payload = MiniQmtClient.call("get_full_tick", symbols)
                return ProviderResponse(data=full_tick_to_frame(payload), meta={"api_name": "quote"})

            if normalized == "download_history":
                period = str(params.get("period") or "1d")
                start_time = str(params.get("start_time") or "")
                end_time = str(params.get("end_time") or "")
                for symbol in symbols:
                    MiniQmtClient.call(
                        "download_history_data",
                        symbol,
                        period=period,
                        start_time=start_time,
                        end_time=end_time,
                        incrementally=True,
                    )
                return ProviderResponse(
                    data=pd.DataFrame([{"symbol": symbol, "downloaded": True} for symbol in symbols]),
                    meta={"api_name": "download_history", "period": period},
                )

            if normalized in {"history", "market_data", "daily", "day", "minute", "min", "tick"}:
                period = self._PERIOD_ALIASES.get(normalized, str(params.get("period") or "1d"))
                fields_raw = params.get("fields") or []
                fields = (
                    [item.strip() for item in fields_raw.split(",") if item.strip()]
                    if isinstance(fields_raw, str)
                    else list(fields_raw)
                )
                payload = MiniQmtClient.call(
                    "get_market_data_ex",
                    fields,
                    symbols,
                    period=period,
                    start_time=str(params.get("start_time") or ""),
                    end_time=str(params.get("end_time") or ""),
                    count=int(params.get("count", -1)),
                    dividend_type=str(params.get("dividend_type") or "none"),
                    fill_data=_as_bool(params.get("fill_data"), True),
                )
                return ProviderResponse(
                    data=market_data_to_frame(payload),
                    meta={"api_name": "history", "period": period},
                )

            return ProviderResponse(error=f"MiniQMT暂不支持数据类型：{data_type}")
        except Exception as exc:
            return ProviderResponse(error=f"{exc.__class__.__name__}: {exc}")

    def scope_for(self, data_type: str) -> str:
        return "market:miniqmt:read"

    def is_realtime(self, data_type: str) -> bool:
        return self.normalize_data_type(data_type) in {"quote", "full_tick", "realtime", "tick"}
