"""
comps.py — fetches peer companies and valuation multiples for a
comparable-company analysis (Comps) tab.

Uses FMP endpoints:
  - stock-peers: get list of peer tickers
  - key-metrics-ttm: TTM valuation multiples per ticker
  - profile: company name, market cap, sector

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"
MAX_PEERS = 8  # cap peers to keep API calls reasonable


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

def _get_api_key() -> str:
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")
    return key


def _fetch_json(url: str, params: dict, timeout: int = 15):
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _safe_float(d: dict, key: str) -> Optional[float]:
    val = d.get(key)
    if val is None:
        return None
    try:
        f = float(val)
        return f if f != 0 and abs(f) < 1e10 else (f if f == 0 else None)
    except (ValueError, TypeError):
        return None


def _median(values: List[float]) -> Optional[float]:
    clean = sorted([v for v in values if v is not None and v > 0])
    if not clean:
        return None
    n = len(clean)
    mid = n // 2
    if n % 2 == 0:
        return (clean[mid - 1] + clean[mid]) / 2
    return clean[mid]


def _build_comp_entry(
    ticker: str, profile: dict, metrics: dict, is_target: bool = False,
) -> CompEntry:
    """Build a CompEntry from FMP profile and key-metrics-ttm responses."""
    return CompEntry(
        ticker=ticker,
        company_name=profile.get("companyName") or ticker,
        market_cap=float(profile.get("mktCap") or profile.get("marketCap") or 0),
        sector=profile.get("sector") or "",
        industry=profile.get("industry") or "",
        price=float(profile.get("price") or 0),
        pe_ratio=_safe_float(metrics, "peRatioTTM"),
        ev_to_ebitda=_safe_float(metrics, "enterpriseValueOverEBITDATTM"),
        price_to_sales=_safe_float(metrics, "priceToSalesRatioTTM"),
        price_to_book=_safe_float(metrics, "priceToBookRatioTTM"),
        ev_to_revenue=_safe_float(metrics, "evToSalesTTM"),
        peg_ratio=_safe_float(metrics, "pegRatioTTM"),
        gross_margin=_safe_float(metrics, "grossProfitMarginTTM"),
        operating_margin=_safe_float(metrics, "operatingProfitMarginTTM"),
        net_margin=_safe_float(metrics, "netProfitMarginTTM"),
        roe=_safe_float(metrics, "returnOnEquityTTM"),
        roic=_safe_float(metrics, "returnOnCapitalEmployedTTM"),
        revenue_growth=_safe_float(metrics, "revenueGrowthTTM"),
        eps_growth=_safe_float(metrics, "epsgrowthTTM"),
        dividend_yield=_safe_float(metrics, "dividendYieldTTM"),
        debt_to_equity=_safe_float(metrics, "debtToEquityTTM"),
        is_target=is_target,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_comps(ticker: str) -> CompsResult:
    """
    Fetch peer companies and their valuation multiples for comparable analysis.
    """
    api_key = _get_api_key()
    ticker = ticker.upper()

    # Step 1: Get peers
    try:
        peers_data = _fetch_json(
            f"{FMP_BASE_URL}/stock-peers",
            {"symbol": ticker, "apikey": api_key},
        )
        if peers_data and isinstance(peers_data, list) and len(peers_data) > 0:
            peer_list = peers_data[0].get("peersList") or []
        elif peers_data and isinstance(peers_data, dict):
            peer_list = peers_data.get("peersList") or []
        else:
            peer_list = []
    except Exception as exc:
        print(f"[Comps] Peers fetch failed: {exc}")
        peer_list = []

    # Limit peers and ensure target is included
    peer_tickers = [p for p in peer_list if p != ticker][:MAX_PEERS]
    all_tickers = [ticker] + peer_tickers

    print(f"[Comps] {ticker}: {len(peer_tickers)} peers found: {peer_tickers}")

    # Step 2: Fetch profile and key-metrics-ttm for each ticker
    entries: List[CompEntry] = []
    for t in all_tickers:
        try:
            # Profile
            prof_data = _fetch_json(
                f"{FMP_BASE_URL}/profile",
                {"symbol": t, "apikey": api_key},
            )
            prof = prof_data[0] if prof_data else {}

            # Key metrics TTM
            met_data = _fetch_json(
                f"{FMP_BASE_URL}/key-metrics-ttm",
                {"symbol": t, "apikey": api_key},
            )
            met = met_data[0] if met_data else {}

            entry = _build_comp_entry(t, prof, met, is_target=(t == ticker))
            entries.append(entry)
            print(f"[Comps]   {t}: PE={entry.pe_ratio}  EV/EBITDA={entry.ev_to_ebitda}  P/S={entry.price_to_sales}")

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
