"""
finviz_fetcher.py — scrapes Finviz for supplementary stock data.

Provides:
  - Peer company lists (replaces paywalled FMP stock-peers endpoint)
  - 90+ fundamental metrics (PEG, forward P/E, analyst target, etc.)
  - Analyst consensus ratings

Uses the unofficial `finvizfinance` library (pip install finvizfinance).
No API key required. Free for low-volume academic use.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from finvizfinance.quote import finvizfinance


# ── Data container ────────────────────────────────────────────────────────────

@dataclass
class FinvizData:
    ticker: str
    peers: List[str] = field(default_factory=list)
    metrics: Dict[str, str] = field(default_factory=dict)  # all 90+ raw metrics

    # Parsed numeric fields
    analyst_target: Optional[float] = None
    analyst_recom: Optional[float] = None   # 1=Strong Buy → 5=Sell
    forward_pe: Optional[float] = None
    peg: Optional[float] = None
    ps: Optional[float] = None
    pb: Optional[float] = None
    pfcf: Optional[float] = None
    beta: Optional[float] = None

    # String fields (contain % signs)
    roe: Optional[str] = None
    dividend_yield: Optional[str] = None
    insider_own: Optional[str] = None
    inst_own: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_float(value: str) -> Optional[float]:
    """Try to parse a Finviz metric string as float. Returns None if '-' or invalid."""
    if value is None or value == "-" or value == "":
        return None
    try:
        # Remove % sign if present (some fields like ROE are "45.97%")
        clean = str(value).replace("%", "").replace(",", "").strip()
        return float(clean)
    except (ValueError, TypeError):
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_finviz(ticker: str) -> FinvizData:
    """
    Scrape Finviz for fundamentals and peer list.

    Returns a FinvizData with whatever data could be fetched.
    On any failure, returns a minimal FinvizData with empty peers and None fields.
    """
    ticker = ticker.upper()
    result = FinvizData(ticker=ticker)

    try:
        stock = finvizfinance(ticker)

        # Fundamentals — dict of 90+ key-value pairs
        fundament = stock.ticker_fundament()
        result.metrics = fundament
        print(f"[Finviz] {ticker}: fetched {len(fundament)} metrics")

        # Peers — list of ticker strings
        try:
            peers = stock.ticker_peer()
            result.peers = peers if isinstance(peers, list) else []
            print(f"[Finviz] {ticker}: {len(result.peers)} peers — {result.peers}")
        except Exception as exc:
            print(f"[Finviz] {ticker}: peer fetch failed — {exc}")
            result.peers = []

        # Parse key numeric fields
        result.analyst_target = _parse_float(fundament.get("Target Price", "-"))
        result.analyst_recom = _parse_float(fundament.get("Recom", "-"))
        result.forward_pe = _parse_float(fundament.get("Forward P/E", "-"))
        result.peg = _parse_float(fundament.get("PEG", "-"))
        result.ps = _parse_float(fundament.get("P/S", "-"))
        result.pb = _parse_float(fundament.get("P/B", "-"))
        result.pfcf = _parse_float(fundament.get("P/FCF", "-"))
        result.beta = _parse_float(fundament.get("Beta", "-"))

        # String fields (keep as-is with % signs)
        result.roe = fundament.get("ROE", None)
        result.dividend_yield = fundament.get("Dividend %", None)
        result.insider_own = fundament.get("Insider Own", None)
        result.inst_own = fundament.get("Inst Own", None)

        print(
            f"[Finviz] {ticker}: Target=${result.analyst_target}  "
            f"Recom={result.analyst_recom}  PEG={result.peg}  "
            f"FwdPE={result.forward_pe}  Beta={result.beta}"
        )

    except Exception as exc:
        print(f"[Finviz] {ticker}: FAILED — {type(exc).__name__}: {exc}")

    # Polite delay to avoid hammering Finviz
    time.sleep(1)
    return result
