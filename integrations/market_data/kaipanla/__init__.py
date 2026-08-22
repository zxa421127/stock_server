"""Kaipanla unified-provider package with lazy provider import."""
from __future__ import annotations

__all__ = ["KaipanlaProvider"]


def __getattr__(name: str):
    if name == "KaipanlaProvider":
        from .provider import KaipanlaProvider
        return KaipanlaProvider
    raise AttributeError(name)
