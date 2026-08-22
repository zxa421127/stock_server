# -*- coding: utf-8 -*-
"""Convert XtQuant return objects into stable tabular responses."""
from __future__ import annotations

from typing import Any

import pandas as pd


def market_data_to_frame(payload: Any) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, pd.DataFrame):
        return payload.reset_index(drop=False)
    if not isinstance(payload, dict):
        return pd.DataFrame(payload)

    frames: list[pd.DataFrame] = []
    for symbol, value in payload.items():
        if isinstance(value, pd.DataFrame):
            frame = value.copy()
            frame = frame.reset_index(drop=False)
        elif isinstance(value, dict):
            frame = pd.DataFrame([value])
        else:
            frame = pd.DataFrame(value)
        if "symbol" not in frame.columns:
            frame.insert(0, "symbol", symbol)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def full_tick_to_frame(payload: Any) -> pd.DataFrame:
    if not isinstance(payload, dict):
        return pd.DataFrame()
    rows = []
    for symbol, values in payload.items():
        row = {"symbol": symbol}
        if isinstance(values, dict):
            row.update(values)
        else:
            row["value"] = values
        rows.append(row)
    return pd.DataFrame(rows)
