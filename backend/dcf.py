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
from dotenv import find_dotenv, load_dotenv

from .config import (
    DEFAULT_BETA,
    MIN_GROWTH_RATE,
    PROJECTION_YEARS,
    TAX_RATE,
    TERMINAL_GROWTH_RATE,
)
from .market_data import get_equity_risk_premium, get_risk_free_rate

# Use find_dotenv() so the .env file is located by walking up from this file,
# regardless of the working directory uvicorn was launched from.
_dotenv_path = find_dotenv()
print(f"[DCF] .env path resolved to: {_dotenv_path!r}")
load_dotenv(_dotenv_path, override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"

TERMINAL_GROWTH     = TERMINAL_GROWTH_RATE
DEFAULT_DEBT_RATIO  = 0.20    # fallback when balance sheet data is missing
COST_OF_DEBT_MIN    = 0.01    # floor for calculated cost of debt
COST_OF_DEBT_MAX    = 0.20    # ceiling for calculated cost of debt
COD_FALLBACK_SPREAD = 0.015   # added to risk-free rate when company is debt-free


@dataclass
class DCFResult:
    ticker: str
    current_price: float
    intrinsic_value: float
    upside_downside: float       # positive = upside %, negative = downside %

    # Market / CAPM inputs
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float
    cost_of_debt: float

    # Model assumptions
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
        print("[DCF] ERROR: FMP_API_KEY not found in environment after load_dotenv.")
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")
    print(f"[DCF] FMP_API_KEY loaded OK: {key[:4]}...{key[-4:]} (length={len(key)})")
    return key


def _fetch(endpoint: str, api_key: str, **params) -> list:
    """GET a FMP stable endpoint and return the parsed JSON list."""
    params["apikey"] = api_key
    url = f"{FMP_BASE_URL}/{endpoint}"

    prepared = requests.Request("GET", url, params=params).prepare()
    print(f"[DCF] GET {prepared.url}")

    resp = requests.get(url, params=params, timeout=15)
    print(f"[DCF] Status: {resp.status_code} | Body[:500]: {resp.text[:500]}")

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
    DCFResult dataclass with price, intrinsic value, CAPM inputs, assumptions,
    and per-year projections.

    Raises
    ------
    EnvironmentError  if FMP_API_KEY is not set.
    ValueError        if required data is missing or insufficient.
    """
    api_key = _get_api_key()
    ticker = ticker.upper()

    # ── Step 1: fetch raw data ────────────────────────────────────────────────
    try:
        income_stmts   = _fetch("income-statement",        api_key, symbol=ticker, limit=4)
        cash_flows     = _fetch("cash-flow-statement",     api_key, symbol=ticker, limit=4)
        balance_sheets = _fetch("balance-sheet-statement", api_key, symbol=ticker, limit=1)
        quotes         = _fetch("quote",                   api_key, symbol=ticker)
    except Exception as exc:
        print(f"[DCF] FAILED step 1 (data fetch): {type(exc).__name__}: {exc}")
        raise

    # ── Step 2: parse quote ───────────────────────────────────────────────────
    try:
        quote = quotes[0]
        print(f"[DCF] quote keys: {list(quote.keys())}")
        print(f"[DCF] quote price={quote.get('price')!r}  "
              f"marketCap={quote.get('marketCap')!r}  "
              f"beta={quote.get('beta')!r}")
        current_price    = float(quote.get("price") or 0)
        market_cap_quote = float(quote.get("marketCap") or 0)
        if current_price <= 0:
            raise ValueError(f"price is {quote.get('price')!r} — missing or zero.")
        if market_cap_quote <= 0:
            raise ValueError(f"marketCap is {quote.get('marketCap')!r} — missing or zero.")
        shares_outstanding = market_cap_quote / current_price
        raw_beta           = float(quote.get("beta") or 0)
        beta               = raw_beta if raw_beta > 0 else DEFAULT_BETA
        print(f"[DCF] derived shares_outstanding={shares_outstanding:.0f}  beta={beta:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 2 (quote parsing): {type(exc).__name__}: {exc}")
        raise

    # ── Step 3: extract revenue, FCF, and interest expense series ────────────
    try:
        print(f"[DCF] income_stmts[0] keys: {list(income_stmts[0].keys())}")
        print(f"[DCF] income_stmts[0] revenue={income_stmts[0].get('revenue')!r}  "
              f"interestExpense={income_stmts[0].get('interestExpense')!r}")
        print(f"[DCF] cash_flows[0] freeCashFlow={cash_flows[0].get('freeCashFlow')!r}")
        revenues = [float(s.get("revenue") or 0) for s in income_stmts]
        fcfs     = [float(s.get("freeCashFlow") or 0) for s in cash_flows]
        # FMP may report interestExpense as a negative number; take abs value
        interest_expenses = [
            abs(float(s.get("interestExpense") or 0)) for s in income_stmts
        ]
        print(f"[DCF] revenues={revenues}")
        print(f"[DCF] fcfs={fcfs}")
        print(f"[DCF] interest_expenses={interest_expenses}")
    except Exception as exc:
        print(f"[DCF] FAILED step 3 (revenue/FCF/interest extraction): {type(exc).__name__}: {exc}")
        raise

    # ── Step 4: weighted revenue growth rate ──────────────────────────────────
    try:
        growth_rates = []
        for i in range(len(revenues) - 1):
            if revenues[i + 1] > 0:
                growth_rates.append((revenues[i] - revenues[i + 1]) / revenues[i + 1])
        if not growth_rates:
            raise ValueError(f"No positive prior-year revenues. revenues={revenues}")
        # Descending weights: most recent (index 0) gets the highest weight
        n = len(growth_rates)
        weights = [n - i for i in range(n)]
        total_weight = sum(weights)
        raw_growth = sum(w * g for w, g in zip(weights, growth_rates)) / total_weight
        revenue_growth_rate = max(MIN_GROWTH_RATE, min(0.40, raw_growth))
        print(f"[DCF] growth_rates={growth_rates}  weighted_raw={raw_growth:.4f}  "
              f"revenue_growth_rate={revenue_growth_rate:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 4 (growth rate): {type(exc).__name__}: {exc}")
        raise

    # ── Step 5: FCF margin ────────────────────────────────────────────────────
    try:
        fcf_margins = [
            fcfs[i] / revenues[i]
            for i in range(min(len(fcfs), len(revenues)))
            if revenues[i] > 0
        ]
        if not fcf_margins:
            raise ValueError(f"No valid FCF/revenue pairs. fcfs={fcfs}  revenues={revenues}")
        fcf_margin = sum(fcf_margins) / len(fcf_margins)
        print(f"[DCF] fcf_margins={fcf_margins}  fcf_margin={fcf_margin:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 5 (FCF margin): {type(exc).__name__}: {exc}")
        raise

    # ── Step 6: balance sheet ─────────────────────────────────────────────────
    try:
        balance = balance_sheets[0]
        print(f"[DCF] balance_sheet keys: {list(balance.keys())}")
        cash = float(
            balance.get("cashAndCashEquivalents")
            or balance.get("cashAndShortTermInvestments")
            or 0
        )
        total_debt = float(balance.get("totalDebt") or 0)
        net_cash   = cash - total_debt
        print(f"[DCF] cash={cash}  total_debt={total_debt}  net_cash={net_cash}")
    except Exception as exc:
        print(f"[DCF] FAILED step 6 (balance sheet): {type(exc).__name__}: {exc}")
        raise

    # ── Step 7: live market rates ─────────────────────────────────────────────
    try:
        risk_free_rate, rfr_source = get_risk_free_rate()
        equity_risk_premium, erp_source = get_equity_risk_premium()
        print(f"[DCF] risk_free_rate={risk_free_rate:.4f} ({rfr_source})  "
              f"equity_risk_premium={equity_risk_premium:.4f} ({erp_source})")
    except Exception as exc:
        print(f"[DCF] FAILED step 7 (market rates): {type(exc).__name__}: {exc}")
        raise

    # ── Step 8: cost of equity (CAPM) and cost of debt ───────────────────────
    try:
        cost_of_equity = risk_free_rate + beta * equity_risk_premium

        # Use most recent year's interest expense divided by total debt
        if total_debt > 0 and interest_expenses and interest_expenses[0] > 0:
            raw_cod = interest_expenses[0] / total_debt
            cost_of_debt = max(COST_OF_DEBT_MIN, min(COST_OF_DEBT_MAX, raw_cod))
        else:
            cost_of_debt = risk_free_rate + COD_FALLBACK_SPREAD

        print(f"[DCF] cost_of_equity={cost_of_equity:.4f}  cost_of_debt={cost_of_debt:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 8 (cost of capital): {type(exc).__name__}: {exc}")
        raise

    # ── Step 9: WACC ──────────────────────────────────────────────────────────
    try:
        market_cap   = current_price * shares_outstanding
        total_cap    = market_cap + total_debt
        debt_ratio   = (total_debt / total_cap) if total_cap > 0 else DEFAULT_DEBT_RATIO
        equity_ratio = 1.0 - debt_ratio
        wacc = equity_ratio * cost_of_equity + debt_ratio * cost_of_debt * (1.0 - TAX_RATE)
        if wacc <= TERMINAL_GROWTH:
            wacc = TERMINAL_GROWTH + 0.02
        print(f"[DCF] debt_ratio={debt_ratio:.4f}  equity_ratio={equity_ratio:.4f}  wacc={wacc:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 9 (WACC): {type(exc).__name__}: {exc}")
        raise

    # ── Step 10: 5-year FCF projections ───────────────────────────────────────
    try:
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
        print(f"[DCF] projected_fcf={projected_fcf}")
        print(f"[DCF] pv_projected_fcf={pv_projected_fcf}  pv_fcfs={pv_fcfs}")
    except Exception as exc:
        print(f"[DCF] FAILED step 10 (FCF projections): {type(exc).__name__}: {exc}")
        raise

    # ── Step 11: terminal value ────────────────────────────────────────────────
    try:
        terminal_fcf      = projected_fcf[-1] * (1 + TERMINAL_GROWTH)
        terminal_value    = terminal_fcf / (wacc - TERMINAL_GROWTH)
        pv_terminal_value = terminal_value / (1 + wacc) ** PROJECTION_YEARS
        print(f"[DCF] terminal_value={terminal_value:.0f}  pv_terminal_value={pv_terminal_value:.0f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 11 (terminal value): {type(exc).__name__}: {exc}")
        raise

    # ── Step 12: enterprise → equity → intrinsic value ───────────────────────
    try:
        enterprise_value = pv_fcfs + pv_terminal_value
        equity_value     = enterprise_value + net_cash
        intrinsic_value  = equity_value / shares_outstanding
        upside_downside  = (
            (intrinsic_value - current_price) / current_price * 100
            if current_price > 0 else 0.0
        )
        print(f"[DCF] enterprise_value={enterprise_value:.0f}  equity_value={equity_value:.0f}")
        print(f"[DCF] intrinsic_value={intrinsic_value:.2f}  current_price={current_price}  "
              f"upside={upside_downside:.1f}%")
    except Exception as exc:
        print(f"[DCF] FAILED step 12 (final valuation): {type(exc).__name__}: {exc}")
        raise

    print(f"[DCF] SUCCESS for {ticker}")
    return DCFResult(
        ticker               = ticker,
        current_price        = round(current_price, 2),
        intrinsic_value      = round(intrinsic_value, 2),
        upside_downside      = round(upside_downside, 1),
        risk_free_rate       = round(risk_free_rate, 4),
        equity_risk_premium  = round(equity_risk_premium, 4),
        beta                 = round(beta, 4),
        cost_of_equity       = round(cost_of_equity, 4),
        cost_of_debt         = round(cost_of_debt, 4),
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
