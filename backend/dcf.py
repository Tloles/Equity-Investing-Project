"""
DCF calculator — fetches income statement, cash flow statement, balance sheet,
and quote data from FMP, then calculates a 5-year discounted cash flow (DCF)
intrinsic value per share.

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass
from typing import List

import requests
from dotenv import load_dotenv

load_dotenv()

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

# ── DCF constants ──────────────────────────────────────────────────────────────
RISK_FREE_RATE     = 0.045   # approximate 10-year US Treasury yield
MARKET_PREMIUM     = 0.055   # equity risk premium
TERMINAL_GROWTH    = 0.025   # conservative long-run FCF growth rate
TAX_RATE           = 0.21    # US corporate tax rate
DEFAULT_BETA       = 1.2     # fallback when beta is missing or zero
DEFAULT_DEBT_RATIO = 0.20    # fallback when balance sheet data is missing
COST_OF_DEBT       = 0.05    # approximate pre-tax cost of debt
PROJECTION_YEARS   = 5


@dataclass
class DCFResult:
    ticker: str
    current_price: float
    intrinsic_value: float
    upside_downside: float       # positive = upside %, negative = downside %

    # Assumptions
    revenue_growth_rate: float   # decimal, e.g. 0.12 == 12 %
    fcf_margin: float            # decimal
    wacc: float                  # decimal
    terminal_growth_rate: float  # decimal

    # Per-year projections (length == PROJECTION_YEARS)
    projected_fcf: List[float]
    pv_projected_fcf: List[float]

    # Value components (all in USD)
    pv_fcfs: float
    pv_terminal_value: float
    enterprise_value: float
    net_cash: float              # cash − total debt
    equity_value: float
    shares_outstanding: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")
    return key


def _fetch(endpoint: str, api_key: str, **params) -> list:
    """GET a FMP v3 endpoint and return the parsed JSON list."""
    params["apikey"] = api_key
    resp = requests.get(f"{FMP_BASE_URL}/{endpoint}", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"FMP returned empty data for: {endpoint}")
    return data


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_dcf(ticker: str) -> DCFResult:
    """
    Fetch FMP financial data and compute a 5-year DCF intrinsic value.

    Returns
    -------
    DCFResult dataclass with price, intrinsic value, assumptions, and
    per-year projections.

    Raises
    ------
    EnvironmentError  if FMP_API_KEY is not set.
    ValueError        if required data is missing or insufficient.
    """
    api_key = _get_api_key()
    ticker = ticker.upper()

    # ── Fetch all required statements ────────────────────────────────────────
    income_stmts   = _fetch(f"income-statement/{ticker}",        api_key, limit=4)
    cash_flows     = _fetch(f"cash-flow-statement/{ticker}",     api_key, limit=4)
    balance_sheets = _fetch(f"balance-sheet-statement/{ticker}", api_key, limit=1)
    quotes         = _fetch(f"quote/{ticker}",                   api_key)

    # ── Quote ─────────────────────────────────────────────────────────────────
    quote = quotes[0]
    current_price      = float(quote.get("price") or 0)
    shares_outstanding = float(quote.get("sharesOutstanding") or 0)
    raw_beta           = float(quote.get("beta") or 0)
    beta               = raw_beta if raw_beta > 0 else DEFAULT_BETA

    if shares_outstanding <= 0:
        raise ValueError(f"Invalid shares outstanding for {ticker}.")

    # ── Revenue and FCF history ───────────────────────────────────────────────
    # FMP returns statements newest-first, so index 0 is the most recent year.
    revenues = [float(s.get("revenue") or 0) for s in income_stmts]
    fcfs     = [float(s.get("freeCashFlow") or 0) for s in cash_flows]

    # Year-over-year revenue growth rates (need at least 2 data points)
    growth_rates = []
    for i in range(len(revenues) - 1):
        if revenues[i + 1] > 0:
            growth_rates.append((revenues[i] - revenues[i + 1]) / revenues[i + 1])

    if not growth_rates:
        raise ValueError(
            f"Insufficient revenue history to calculate growth rate for {ticker}."
        )

    # Cap to a reasonable range: −10 % → +40 %
    raw_growth = sum(growth_rates) / len(growth_rates)
    revenue_growth_rate = max(-0.10, min(0.40, raw_growth))

    # Average FCF margin over available history
    fcf_margins = [
        fcfs[i] / revenues[i]
        for i in range(min(len(fcfs), len(revenues)))
        if revenues[i] > 0
    ]
    if not fcf_margins:
        raise ValueError(f"Cannot calculate FCF margin for {ticker}.")
    fcf_margin = sum(fcf_margins) / len(fcf_margins)

    # ── Balance sheet ─────────────────────────────────────────────────────────
    balance = balance_sheets[0]
    cash = float(
        balance.get("cashAndCashEquivalents")
        or balance.get("cashAndShortTermInvestments")
        or 0
    )
    total_debt = float(balance.get("totalDebt") or 0)
    net_cash   = cash - total_debt

    # ── WACC ──────────────────────────────────────────────────────────────────
    market_cap   = current_price * shares_outstanding
    total_cap    = market_cap + total_debt
    debt_ratio   = (total_debt / total_cap) if total_cap > 0 else DEFAULT_DEBT_RATIO
    equity_ratio = 1.0 - debt_ratio

    cost_of_equity = RISK_FREE_RATE + beta * MARKET_PREMIUM
    wacc = (
        equity_ratio * cost_of_equity
        + debt_ratio * COST_OF_DEBT * (1.0 - TAX_RATE)
    )

    # Gordon Growth Model requires WACC strictly > terminal growth rate
    if wacc <= TERMINAL_GROWTH:
        wacc = TERMINAL_GROWTH + 0.02

    # ── 5-year FCF projections ────────────────────────────────────────────────
    base_revenue     = revenues[0]
    projected_fcf    = []
    pv_projected_fcf = []

    for year in range(1, PROJECTION_YEARS + 1):
        proj_revenue = base_revenue * (1 + revenue_growth_rate) ** year
        fcf          = proj_revenue * fcf_margin
        pv           = fcf / (1 + wacc) ** year
        projected_fcf.append(round(fcf, 0))
        pv_projected_fcf.append(round(pv, 0))

    pv_fcfs = sum(pv_projected_fcf)

    # ── Terminal value (Gordon Growth Model) ─────────────────────────────────
    terminal_fcf      = projected_fcf[-1] * (1 + TERMINAL_GROWTH)
    terminal_value    = terminal_fcf / (wacc - TERMINAL_GROWTH)
    pv_terminal_value = terminal_value / (1 + wacc) ** PROJECTION_YEARS

    # ── Enterprise → equity → per share ──────────────────────────────────────
    enterprise_value = pv_fcfs + pv_terminal_value
    equity_value     = enterprise_value + net_cash
    intrinsic_value  = equity_value / shares_outstanding

    upside_downside = (
        (intrinsic_value - current_price) / current_price * 100
        if current_price > 0 else 0.0
    )

    return DCFResult(
        ticker               = ticker,
        current_price        = round(current_price, 2),
        intrinsic_value      = round(intrinsic_value, 2),
        upside_downside      = round(upside_downside, 1),
        revenue_growth_rate  = round(revenue_growth_rate, 4),
        fcf_margin           = round(fcf_margin, 4),
        wacc                 = round(wacc, 4),
        terminal_growth_rate = TERMINAL_GROWTH,
        projected_fcf        = projected_fcf,
        pv_projected_fcf     = pv_projected_fcf,
        pv_fcfs              = round(pv_fcfs, 0),
        pv_terminal_value    = round(pv_terminal_value, 0),
        enterprise_value     = round(enterprise_value, 0),
        net_cash             = round(net_cash, 0),
        equity_value         = round(equity_value, 0),
        shares_outstanding   = shares_outstanding,
    )
