# -*- coding: utf-8 -*-
"""Contracts shared by all market-data providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


@dataclass(slots=True)
class ProviderResponse:
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class MarketDataProvider(ABC):
    code: str
    display_name: str

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return provider availability without raising to the HTTP layer."""
        raise NotImplementedError

    @abstractmethod
    def catalog(self) -> list[dict[str, Any]]:
        """Return data types exposed by this provider."""
        raise NotImplementedError

    @abstractmethod
    def query(self, data_type: str, params: Mapping[str, Any]) -> ProviderResponse:
        """Query one provider-specific data type."""
        raise NotImplementedError

    def normalize_data_type(self, data_type: str) -> str:
        return (data_type or "").strip().lower().replace("-", "_")

    def scope_for(self, data_type: str) -> str:
        return f"market:{self.code}:read"

    def is_realtime(self, data_type: str) -> bool:
        return False

    def cache_ttl_seconds(self, data_type: str) -> int:
        return 0 if self.is_realtime(data_type) else 300
