# -*- coding: utf-8 -*-
"""Backward-compatible sync results with explicit status metadata."""
from __future__ import annotations

from collections.abc import Iterable


class SyncResult(tuple):
    """Tuple-compatible count result carrying an explicit execution status.

    Existing callers may keep unpacking or comparing the result with a normal
    tuple.  Interactive callers get a descriptive representation instead of an
    ambiguous ``(0, 0)`` when a task was skipped or failed.
    """

    def __new__(
        cls,
        counts: Iterable[int],
        *,
        status: str = "ok",
        message: str = "",
    ) -> "SyncResult":
        obj = super().__new__(cls, tuple(int(value) for value in counts))
        obj.status = str(status or "ok")
        obj.message = str(message or "")
        return obj

    @property
    def success(self) -> bool:
        return self.status in {"ok", "empty", "skipped"}

    @property
    def counts(self) -> tuple[int, ...]:
        return tuple(self)

    def to_dict(self) -> dict:
        return {
            "counts": list(self),
            "status": self.status,
            "message": self.message,
            "success": self.success,
        }

    def __repr__(self) -> str:
        return (
            f"SyncResult(counts={tuple(self)!r}, status={self.status!r}, "
            f"message={self.message!r})"
        )

    __str__ = __repr__
