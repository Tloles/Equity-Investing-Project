"""
alpaca_client.py — Live price and market data from Alpaca Markets API.

Replaces FMP for: current price, beta, market cap, shares outstanding,
52-week range, and historical bars for beta computation.

Requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv

from .cache import TTLCache

load_dotenv(find_dotenv(), override=True)

# Alpaca API endpoints
TRADING_BASE = "https://paper-api.alpaca.markets/v2"
DATA_BASE = "https://data.alpaca.markets/v2"

# Cache: 15-minute TTL for quotes
_quote_cache = TTLCache(default_ttl=900)


@dataclass
class AlpacaQuote:
    ticker: str
    price: float
    market_cap: Optional[float]
    beta: Optional[float]
    shares_outstanding: Optional[float]
    high_52w: Optional[float]
    low_52w: Optional[float]
    volume: Optional[int]


def _get_keys():
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise EnvironmentError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env"
        )
    return api_key, secret_key


def _headers():
    api_key, secret_key = _get_keys()
    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
        "Accept": "application/json",
    }


def fetch_historical(ticker: str, days: int = 365) -> List[dict]:
    """
    Fetch daily historical bars from Alpaca for beta computation.
    Returns list of {timestamp, open, high, low, close, volume}.
    """
    ticker = ticker.upper()
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    url = f"{DATA_BASE}/stocks/{ticker}/bars"
    params = {
        "start": start.strftime("%Y-%m-%dT00:00:00Z"),
        "end": end.strftime("%Y-%m-%dT00:00:00Z"),
        "timeframe": "1Day",
        "limit": 10000,
        "adjustment": "split",
    }

    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    bars = data.get("bars") or []
    print(f"[Alpaca] Historical bars for {ticker}: {len(bars)} days")
    return bars


def compute_beta(ticker: str, benchmark: str = "SPY", days: int = 365) -> float:
    """
    Compute beta from daily returns vs benchmark over the given period.
    Returns DEFAULT_BETA (1.0) if insufficient data.
    """
    try:
        stock_bars = fetch_historical(ticker, days)
        bench_bars = fetch_historical(benchmark, days)
    except Exception as exc:
        print(f"[Alpaca] Beta computation failed — {type(exc).__name__}: {exc}")
        return 1.0

    if len(stock_bars) < 30 or len(bench_bars) < 30:
        return 1.0

    # Align dates
    stock_closes = {b["t"][:10]: b["c"] for b in stock_bars}
    bench_closes = {b["t"][:10]: b["c"] for b in bench_bars}

    common_dates = sorted(set(stock_closes.keys()) & set(bench_closes.keys()))
    if len(common_dates) < 30:
        return 1.0

    # Compute daily returns
    stock_returns = []
    bench_returns = []
    for i in range(1, len(common_dates)):
        prev_d = common_dates[i - 1]
        curr_d = common_dates[i]
        s_prev = stock_closes[prev_d]
        s_curr = stock_closes[curr_d]
        b_prev = bench_closes[prev_d]
        b_curr = bench_closes[curr_d]

        if s_prev > 0 and b_prev > 0:
            stock_returns.append((s_curr - s_prev) / s_prev)
            bench_returns.append((b_curr - b_prev) / b_prev)

    if len(stock_returns) < 20:
        return 1.0

    # Covariance / variance
    n = len(stock_returns)
    mean_s = sum(stock_returns) / n
    mean_b = sum(bench_returns) / n

    cov = sum(
        (stock_returns[i] - mean_s) * (bench_returns[i] - mean_b)
        for i in range(n)
    ) / (n - 1)

    var_b = sum((bench_returns[i] - mean_b) ** 2 for i in range(n)) / (n - 1)

    if var_b == 0:
        return 1.0

    beta = cov / var_b
    # Clamp to reasonable range
    beta = max(0.1, min(3.0, beta))
    print(f"[Alpaca] Computed beta for {ticker}: {beta:.4f} (n={n} days)")
    return beta


def fetch_quote(ticker: str) -> AlpacaQuote:
    """
    Fetch latest quote/snapshot from Alpaca.
    Computes beta from historical data.
    Returns AlpacaQuote with price, beta, and market data.
    """
    ticker = ticker.upper()

    # Check cache
    cached = _quote_cache.get(f"quote:{ticker}")
    if cached is not None:
        print(f"[Alpaca] Quote cache hit for {ticker}")
        return cached

    hdrs = _headers()

    # Fetch latest trade for current price
    trade_url = f"{DATA_BASE}/stocks/{ticker}/trades/latest"
    resp = requests.get(trade_url, headers=hdrs, timeout=10)
    resp.raise_for_status()
    trade_data = resp.json()
    trade = trade_data.get("trade", {})
    price = float(trade.get("p", 0))

    if price <= 0:
        # Fallback: try latest quote (bid/ask midpoint)
        quote_url = f"{DATA_BASE}/stocks/{ticker}/quotes/latest"
        resp = requests.get(quote_url, headers=hdrs, timeout=10)
        resp.raise_for_status()
        quote_data = resp.json()
        q = quote_data.get("quote", {})
        bid = float(q.get("bp", 0))
        ask = float(q.get("ap", 0))
        if bid > 0 and ask > 0:
            price = (bid + ask) / 2

    if price <= 0:
        raise ValueError(f"Could not get price for {ticker} from Alpaca")

    print(f"[Alpaca] {ticker} price: ${price:.2f}")

    # Fetch snapshot for volume and 52-week data
    high_52w = None
    low_52w = None
    volume = None
    try:
        snap_url = f"{DATA_BASE}/stocks/{ticker}/snapshot"
        resp = requests.get(snap_url, headers=hdrs, timeout=10)
        resp.raise_for_status()
        snap = resp.json()
        daily_bar = snap.get("dailyBar", {})
        volume = int(daily_bar.get("v", 0)) or None
    except Exception:
        pass

    # Compute 52-week high/low from historical bars
    try:
        bars = fetch_historical(ticker, days=365)
        if bars:
            highs = [b["h"] for b in bars]
            lows = [b["l"] for b in bars]
            high_52w = max(highs)
            low_52w = min(lows)
    except Exception:
        pass

    # Compute beta
    beta = compute_beta(ticker)

    # Estimate shares outstanding and market cap
    # Alpaca doesn't provide these directly; we'll fill them from EDGAR later
    shares_outstanding = None
    market_cap = None

    quote = AlpacaQuote(
        ticker=ticker,
        price=round(price, 2),
        market_cap=market_cap,
        beta=round(beta, 4),
        shares_outstanding=shares_outstanding,
        high_52w=round(high_52w, 2) if high_52w else None,
        low_52w=round(low_52w, 2) if low_52w else None,
        volume=volume,
    )

    # Cache for 15 minutes
    _quote_cache.set(f"quote:{ticker}", quote, ttl=900)
    return quote
