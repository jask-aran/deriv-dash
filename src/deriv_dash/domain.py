from __future__ import annotations

"""Domain models and configuration types."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

PriceField = Literal["close", "adj_close"]


@dataclass(slots=True)
class PriceQuery:
    tickers: list[str]
    start: date
    end: date
    interval: str = "1d"
    auto_adjust: bool = False
    include_extended: bool = False


@dataclass(slots=True)
class DashboardState:
    price_field: PriceField = "adj_close"
    normalize: bool = False
    log_scale: bool = False
    show_table: bool = True
    include_extended: bool = False


# Backwards-friendly alias
DashboardConfig = DashboardState
