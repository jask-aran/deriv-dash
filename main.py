"""Streamlit entrypoint for the equity prices dashboard."""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# --- Ensure src is on path for local imports ---
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

# --- yfinance Initialization ---
from deriv_dash.utils import yf_patch  # noqa: F401
import yfinance as yf
# -------------------------------

import pandas as pd
import streamlit as st

from deriv_dash import DashboardState, PriceField, PriceQuery  # noqa: E402
from deriv_dash.data import YFinancePricesProvider  # noqa: E402
from deriv_dash.services import build_summary_table, get_normalized_matrix, get_price_matrix, get_prices  # noqa: E402
from deriv_dash.services.discovery import TICKER_UNIVERSE, get_discovery_insights, get_ticker_universe_metadata  # noqa: E402
from deriv_dash.utils import DataRetrievalError  # noqa: E402
from deriv_dash.viz import make_price_chart  # noqa: E402

DEFAULT_TICKERS = ["AAPL", "MSFT", "SPY"]


@dataclass
class UiInputs:
    tickers: list[str]
    start_date: date
    end_date: date
    config: DashboardState


def parse_tickers(raw: str) -> list[str]:
    parts = [part.strip().upper() for raw_part in raw.replace(";", ",").split(",")]
    tickers = [part for part in parts if part]
    deduped = list(dict.fromkeys(tickers))
    return deduped


@st.cache_data(show_spinner=False)
def load_prices_cached(
    tickers: tuple[str, ...], start: date, end: date, interval: str, auto_adjust: bool, include_extended: bool
) -> pd.DataFrame:
    query = PriceQuery(
        tickers=list(tickers), 
        start=start, 
        end=end, 
        interval=interval, 
        auto_adjust=auto_adjust,
        include_extended=include_extended
    )
    provider = YFinancePricesProvider()
    return get_prices(provider, query)


def render_sidebar() -> UiInputs:
    st.sidebar.header("Dashboard Controls")
    
    with st.sidebar.expander("📂 Data Selection", expanded=True):
        # Initialize session state for tickers if not present
        if "selected_tickers" not in st.session_state:
            st.session_state.selected_tickers = DEFAULT_TICKERS

        # Initialize dates in session state for synchronization with timeframe buttons
        today = date.today()
        if "start_date" not in st.session_state:
            st.session_state.start_date = today - timedelta(days=365)
        if "end_date" not in st.session_state:
            st.session_state.end_date = today

        # Use multiselect with current selections preserved in options
        # We use a key for stable state management to prevent disappearing tickers
        options = sorted(list(set(TICKER_UNIVERSE + st.session_state.selected_tickers)))
        st.multiselect(
            "Analysis Tickers",
            options=options,
            key="selected_tickers",
            help="Select from common assets or add custom ones below"
        )
        
        # Small helper to add any ticker (Streamlit multiselect doesn't allow direct typing of new options)
        new_ticker = st.text_input("Add Ticker", key="new_ticker_input", placeholder="e.g. BTC-USD").upper().strip()
        if new_ticker and new_ticker not in st.session_state.selected_tickers:
            st.session_state.selected_tickers.append(new_ticker)
            st.session_state.new_ticker_input = "" # Clear for next entry
            st.rerun()

        col1, col2 = st.columns(2)
        with col1:
            # Bind directly to session state keys for two-way sync
            st.date_input("Start date", key="start_date")
        with col2:
            st.date_input("End date", key="end_date")

    with st.sidebar.expander("⚙️ View Settings", expanded=True):
        price_field_label_map = {"Adj Close": "adj_close", "Close": "close"}
        price_field = st.radio(
            "Price field",
            options=list(price_field_label_map.keys()),
            index=0,
            horizontal=True
        )
        price_field_value: PriceField = price_field_label_map[price_field]  # type: ignore[assignment]

        st.divider()
        normalize = st.checkbox("Normalize to 100", value=False, help="Rebase all series to 100 at the start date")
        log_scale = st.checkbox("Log scale", value=False)
        show_table = st.checkbox("Show summary table", value=True)
        include_extended = st.checkbox("Show Extended Hours", value=False, help="Include pre-market and after-hours data")

    all_tickers = st.session_state.selected_tickers
    config = DashboardState(
        price_field=price_field_value, 
        normalize=normalize, 
        log_scale=log_scale, 
        show_table=show_table,
        include_extended=include_extended
    )

    return UiInputs(
        tickers=all_tickers, 
        start_date=st.session_state.start_date, 
        end_date=st.session_state.end_date, 
        config=config
    )


def set_timeframe(days: int | None = None, ytd: bool = False, max_period: bool = False) -> None:
    """Callback to update session state dates for timeframe buttons."""
    today = date.today()
    if ytd:
        st.session_state.start_date = date(today.year, 1, 1)
    elif max_period:
        st.session_state.start_date = date(2000, 1, 1)
    elif days:
        st.session_state.start_date = today - timedelta(days=days)
    st.session_state.end_date = today


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
        delta_days = (inputs.end_date - inputs.start_date).days
        interval = "1d"
        if delta_days <= 2:
            interval = "1m"
        elif delta_days <= 7:
            interval = "5m"
        elif delta_days <= 30:
            interval = "1h"

        with st.spinner(f"Fetching prices ({interval} interval)..."):
            prices_long = load_prices_cached(
                tuple(inputs.tickers),
                inputs.start_date,
                inputs.end_date,
                interval,
                False,
                inputs.config.include_extended,
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

    # --- Persistent Chart & Timeframe Tools ---
    st.divider()
    
    # Timeframe selection row
    tf_row = st.columns([1, 1, 1, 1, 1, 3]) # Last one for spacing
    
    tf_row[0].button("1W", on_click=set_timeframe, kwargs={"days": 7}, use_container_width=True)
    tf_row[1].button("1M", on_click=set_timeframe, kwargs={"days": 30}, use_container_width=True)
    tf_row[2].button("YTD", on_click=set_timeframe, kwargs={"ytd": True}, use_container_width=True)
    tf_row[3].button("1Y", on_click=set_timeframe, kwargs={"days": 365}, use_container_width=True)
    tf_row[4].button("MAX", on_click=set_timeframe, kwargs={"max_period": True}, use_container_width=True)

    # Main Chart
    price_matrix = get_price_matrix(prices_long, inputs.config.price_field)
    if inputs.config.normalize:
        price_matrix = get_normalized_matrix(price_matrix)

    title = f"{inputs.config.price_field.replace('_', ' ').title()} prices"
    if interval != "1d":
        title += f" ({interval} interval)"
    if inputs.config.normalize:
        title += " (rebased to 100)"

    chart = make_price_chart(
        price_matrix, 
        title=title, 
        log_y=inputs.config.log_scale,
        show_markers=(interval != "1d")
    )
    st.plotly_chart(chart, use_container_width=True)

    # --- Sub-content Tabs ---
    tab_discovery, tab_table, tab_download = st.tabs(["🔍 Discovery", "📊 Summary", "📥 Downloads"])

    with tab_discovery:
        st.subheader("Market Discovery & Insights")
        with st.spinner("Fetching discovery meta..."):
            universe_meta = get_ticker_universe_metadata()
            top_mcap, top_vol = get_discovery_insights(universe_meta)
        
        col_mcap, col_vol = st.columns(2)
        
        with col_mcap:
            st.markdown("#### 💎 Top Market Cap")
            st.caption("The largest companies in our universe")
            # Format Market Cap for display
            top_mcap_display = top_mcap.copy()
            top_mcap_display["Market Cap"] = top_mcap_display["Market Cap"].apply(lambda x: f"${x/1e12:.2f}T" if x >= 1e12 else f"${x/1e9:.2f}B")
            st.dataframe(top_mcap_display[["Ticker", "Name", "Market Cap", "Sector"]], hide_index=True, width="stretch")
            
        with col_vol:
            st.markdown("#### ⚡ High Volatility")
            st.caption("Highest annualized 30-day volatility")
            top_vol_display = top_vol.copy()
            top_vol_display["Volatility (30d)"] = top_vol_display["Volatility (30d)"].apply(lambda x: f"{x*100:.1f}%")
            st.dataframe(top_vol_display[["Ticker", "Name", "Volatility (30d)", "Sector"]], hide_index=True, width="stretch")
            
        st.info("💡 Use the sidebar to add these tickers to your active analysis.")
        
        if st.button("🔄 Clear Discovery Cache", help="Force refresh of volatility and metadata"):
            # Only clear the specific discovery functions to avoid a full app hang
            get_ticker_universe_metadata.clear()
            get_universe_volatility.clear()
            st.rerun()

    with tab_table:
        summary = build_summary_table(prices_long, inputs.config.price_field)
        if inputs.config.show_table:
            st.subheader("Performance Summary")
            if summary.empty:
                st.info("Summary not available for the selected inputs.")
            else:
                display_summary = summary.set_index("ticker")
                display_summary["total_return_pct"] = display_summary["total_return_pct"].map("{:.2f}%".format)
                st.dataframe(display_summary, width="stretch")
        else:
            st.info("Table display is disabled in settings.")

    with tab_download:
        st.subheader("Data Export")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "Download canonical (long) CSV",
                data=prices_long.to_csv(index=False),
                file_name=f"prices_long_{date.today()}.csv",
                mime="text/csv",
                width="stretch"
            )
        with c2:
            if not price_matrix.empty:
                st.download_button(
                    "Download matrix CSV",
                    data=price_matrix.to_csv(),
                    file_name=f"prices_matrix_{date.today()}.csv",
                    mime="text/csv",
                    width="stretch"
                )


if __name__ == "__main__":
    main()
