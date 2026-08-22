# -*- coding: utf-8 -*-
"""Tushare implementation of the unified provider contract."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

from integrations.market_data.base import MarketDataProvider, ProviderResponse
from integrations.market_data.tushare.catalog import (
    get_api_meta,
    is_allowed_tushare_api,
    list_tushare_apis,
    normalize_api_name,
)
from integrations.market_data.tushare.client import TushareClient, call_tushare_api
from integrations.market_data.tushare.latest_available import query_with_latest_available
from integrations.market_data.tushare.permissions import (
    TUSHARE_CATALOG_SCOPE,
    required_scope_for_api,
)


class TushareProvider(MarketDataProvider):
    code = "tushare"
    display_name = "Tushare"

    def normalize_data_type(self, data_type: str) -> str:
        return normalize_api_name(data_type)

    def catalog(self) -> list[dict[str, Any]]:
        rows = list_tushare_apis()
        for row in rows:
            row["provider"] = self.code
        return rows

    def health_check(self) -> dict[str, Any]:
        end_day = datetime.now().date()
        start_day = end_day - timedelta(days=7)
        response = self.query(
            "trade_cal",
            {
                "exchange": "SSE",
                "start_date": start_day.strftime("%Y%m%d"),
                "end_date": end_day.strftime("%Y%m%d"),
                "fields": "exchange,cal_date,is_open,pretrade_date",
            },
        )
        return {
            "available": response.error is None,
            "mode": TushareClient.mode(),
            "rows": len(response.data),
            "error": response.error,
        }

    def query(self, data_type: str, params: Mapping[str, Any]) -> ProviderResponse:
        api_name = self.normalize_data_type(data_type)
        if not is_allowed_tushare_api(api_name):
            return ProviderResponse(error=f"未开放或不支持的Tushare接口：{data_type}")

        def raw_query(name: str, query_params: dict[str, Any]):
            return call_tushare_api(name, **query_params)

        df, error, freshness_meta = query_with_latest_available(
            api_name,
            dict(params or {}),
            raw_query,
        )
        return ProviderResponse(
            data=df,
            error=error,
            meta={
                "mode": TushareClient.mode(),
                "api_name": api_name,
                **freshness_meta,
            },
        )

    def scope_for(self, data_type: str) -> str:
        api_name = self.normalize_data_type(data_type)
        if not get_api_meta(api_name):
            # Provider catalog / health metadata is available to both paid tiers.
            return TUSHARE_CATALOG_SCOPE
        return required_scope_for_api(api_name)

    def is_realtime(self, data_type: str) -> bool:
        meta = get_api_meta(data_type)
        return bool(meta and meta.realtime)
