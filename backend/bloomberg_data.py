"""
Bloomberg Pre-Export Data Reader

Reads JSON files from the data/ directory that were exported from
Bloomberg Excel templates via export_bloomberg.py.

This module provides the same data interface as FMP/Finviz fetchers
so it can slot into the existing data pipeline as a higher-priority source.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@dataclass
class BloombergProfile:
    """Company profile from Bloomberg BDP fields."""
    ticker: str = ""
    name: str = ""
    sector: str = ""
    industry: str = ""
    sub_industry: str = ""
    price: float = 0.0
    market_cap: float = 0.0
    beta: float = 1.0
    shares_outstanding: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
    description: str = ""
    exchange: str = ""
    currency: str = "USD"


@dataclass
class BloombergConsensus:
    """Analyst consensus from Bloomberg."""
    target_price: Optional[float] = None
    analyst_rating: Optional[float] = None  # 1-5 scale (1=Strong Buy)
    buy_ratings: Optional[int] = None
    hold_ratings: Optional[int] = None
    sell_ratings: Optional[int] = None
    consensus_eps_cy: Optional[float] = None
    consensus_eps_ny: Optional[float] = None
    forward_dps: Optional[float] = None
    forward_div_growth: Optional[float] = None


@dataclass
class BloombergValuation:
    """Valuation multiples from Bloomberg."""
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ev_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    peg_ratio: Optional[float] = None
    ev_revenue: Optional[float] = None
    enterprise_value: Optional[float] = None
    fcf_yield: Optional[float] = None


@dataclass
class BloombergFinancialYear:
    """Single fiscal year of financial data."""
    revenue: Optional[float] = None
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    rd_expense: Optional[float] = None
    sga_expense: Optional[float] = None
    operating_income: Optional[float] = None
    interest_expense: Optional[float] = None
    pretax_income: Optional[float] = None
    tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    diluted_eps: Optional[float] = None
    diluted_shares: Optional[float] = None
    ebitda: Optional[float] = None
    depreciation: Optional[float] = None
    operating_cash_flow: Optional[float] = None
    capex: Optional[float] = None
    free_cash_flow: Optional[float] = None
    dividends_paid: Optional[float] = None
    share_repurchases: Optional[float] = None
    cash: Optional[float] = None
    current_assets: Optional[float] = None
    total_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    short_term_debt: Optional[float] = None
    long_term_debt: Optional[float] = None
    total_liabilities: Optional[float] = None
    shareholders_equity: Optional[float] = None


@dataclass
class BloombergPeer:
    """Single peer company data."""
    ticker: str = ""
    name: str = ""
    price: float = 0.0
    market_cap: float = 0.0
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    ev_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    peg_ratio: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None
    target_price: Optional[float] = None
    is_target: bool = False


@dataclass
class BloombergDividend:
    """Single year dividend data."""
    year: int = 0
    dps: float = 0.0
    growth: Optional[float] = None


@dataclass
class BloombergData:
    """Complete Bloomberg data export for a single ticker."""
    ticker: str = ""
    source: str = "bloomberg"
    exported_at: str = ""
    profile: BloombergProfile = field(default_factory=BloombergProfile)
    valuation: BloombergValuation = field(default_factory=BloombergValuation)
    consensus: BloombergConsensus = field(default_factory=BloombergConsensus)
    profitability: dict = field(default_factory=dict)
    dividends_snapshot: dict = field(default_factory=dict)
    other: dict = field(default_factory=dict)
    financials: dict = field(default_factory=dict)  # {FY0: BloombergFinancialYear, ...}
    peers: list = field(default_factory=list)  # list of ticker strings
    peer_data: list = field(default_factory=list)  # list of BloombergPeer
    peer_medians: dict = field(default_factory=dict)
    dividend_history: list = field(default_factory=list)  # list of BloombergDividend

    @property
    def age_hours(self) -> float:
        """Hours since data was exported."""
        if not self.exported_at:
            return float('inf')
        try:
            exported = datetime.fromisoformat(self.exported_at)
            return (datetime.now() - exported).total_seconds() / 3600
        except (ValueError, TypeError):
            return float('inf')

    @property
    def is_fresh(self) -> bool:
        """True if data is less than 24 hours old."""
        return self.age_hours < 24


def has_bloomberg_data(ticker: str) -> bool:
    """Check if pre-exported Bloomberg data exists for this ticker."""
    path = os.path.join(DATA_DIR, f"{ticker.upper()}.json")
    if not os.path.exists(path):
        return False
    # Verify it's a Bloomberg export (not some other JSON)
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("source") == "bloomberg"
    except (json.JSONDecodeError, IOError):
        return False


def load_bloomberg_data(ticker: str) -> Optional[BloombergData]:
    """
    Load pre-exported Bloomberg data for a ticker.

    Returns None if no data file exists.
    """
    ticker = ticker.upper()
    path = os.path.join(DATA_DIR, f"{ticker}.json")

    if not os.path.exists(path):
        print(f"[Bloomberg] {ticker}: No pre-exported data found at {path}")
        return None

    try:
        with open(path) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Bloomberg] {ticker}: Error reading {path}: {e}")
        return None

    if raw.get("source") != "bloomberg":
        print(f"[Bloomberg] {ticker}: File exists but not a Bloomberg export")
        return None

    # Parse profile
    p = raw.get("profile", {})
    profile = BloombergProfile(
        ticker=ticker,
        name=p.get("name", ""),
        sector=p.get("sector", ""),
        industry=p.get("industry", ""),
        sub_industry=p.get("sub_industry", ""),
        price=p.get("price", 0) or 0,
        market_cap=p.get("market_cap", 0) or 0,
        beta=p.get("beta", 1.0) or 1.0,
        shares_outstanding=p.get("shares_outstanding", 0) or 0,
        high_52w=p.get("high_52w", 0) or 0,
        low_52w=p.get("low_52w", 0) or 0,
        description=p.get("description", ""),
        exchange=p.get("exchange", ""),
        currency=p.get("currency", "USD"),
    )

    # Parse valuation
    v = raw.get("valuation", {})
    valuation = BloombergValuation(
        pe_ratio=v.get("pe_ratio"),
        forward_pe=v.get("forward_pe"),
        ev_ebitda=v.get("ev_ebitda"),
        price_to_sales=v.get("price_to_sales"),
        price_to_book=v.get("price_to_book"),
        peg_ratio=v.get("peg_ratio"),
        ev_revenue=v.get("ev_revenue"),
        enterprise_value=v.get("enterprise_value"),
        fcf_yield=v.get("fcf_yield"),
    )

    # Parse consensus
    c = raw.get("consensus", {})
    consensus = BloombergConsensus(
        target_price=c.get("target_price"),
        analyst_rating=c.get("analyst_rating"),
        buy_ratings=int(c["buy_ratings"]) if c.get("buy_ratings") else None,
        hold_ratings=int(c["hold_ratings"]) if c.get("hold_ratings") else None,
        sell_ratings=int(c["sell_ratings"]) if c.get("sell_ratings") else None,
        consensus_eps_cy=c.get("consensus_eps_cy"),
        consensus_eps_ny=c.get("consensus_eps_ny"),
        forward_dps=c.get("forward_dps"),
        forward_div_growth=c.get("forward_div_growth"),
    )

    # Parse financials
    financials = {}
    for fy_key, fy_data in raw.get("financials", {}).items():
        if isinstance(fy_data, dict):
            financials[fy_key] = BloombergFinancialYear(**{
                k: v for k, v in fy_data.items()
                if k in BloombergFinancialYear.__dataclass_fields__
            })

    # Parse peers
    peers = raw.get("peers", [])
    peer_data = []
    for pd_raw in raw.get("peer_data", []):
        peer = BloombergPeer(
            ticker=pd_raw.get("ticker", ""),
            name=pd_raw.get("name", ""),
            price=pd_raw.get("price", 0) or 0,
            market_cap=pd_raw.get("market_cap", 0) or 0,
            pe_ratio=pd_raw.get("pe_ratio"),
            forward_pe=pd_raw.get("forward_pe"),
            ev_ebitda=pd_raw.get("ev_ebitda"),
            price_to_sales=pd_raw.get("price_to_sales"),
            price_to_book=pd_raw.get("price_to_book"),
            peg_ratio=pd_raw.get("peg_ratio"),
            gross_margin=pd_raw.get("gross_margin"),
            operating_margin=pd_raw.get("operating_margin"),
            net_margin=pd_raw.get("net_margin"),
            roe=pd_raw.get("roe"),
            dividend_yield=pd_raw.get("dividend_yield"),
            beta=pd_raw.get("beta"),
            target_price=pd_raw.get("target_price"),
            is_target=pd_raw.get("is_target", False),
        )
        peer_data.append(peer)

    # Parse dividends
    dividend_history = []
    for d in raw.get("dividend_history", []):
        dividend_history.append(BloombergDividend(
            year=d.get("year", 0),
            dps=d.get("dps", 0),
            growth=d.get("growth"),
        ))

    result = BloombergData(
        ticker=ticker,
        source="bloomberg",
        exported_at=raw.get("exported_at", ""),
        profile=profile,
        valuation=valuation,
        consensus=consensus,
        profitability=raw.get("profitability", {}),
        dividends_snapshot=raw.get("dividends_snapshot", {}),
        other=raw.get("other", {}),
        financials=financials,
        peers=peers,
        peer_data=peer_data,
        peer_medians=raw.get("peer_medians", {}),
        dividend_history=dividend_history,
    )

    age = f"{result.age_hours:.1f}h ago" if result.age_hours < 1000 else "unknown age"
    print(f"[Bloomberg] {ticker}: Loaded pre-exported data ({age})")
    print(f"[Bloomberg]   Profile: {profile.name} | ${profile.price} | {profile.sector}")
    print(f"[Bloomberg]   Financials: {len(financials)} years | Peers: {len(peers)} | Dividends: {len(dividend_history)} years")

    return result


def list_available_tickers() -> list:
    """List all tickers that have pre-exported Bloomberg data."""
    if not os.path.exists(DATA_DIR):
        return []

    tickers = []
    for f in os.listdir(DATA_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(DATA_DIR, f)) as fh:
                    data = json.load(fh)
                if data.get("source") == "bloomberg":
                    tickers.append(data["ticker"])
            except (json.JSONDecodeError, IOError, KeyError):
                continue

    return sorted(tickers)
