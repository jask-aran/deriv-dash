# Dashboard Plan: Interactive Equity Prices with Streamlit + yfinance

## Architecture (modular, Streamlit-first, Dash-ready)
- Core principle: UI layer (Streamlit/Dash) should only orchestrate; all "real work" lives in UI-agnostic modules.
- Separate concerns into four layers:
  1. **Domain models**: typed configs + validated inputs
  2. **Data access**: yfinance adapter + normalization + caching hooks
  3. **Analytics**: pure transforms/summary tables
  4. **Viz**: Plotly figure builders (shared by Streamlit and Dash)

## Proposed repo layout
- `main.py` (Streamlit entry point only; minimal logic)
- `src/deriv_dash/`
  - `__init__.py`
  - `domain.py` (dataclasses / types)
  - `services/`
    - `prices_service.py` (orchestrates fetch + cleanup + outputs for UI)
  - `data/`
    - `providers.py` (Provider/Protocol definitions)
    - `yfinance_provider.py` (yfinance implementation)
    - `normalization.py` (reshape/clean to canonical schema)
  - `analytics/`
    - `returns.py` (daily returns, cumulative returns)
    - `summary.py` (metrics table: last, return, vol, drawdown later)
  - `viz/`
    - `price_charts.py` (Plotly multi-ticker line chart)
  - `utils/`
    - `errors.py` (custom exceptions)
    - `logging.py` (optional, minimal)
- `tests/` (optional, but good foundation)
  - `test_normalization.py`
  - `test_returns.py`

This keeps Streamlit/Dash "swap" mostly confined to `main.py` vs `dash_app.py`, while `src/deriv_dash/*` stays unchanged.

## Canonical data contract (the key to scalability)
Normalize everything to a single long-form DataFrame:

Columns:
- `date` (datetime64[ns], normalized to date for daily bars)
- `ticker` (string)
- `close` (float)
- `adj_close` (float, nullable if not provided)
- `volume` (float/int, nullable)

This avoids the classic yfinance "single-ticker returns Series, multi-ticker returns multi-index columns" mess and makes charts/tables consistent.

Also provide convenience "wide" views when needed:
- wide prices: index=`date`, columns=`ticker`, values=`close` or `adj_close`

## Domain types (forward-thinking)
In `src/deriv_dash/domain.py`:
- `PriceField = Literal["close", "adj_close"]`
- `PriceQuery` dataclass:
  - `tickers: list[str]`
  - `start: date`
  - `end: date`
  - `interval: Literal["1d"]` (future-proof but fixed for now)
  - `auto_adjust: bool` (we can keep it `False` initially to preserve both close/adj_close; see note below)
- `DashboardState` / `ViewConfig` dataclass:
  - `price_field: PriceField`
  - `normalize: bool` (rebased to 100)
  - `log_scale: bool` (optional)
  - `show_table: bool` etc.

## Data layer plan (yfinance, daily only)
In `src/deriv_dash/data/providers.py`:
- Define a `PricesProvider` protocol:
  - `fetch_prices(query: PriceQuery) -> pd.DataFrame` (returns canonical long form)

In `src/deriv_dash/data/yfinance_provider.py`:
- Implement `YFinancePricesProvider(PricesProvider)`
- Use `yfinance.download(...)` with:
  - `tickers=" ".join(query.tickers)` (or list)
  - `start/end`
  - `interval="1d"`
  - `group_by="ticker"`
  - `auto_adjust=False` (recommended so you can display BOTH Close and Adj Close)
- Normalize with a dedicated function in `normalization.py` that handles:
  - single vs multiple tickers
  - columns like `("AAPL","Close")` vs `"Close"` edge cases
  - missing `Adj Close` for some assets (rare, but handle)

**Caching strategy (UI-agnostic)**
- Keep provider pure (no Streamlit dependency).
- Add caching at the service layer with a "cache hook":
  - Streamlit uses `st.cache_data`
  - Dash later can use `flask-caching` or `diskcache`
- This avoids having Streamlit decorators leaking into your core modules.

## Service layer (what Streamlit/Dash calls)
In `src/deriv_dash/services/prices_service.py`:
- `get_prices(provider, query) -> pd.DataFrame` (canonical long)
- `get_price_matrix(prices_long, field) -> pd.DataFrame` (wide)
- `get_normalized_matrix(prices_matrix) -> pd.DataFrame` (rebased)
- `build_summary(prices_long, field) -> pd.DataFrame` (per ticker: last price, total return over selected window)

This becomes the stable "API" your UIs depend on.

## Visualization layer (shared Plotly)
In `src/deriv_dash/viz/price_charts.py`:
- `make_price_chart(prices_matrix: pd.DataFrame, title: str, log_y: bool) -> plotly.graph_objects.Figure`
- It only receives already-prepared data (wide matrix), so it's reusable in Dash.

No overlays for now—keep chart simple and fast.

## Streamlit UI plan (`main.py`)
**Sidebar inputs**
- Tickers: text input (`AAPL, MSFT, SPY`) → parse to list, uppercase, strip, dedupe
- Date range: start/end (default: last 365 trading days)
- Price field: radio/select (`Adj Close`, `Close`)
- Options: normalize (rebased), log scale
- Buttons: "Refresh data" (optional; otherwise auto-refresh on changes)

**Main**
- Title + small status line (tickers count, date window)
- Plotly chart (multi-line, one per ticker)
- Summary table
- Download CSV buttons:
  - long canonical dataset
  - wide matrix for selected field (optional)

**Error/empty states**
- If no tickers: show help text
- If yfinance returns empty: show `st.error("No data returned...")` with suggestions
- If partial tickers missing: show warning and continue with available ones

## Dash "path open" (what we do now to enable it later)
- Keep `main.py` thin; do not put business logic in it.
- Plotly figures come from `viz/` functions.
- Data fetching is behind `PricesProvider` + service functions.
- Later, a `dash_app.py` can:
  - reuse the same provider + services
  - use the same Plotly figure builders
  - replace `st.cache_data` with Dash/flask caching

## Concrete implementation steps (order of work)
1. Create `src/deriv_dash/` package skeleton + domain types
2. Implement yfinance provider + robust normalization into canonical long DataFrame
3. Implement service functions (matrix conversion, normalization, summary table)
4. Implement Plotly price chart builder (multi-ticker)
5. Build `main.py` Streamlit UI wiring everything together
6. Add 2–4 small pytest tests for normalization + returns/summary math (optional but recommended)

## One decision to confirm (important)
yfinance has `auto_adjust=True` which "bakes in" adjustments and effectively removes the need for Adj Close, but you asked to support both Close and Adj Close. To support both cleanly, I recommend:
- `auto_adjust=False` always, and expose `price_field = close|adj_close` in the UI.

If you agree, I'll proceed with that assumption when we implement.

Anything you want as default behavior?
- Default `price_field`: `adj_close` (common for longer horizons) or `close` (raw)?