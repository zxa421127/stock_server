# -*- coding: utf-8 -*-
"""Kaipanla provider exposing live and immutable historical bidding data."""
from __future__ import annotations
from typing import Any, Mapping
import config
from integrations.market_data.base import MarketDataProvider, ProviderResponse
from services.kaipanla_bidding_service import get_kaipanla_bidding_service


class KaipanlaProvider(MarketDataProvider):
    code="kaipanla"; display_name="开盘啦"

    def catalog(self) -> list[dict[str,Any]]:
        return [
            {"provider":self.code,"api_name":"morning_bidding","title":"早盘集合竞价（实时）","category":"竞价数据","group":"开盘啦","realtime":True,"url":"/api/v1/market/kaipanla/morning_bidding"},
            {"provider":self.code,"api_name":"morning_bidding/history","title":"早盘集合竞价历史快照","category":"竞价数据","group":"开盘啦","realtime":False,"url":"/api/v1/market/kaipanla/morning_bidding/history"},
        ]

    def health_check(self) -> dict[str,Any]:
        configured=bool(config.KAIPANLA_USER_ID and config.KAIPANLA_TOKEN and config.KAIPANLA_DEVICE_ID)
        return {"available":configured,"configured":configured,"error":None if configured else "KAIPANLA_USER_ID/TOKEN/DEVICE_ID 未完整配置"}

    def query(self,data_type: str,params: Mapping[str,Any]) -> ProviderResponse:
        return get_kaipanla_bidding_service().query(data_type,dict(params or {}))

    def scope_for(self,data_type: str) -> str: return "market:kaipanla:read"
    def is_realtime(self,data_type: str) -> bool:
        return self.normalize_data_type(data_type).replace("/","_") not in {"morning_bidding_history","bidding_history"}
