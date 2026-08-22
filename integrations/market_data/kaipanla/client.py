# -*- coding: utf-8 -*-
"""Paginated Kaipanla morning-bidding client."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd

from integrations.kaipanla.morning_bidding import get_morning_bidding_page_raw

FetchPage = Callable[..., tuple[pd.DataFrame, Any | None, str | None, dict[str, Any]]]


@dataclass(slots=True)
class KaipanlaFetchResult:
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_pages: list[Any] = field(default_factory=list)
    error: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


class KaipanlaClient:
    def __init__(self, fetch_page: FetchPage | None = None) -> None:
        self._fetch_page = fetch_page or get_morning_bidding_page_raw

    @staticmethod
    def _page_signature(df: pd.DataFrame, raw: Any) -> str:
        payload = raw
        if payload is None:
            payload = df.where(pd.notna(df), None).values.tolist()
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        for column in (0, "0", "股票代码", "证券代码", "代码", "symbol", "ts_code"):
            if column in df.columns:
                return df.drop_duplicates(subset=[column], keep="first").reset_index(drop=True)
        return df.drop_duplicates(keep="first").reset_index(drop=True)

    @staticmethod
    def _code_set(df: pd.DataFrame) -> set[str]:
        for column in (0, "0", "股票代码", "证券代码", "代码", "symbol", "ts_code"):
            if column in df.columns:
                return set(df[column].dropna().astype(str).str.extract(r"(\d{6})", expand=False).dropna())
        return set()

    def fetch_all(
        self,
        *,
        order: int = 1,
        page_size: int = 200,
        start_index: int = 0,
        pid_type: int = 0,
        b_type: int = 4,
        max_pages: int = 20,
    ) -> KaipanlaFetchResult:
        page_size = min(max(int(page_size), 1), 1000)
        max_pages = min(max(int(max_pages), 1), 100)
        base_params = {
            "order": int(order),
            "st": page_size,
            "index": max(int(start_index), 0),
            "pid_type": int(pid_type),
            "b_type": int(b_type),
        }
        frames: list[pd.DataFrame] = []
        raw_pages: list[Any] = []
        previous_signature: str | None = None
        previous_codes: set[str] = set()
        seen_codes: set[str] = set()
        effective_page_size = page_size
        request_index = base_params["index"]
        index_mode = "unknown"

        for request_no in range(max_pages):
            request_params = dict(base_params)
            request_params["index"] = request_index
            df, raw, error, _public_params = self._fetch_page(**request_params)
            result_params = {
                **base_params,
                "index_mode": index_mode,
                "effective_page_size": effective_page_size,
            }
            if error:
                partial = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
                return KaipanlaFetchResult(
                    data=self._deduplicate(partial),
                    raw_pages=raw_pages,
                    error=error,
                    params=result_params,
                )
            df = pd.DataFrame() if df is None else df
            if df.empty:
                break

            signature = self._page_signature(df, raw)
            if signature == previous_signature:
                break

            current_codes = self._code_set(df)
            if request_no > 0 and current_codes and not (current_codes - seen_codes):
                # Index is ignored (or the upstream wrapped around). Do not loop
                # merely because real-time values changed inside the same rows.
                break
            if request_no == 1 and index_mode == "unknown":
                denominator = min(len(previous_codes), len(current_codes))
                overlap_ratio = (
                    len(previous_codes & current_codes) / denominator
                    if denominator > 0
                    else 0.0
                )
                index_mode = "offset" if overlap_ratio >= 0.80 else "page"

            if request_no == 0:
                # Some upstream versions cap st below the requested size. Probe
                # one more page before deciding that a short first response is final.
                effective_page_size = max(len(df), 1)

            previous_signature = signature
            previous_codes = current_codes
            seen_codes.update(current_codes)
            frames.append(df)
            raw_pages.append({"index": request_index, "response": raw})
            if request_no > 0 and len(df) < effective_page_size:
                break

            if request_no == 0:
                # Probe index+1 once. The overlap with page zero tells us whether
                # Index is a page number or a row offset on this upstream version.
                request_index = base_params["index"] + 1
            elif index_mode == "offset":
                if request_index == base_params["index"] + 1:
                    request_index = base_params["index"] + effective_page_size
                else:
                    request_index += effective_page_size
            else:
                request_index += 1

        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return KaipanlaFetchResult(
            data=self._deduplicate(combined),
            raw_pages=raw_pages,
            error=None,
            params={
                **base_params,
                "index_mode": index_mode,
                "effective_page_size": effective_page_size,
            },
        )
