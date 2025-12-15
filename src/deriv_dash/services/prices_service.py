"""Service helpers that UI layers call."""

from __future__ import annotations

import pandas as pd

from ..analytics.summary import build_summary
from ..domain import PriceField, PriceQuery
from ..utils import DataRetrievalError
from ..data.providers import PricesProvider


def get_prices(provider: PricesProvider, query: PriceQuery) -> pd.DataFrame:
    """Fetch canonical long-form prices."""
    try:
        return provider.fetch_prices(query)
    except Exception as err:
        msg = f"Failed to fetch prices: {err}"
        if isinstance(err, DataRetrievalError):
            raise
        raise DataRetrievalError(msg) from err


def get_price_matrix(prices_long: pd.DataFrame, field: PriceField) -> pd.DataFrame:
    """Pivot long-form prices to a wide matrix for charting."""
    if prices_long.empty:
        return pd.DataFrame()
    usable = prices_long.dropna(subset=[field])
    if usable.empty:
        return pd.DataFrame()
    matrix = usable.pivot(index="date", columns="ticker", values=field)
    return matrix.sort_index()


def get_normalized_matrix(prices_matrix: pd.DataFrame) -> pd.DataFrame:
    """Rebase price matrix to 100 on the first available value."""
    if prices_matrix.empty:
        return pd.DataFrame()

    def _normalize_series(series: pd.Series) -> pd.Series:
        non_na = series.dropna()
        if non_na.empty:
            return series
        base = non_na.iloc[0]
        if base == 0:
            return series
        return (series / base) * 100

    return prices_matrix.apply(_normalize_series)


def build_summary_table(prices_long: pd.DataFrame, field: PriceField) -> pd.DataFrame:
    """Expose analytics summary to UIs."""
    return build_summary(prices_long, field)

