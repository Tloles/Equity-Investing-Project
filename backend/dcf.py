"""
DCF calculator — fetches ACTUALS_YEARS of income statement, cash-flow, and
balance-sheet data from FMP, then computes an equity-basis 5-year DCF.

Valuation approach
------------------
  Discount rate : Cost of Equity  Re = Rf + β × ERP
  FCF           : Net Income + D&A − Capex  (per projected year)
  Terminal value: Year-5 Net Income × P/E exit multiple  (total equity value)
  Intrinsic value per share = (PV of FCFs + PV of Terminal Value)
                              / base diluted shares

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from dotenv import find_dotenv, load_dotenv

from .config import (
    ACTUALS_YEARS,
    DEFAULT_BETA,
    DEFAULT_EXIT_PE,
    PROJECTION_YEARS,
    TAX_RATE,
)
from .industry_classifier import SectorInfo
from .industry_config import SectorRules, get_sector_rules
from .market_data import get_equity_risk_premium, get_risk_free_rate

_dotenv_path = find_dotenv()
print(f"[DCF] .env path resolved to: {_dotenv_path!r}")
load_dotenv(_dotenv_path, override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"


# ── Per-year data container ────────────────────────────────────────────────────

@dataclass
class YearData:
    year: int
    revenue: float
    operating_income: float
    interest_expense: float      # absolute value (cost normalised to positive)
    pretax_income: float
    tax_expense: float           # absolute value
    net_income: float
    diluted_shares: float        # weighted average diluted shares (absolute count)
    eps: float                   # diluted EPS in dollars
    capex: float                 # absolute value (cash outflow normalised to positive)
    da: float                    # depreciation & amortisation
    fcf: float                   # net_income + da − capex
    revenue_growth: Optional[float]   # y/y rate; None for oldest year
    shares_growth: Optional[float]    # y/y rate; None for oldest year
    cash: float
    long_term_debt: float
    short_term_debt: float
    net_debt: float              # long_term_debt + short_term_debt − cash


# ── Top-level result ───────────────────────────────────────────────────────────

@dataclass
class DCFResult:
    ticker: str
    current_price: float
    intrinsic_value: float
    upside_downside: float       # positive = upside %, negative = downside %

    # CAPM
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float

    # Historical actuals, oldest → newest (len == ACTUALS_YEARS or fewer)
    actuals: List[YearData]

    # Projection base assumptions (uniform starting point for all 5 forecast years)
    base_revenue_growth: float       # weighted avg of historical y/y rates
    base_op_margin: float            # last actual operating_income / revenue
    base_interest_expense: float     # last actual; held constant in projections
    base_tax_rate: float             # last actual tax / pretax (or fallback)
    base_capex_pct: float            # last actual capex / revenue
    base_da_pct: float               # last actual da / revenue
    base_shares_growth: float        # simple avg of historical y/y rates
    exit_pe_multiple: float          # P/E applied to Year-5 net income
    base_diluted_shares: float       # last actual (denominator for IV per share)

    # Valuation bridge (initial — before any user overrides)
    pv_fcfs: float
    pv_terminal_value: float
    equity_value: float


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


def _weighted_growth(values: List[float], sector_rules: SectorRules) -> float:
    """
    Compute a recency-weighted average growth rate (newest value first).
    Clamps result to [sector_rules.growth_floor, sector_rules.growth_cap].
    """
    if not values:
        return sector_rules.growth_floor
    n = len(values)
    weights = [float(n - i) for i in range(n)]
    if sector_rules.growth_recency_bias != 1.0:
        weights[0] *= sector_rules.growth_recency_bias
    total_w = sum(weights)
    raw = sum(w * g for w, g in zip(weights, values)) / total_w
    return max(sector_rules.growth_floor, min(sector_rules.growth_cap, raw))


def _compute_initial_projections(
    base_revenue: float,
    base_diluted_shares: float,
    interest_expense: float,
    revenue_growth: float,
    op_margin: float,
    tax_rate: float,
    capex_pct: float,
    da_pct: float,
    shares_growth: float,
    exit_pe: float,
    cost_of_equity: float,
) -> tuple:
    """
    Compute 5-year projections using uniform assumptions.
    Returns (pv_fcfs, pv_tv, equity_value, intrinsic_value).
    """
    prev_rev    = base_revenue
    prev_shares = base_diluted_shares
    pv_fcfs     = 0.0
    last_net_income = 0.0

    for t in range(1, PROJECTION_YEARS + 1):
        rev        = prev_rev * (1.0 + revenue_growth)
        op_inc     = rev * op_margin
        pretax     = op_inc - interest_expense
        tax        = pretax * tax_rate if pretax > 0 else 0.0
        net_income = pretax - tax
        shares     = prev_shares * (1.0 + shares_growth)
        capex      = rev * capex_pct
        da         = rev * da_pct
        fcf        = net_income + da - capex
        pv_fcfs   += fcf / (1.0 + cost_of_equity) ** t
        prev_rev        = rev
        prev_shares     = shares
        last_net_income = net_income

    tv            = last_net_income * exit_pe
    pv_tv         = tv / (1.0 + cost_of_equity) ** PROJECTION_YEARS
    equity_value  = pv_fcfs + pv_tv
    iv            = equity_value / base_diluted_shares if base_diluted_shares > 0 else 0.0
    return pv_fcfs, pv_tv, equity_value, iv


# ── Main entry point ───────────────────────────────────────────────────────────

def fetch_dcf(ticker: str, sector_info: Optional[SectorInfo] = None) -> DCFResult:
    """
    Fetch FMP financial data and compute an equity-basis DCF intrinsic value.

    Returns
    -------
    DCFResult with historical actuals, CAPM inputs, base assumptions, and
    initial valuation bridge components.

    Raises
    ------
    EnvironmentError  if FMP_API_KEY is not set.
    ValueError        if required data is missing or insufficient.
    """
    api_key = _get_api_key()
    ticker  = ticker.upper()

    # ── Step 1: fetch raw data ────────────────────────────────────────────────
    try:
        income_stmts   = _fetch("income-statement",        api_key, symbol=ticker, limit=ACTUALS_YEARS)
        cash_flows     = _fetch("cash-flow-statement",     api_key, symbol=ticker, limit=ACTUALS_YEARS)
        balance_sheets = _fetch("balance-sheet-statement", api_key, symbol=ticker, limit=ACTUALS_YEARS)
        quotes         = _fetch("quote",                   api_key, symbol=ticker)
    except Exception as exc:
        print(f"[DCF] FAILED step 1 (data fetch): {type(exc).__name__}: {exc}")
        raise

    # ── Step 2: parse quote ───────────────────────────────────────────────────
    try:
        quote            = quotes[0]
        current_price    = float(quote.get("price") or 0)
        market_cap_quote = float(quote.get("marketCap") or 0)
        if current_price <= 0:
            raise ValueError(f"price is {quote.get('price')!r} — missing or zero.")
        if market_cap_quote <= 0:
            raise ValueError(f"marketCap is {quote.get('marketCap')!r} — missing or zero.")

        profile_beta = sector_info.beta if sector_info else 0.0
        quote_beta   = float(quote.get("beta") or 0)
        raw_beta     = profile_beta if profile_beta > 0 else quote_beta
        beta         = raw_beta if raw_beta > 0 else DEFAULT_BETA
        print(f"[DCF] current_price={current_price}  beta={beta:.4f}")
    except Exception as exc:
        print(f"[DCF] FAILED step 2 (quote): {type(exc).__name__}: {exc}")
        raise

    # ── Sector rules ──────────────────────────────────────────────────────────
    sector_label  = sector_info.sector if sector_info else ""
    sector_rules: SectorRules = get_sector_rules(sector_label)
    print(f"[DCF] sector={sector_label!r}  rules={sector_rules.sector_label}")

    # ── Step 3: live market rates + CAPM cost of equity ───────────────────────
    try:
        risk_free_rate, rfr_source = get_risk_free_rate()
        equity_risk_premium, erp_source = get_equity_risk_premium()
        cost_of_equity = risk_free_rate + beta * equity_risk_premium
        print(
            f"[DCF] rfr={risk_free_rate:.4f} ({rfr_source})  "
            f"erp={equity_risk_premium:.4f} ({erp_source})  "
            f"Re={cost_of_equity:.4f}"
        )
    except Exception as exc:
        print(f"[DCF] FAILED step 3 (market rates): {type(exc).__name__}: {exc}")
        raise

    # ── Step 4: align statements and build actuals list ───────────────────────
    # All three FMP endpoints return data newest-first (index 0 = most recent).
    # We align by index (best-effort across statement types) and reverse to
    # produce an oldest → newest list for display.
    try:
        n = min(len(income_stmts), len(cash_flows), len(balance_sheets))
        if n < 2:
            raise ValueError(
                f"Insufficient historical data: income={len(income_stmts)}, "
                f"cashflow={len(cash_flows)}, balance={len(balance_sheets)}"
            )

        actuals: List[YearData] = []
        for idx in range(n):
            stmt = income_stmts[idx]
            cf   = cash_flows[idx]
            bs   = balance_sheets[idx]

            _yr_raw = stmt.get("calendarYear") or stmt.get("date", "")[:4]
            year    = int(_yr_raw) if str(_yr_raw).isdigit() else 0

            revenue      = float(stmt.get("revenue") or 0)
            op_income    = float(stmt.get("operatingIncome") or 0)
            # FMP reports interestExpense as negative (cash outflow) — normalise
            int_exp      = abs(float(stmt.get("interestExpense") or 0))
            pretax       = float(stmt.get("incomeBeforeTax") or 0)
            tax_exp      = abs(float(stmt.get("incomeTaxExpense") or 0))
            net_income   = float(stmt.get("netIncome") or 0)
            dil_shares   = float(stmt.get("weightedAverageShsOutDil") or 0)
            eps          = float(stmt.get("epsDiluted") or 0)

            # FMP reports capitalExpenditure as negative — normalise
            capex = abs(float(cf.get("capitalExpenditure") or 0))
            da    = float(cf.get("depreciationAndAmortization") or 0)
            fcf   = net_income + da - capex

            cash = float(
                bs.get("cashAndCashEquivalents")
                or bs.get("cashAndShortTermInvestments")
                or 0
            )
            ltd     = float(bs.get("longTermDebt") or 0)
            std     = float(bs.get("shortTermDebt") or 0)
            net_dbt = ltd + std - cash

            actuals.append(YearData(
                year=year, revenue=revenue, operating_income=op_income,
                interest_expense=int_exp, pretax_income=pretax,
                tax_expense=tax_exp, net_income=net_income,
                diluted_shares=dil_shares, eps=eps,
                capex=capex, da=da, fcf=fcf,
                revenue_growth=None, shares_growth=None,
                cash=cash, long_term_debt=ltd, short_term_debt=std, net_debt=net_dbt,
            ))

        # Reverse to oldest → newest for display
        actuals.reverse()

        # Fill in y/y growth rates (first year stays None — no prior-year data)
        for i in range(1, len(actuals)):
            prev = actuals[i - 1]
            curr = actuals[i]
            if prev.revenue > 0:
                curr.revenue_growth = (curr.revenue - prev.revenue) / prev.revenue
            if prev.diluted_shares > 0:
                curr.shares_growth = (
                    (curr.diluted_shares - prev.diluted_shares) / prev.diluted_shares
                )

        print(f"[DCF] actuals aligned: {[a.year for a in actuals]}")
    except Exception as exc:
        print(f"[DCF] FAILED step 4 (actuals): {type(exc).__name__}: {exc}")
        raise

    # ── Step 5: derive base assumptions from recent actuals ───────────────────
    try:
        last = actuals[-1]   # most recent year

        # Revenue growth: weighted avg of available y/y rates (newest first)
        rev_growths_newest_first = list(reversed([
            a.revenue_growth for a in actuals if a.revenue_growth is not None
        ]))
        base_revenue_growth = _weighted_growth(rev_growths_newest_first, sector_rules)

        # Operating margin from last actual
        base_op_margin = (
            last.operating_income / last.revenue if last.revenue > 0 else 0.15
        )

        # Interest expense from last actual (constant in projections)
        base_interest_expense = last.interest_expense

        # Tax rate from last actual (clamp to reasonable range)
        if last.pretax_income > 0 and last.tax_expense >= 0:
            base_tax_rate = min(0.50, last.tax_expense / last.pretax_income)
        else:
            base_tax_rate = TAX_RATE

        # Capex and D&A as % of revenue from last actual
        base_capex_pct = last.capex / last.revenue if last.revenue > 0 else 0.05
        base_da_pct    = last.da   / last.revenue if last.revenue > 0 else 0.03

        # Shares growth: simple average of available y/y rates
        shr_growths = [a.shares_growth for a in actuals if a.shares_growth is not None]
        base_shares_growth = sum(shr_growths) / len(shr_growths) if shr_growths else 0.0
        # Clamp to [-0.15, +0.15]
        base_shares_growth = max(-0.15, min(0.15, base_shares_growth))

        base_diluted_shares = (
            last.diluted_shares if last.diluted_shares > 0
            else market_cap_quote / current_price
        )

        exit_pe_multiple = DEFAULT_EXIT_PE

        print(
            f"[DCF] base_revenue_growth={base_revenue_growth:.4f}  "
            f"base_op_margin={base_op_margin:.4f}  "
            f"base_tax_rate={base_tax_rate:.4f}  "
            f"base_capex_pct={base_capex_pct:.4f}  "
            f"base_da_pct={base_da_pct:.4f}  "
            f"base_shares_growth={base_shares_growth:.4f}  "
            f"exit_pe={exit_pe_multiple}"
        )
    except Exception as exc:
        print(f"[DCF] FAILED step 5 (base assumptions): {type(exc).__name__}: {exc}")
        raise

    # ── Step 6: initial valuation ──────────────────────────────────────────────
    try:
        pv_fcfs, pv_tv, equity_value, intrinsic_value = _compute_initial_projections(
            base_revenue       = last.revenue,
            base_diluted_shares= base_diluted_shares,
            interest_expense   = base_interest_expense,
            revenue_growth     = base_revenue_growth,
            op_margin          = base_op_margin,
            tax_rate           = base_tax_rate,
            capex_pct          = base_capex_pct,
            da_pct             = base_da_pct,
            shares_growth      = base_shares_growth,
            exit_pe            = exit_pe_multiple,
            cost_of_equity     = cost_of_equity,
        )
        upside_downside = (
            (intrinsic_value - current_price) / current_price * 100
            if current_price > 0 else 0.0
        )
        print(
            f"[DCF] pv_fcfs={pv_fcfs:.0f}  pv_tv={pv_tv:.0f}  "
            f"equity_value={equity_value:.0f}  "
            f"intrinsic_value={intrinsic_value:.2f}  "
            f"upside={upside_downside:.1f}%"
        )
    except Exception as exc:
        print(f"[DCF] FAILED step 6 (initial valuation): {type(exc).__name__}: {exc}")
        raise

    print(f"[DCF] SUCCESS for {ticker}")
    return DCFResult(
        ticker              = ticker,
        current_price       = round(current_price, 2),
        intrinsic_value     = round(intrinsic_value, 2),
        upside_downside     = round(upside_downside, 1),
        risk_free_rate      = round(risk_free_rate, 4),
        equity_risk_premium = round(equity_risk_premium, 4),
        beta                = round(beta, 4),
        cost_of_equity      = round(cost_of_equity, 4),
        actuals             = actuals,
        base_revenue_growth = round(base_revenue_growth, 4),
        base_op_margin      = round(base_op_margin, 4),
        base_interest_expense = round(base_interest_expense, 0),
        base_tax_rate       = round(base_tax_rate, 4),
        base_capex_pct      = round(base_capex_pct, 4),
        base_da_pct         = round(base_da_pct, 4),
        base_shares_growth  = round(base_shares_growth, 4),
        exit_pe_multiple    = exit_pe_multiple,
        base_diluted_shares = round(base_diluted_shares, 0),
        pv_fcfs             = round(pv_fcfs, 0),
        pv_terminal_value   = round(pv_tv, 0),
        equity_value        = round(equity_value, 0),
    )
