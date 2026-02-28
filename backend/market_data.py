"""
market_data.py — fetches live macroeconomic inputs for the DCF model.

Functions
---------
get_risk_free_rate()      -> (float, str)   current 10-yr Treasury yield
get_equity_risk_premium() -> (float, str)   implied equity risk premium

Both functions cache their result for 24 hours and fall back to the
hardcoded defaults in config.py on any network / parse failure.
"""

from typing import Tuple

import requests
from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv

from .cache import TTLCache
from .config import FALLBACK_ERP, FALLBACK_RISK_FREE_RATE

load_dotenv(find_dotenv())

_CACHE_TTL = 86_400   # 24 hours in seconds
_cache = TTLCache(default_ttl=_CACHE_TTL)


# ── 10-Year Treasury yield (FRED) ─────────────────────────────────────────────

def get_risk_free_rate() -> Tuple[float, str]:
    """
    Return the current 10-year US Treasury yield as a decimal (e.g. 0.043).

    Fetches from FRED's public CSV endpoint (DGS10).  Result is cached for
    24 hours; falls back to FALLBACK_RISK_FREE_RATE from config on any error.
    """
    key = "risk_free_rate"
    cached = _cache.get_with_source(key)
    if cached is not None:
        value, source = cached
        print(f"[market_data] risk_free_rate cache hit: {value:.4f} ({source})")
        return value, source

    try:
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "equity-research-tool research@equityresearch.com"},
        )
        resp.raise_for_status()

        # Each line after the header: "2024-01-02,4.00" or "2024-01-03,."
        lines = resp.text.strip().splitlines()
        value = None
        for line in reversed(lines[1:]):   # skip CSV header
            parts = line.split(",")
            if len(parts) == 2 and parts[1].strip() not in (".", ""):
                value = float(parts[1].strip()) / 100.0
                break

        if value is None:
            raise ValueError("No valid DGS10 observation found in FRED response")

        source = "FRED DGS10 (live)"
        _cache.set_with_source(key, value, source)
        print(f"[market_data] risk_free_rate fetched: {value:.4f} ({source})")
        return value, source

    except Exception as exc:
        print(f"[market_data] risk_free_rate fetch failed ({exc}); using fallback")
        return FALLBACK_RISK_FREE_RATE, "config fallback"


# ── Equity Risk Premium (Damodaran) ───────────────────────────────────────────

def get_equity_risk_premium() -> Tuple[float, str]:
    """
    Return the current implied equity risk premium as a decimal (e.g. 0.055).

    Scrapes Damodaran's implied ERP data page.  The last numeric value in the
    1–20 % range found in table cells is taken as the most recent ERP.
    Result is cached for 24 hours; falls back to FALLBACK_ERP on any error.
    """
    key = "equity_risk_premium"
    cached = _cache.get_with_source(key)
    if cached is not None:
        value, source = cached
        print(f"[market_data] equity_risk_premium cache hit: {value:.4f} ({source})")
        return value, source

    try:
        url = (
            "http://pages.stern.nyu.edu/~adamodar/"
            "New_Home_Page/datafile/implprem.html"
        )
        resp = requests.get(
            url, timeout=15,
            headers={"User-Agent": "equity-research-tool research@equityresearch.com"},
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Walk every table cell; collect values in the 1–20 % range.
        # The implied ERP appears as a bare percentage number (e.g. "5.50" or
        # "5.50%").  The last such value in the table is the most recent year.
        candidates = []
        for td in soup.find_all("td"):
            text = td.get_text(strip=True).replace("%", "").replace(",", "")
            try:
                val = float(text)
                if 1.0 <= val <= 20.0:
                    candidates.append(val / 100.0)
            except ValueError:
                continue

        if not candidates:
            raise ValueError("No ERP candidates found in Damodaran page")

        value = candidates[-1]   # most recent entry is last in the table
        source = "Damodaran implied ERP (live)"
        _cache.set_with_source(key, value, source)
        print(f"[market_data] equity_risk_premium fetched: {value:.4f} ({source})")
        return value, source

    except Exception as exc:
        print(f"[market_data] equity_risk_premium fetch failed ({exc}); using fallback")
        return FALLBACK_ERP, "config fallback"
