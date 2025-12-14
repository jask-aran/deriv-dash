"""yfinance-backed prices provider."""

from __future__ import annotations

import pandas as pd
import yfinance as yf
import yfinance.data

# Patch yfinance to bypass fc.yahoo.com check which is blocked in some environments
def _get_cookie_basic_patched(self, timeout=30):
    return True

yfinance.data.YfData._get_cookie_basic = _get_cookie_basic_patched

from ..domain import PriceQuery
from ..utils import DataRetrievalError
from .normalization import empty_prices_frame, normalize_yfinance_frame
from .providers import PricesProvider


class YFinancePricesProvider(PricesProvider):
    """Adapter around yfinance.download that emits canonical frames."""

    def fetch_prices(self, query: PriceQuery) -> pd.DataFrame:
        if not query.tickers:
            return empty_prices_frame()

        try:
            raw = yf.download(
                tickers=" ".join(query.tickers),
                start=query.start,
                end=query.end,
                interval=query.interval,
                auto_adjust=query.auto_adjust,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as err:  # pragma: no cover - defensive against network issues
            raise DataRetrievalError(f"yfinance download failed: {err}") from err

        if isinstance(raw, tuple):
            raw = raw[0]

        return normalize_yfinance_frame(raw, query.tickers)

