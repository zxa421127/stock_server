# -*- coding: utf-8 -*-
"""Cross-process advisory file locks implemented with the Python standard library."""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_thread_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}


def _thread_lock_for(path: Path) -> threading.Lock:
    key = os.path.normcase(str(path.resolve()))
    with _thread_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _thread_locks[key] = lock
        return lock


def _prepare_handle(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    return handle


def _try_platform_lock(handle) -> bool:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, OSError):
        return False


def _unlock_platform(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def process_lock(
    path: str | os.PathLike,
    *,
    timeout: float = 0.0,
    poll_interval: float = 0.05,
) -> Iterator[bool]:
    """Yield whether a process-wide lock was acquired.

    The file descriptor stays open for the full context and the operating
    system releases the lock automatically if the process exits unexpectedly.
    A small in-process lock complements the platform file lock because lock
    semantics differ for multiple file descriptors owned by the same process.
    """

    lock_path = Path(path)
    thread_lock = _thread_lock_for(lock_path)
    timeout = max(0.0, float(timeout or 0.0))
    poll_interval = max(0.01, float(poll_interval or 0.05))
    deadline = time.monotonic() + timeout

    if timeout == 0:
        acquired_thread = thread_lock.acquire(blocking=False)
    else:
        acquired_thread = thread_lock.acquire(timeout=timeout)
    if not acquired_thread:
        yield False
        return

    handle = None
    platform_acquired = False
    try:
        handle = _prepare_handle(lock_path)
        while True:
            platform_acquired = _try_platform_lock(handle)
            if platform_acquired:
                break
            if time.monotonic() >= deadline:
                yield False
                return
            time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
        yield True
    finally:
        if platform_acquired and handle is not None:
            try:
                _unlock_platform(handle)
            except OSError:
                pass
        if handle is not None:
            handle.close()
        thread_lock.release()
