"""Streamlit entrypoint for the equity prices dashboard."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

from deriv_dash import DashboardState, PriceField, PriceQuery  # noqa: E402
from deriv_dash.data import YFinancePricesProvider  # noqa: E402
from deriv_dash.services import build_summary_table, get_normalized_matrix, get_price_matrix, get_prices  # noqa: E402
from deriv_dash.utils import DataRetrievalError  # noqa: E402
from deriv_dash.viz import make_price_chart  # noqa: E402

DEFAULT_TICKERS = "AAPL, MSFT, SPY"


@dataclass
class UiInputs:
    tickers: list[str]
    start_date: date
    end_date: date
    config: DashboardState


def parse_tickers(raw: str) -> list[str]:
    parts = [part.strip().upper() for part in raw.replace(";", ",").split(",")]
    tickers = [part for part in parts if part]
    deduped = list(dict.fromkeys(tickers))
    return deduped


@st.cache_data(show_spinner=False)
def load_prices_cached(
    tickers: tuple[str, ...], start: date, end: date, interval: str, auto_adjust: bool
) -> pd.DataFrame:
    query = PriceQuery(tickers=list(tickers), start=start, end=end, interval=interval, auto_adjust=auto_adjust)
    provider = YFinancePricesProvider()
    return get_prices(provider, query)


def render_sidebar() -> UiInputs:
    st.sidebar.header("Controls")
    ticker_text = st.sidebar.text_input("Tickers", value=DEFAULT_TICKERS, help="Comma-separated list")

    today = date.today()
    default_start = today - timedelta(days=365)

    start_date = st.sidebar.date_input("Start date", value=default_start)
    end_date = st.sidebar.date_input("End date", value=today)

    price_field_label_map = {"Adj Close": "adj_close", "Close": "close"}
    price_field = st.sidebar.radio(
        "Price field",
        options=list(price_field_label_map.keys()),
        index=0,
    )
    price_field_value: PriceField = price_field_label_map[price_field]  # type: ignore[assignment]

    normalize = st.sidebar.checkbox("Normalize to 100", value=False)
    log_scale = st.sidebar.checkbox("Log scale", value=False)
    show_table = st.sidebar.checkbox("Show summary table", value=True)

    tickers = parse_tickers(ticker_text)
    config = DashboardState(price_field=price_field_value, normalize=normalize, log_scale=log_scale, show_table=show_table)

    return UiInputs(tickers=tickers, start_date=start_date, end_date=end_date, config=config)


def main() -> None:
    st.set_page_config(page_title="Equity Dashboard", layout="wide")
    st.title("Equity Prices Dashboard")
    st.caption("Streamlit + yfinance + Plotly")

    inputs = render_sidebar()

    if inputs.start_date > inputs.end_date:
        st.error("Start date must be on or before end date.")
        return

    if not inputs.tickers:
        st.info("Add at least one ticker symbol to begin.")
        return

    try:
        with st.spinner("Fetching prices..."):
            prices_long = load_prices_cached(
                tuple(inputs.tickers),
                inputs.start_date,
                inputs.end_date,
                "1d",
                False,
            )
    except DataRetrievalError as err:
        st.error(f"Failed to fetch data: {err}")
        return

    if prices_long.empty:
        st.error("No data returned for the selected inputs.")
        return

    requested = set(inputs.tickers)
    available = set(prices_long["ticker"].unique())
    missing = requested - available
    if missing:
        st.warning(f"No data returned for: {', '.join(sorted(missing))}")

    price_matrix = get_price_matrix(prices_long, inputs.config.price_field)
    if inputs.config.normalize:
        price_matrix = get_normalized_matrix(price_matrix)

    title = f"{inputs.config.price_field.replace('_', ' ').title()} prices"
    if inputs.config.normalize:
        title += " (rebased to 100)"

    chart = make_price_chart(price_matrix, title=title, log_y=inputs.config.log_scale)
    st.plotly_chart(chart, use_container_width=True)

    summary = build_summary_table(prices_long, inputs.config.price_field)
    if inputs.config.show_table:
        st.subheader("Summary")
        if summary.empty:
            st.info("Summary not available for the selected inputs.")
        else:
            display_summary = summary.set_index("ticker")
            display_summary["total_return_pct"] = display_summary["total_return_pct"].map("{:.2f}%".format)
            st.dataframe(display_summary)

    st.subheader("Downloads")
    st.download_button(
        "Download canonical (long) CSV",
        data=prices_long.to_csv(index=False),
        file_name="prices_long.csv",
        mime="text/csv",
    )
    if not price_matrix.empty:
        st.download_button(
            "Download matrix CSV",
            data=price_matrix.to_csv(),
            file_name="prices_matrix.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
