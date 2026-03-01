"""
comps.py — fetches peer companies and valuation multiples for a
comparable-company analysis (Comps) tab.

Uses Finviz (via finvizfinance library) for all data:
  - Peer list from ticker_peer()
  - Fundamentals (90+ metrics) from ticker_fundament()

No API key required. Free for low-volume academic use.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional

from finvizfinance.quote import finvizfinance


MAX_PEERS = 8  # cap peers to keep scraping reasonable


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class CompEntry:
    ticker: str
    company_name: str
    market_cap: float           # raw number
    sector: str
    industry: str
    price: float

    # Valuation multiples (TTM)
    pe_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    ev_to_revenue: Optional[float] = None
    peg_ratio: Optional[float] = None

    # Profitability
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None

    # Growth
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None

    # Other
    dividend_yield: Optional[float] = None
    debt_to_equity: Optional[float] = None

    is_target: bool = False     # True for the ticker being analyzed


@dataclass
class CompsResult:
    ticker: str
    peers: List[CompEntry]
    # Summary stats
    median_pe: Optional[float] = None
    median_ev_ebitda: Optional[float] = None
    median_ps: Optional[float] = None
    median_pb: Optional[float] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_float(value) -> Optional[float]:
    """Parse a Finviz metric value as float. Returns None if '-' or invalid."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("-", "", "N/A"):
        return None
    try:
        clean = s.replace("%", "").replace(",", "").replace("$", "")
        f = float(clean)
        return f if abs(f) < 1e12 else None
    except (ValueError, TypeError):
        return None


def _parse_market_cap(value) -> float:
    """Parse Finviz market cap string like '267.29B' or '1.23T' into raw number."""
    if value is None:
        return 0.0
    s = str(value).strip().replace(",", "")
    if s in ("-", "", "N/A"):
        return 0.0
    try:
        if s.endswith("T"):
            return float(s[:-1]) * 1e12
        elif s.endswith("B"):
            return float(s[:-1]) * 1e9
        elif s.endswith("M"):
            return float(s[:-1]) * 1e6
        elif s.endswith("K"):
            return float(s[:-1]) * 1e3
        else:
            return float(s)
    except (ValueError, TypeError):
        return 0.0


def _median(values: List[float]) -> Optional[float]:
    clean = sorted([v for v in values if v is not None and v > 0])
    if not clean:
        return None
    n = len(clean)
    mid = n // 2
    if n % 2 == 0:
        return (clean[mid - 1] + clean[mid]) / 2
    return clean[mid]


def _build_comp_entry_from_finviz(
    ticker: str, fundament: dict, is_target: bool = False,
) -> CompEntry:
    """Build a CompEntry from Finviz ticker_fundament() data."""
    return CompEntry(
        ticker=ticker,
        company_name=fundament.get("Company") or ticker,
        market_cap=_parse_market_cap(fundament.get("Market Cap")),
        sector=fundament.get("Sector") or "",
        industry=fundament.get("Industry") or "",
        price=_parse_float(fundament.get("Price")) or 0.0,
        pe_ratio=_parse_float(fundament.get("P/E")),
        ev_to_ebitda=_parse_float(fundament.get("EV/EBITDA")),
        price_to_sales=_parse_float(fundament.get("P/S")),
        price_to_book=_parse_float(fundament.get("P/B")),
        ev_to_revenue=None,  # Finviz doesn't have a direct EV/Revenue field
        peg_ratio=_parse_float(fundament.get("PEG")),
        gross_margin=_pct_to_decimal(fundament.get("Gross Margin")),
        operating_margin=_pct_to_decimal(fundament.get("Oper. Margin")),
        net_margin=_pct_to_decimal(fundament.get("Profit Margin")),
        roe=_pct_to_decimal(fundament.get("ROE")),
        roic=_pct_to_decimal(fundament.get("ROI")),
        revenue_growth=_pct_to_decimal(fundament.get("Sales Q/Q")),
        eps_growth=_pct_to_decimal(fundament.get("EPS Q/Q")),
        dividend_yield=_pct_to_decimal(fundament.get("Dividend %")),
        debt_to_equity=_parse_float(fundament.get("Debt/Eq")),
        is_target=is_target,
    )


def _pct_to_decimal(value) -> Optional[float]:
    """Convert Finviz percentage string like '45.97%' to decimal 0.4597."""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("-", "", "N/A"):
        return None
    try:
        clean = s.replace("%", "").replace(",", "")
        return float(clean) / 100.0
    except (ValueError, TypeError):
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_comps(ticker: str, finviz_peers: list = None) -> CompsResult:
    """
    Fetch peer companies and their valuation multiples using Finviz.

    Args:
        ticker: The target stock ticker.
        finviz_peers: Optional pre-fetched peer list from finviz_fetcher.
                      If provided, skips the peer lookup for the target ticker.
    """
    ticker = ticker.upper()

    # Step 1: Get peers (use pre-fetched list or scrape fresh)
    if finviz_peers:
        peer_list = finviz_peers
        print(f"[Comps] Using pre-fetched Finviz peers: {peer_list}")
    else:
        try:
            stock = finvizfinance(ticker)
            peer_list = stock.ticker_peer()
            if not isinstance(peer_list, list):
                peer_list = []
            print(f"[Comps] Fetched Finviz peers for {ticker}: {peer_list}")
            time.sleep(0.5)
        except Exception as exc:
            print(f"[Comps] Peer fetch failed: {type(exc).__name__}: {exc}")
            peer_list = []

    # Limit peers and ensure target is included
    peer_tickers = [p for p in peer_list if p != ticker][:MAX_PEERS]
    all_tickers = [ticker] + peer_tickers

    print(f"[Comps] {ticker}: {len(peer_tickers)} peers to fetch: {peer_tickers}")

    # Step 2: Fetch fundamentals from Finviz for each ticker
    entries: List[CompEntry] = []
    for t in all_tickers:
        try:
            stock = finvizfinance(t)
            fundament = stock.ticker_fundament()
            entry = _build_comp_entry_from_finviz(t, fundament, is_target=(t == ticker))
            entries.append(entry)
            print(
                f"[Comps]   {t}: PE={entry.pe_ratio}  "
                f"EV/EBITDA={entry.ev_to_ebitda}  P/S={entry.price_to_sales}  "
                f"P/B={entry.price_to_book}"
            )
            # Polite delay between requests
            time.sleep(0.5)

        except Exception as exc:
            print(f"[Comps]   {t}: FAILED — {type(exc).__name__}: {exc}")
            continue

    # Step 3: Compute medians (excluding target)
    peer_entries = [e for e in entries if not e.is_target]

    result = CompsResult(
        ticker=ticker,
        peers=entries,
        median_pe=_median([e.pe_ratio for e in peer_entries]),
        median_ev_ebitda=_median([e.ev_to_ebitda for e in peer_entries]),
        median_ps=_median([e.price_to_sales for e in peer_entries]),
        median_pb=_median([e.price_to_book for e in peer_entries]),
    )

    print(
        f"[Comps] Medians — PE={result.median_pe}  "
        f"EV/EBITDA={result.median_ev_ebitda}  P/S={result.median_ps}  P/B={result.median_pb}"
    )

    return result
