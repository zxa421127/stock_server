# -*- coding: utf-8 -*-
"""Reference-counted per-key locks used to collapse identical upstream calls."""
from __future__ import annotations

import threading
from contextlib import contextmanager

_guard = threading.Lock()
_locks: dict[str, tuple[threading.Lock, int]] = {}


@contextmanager
def keyed_lock(key: str):
    with _guard:
        lock, refs = _locks.get(key, (threading.Lock(), 0))
        _locks[key] = (lock, refs + 1)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
        with _guard:
            current_lock, refs = _locks.get(key, (lock, 1))
            if current_lock is lock and refs <= 1:
                _locks.pop(key, None)
            elif current_lock is lock:
                _locks[key] = (lock, refs - 1)
