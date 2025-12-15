"""Summary table helpers for price data."""

from __future__ import annotations

import pandas as pd


def build_summary(prices_long: pd.DataFrame, field: str) -> pd.DataFrame:
    """Compute last price and total return per ticker for the selected field."""
    if prices_long.empty or field not in prices_long.columns:
        return pd.DataFrame(columns=["ticker", "last_price", "total_return_pct", "start_date", "end_date"])

    value_col = field
    subset = prices_long.dropna(subset=[value_col])
    if subset.empty:
        return pd.DataFrame(columns=["ticker", "last_price", "total_return_pct", "start_date", "end_date"])

    ordered = subset.sort_values(["ticker", "date"])
    grouped = ordered.groupby("ticker", sort=True)

    first = grouped.first()
    last = grouped.last()

    summary = pd.DataFrame(
        {
            "ticker": last.index,
            "start_date": first["date"].values,
            "end_date": last["date"].values,
            "start_price": first[value_col].values,
            "last_price": last[value_col].values,
        }
    )

    summary["total_return_pct"] = (summary["last_price"] / summary["start_price"] - 1) * 100

    return summary[["ticker", "last_price", "total_return_pct", "start_date", "end_date"]]

