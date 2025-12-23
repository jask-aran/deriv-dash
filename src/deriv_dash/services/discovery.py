"""Service for ticker discovery and metadata fetching."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from ..utils import yf_patch  # noqa: F401
from ..data.yfinance_provider import YFinancePricesProvider
from ..domain import PriceQuery

logger = logging.getLogger(__name__)

# A curated universe of well-known liquid tickers
TICKER_UNIVERSE = [
    # Indices/ETFs
    "SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "VEU", "VWO", "GLD", "SLV",
    # Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX", "ADBE", "CRM",
    "INTC", "AMD", "CSCO", "ORCL", "TSM", "ASML", "AVGO", "TXN", "QCOM", "MU",
    # Finance
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "V", "MA", "AXP", "PYPL",
    # Healthcare
    "JNJ", "PFE", "UNH", "ABBV", "LLY", "MRK", "TMO", "ABT", "DHR", "BMY",
    # Consumer Standar/Discretionary
    "WMT", "COST", "PG", "KO", "PEP", "HD", "LOW", "NKE", "SBUX", "MCD", "DIS",
    # Energy/Industrials
    "XOM", "CVX", "SHEL", "BP", "TTE", "CAT", "DE", "GE", "HON", "BA", "UPS", "FDX",
]

@dataclass
class TickerMetadata:
    ticker: str
    name: str
    market_cap: Optional[float]
    sector: Optional[str]
    volatility_30d: Optional[float] = None

# Static mapping for curated universe names and sectors to avoid hundreds of slow API calls
UNIVERSE_DATA = {
    # Indices/ETFs
    "SPY": ("S&P 500 ETF Trust", "ETF"), "QQQ": ("Invesco QQQ Trust", "ETF"), 
    "DIA": ("SPDR Dow Jones Industrial Average ETF", "ETF"), "IWM": ("iShares Russell 2000 ETF", "ETF"),
    "VTI": ("Vanguard Total Stock Market ETF", "ETF"), "VOO": ("Vanguard S&P 500 ETF", "ETF"),
    "VEU": ("Vanguard FTSE All-World ex-US ETF", "ETF"), "VWO": ("Vanguard FTSE Emerging Markets ETF", "ETF"),
    "GLD": ("SPDR Gold Shares", "ETF"), "SLV": ("iShares Silver Trust", "ETF"),
    # Tech
    "AAPL": ("Apple Inc.", "Technology"), "MSFT": ("Microsoft Corporation", "Technology"),
    "GOOGL": ("Alphabet Inc.", "Technology"), "AMZN": ("Amazon.com Inc.", "Consumer Cyclical"),
    "META": ("Meta Platforms Inc.", "Communication Services"), "NVDA": ("NVIDIA Corporation", "Technology"),
    "TSLA": ("Tesla Inc.", "Consumer Cyclical"), "NFLX": ("Netflix Inc.", "Communication Services"),
    "ADBE": ("Adobe Inc.", "Technology"), "CRM": ("Salesforce Inc.", "Technology"),
    "INTC": ("Intel Corporation", "Technology"), "AMD": ("Advanced Micro Devices Inc.", "Technology"),
    "CSCO": ("Cisco Systems Inc.", "Technology"), "ORCL": ("Oracle Corporation", "Technology"),
    "TSM": ("Taiwan Semiconductor Manufacturing", "Technology"), "ASML": ("ASML Holding N.V.", "Technology"),
    "AVGO": ("Broadcom Inc.", "Technology"), "TXN": ("Texas Instruments Inc.", "Technology"),
    "QCOM": ("QUALCOMM Incorporated", "Technology"), "MU": ("Micron Technology Inc.", "Technology"),
    # Finance
    "JPM": ("JPMorgan Chase & Co.", "Financial Services"), "BAC": ("Bank of America Corp.", "Financial Services"),
    "WFC": ("Wells Fargo & Company", "Financial Services"), "C": ("Citigroup Inc.", "Financial Services"),
    "GS": ("The Goldman Sachs Group", "Financial Services"), "MS": ("Morgan Stanley", "Financial Services"),
    "BLK": ("BlackRock Inc.", "Financial Services"), "V": ("Visa Inc.", "Financial Services"),
    "MA": ("Mastercard Incorporated", "Financial Services"), "AXP": ("American Express Company", "Financial Services"),
    "PYPL": ("PayPal Holdings Inc.", "Financial Services"),
    # Healthcare
    "JNJ": ("Johnson & Johnson", "Healthcare"), "PFE": ("Pfizer Inc.", "Healthcare"),
    "UNH": ("UnitedHealth Group Inc.", "Healthcare"), "ABBV": ("AbbVie Inc.", "Healthcare"),
    "LLY": ("Eli Lilly and Company", "Healthcare"), "MRK": ("Merck & Co. Inc.", "Healthcare"),
    "TMO": ("Thermo Fisher Scientific Inc.", "Healthcare"), "ABT": ("Abbott Laboratories", "Healthcare"),
    "DHR": ("Danaher Corporation", "Healthcare"), "BMY": ("Bristol-Myers Squibb Company", "Healthcare"),
    # Consumer
    "WMT": ("Walmart Inc.", "Consumer Defensive"), "COST": ("Costco Wholesale Corp.", "Consumer Defensive"),
    "PG": ("Procter & Gamble Co.", "Consumer Defensive"), "KO": ("The Coca-Cola Company", "Consumer Defensive"),
    "PEP": ("PepsiCo Inc.", "Consumer Defensive"), "HD": ("The Home Depot Inc.", "Consumer Cyclical"),
    "LOW": ("Lowe's Companies Inc.", "Consumer Cyclical"), "NKE": ("NIKE Inc.", "Consumer Cyclical"),
    "SBUX": ("Starbucks Corporation", "Consumer Cyclical"), "MCD": ("McDonald's Corporation", "Consumer Cyclical"),
    "DIS": ("The Walt Disney Company", "Communication Services"),
    # Energy/Industrials
    "XOM": ("Exxon Mobil Corporation", "Energy"), "CVX": ("Chevron Corporation", "Energy"),
    "SHEL": ("Shell PLC", "Energy"), "BP": ("BP p.l.c.", "Energy"), "TTE": ("TotalEnergies SE", "Energy"),
    "CAT": ("Caterpillar Inc.", "Industrials"), "DE": ("Deere & Company", "Industrials"),
    "GE": ("GE Aerospace", "Industrials"), "HON": ("Honeywell International Inc.", "Industrials"),
    "BA": ("The Boeing Company", "Industrials"), "UPS": ("United Parcel Service Inc.", "Industrials"),
    "FDX": ("FedEx Corporation", "Industrials"),
}

@st.cache_data(ttl=86400)  # Cache for 24 hours
def get_ticker_universe_metadata() -> List[TickerMetadata]:
    """Fetch metadata for the curated ticker universe efficiently."""
    metadata_list = []
    
    # Process in chunks to fetch fast_info (much faster than .info)
    chunk_size = 20
    for i in range(0, len(TICKER_UNIVERSE), chunk_size):
        chunk = TICKER_UNIVERSE[i:i+chunk_size]
        tickers_obj = yf.Tickers(" ".join(chunk))
        
        for symbol in chunk:
            name, sector = UNIVERSE_DATA.get(symbol, (symbol, "Unknown"))
            try:
                # fast_info is significantly faster and doesn't require slow web scraping
                mkt_cap = tickers_obj.tickers[symbol].fast_info.get("marketCap")
                
                metadata_list.append(TickerMetadata(
                    ticker=symbol,
                    name=name,
                    market_cap=mkt_cap,
                    sector=sector
                ))
            except Exception as e:
                logger.warning(f"Failed to fetch fast_info for {symbol}: {e}")
                metadata_list.append(TickerMetadata(
                    ticker=symbol,
                    name=name,
                    market_cap=None,
                    sector=sector
                ))
    
    # Enrich with volatility
    vol_map = get_universe_volatility(TICKER_UNIVERSE)
    for meta in metadata_list:
        meta.volatility_30d = vol_map.get(meta.ticker)
        
    return metadata_list

@st.cache_data(ttl=86400)
def get_universe_volatility(tickers: List[str]) -> Dict[str, float]:
    """Calculate annualized 30-day volatility for a list of tickers in chunks."""
    end_date = date.today()
    start_date = end_date - timedelta(days=45)
    
    provider = YFinancePricesProvider()
    all_vols = {}
    
    # Process in chunks to avoid yfinance throttling/failures on large batches
    chunk_size = 20
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i : i + chunk_size]
        query = PriceQuery(
            tickers=chunk,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=True
        )
        
        try:
            logger.info(f"Fetching volatility data for chunk {i//chunk_size + 1} ({len(chunk)} tickers)")
            df = provider.fetch_prices(query)
            if df.empty:
                logger.warning(f"No price data found for chunk starting with {chunk[0]}")
                continue
                
            wide = df.pivot(index="date", columns="ticker", values="close")
            if len(wide) < 2:
                continue

            returns = wide.pct_change().dropna(how="all")
            recent_returns = returns.tail(30)
            
            if not recent_returns.empty:
                vols = recent_returns.std() * np.sqrt(252)
                all_vols.update(vols.dropna().to_dict())
                
        except Exception as e:
            logger.error(f"Failed to calculate volatility for chunk: {e}")
            continue
            
    logger.info(f"Total tickers with volatility calculated: {len(all_vols)}")
    return all_vols

def get_discovery_insights(metadata: List[TickerMetadata]):
    """Prepare insights for the discovery UI."""
    df = pd.DataFrame([
        {
            "Ticker": m.ticker,
            "Name": m.name,
            "Market Cap": m.market_cap,
            "Sector": m.sector,
            "Volatility (30d)": m.volatility_30d
        } for m in metadata
    ])
    
    top_mcap = df.dropna(subset=["Market Cap"]).sort_values("Market Cap", ascending=False).head(10)
    top_vol = df.dropna(subset=["Volatility (30d)"]).sort_values("Volatility (30d)", ascending=False).head(10)
    
    return top_mcap, top_vol
