# Repository Guidelines

## Project Structure & Modules
Core code lives in `main.py` (current CLI entry point). Project metadata and dependencies are in `pyproject.toml`; README is intentionally minimal. A `.venv` is created by uv for local work; keep any generated artifacts out of version control. Place new app modules under `src/` or alongside `main.py` until a clearer layout emerges; keep datasets in `data/` (git-ignored) and reusable charts/utils in `analytics/` to separate sourcing, transformation, and visualization logic.

## Environment, Build & Run
Install tools: `uv venv` then `source .venv/bin/activate`. Sync dependencies (Streamlit, Plotly, Dash, numpy/pandas/scipy, statsmodels, scikit-learn, yfinance) with `uv sync`. Add new libs with `uv add <package>` to persist them. Run the current entry point via `uv run python main.py`. For a Streamlit prototype, use `uv run streamlit run main.py`; for Dash, expose a `server` or `app` callable and launch with `uv run python main.py`.

## Coding Style & Naming Conventions
Target Python 3.14. Follow PEP 8 with 4-space indents and snake_case for functions/variables; use PascalCase for classes and kebab-case for CLI flags if added. Prefer pure, typed functions for transforms; keep plotting/layout code separate from data fetching to ease reuse across Streamlit and Dash. Document module intent with short docstrings and inline comments only where logic is non-obvious.

## Testing Guidelines
No tests exist yet; prefer `pytest` in `tests/` mirroring module paths (e.g., `tests/test_main.py`). Use given/when/then naming or descriptive test function names. Run with `uv run pytest` once added; aim to cover data cleaning branches and callbacks/state updates. For notebooks or exploratory scripts, pin expected outputs or sample CSVs in `tests/fixtures/` and stub external calls (e.g., yfinance) to keep runs deterministic.

## Commit & Pull Request Guidelines
Use imperative, concise commit messages (`feat: add streamlit entrypoint`, `fix: guard empty ticker input`). Keep each commit scoped to one concern. PRs should include a short summary, screenshots/GIFs for UI changes, and linked issue/ticket IDs. Note any new dependencies or migrations, and list manual test steps (commands run, sample tickers/dates used). Avoid committing credentials or raw datasets; prefer `.env.example` for required keys.
