# -*- coding: utf-8 -*-
"""Thread-safe registry for pluggable market-data providers."""
from __future__ import annotations

import threading
from typing import Iterable

import config
from integrations.market_data.base import MarketDataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {}
        self._lock = threading.RLock()

    def register(self, provider: MarketDataProvider, *, replace: bool = False) -> None:
        code = (provider.code or "").strip().lower()
        if not code:
            raise ValueError("数据源 code 不能为空")
        with self._lock:
            if code in self._providers and not replace:
                raise ValueError(f"数据源已注册：{code}")
            self._providers[code] = provider

    def unregister(self, code: str) -> None:
        with self._lock:
            self._providers.pop((code or "").strip().lower(), None)

    def get(self, code: str) -> MarketDataProvider:
        normalized = (code or "").strip().lower()
        with self._lock:
            provider = self._providers.get(normalized)
        if provider is None:
            raise KeyError(f"未知数据源：{code}")
        return provider

    def list(self) -> list[MarketDataProvider]:
        with self._lock:
            return list(self._providers.values())

    def codes(self) -> list[str]:
        return sorted(provider.code for provider in self.list())

    def extend(self, providers: Iterable[MarketDataProvider]) -> None:
        for provider in providers:
            self.register(provider)


_registry: ProviderRegistry | None = None
_registry_lock = threading.Lock()


def build_default_registry() -> ProviderRegistry:
    from integrations.market_data.kaipanla.provider import KaipanlaProvider
    from integrations.market_data.tushare.provider import TushareProvider

    registry = ProviderRegistry()
    registry.register(TushareProvider())
    registry.register(KaipanlaProvider())

    if getattr(config, "MINIQMT_ENABLED", False):
        from integrations.market_data.miniqmt.provider import MiniQmtProvider
        registry.register(MiniQmtProvider())
    return registry


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = build_default_registry()
    return _registry


def reset_provider_registry() -> None:
    global _registry
    with _registry_lock:
        _registry = None
