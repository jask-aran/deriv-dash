"""Return calculations on price matrices."""

from __future__ import annotations

import pandas as pd


def compute_daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily percentage change."""
    if prices.empty:
        return prices.copy()
    return prices.pct_change().dropna(how="all")


def compute_cumulative_returns(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """Convert daily returns to cumulative return curves."""
    if daily_returns.empty:
        return daily_returns.copy()
    return (1 + daily_returns).cumprod() - 1

