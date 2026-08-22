# -*- coding: utf-8 -*-
"""Short-lived auth-context cache to avoid three SQLite reads per API call."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

import config
from services.redis_backend import get_redis, redis_key

_lock = threading.RLock()
_cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_MAX_ITEMS = 10000


def _token_hash(token: str) -> str:
    from services.api_token_security import configured_hash_secret, hash_api_token
    digest = hash_api_token(token, configured_hash_secret(config))
    return digest or hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def get_cached_auth_context(token: str) -> dict[str, Any] | None:
    ttl = int(getattr(config, "AUTH_CONTEXT_CACHE_TTL_SECONDS", 30) or 0)
    if ttl <= 0 or not token:
        return None
    key = _token_hash(token)
    now = time.time()
    with _lock:
        item = _cache.get(key)
        if item:
            expire_at, context = item
            if expire_at > now:
                _cache.move_to_end(key)
                return json.loads(json.dumps(context, ensure_ascii=False))
            _cache.pop(key, None)

    client = get_redis()
    if client is None:
        return None
    payload = client.get(redis_key("auth", key))
    if not payload:
        return None
    try:
        context = json.loads(payload.decode("utf-8"))
    except Exception:
        return None
    with _lock:
        _cache[key] = (now + min(ttl, 10), context)
    return context


def set_cached_auth_context(token: str, context: dict[str, Any]) -> None:
    ttl = int(getattr(config, "AUTH_CONTEXT_CACHE_TTL_SECONDS", 30) or 0)
    if ttl <= 0 or not token:
        return
    key = _token_hash(token)
    safe_context = json.loads(json.dumps(context, ensure_ascii=False, default=str))
    with _lock:
        _cache[key] = (time.time() + ttl, safe_context)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ITEMS:
            _cache.popitem(last=False)
    client = get_redis()
    if client is not None:
        try:
            client.set(redis_key("auth", key), json.dumps(safe_context, ensure_ascii=False), ex=ttl)
        except Exception:
            pass


def get_or_load_auth_context(token: str, loader: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    cached = get_cached_auth_context(token)
    if cached is not None:
        return cached
    context = loader(token)
    set_cached_auth_context(token, context)
    return context


def clear_auth_context_cache(token: str | None = None) -> None:
    client = get_redis()
    if token:
        key = _token_hash(token)
        with _lock:
            _cache.pop(key, None)
        if client is not None:
            try:
                client.delete(redis_key("auth", key))
            except Exception:
                pass
        return

    with _lock:
        _cache.clear()
    if client is not None:
        try:
            keys = list(client.scan_iter(match=redis_key("auth", "*"), count=500))
            if keys:
                client.delete(*keys)
        except Exception:
            pass


def clear_user_auth_context_cache(user_id: int) -> int:
    """Clear all cached auth contexts for every API key owned by one user."""
    try:
        from db_utils import get_conn
        rows = get_conn().execute(
            "SELECT token_hash FROM api_keys WHERE user_id=? AND COALESCE(token_hash,'')!=''",
            (int(user_id),),
        ).fetchall()
    except Exception:
        rows = []
    client = get_redis()
    cleared = 0
    for row in rows:
        key = row[0] if not hasattr(row, "keys") else row["token_hash"]
        if not key:
            continue
        with _lock:
            _cache.pop(str(key), None)
        if client is not None:
            try:
                client.delete(redis_key("auth", str(key)))
            except Exception:
                pass
        cleared += 1
    return cleared
