"""Normalize yfinance outputs into a canonical schema."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

RAW_FIELD_NAMES = {"Close", "Adj Close", "Volume", "Open", "High", "Low"}
CANONICAL_COLUMNS = ["date", "ticker", "close", "adj_close", "volume"]


def empty_prices_frame() -> pd.DataFrame:
    """Return an empty canonical frame."""
    return pd.DataFrame(columns=CANONICAL_COLUMNS)


def normalize_yfinance_frame(raw: pd.DataFrame, tickers: Iterable[str]) -> pd.DataFrame:
    """Convert raw yfinance DataFrame to long-form canonical schema."""
    if raw is None or raw.empty:
        return empty_prices_frame()

    tickers_list = list(tickers)
    df = _ensure_tickers_first(raw)

    if isinstance(df.columns, pd.MultiIndex):
        frames = [_normalize_single_ticker(df[ticker], str(ticker)) for ticker in df.columns.get_level_values(0).unique()]
        normalized = pd.concat(frames, ignore_index=True)
    else:
        inferred_ticker = tickers_list[0] if tickers_list else "TICKER"
        normalized = _normalize_single_ticker(df, inferred_ticker)

    normalized["date"] = pd.to_datetime(normalized["date"]).dt.normalize()

    return normalized.sort_values(["ticker", "date"]).reset_index(drop=True)


def _ensure_tickers_first(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    level0 = df.columns.get_level_values(0)
    level1 = df.columns.get_level_values(1)

    fields_in_level0 = _has_raw_field(level0)
    fields_in_level1 = _has_raw_field(level1)

    if fields_in_level0 and not fields_in_level1:
        return df.swaplevel(0, 1, axis=1)
    return df


def _has_raw_field(level: Any) -> bool:
    try:
        return bool(set(level) & RAW_FIELD_NAMES)
    except TypeError:
        return False


def _normalize_single_ticker(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(frame, pd.Series):
        frame = frame.to_frame()

    rename_map = {
        "Close": "close",
        "Adj Close": "adj_close",
        "AdjClose": "adj_close",
        "Adj_Close": "adj_close",
        "Volume": "volume",
        "Close*": "close",
    }

    working = frame.copy()
    working.columns = [rename_map.get(col, col).lower() if isinstance(col, str) else col for col in working.columns]

    ordered_cols = [col for col in ("close", "adj_close", "volume") if col in working.columns]
    working = working[ordered_cols]

    working = working.reset_index().rename(columns={"Date": "date", "index": "date"})
    if "date" not in working.columns:
        working["date"] = working.index

    for missing in ("close", "adj_close", "volume"):
        if missing not in working.columns:
            working[missing] = pd.NA

    working["ticker"] = ticker.upper()

    return working[CANONICAL_COLUMNS]
