"""Plotly figure builders for price charts."""

from __future__ import annotations

import plotly.graph_objects as go
import pandas as pd


def make_price_chart(prices_matrix: pd.DataFrame, title: str, log_y: bool = False, show_markers: bool = False) -> go.Figure:
    """Build a multi-ticker line chart from a price matrix."""
    fig = go.Figure()

    if prices_matrix.empty:
        fig.add_annotation(text="No data to display", showarrow=False, x=0.5, y=0.5, xref="paper", yref="paper")
        fig.update_layout(title=title, template="plotly_white")
        return fig

    mode = "lines+markers" if show_markers else "lines"
    
    for ticker in prices_matrix.columns:
        fig.add_trace(
            go.Scatter(
                x=prices_matrix.index,
                y=prices_matrix[ticker],
                mode=mode,
                name=str(ticker),
                marker=dict(size=4) if show_markers else None
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Price",
        hovermode="x unified",
        template="plotly_white",
        legend_title="Ticker",
    )

    if log_y:
        fig.update_yaxes(type="log")

    return fig

