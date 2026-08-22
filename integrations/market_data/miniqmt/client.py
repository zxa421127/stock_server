# -*- coding: utf-8 -*-
"""Lazy, thread-safe access to the optional XtQuant ``xtdata`` module."""
from __future__ import annotations

import importlib
import threading
from typing import Any, Callable

import config


class MiniQmtUnavailable(RuntimeError):
    pass


class MiniQmtClient:
    _lock = threading.RLock()
    _xtdata = None

    @classmethod
    def xtdata(cls):
        with cls._lock:
            if cls._xtdata is not None:
                return cls._xtdata
            try:
                module = importlib.import_module("xtquant.xtdata")
            except Exception:
                try:
                    package = importlib.import_module("xtquant")
                    module = getattr(package, "xtdata")
                except Exception as exc:
                    raise MiniQmtUnavailable(
                        "未安装或无法导入 xtquant；请从QMT安装目录配置官方xtquant库"
                    ) from exc
            cls._xtdata = module
            return module

    @classmethod
    def health(cls) -> dict[str, Any]:
        try:
            xtdata = cls.xtdata()
            status_getter = getattr(xtdata, "get_quote_server_status", None)
            status = status_getter() if callable(status_getter) else {}
            return {"available": True, "quote_servers": str(status)}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    @classmethod
    def call(cls, method_name: str, *args, **kwargs):
        xtdata = cls.xtdata()
        method: Callable[..., Any] | None = getattr(xtdata, method_name, None)
        if not callable(method):
            raise MiniQmtUnavailable(f"当前xtquant版本不支持：{method_name}")
        with cls._lock:
            return method(*args, **kwargs)

    @classmethod
    def max_symbols(cls) -> int:
        return int(getattr(config, "MINIQMT_MAX_SYMBOLS_PER_REQUEST", 200) or 200)
