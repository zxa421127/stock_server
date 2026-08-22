# -*- coding: utf-8 -*-
"""Small subscription manager for future MiniQMT realtime use."""
from __future__ import annotations

import threading
from typing import Callable

from .client import MiniQmtClient


class MiniQmtSubscriptionManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscriptions: dict[tuple[str, str], int | str | None] = {}

    def subscribe(self, symbol: str, period: str = "tick", callback: Callable | None = None):
        key = (symbol, period)
        with self._lock:
            if key in self._subscriptions:
                return self._subscriptions[key]
            sub_id = MiniQmtClient.call(
                "subscribe_quote", symbol, period=period, count=-1, callback=callback
            )
            self._subscriptions[key] = sub_id
            return sub_id

    def unsubscribe(self, symbol: str, period: str = "tick") -> bool:
        key = (symbol, period)
        with self._lock:
            sub_id = self._subscriptions.pop(key, None)
        if sub_id is None:
            return False
        MiniQmtClient.call("unsubscribe_quote", sub_id)
        return True

    def snapshot(self) -> list[dict[str, object]]:
        with self._lock:
            return [
                {"symbol": symbol, "period": period, "subscription_id": sub_id}
                for (symbol, period), sub_id in self._subscriptions.items()
            ]
