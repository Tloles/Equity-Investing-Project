"""
DDM calculator — accepts pre-fetched EDGAR financial data and Alpaca quote,
then computes both a Gordon Growth Model (single-stage) and a Two-Stage DDM
intrinsic value.

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

Data sources: SEC EDGAR (via EdgarFinancials) + Alpaca (via AlpacaQuote).
"""

from dataclasses import dataclass
from typing import List, Optional

from .alpaca_client import AlpacaQuote
from .config import ACTUALS_YEARS, DEFAULT_BETA
from .edgar_extractor import EdgarFinancials
from .industry_profiles import IndustryProfile
from .market_data import get_equity_risk_premium, get_risk_free_rate


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


def _empty_result(ticker: str, current_price: float, risk_free_rate: float,
                  equity_risk_premium: float, beta: float,
                  cost_of_equity: float) -> DDMResult:
    """Return a minimal DDMResult for non-dividend-paying companies."""
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


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_ddm(
    ticker: str,
    edgar_data: EdgarFinancials,
    quote: AlpacaQuote,
    profile: IndustryProfile,
) -> DDMResult:
    """
    Compute Gordon Growth and Two-Stage DDM intrinsic values from
    EDGAR financial data.

    Parameters
    ----------
    ticker      : Stock ticker symbol.
    edgar_data  : Pre-fetched EDGAR financial data (5 years, oldest→newest).
    quote       : Live price and beta from Alpaca.
    profile     : Industry profile with sector-specific rules.

    Returns
    -------
    DDMResult with dividend history, both model valuations, and base
    assumptions.
    """
    ticker = ticker.upper()

    current_price = quote.price
    if current_price <= 0:
        raise ValueError(f"Current price unavailable for {ticker}")

    beta = quote.beta if quote.beta and quote.beta > 0 else DEFAULT_BETA

    # ── CAPM cost of equity ───────────────────────────────────────────────
    risk_free_rate, _ = get_risk_free_rate()
    equity_risk_premium, _ = get_equity_risk_premium()
    cost_of_equity = risk_free_rate + beta * equity_risk_premium

    # ── Extract dividend history from EDGAR data ──────────────────────────
    # DPS = dividends_paid / diluted_shares per year
    import datetime as _dt
    current_year = _dt.date.today().year

    yearly_divs = {}  # year → DPS
    eps_by_year = {}  # year → EPS

    for ey in edgar_data.years:
        yr = ey.fiscal_year

        # Skip current (incomplete) year
        if yr >= current_year:
            continue

        eps_val = ey.eps or (ey.net_income / ey.diluted_shares if ey.diluted_shares > 0 else 0.0)
        eps_by_year[yr] = eps_val

        if ey.dividends_paid and ey.dividends_paid > 0 and ey.diluted_shares > 0:
            dps = ey.dividends_paid / ey.diluted_shares
            yearly_divs[yr] = dps

    print(f"[DDM] {ticker}: {len(yearly_divs)} years with dividends: {dict(sorted(yearly_divs.items()))}")

    # ── No dividends → return minimal result ──────────────────────────────
    if not yearly_divs:
        return _empty_result(ticker, current_price, risk_free_rate,
                             equity_risk_premium, beta, cost_of_equity)

    # ── Build history list ────────────────────────────────────────────────
    sorted_years = sorted(yearly_divs.keys())

    # Keep only last ACTUALS_YEARS + 1 years
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

    if not history:
        return _empty_result(ticker, current_price, risk_free_rate,
                             equity_risk_premium, beta, cost_of_equity)

    # ── Derive assumptions ────────────────────────────────────────────────
    latest_dps = history[-1].annual_dps

    growth_rates = [h.dps_growth for h in history if h.dps_growth is not None]
    growth_rates_clean = [g for g in growth_rates if -0.50 <= g <= 1.00]

    avg_growth = (
        sum(growth_rates_clean) / len(growth_rates_clean)
        if growth_rates_clean else 0.02
    )
    w_growth = (
        _weighted_growth(list(reversed(growth_rates_clean)))
        if growth_rates_clean else 0.02
    )

    payout_ratios = [h.payout_ratio for h in history if h.payout_ratio is not None]
    avg_payout = (
        sum(payout_ratios) / len(payout_ratios) if payout_ratios else 0.0
    )

    current_yield = latest_dps / current_price if current_price > 0 else 0.0

    # ── Gordon Growth Model ───────────────────────────────────────────────
    ggm_g = min(w_growth, cost_of_equity - 0.005)
    ggm_g = max(ggm_g, 0.0)
    ggm_d1 = latest_dps * (1.0 + ggm_g)
    ggm_iv = _compute_ggm(ggm_d1, cost_of_equity, ggm_g)
    ggm_upside = (
        (ggm_iv - current_price) / current_price * 100
        if current_price > 0 and ggm_iv > 0 else 0.0
    )

    # ── Two-Stage DDM ─────────────────────────────────────────────────────
    ts_g1 = w_growth
    ts_g1 = max(-0.10, min(0.25, ts_g1))
    ts_n = 5
    ts_g2 = min(0.03, cost_of_equity - 0.01)
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
