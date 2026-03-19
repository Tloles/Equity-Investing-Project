"""
DCF calculator — accepts pre-fetched EDGAR financial data and Alpaca quote,
then computes an equity-basis 5-year DCF.

Valuation approach
------------------
  Discount rate : Cost of Equity  Re = Rf + β × ERP
  FCF           : Net Income + D&A − Capex  (per projected year)
  Terminal value: Year-5 Net Income × P/E exit multiple  (total equity value)
  Intrinsic value per share = (PV of FCFs + PV of Terminal Value)
                              / base diluted shares

Data sources: SEC EDGAR (via EdgarFinancials) + Alpaca (via AlpacaQuote).
"""

from dataclasses import dataclass
from typing import List, Optional

from .alpaca_client import AlpacaQuote
from .config import (
    DEFAULT_BETA,
    DEFAULT_EXIT_PE,
    PROJECTION_YEARS,
    TAX_RATE,
)
from .edgar_extractor import EdgarFinancials
from .industry_config import SectorRules, get_sector_rules
from .industry_profiles import IndustryProfile
from .market_data import get_equity_risk_premium, get_risk_free_rate


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

def fetch_dcf(
    ticker: str,
    edgar_data: EdgarFinancials,
    quote: AlpacaQuote,
    profile: IndustryProfile,
) -> DCFResult:
    """
    Compute an equity-basis DCF intrinsic value from EDGAR financial data.

    Parameters
    ----------
    ticker       : Stock ticker symbol.
    edgar_data   : Pre-fetched EDGAR financial data (5 years, oldest→newest).
    quote        : Live price and beta from Alpaca.
    profile      : Industry profile with sector-specific rules.

    Returns
    -------
    DCFResult with historical actuals, CAPM inputs, base assumptions, and
    initial valuation bridge components.
    """
    ticker = ticker.upper()
    current_price = quote.price
    if current_price <= 0:
        raise ValueError(f"Current price unavailable for {ticker}")

    # ── Beta ──────────────────────────────────────────────────────────────
    beta = quote.beta if quote.beta and quote.beta > 0 else DEFAULT_BETA
    print(f"[DCF] current_price={current_price}  beta={beta:.4f}")

    # ── Sector rules ──────────────────────────────────────────────────────
    sector_rules = profile.sector_rules or get_sector_rules(edgar_data.sector)
    print(f"[DCF] sector={edgar_data.sector!r}  rules={sector_rules.sector_label}")

    # ── CAPM cost of equity ───────────────────────────────────────────────
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
        print(f"[DCF] FAILED (market rates): {type(exc).__name__}: {exc}")
        raise

    # ── Build actuals from EDGAR data ─────────────────────────────────────
    # EDGAR data is already oldest→newest, signs already normalised
    try:
        if len(edgar_data.years) < 2:
            raise ValueError(
                f"Insufficient historical data: {len(edgar_data.years)} years"
            )

        actuals: List[YearData] = []
        for ey in edgar_data.years:
            cash = ey.cash or 0.0
            ltd = ey.long_term_debt or 0.0
            std = ey.short_term_debt or 0.0
            net_dbt = ltd + std - cash

            # Apply industry-specific substitutions
            da = ey.depreciation_amortization
            net_inc = ey.net_income
            capex = ey.capex
            fcf = net_inc + da - capex

            # SBC addback for Technology
            if profile.addback_sbc and ey.sbc:
                fcf += ey.sbc

            actuals.append(YearData(
                year=ey.fiscal_year,
                revenue=ey.revenue,
                operating_income=ey.operating_income or 0.0,
                interest_expense=ey.interest_expense or 0.0,
                pretax_income=ey.pretax_income or 0.0,
                tax_expense=ey.income_tax or 0.0,
                net_income=net_inc,
                diluted_shares=ey.diluted_shares,
                eps=ey.eps or (net_inc / ey.diluted_shares if ey.diluted_shares > 0 else 0.0),
                capex=capex,
                da=da,
                fcf=fcf,
                revenue_growth=None,
                shares_growth=None,
                cash=cash,
                long_term_debt=ltd,
                short_term_debt=std,
                net_debt=net_dbt,
            ))

        # Fill in y/y growth rates (first year stays None)
        for i in range(1, len(actuals)):
            prev = actuals[i - 1]
            curr = actuals[i]
            if prev.revenue > 0:
                curr.revenue_growth = (curr.revenue - prev.revenue) / prev.revenue
            if prev.diluted_shares > 0:
                curr.shares_growth = (
                    (curr.diluted_shares - prev.diluted_shares) / prev.diluted_shares
                )

        print(f"[DCF] actuals: {[a.year for a in actuals]}")
    except Exception as exc:
        print(f"[DCF] FAILED (actuals): {type(exc).__name__}: {exc}")
        raise

    # ── Derive base assumptions from recent actuals ───────────────────────
    try:
        last = actuals[-1]

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

        # Shares: use EDGAR data, fall back to Alpaca market cap / price
        base_diluted_shares = last.diluted_shares
        if base_diluted_shares <= 0 and quote.market_cap and current_price > 0:
            base_diluted_shares = quote.market_cap / current_price
        if base_diluted_shares <= 0:
            base_diluted_shares = edgar_data.shares_outstanding

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
        print(f"[DCF] FAILED (base assumptions): {type(exc).__name__}: {exc}")
        raise

    # ── Initial valuation ─────────────────────────────────────────────────
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
        print(f"[DCF] FAILED (initial valuation): {type(exc).__name__}: {exc}")
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
