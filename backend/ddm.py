"""
DDM calculator — fetches dividend history from FMP and computes both a
Gordon Growth Model (single-stage) and a Two-Stage DDM intrinsic value.

Valuation approaches
--------------------
  Gordon Growth Model:  P = D₁ / (Re − g)
    where D₁ = most recent annual DPS × (1 + g)
          Re = CAPM cost of equity (same as DCF module)
          g  = stable long-term dividend growth rate

  Two-Stage DDM:
    Stage 1 (high-growth):  PV of dividends growing at g₁ for N years
    Stage 2 (terminal):     Gordon Growth terminal value at year N,
                            discounted back to present

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv

from .config import ACTUALS_YEARS, DEFAULT_BETA
from .industry_classifier import SectorInfo
from .market_data import get_equity_risk_premium, get_risk_free_rate

load_dotenv(find_dotenv(), override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class DividendYear:
    year: int
    annual_dps: float                       # total dividends per share for the year
    payout_ratio: Optional[float]           # dps / eps (None if EPS unavailable or ≤ 0)
    dps_growth: Optional[float]             # y/y growth rate (None for oldest year)


@dataclass
class DDMResult:
    ticker: str
    current_price: float
    pays_dividends: bool                    # False → DDM not applicable

    # Cost of equity (shared with DCF)
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float

    # Dividend history (oldest → newest)
    history: List[DividendYear]

    # Derived base assumptions
    latest_annual_dps: float                # most recent full-year DPS
    avg_dps_growth: float                   # simple average of historical y/y rates
    weighted_dps_growth: float              # recency-weighted average
    avg_payout_ratio: float                 # average of valid payout ratios
    current_yield: float                    # latest_annual_dps / current_price

    # Gordon Growth Model
    ggm_growth_rate: float                  # g  (default = weighted avg)
    ggm_d1: float                           # D₁ = latest_dps × (1 + g)
    ggm_intrinsic_value: float              # P  = D₁ / (Re − g)
    ggm_upside_downside: float              # % vs current price

    # Two-Stage DDM
    ts_high_growth_rate: float              # g₁ (stage 1)
    ts_high_growth_years: int               # N  (stage 1 duration)
    ts_terminal_growth_rate: float          # g₂ (stage 2 / terminal)
    ts_intrinsic_value: float               # PV(stage 1) + PV(terminal)
    ts_pv_stage1: float                     # PV of high-growth dividends
    ts_pv_terminal: float                   # PV of terminal value
    ts_upside_downside: float               # % vs current price


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")
    return key


def _fetch(endpoint: str, api_key: str, **params) -> list:
    """GET a FMP stable endpoint and return the parsed JSON list."""
    params["apikey"] = api_key
    url = f"{FMP_BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"FMP returned empty data for: {endpoint}")
    return data


def _weighted_growth(rates: List[float]) -> float:
    """Recency-weighted average (newest first in input list)."""
    if not rates:
        return 0.0
    n = len(rates)
    weights = [float(n - i) for i in range(n)]
    total_w = sum(weights)
    return sum(w * g for w, g in zip(weights, rates)) / total_w


def _compute_ggm(d1: float, cost_of_equity: float, g: float) -> float:
    """Gordon Growth Model: P = D₁ / (Re − g).  Returns 0 if invalid."""
    denom = cost_of_equity - g
    if denom <= 0 or d1 <= 0:
        return 0.0
    return d1 / denom


def _compute_two_stage(
    latest_dps: float,
    g1: float,
    n: int,
    g2: float,
    re: float,
) -> tuple:
    """
    Two-stage DDM.
    Returns (pv_stage1, pv_terminal, intrinsic_value).
    """
    pv_stage1 = 0.0
    div = latest_dps
    for t in range(1, n + 1):
        div *= (1.0 + g1)
        pv_stage1 += div / (1.0 + re) ** t

    # Terminal value at end of stage 1
    d_terminal = div * (1.0 + g2)
    denom = re - g2
    if denom <= 0:
        return pv_stage1, 0.0, pv_stage1

    tv = d_terminal / denom
    pv_terminal = tv / (1.0 + re) ** n
    return pv_stage1, pv_terminal, pv_stage1 + pv_terminal


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_ddm(ticker: str, sector_info: Optional[SectorInfo] = None) -> DDMResult:
    """
    Fetch FMP dividend and financial data, then compute Gordon Growth
    and Two-Stage DDM intrinsic values.

    Returns
    -------
    DDMResult with dividend history, both model valuations, and base
    assumptions.

    Raises
    ------
    EnvironmentError  if FMP_API_KEY is not set.
    ValueError        if required data is missing.
    """
    api_key = _get_api_key()
    ticker = ticker.upper()

    # ── Step 1: fetch data ────────────────────────────────────────────────────
    quotes = _fetch("quote", api_key, symbol=ticker)
    quote = quotes[0]
    current_price = float(quote.get("price") or 0)
    if current_price <= 0:
        raise ValueError(f"Current price unavailable for {ticker}")

    profile_beta = sector_info.beta if sector_info else 0.0
    quote_beta = float(quote.get("beta") or 0)
    raw_beta = profile_beta if profile_beta > 0 else quote_beta
    beta = raw_beta if raw_beta > 0 else DEFAULT_BETA

    # Dividend history — FMP dividends company endpoint
    try:
        params = {"apikey": api_key, "symbol": ticker}
        url = f"{FMP_BASE_URL}/dividends"
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        dividends_raw = resp.json() or []
        print(f"[DDM] Dividend fetch: {len(dividends_raw)} records")
    except Exception as exc:
        print(f"[DDM] Dividend fetch failed: {type(exc).__name__}: {exc}")
        dividends_raw = []

    # Income statement for EPS (payout ratio calculation)
    try:
        income_stmts = _fetch(
            "income-statement", api_key,
            symbol=ticker, limit=ACTUALS_YEARS,
        )
    except ValueError:
        income_stmts = []

    # ── Step 2: aggregate dividends by calendar year ──────────────────────────
    # FMP returns individual dividend payments; we need annual totals.
    # The dividends endpoint returns objects with keys like:
    #   date, adjDividend, dividend, recordDate, paymentDate, declarationDate
    yearly_divs: dict = {}   # year → total DPS
    for d in dividends_raw:
        # Try multiple date fields
        date_str = (
            d.get("date")
            or d.get("paymentDate")
            or d.get("recordDate")
            or d.get("declarationDate")
            or ""
        )
        if not date_str or len(date_str) < 4:
            continue
        try:
            year = int(date_str[:4])
            # Try multiple amount fields
            amount = float(
                d.get("adjDividend")
                or d.get("dividend")
                or d.get("amount")
                or 0
            )
            if amount > 0:
                yearly_divs[year] = yearly_divs.get(year, 0.0) + amount
        except (ValueError, TypeError):
            continue

    print(f"[DDM] {ticker}: found {len(dividends_raw)} dividend records, {len(yearly_divs)} yearly totals: {dict(sorted(yearly_divs.items()))}")

    # Build EPS lookup from income statements
    eps_by_year: dict = {}
    for stmt in income_stmts:
        yr_raw = stmt.get("calendarYear") or (stmt.get("date") or "")[:4]
        try:
            yr = int(yr_raw)
            eps_by_year[yr] = float(stmt.get("epsDiluted") or 0)
        except (ValueError, TypeError):
            continue

    # ── Step 3: CAPM cost of equity ───────────────────────────────────────────
    risk_free_rate, _ = get_risk_free_rate()
    equity_risk_premium, _ = get_equity_risk_premium()
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    # ── Step 4: build history list ────────────────────────────────────────────
    if not yearly_divs:
        # Company doesn't pay dividends — return a minimal result
        return DDMResult(
            ticker=ticker,
            current_price=round(current_price, 2),
            pays_dividends=False,
            risk_free_rate=round(risk_free_rate, 4),
            equity_risk_premium=round(equity_risk_premium, 4),
            beta=round(beta, 4),
            cost_of_equity=round(cost_of_equity, 4),
            history=[],
            latest_annual_dps=0.0,
            avg_dps_growth=0.0,
            weighted_dps_growth=0.0,
            avg_payout_ratio=0.0,
            current_yield=0.0,
            ggm_growth_rate=0.0,
            ggm_d1=0.0,
            ggm_intrinsic_value=0.0,
            ggm_upside_downside=0.0,
            ts_high_growth_rate=0.0,
            ts_high_growth_years=5,
            ts_terminal_growth_rate=0.0,
            ts_intrinsic_value=0.0,
            ts_pv_stage1=0.0,
            ts_pv_terminal=0.0,
            ts_upside_downside=0.0,
        )

    sorted_years = sorted(yearly_divs.keys())

    # Keep only last ACTUALS_YEARS + 1 years (need extra for first growth calc)
    if len(sorted_years) > ACTUALS_YEARS + 1:
        sorted_years = sorted_years[-(ACTUALS_YEARS + 1):]

    history: List[DividendYear] = []
    for i, yr in enumerate(sorted_years):
        dps = yearly_divs[yr]
        eps = eps_by_year.get(yr)
        payout = (dps / eps) if (eps and eps > 0) else None

        growth = None
        if i > 0:
            prev_dps = yearly_divs[sorted_years[i - 1]]
            if prev_dps > 0:
                growth = (dps - prev_dps) / prev_dps

        history.append(DividendYear(
            year=yr,
            annual_dps=round(dps, 4),
            payout_ratio=round(payout, 4) if payout is not None else None,
            dps_growth=round(growth, 4) if growth is not None else None,
        ))

    # ── Step 5: derive assumptions ────────────────────────────────────────────
    latest_dps = history[-1].annual_dps

    growth_rates = [h.dps_growth for h in history if h.dps_growth is not None]
    # Filter out extreme outliers (> 100% growth or < -50%)
    growth_rates_clean = [g for g in growth_rates if -0.50 <= g <= 1.00]

    avg_growth = (
        sum(growth_rates_clean) / len(growth_rates_clean)
        if growth_rates_clean else 0.02
    )
    # newest-first for weighting
    w_growth = (
        _weighted_growth(list(reversed(growth_rates_clean)))
        if growth_rates_clean else 0.02
    )

    payout_ratios = [h.payout_ratio for h in history if h.payout_ratio is not None]
    avg_payout = (
        sum(payout_ratios) / len(payout_ratios) if payout_ratios else 0.0
    )

    current_yield = latest_dps / current_price if current_price > 0 else 0.0

    # ── Step 6: Gordon Growth Model ───────────────────────────────────────────
    # Clamp growth rate below cost of equity (GGM requirement)
    ggm_g = min(w_growth, cost_of_equity - 0.005)
    ggm_g = max(ggm_g, 0.0)   # floor at 0%
    ggm_d1 = latest_dps * (1.0 + ggm_g)
    ggm_iv = _compute_ggm(ggm_d1, cost_of_equity, ggm_g)
    ggm_upside = (
        (ggm_iv - current_price) / current_price * 100
        if current_price > 0 and ggm_iv > 0 else 0.0
    )

    # ── Step 7: Two-Stage DDM ─────────────────────────────────────────────────
    ts_g1 = w_growth                         # high-growth = recent trend
    ts_g1 = max(-0.10, min(0.25, ts_g1))    # clamp to [-10%, 25%]
    ts_n = 5                                 # 5-year high-growth phase
    ts_g2 = min(0.03, cost_of_equity - 0.01) # terminal: ~3% or below Re
    ts_g2 = max(ts_g2, 0.0)

    ts_pv1, ts_pvt, ts_iv = _compute_two_stage(
        latest_dps, ts_g1, ts_n, ts_g2, cost_of_equity,
    )
    ts_upside = (
        (ts_iv - current_price) / current_price * 100
        if current_price > 0 and ts_iv > 0 else 0.0
    )

    print(
        f"[DDM] {ticker}: dps={latest_dps:.4f}  yield={current_yield:.4f}  "
        f"avg_g={avg_growth:.4f}  w_g={w_growth:.4f}  "
        f"GGM_iv={ggm_iv:.2f}  2S_iv={ts_iv:.2f}"
    )

    return DDMResult(
        ticker=ticker,
        current_price=round(current_price, 2),
        pays_dividends=True,
        risk_free_rate=round(risk_free_rate, 4),
        equity_risk_premium=round(equity_risk_premium, 4),
        beta=round(beta, 4),
        cost_of_equity=round(cost_of_equity, 4),
        history=history,
        latest_annual_dps=round(latest_dps, 4),
        avg_dps_growth=round(avg_growth, 4),
        weighted_dps_growth=round(w_growth, 4),
        avg_payout_ratio=round(avg_payout, 4),
        current_yield=round(current_yield, 4),
        ggm_growth_rate=round(ggm_g, 4),
        ggm_d1=round(ggm_d1, 4),
        ggm_intrinsic_value=round(ggm_iv, 2),
        ggm_upside_downside=round(ggm_upside, 1),
        ts_high_growth_rate=round(ts_g1, 4),
        ts_high_growth_years=ts_n,
        ts_terminal_growth_rate=round(ts_g2, 4),
        ts_intrinsic_value=round(ts_iv, 2),
        ts_pv_stage1=round(ts_pv1, 2),
        ts_pv_terminal=round(ts_pvt, 2),
        ts_upside_downside=round(ts_upside, 1),
    )
