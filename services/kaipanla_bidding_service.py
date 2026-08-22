# -*- coding: utf-8 -*-
"""Business orchestration for live Kaipanla data, immutable snapshots and fallback."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, time as clock_time
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

from integrations.market_data.base import ProviderResponse
from integrations.market_data.kaipanla.adapter import normalize_kaipanla_bidding
from integrations.market_data.kaipanla.client import KaipanlaClient
from integrations.market_data.kaipanla.schema import SCHEMA_VERSION
from services.kaipanla_snapshot_repository import (
    KaipanlaSnapshotRepository,
    validate_snapshot_type,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_DATE_RE = re.compile(r"^\d{8}$")
# Accept current typed ids and legacy ids so old history remains addressable.
_SNAPSHOT_RE = re.compile(r"^\d{8}_\d{6}_(?:(?:auction|post_open|close)_)?[0-9a-f]{12}$")
_AUCTION_WINDOW_START = clock_time(9, 15, 0)
_AUCTION_WINDOW_END = clock_time(9, 30, 0)
_FALLBACK_WARNING = "未找到开盘啦历史快照，已降级为 Tushare 部分数据；开盘啦特有竞价字段无法还原"


def _default_market_query(provider: str, api_name: str, params: dict[str, Any], **kwargs: Any):
    from services.market_data_service import query_market_data
    return query_market_data(provider, api_name, params, **kwargs)


def _now() -> datetime:
    return datetime.now(_SHANGHAI)


def _as_shanghai(value: datetime) -> datetime:
    return value.replace(tzinfo=_SHANGHAI) if value.tzinfo is None else value.astimezone(_SHANGHAI)


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须为整数") from exc
    return min(max(parsed, minimum), maximum)


class KaipanlaBiddingService:
    def __init__(
        self,
        *,
        repository: KaipanlaSnapshotRepository | None = None,
        client: KaipanlaClient | None = None,
        market_query: Callable[..., Any] | None = None,
        china_now: Callable[[], datetime] | None = None,
        china_today: Callable[[], str] | None = None,
    ) -> None:
        self.repository = repository or KaipanlaSnapshotRepository()
        self.client = client or KaipanlaClient()
        self.market_query = market_query or _default_market_query
        self.china_now = china_now or _now
        self.china_today = china_today

    @staticmethod
    def _validate_date(value: Any, required: bool = True) -> str | None:
        text = str(value or "").strip()
        if not text and not required:
            return None
        if not _DATE_RE.fullmatch(text):
            raise ValueError("trade_date 必须为 YYYYMMDD")
        datetime.strptime(text, "%Y%m%d")
        return text

    def _today(self) -> str:
        if self.china_today is not None:
            return self._validate_date(self.china_today()) or ""
        return _as_shanghai(self.china_now()).strftime("%Y%m%d")

    def _query_tushare(self, api: str, params: dict[str, Any]):
        try:
            return self.market_query("tushare", api, params)
        except Exception as exc:
            logging.warning("[开盘啦竞价] Tushare %s 查询异常: %s", api, exc)
            return ProviderResponse(error=str(exc))

    def get_open_date_status(self, trade_date: str) -> str:
        date = self._validate_date(trade_date)
        result = self._query_tushare(
            "trade_cal",
            {"exchange": "SSE", "start_date": date, "end_date": date, "fields": "cal_date,is_open"},
        )
        if result.error or result.data is None or result.data.empty or "is_open" not in result.data.columns:
            return "unknown"
        value = pd.to_numeric(result.data["is_open"], errors="coerce")
        if value.notna().sum() == 0:
            return "unknown"
        return "open" if bool(value.fillna(0).max() == 1) else "closed"

    def is_open_date(self, trade_date: str) -> bool:
        return self.get_open_date_status(trade_date) == "open"

    def _resolve_latest_open_date(self, on_or_before: str) -> tuple[str | None, str | None]:
        bound = self._validate_date(on_or_before)
        end = datetime.strptime(bound, "%Y%m%d")
        start = (end - timedelta(days=45)).strftime("%Y%m%d")
        result = self._query_tushare(
            "trade_cal",
            {"exchange": "SSE", "start_date": start, "end_date": bound, "fields": "cal_date,is_open"},
        )
        if result.error:
            return None, result.error
        frame = result.data if isinstance(result.data, pd.DataFrame) else pd.DataFrame(result.data)
        if frame.empty or not {"cal_date", "is_open"}.issubset(frame.columns):
            return None, "交易日历未返回可验证数据"
        dates = frame.copy()
        dates["cal_date"] = dates["cal_date"].astype(str).str.replace(r"\D", "", regex=True)
        dates["is_open"] = pd.to_numeric(dates["is_open"], errors="coerce")
        dates = dates[(dates["cal_date"] <= bound) & (dates["is_open"] == 1)]
        if dates.empty:
            return None, f"{bound} 之前未找到可用交易日"
        return str(dates["cal_date"].max()), None

    def _reference_frames(self, trade_date: str | None, *, historical: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
        stock = self._query_tushare(
            "stock_basic",
            {"list_status": "L", "fields": "ts_code,symbol,name,industry,market,exchange,list_status"},
        )
        stock_df = pd.DataFrame() if stock.error else stock.data
        bak_df = pd.DataFrame()
        if historical and trade_date:
            bak = self._query_tushare(
                "bak_basic",
                {"trade_date": trade_date, "fields": "trade_date,ts_code,name,industry,float_share", "latest_available": "false"},
            )
            if not bak.error:
                bak_df = bak.data
        return stock_df, bak_df

    def _normalize(
        self,
        raw: pd.DataFrame,
        *,
        trade_date: str | None,
        snapshot_type: str = "auction",
        snapshot_time: str | None = None,
        snapshot_id: str | None = None,
        historical: bool = False,
        source_provider: str = "kaipanla",
        source_api: str = "morning_bidding",
        data_quality: str = "complete",
    ) -> pd.DataFrame:
        snapshot_type = validate_snapshot_type(snapshot_type)
        stock, bak = self._reference_frames(trade_date, historical=historical)
        return normalize_kaipanla_bidding(
            raw,
            trade_date=trade_date,
            snapshot_type=snapshot_type,
            snapshot_time=snapshot_time,
            snapshot_id=snapshot_id,
            stock_basic_df=stock,
            bak_basic_df=bak,
            historical=historical,
            source_provider=source_provider,
            source_api=source_api,
            data_quality=data_quality,
        )

    def query(self, data_type: str, params: dict[str, Any] | None = None) -> ProviderResponse:
        normalized = (data_type or "").strip().lower().replace("-", "_").replace("/", "_")
        if normalized in {"morning_bidding", "bidding", "morningbiddinglist"}:
            return self.query_live(dict(params or {}))
        if normalized in {"morning_bidding_history", "bidding_history"}:
            return self.query_history(dict(params or {}))
        return ProviderResponse(error=f"开盘啦暂不支持数据类型：{data_type}")

    def query_live(self, params: dict[str, Any]) -> ProviderResponse:
        try:
            allowed = {
                "order": _bounded_int(params.get("order", 1), default=1, minimum=-10, maximum=10, name="order"),
                "page_size": _bounded_int(params.get("st", params.get("page_size", 200)), default=200, minimum=1, maximum=1000, name="page_size"),
                "start_index": _bounded_int(params.get("index", 0), default=0, minimum=0, maximum=1_000_000, name="index"),
                "pid_type": _bounded_int(params.get("pid_type", 0), default=0, minimum=0, maximum=100, name="pid_type"),
                "b_type": _bounded_int(params.get("b_type", 4), default=4, minimum=0, maximum=100, name="b_type"),
                "max_pages": _bounded_int(params.get("max_pages", 1), default=1, minimum=1, maximum=100, name="max_pages"),
            }
        except ValueError as exc:
            return ProviderResponse(error=str(exc), meta={"http_status": 400})
        fetched = self.client.fetch_all(**allowed)
        if fetched.error:
            return ProviderResponse(error=fetched.error, meta={"api_name": "morning_bidding", "source_provider": "kaipanla"})
        if fetched.data is None or fetched.data.empty:
            return ProviderResponse(error="开盘啦实时接口返回空数据，未生成业务结果", meta={"api_name": "morning_bidding", "source_provider": "kaipanla"})

        now = _as_shanghai(self.china_now())
        candidate = self._today()
        in_window = _AUCTION_WINDOW_START <= now.time().replace(tzinfo=None) <= _AUCTION_WINDOW_END
        status = self.get_open_date_status(candidate) if in_window else "unknown"
        verified = in_window and status == "open"
        trade_date = candidate if verified else None
        warning = None
        freshness = "verified_live" if verified else "unverified_realtime"
        quality = "complete" if verified else "unverified"
        if not verified:
            reason = "当前不在 09:15—09:30 集合竞价校验窗口" if not in_window else "交易日状态无法确认"
            warning = f"{reason}，实时结果未标注交易日，不能作为历史快照使用"
        normalized = self._normalize(
            fetched.data,
            trade_date=trade_date,
            snapshot_type="auction",
            snapshot_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            data_quality=quality,
        )
        return ProviderResponse(
            data=normalized,
            meta={
                "api_name": "morning_bidding",
                "source_provider": "kaipanla",
                "source_api": "morning_bidding",
                "actual_trade_date": trade_date,
                "snapshot_type": "auction",
                "fallback_used": False,
                "data_freshness": freshness,
                "data_quality": quality,
                "warning": warning,
                "schema_version": SCHEMA_VERSION,
            },
        )

    @staticmethod
    def _valid_snapshot_frame(frame: pd.DataFrame) -> bool:
        if frame is None or frame.empty:
            return False
        for column in ("股票代码", "0", "ts_code"):
            if column in frame.columns and frame[column].astype(str).str.extract(r"(\d{6})", expand=False).notna().any():
                return True
        return False

    def capture_snapshot(
        self,
        *,
        trade_date: str,
        snapshot_time: str,
        snapshot_type: str = "auction",
        page_size: int = 1000,
        max_pages: int = 10,
    ) -> ProviderResponse:
        trade_date = self._validate_date(trade_date)
        try:
            snapshot_type = validate_snapshot_type(snapshot_type)
        except ValueError as exc:
            return ProviderResponse(error=str(exc), meta={"http_status": 400})
        existing = self.repository.get_snapshot(trade_date, snapshot_type)
        if existing:
            return ProviderResponse(
                data=pd.DataFrame(existing.normalized_data),
                meta={"snapshot_id": existing.snapshot_id, "snapshot_type": snapshot_type, "snapshot_created": False, "record_count": existing.record_count},
            )
        fetched = self.client.fetch_all(page_size=min(max(int(page_size), 1), 1000), max_pages=min(max(int(max_pages), 1), 100))
        if fetched.error:
            return ProviderResponse(error=fetched.error, meta={"source_provider": "kaipanla", "snapshot_type": snapshot_type})
        if not self._valid_snapshot_frame(fetched.data):
            return ProviderResponse(error="开盘啦快照采集结果为空或缺少有效股票代码，已拒绝保存", meta={"source_provider": "kaipanla", "snapshot_type": snapshot_type, "record_count": 0})
        normalized = self._normalize(
            fetched.data,
            trade_date=trade_date,
            snapshot_type=snapshot_type,
            snapshot_time=snapshot_time,
            historical=True,
        )
        if not self._valid_snapshot_frame(normalized):
            return ProviderResponse(error="开盘啦快照标准化后为空或缺少有效股票代码，已拒绝保存", meta={"source_provider": "kaipanla", "snapshot_type": snapshot_type, "record_count": 0})
        save = self.repository.save_snapshot(
            trade_date=trade_date,
            snapshot_type=snapshot_type,
            snapshot_time=snapshot_time,
            source_params=fetched.params,
            raw_payload=fetched.raw_pages,
            normalized_data=normalized.to_dict(orient="records"),
            data_quality="complete",
        )
        return ProviderResponse(
            data=pd.DataFrame(save.snapshot.normalized_data),
            meta={
                "snapshot_id": save.snapshot.snapshot_id,
                "snapshot_type": save.snapshot.snapshot_type,
                "snapshot_created": save.created,
                "record_count": save.snapshot.record_count,
                "schema_version": save.snapshot.schema_version,
            },
        )

    @staticmethod
    def _filter_snapshot(df: pd.DataFrame, params: dict[str, Any]) -> pd.DataFrame:
        result = df.copy()
        ts_code = str(params.get("ts_code") or "").strip()
        symbol = str(params.get("股票代码") or params.get("symbol") or "").strip()
        if ts_code and "ts_code" in result.columns:
            result = result[result["ts_code"].astype(str) == ts_code]
        if symbol:
            column = "股票代码" if "股票代码" in result.columns else "ts_code"
            result = result[result[column].astype(str).str.extract(r"(\d{6})", expand=False) == re.sub(r"\D", "", symbol)[:6]]
        try:
            limit = min(max(int(params.get("limit", 0)), 0), 10_000)
        except (TypeError, ValueError):
            limit = 0
        return result.head(limit) if limit else result

    def _snapshot_response(self, snapshot, params: dict[str, Any], requested: str | None, *, fallback_used: bool, freshness: str) -> ProviderResponse:
        data = self._filter_snapshot(pd.DataFrame(snapshot.normalized_data), params)
        return ProviderResponse(
            data=data,
            meta={
                "api_name": "morning_bidding_history",
                "source_provider": "kaipanla_snapshot",
                "source_api": "morning_bidding",
                "requested_trade_date": requested,
                "actual_trade_date": snapshot.trade_date,
                "snapshot_type": snapshot.snapshot_type,
                "fallback_used": fallback_used,
                "data_freshness": freshness,
                "data_quality": snapshot.data_quality,
                "snapshot_id": snapshot.snapshot_id,
                "snapshot_time": snapshot.snapshot_time,
                "payload_hash": snapshot.payload_hash,
                "schema_version": snapshot.schema_version,
            },
        )

    def query_history(self, params: dict[str, Any]) -> ProviderResponse:
        try:
            requested = self._validate_date(params.get("trade_date"), required=False)
            snapshot_type = validate_snapshot_type(params.get("snapshot_type"), default="auction")
        except ValueError as exc:
            return ProviderResponse(error=str(exc), meta={"http_status": 400})

        sid = str(params.get("snapshot_id") or "").strip() or None
        if sid:
            if not _SNAPSHOT_RE.fullmatch(sid):
                return ProviderResponse(error="snapshot_id 格式无效", meta={"http_status": 400, "snapshot_type": snapshot_type})
            snap = self.repository.get_by_id(sid)
            if snap is None:
                return ProviderResponse(error="未找到指定 snapshot_id 的开盘啦历史快照", meta={"http_status": 404, "snapshot_id": sid, "snapshot_type": snapshot_type})
            if requested and requested != snap.trade_date:
                return ProviderResponse(error="trade_date 与 snapshot_id 对应交易日不一致", meta={"http_status": 400, "snapshot_id": sid, "snapshot_type": snapshot_type})
            if snap.snapshot_type != snapshot_type:
                return ProviderResponse(error="snapshot_id 与 snapshot_type 不一致", meta={"http_status": 400, "snapshot_id": sid, "snapshot_type": snapshot_type})
            return self._snapshot_response(snap, params, requested or snap.trade_date, fallback_used=False, freshness="exact_snapshot_id")

        snap = self.repository.get_latest_snapshot(requested, snapshot_type)
        if snap is not None:
            fallback = bool(requested and snap.trade_date != requested)
            freshness = "latest_snapshot_on_or_before" if fallback else ("exact_snapshot" if requested else "latest_snapshot")
            return self._snapshot_response(snap, params, requested, fallback_used=fallback, freshness=freshness)

        # post_open and close have no equivalent trustworthy upstream history source.
        # Never substitute an auction snapshot or Tushare data while claiming either type.
        if snapshot_type in {"post_open", "close"}:
            return ProviderResponse(
                error=f"未找到指定条件的 {snapshot_type} 历史快照",
                meta={"http_status": 404, "requested_trade_date": requested, "actual_trade_date": None, "snapshot_type": snapshot_type, "fallback_used": False},
            )

        fallback_bound = requested or self._today()
        fallback_date, calendar_error = self._resolve_latest_open_date(fallback_bound)
        if not fallback_date:
            return ProviderResponse(
                error=f"无可用开盘啦快照，且无法确认最近交易日：{calendar_error}",
                meta={"http_status": 502, "requested_trade_date": requested, "actual_trade_date": None, "snapshot_type": snapshot_type, "fallback_used": True, "fallback_reason": "trade_calendar_unavailable"},
            )
        result = self._query_tushare("stk_auction_o", {"trade_date": fallback_date, "latest_available": "false"})
        if result.error:
            return ProviderResponse(error=f"无可用开盘啦快照，Tushare降级失败：{result.error}", meta={"http_status": 502, "requested_trade_date": requested, "actual_trade_date": fallback_date, "snapshot_type": snapshot_type, "fallback_used": True, "fallback_reason": "kaipanla_snapshot_not_found"})
        if result.data is None or result.data.empty:
            return ProviderResponse(error=f"无可用开盘啦快照，Tushare 在交易日 {fallback_date} 也未返回数据", meta={"http_status": 502, "requested_trade_date": requested, "actual_trade_date": fallback_date, "snapshot_type": snapshot_type, "fallback_used": True, "fallback_reason": "kaipanla_snapshot_not_found"})
        actual = str((result.meta or {}).get("actual_trade_date") or fallback_date)
        df = self._normalize(result.data, trade_date=actual, snapshot_type="auction", historical=True, source_provider="tushare", source_api="stk_auction_o", data_quality="partial")
        df = self._filter_snapshot(df, params)
        return ProviderResponse(
            data=df,
            meta={
                "api_name": "morning_bidding_history",
                "source_provider": "tushare",
                "source_api": "stk_auction_o",
                "requested_trade_date": requested,
                "actual_trade_date": actual,
                "snapshot_type": "auction",
                "fallback_used": True,
                "fallback_reason": "kaipanla_snapshot_not_found",
                "data_freshness": "tushare_historical_fallback",
                "data_quality": "partial",
                "warning": _FALLBACK_WARNING,
                "snapshot_id": None,
                "schema_version": SCHEMA_VERSION,
            },
        )


_service: KaipanlaBiddingService | None = None


def get_kaipanla_bidding_service() -> KaipanlaBiddingService:
    global _service
    if _service is None:
        _service = KaipanlaBiddingService()
    return _service
