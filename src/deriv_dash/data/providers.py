"""Provider protocol for fetching price data."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..domain import PriceQuery


class PricesProvider(Protocol):
    """Abstraction for price data sources."""

    def fetch_prices(self, query: PriceQuery) -> pd.DataFrame:
        """Fetch prices in canonical long form."""
        raise NotImplementedError

