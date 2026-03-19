"""
financials.py — builds full financial statement data and computes key ratios
for the Financials tab, using pre-fetched EDGAR data.

Data source: SEC EDGAR (via EdgarFinancials).
"""

from dataclasses import dataclass
from typing import List, Optional

from .edgar_extractor import EdgarFinancials


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class FinancialYear:
    year: int

    # ── Income Statement ──
    revenue: float
    cost_of_revenue: float
    gross_profit: float
    rd_expenses: float
    sga_expenses: float
    operating_expenses: float
    operating_income: float
    interest_expense: float
    pretax_income: float
    tax_expense: float
    net_income: float
    ebitda: float
    diluted_shares: float
    eps: float

    # ── Balance Sheet ──
    cash: float
    total_current_assets: float
    total_assets: float
    total_current_liabilities: float
    total_debt: float
    total_liabilities: float
    total_equity: float

    # ── Cash Flow ──
    operating_cash_flow: float
    capex: float
    free_cash_flow: float
    dividends_paid: float
    share_repurchases: float
    da: float

    # ── Computed Ratios ──
    # Profitability
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    net_margin: Optional[float]
    roe: Optional[float]             # net income / equity
    roa: Optional[float]             # net income / total assets
    roic: Optional[float]            # NOPAT / invested capital

    # Liquidity
    current_ratio: Optional[float]   # current assets / current liabilities

    # Leverage
    debt_to_equity: Optional[float]  # total debt / equity
    interest_coverage: Optional[float]  # operating income / interest expense

    # Efficiency
    asset_turnover: Optional[float]  # revenue / total assets

    # Growth (y/y)
    revenue_growth: Optional[float]
    net_income_growth: Optional[float]
    eps_growth: Optional[float]

    # Per-share & valuation helpers
    fcf_per_share: Optional[float]


@dataclass
class FinancialsResult:
    ticker: str
    years: List[FinancialYear]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_div(num: float, denom: float) -> Optional[float]:
    """Return num/denom or None if denom is zero or negative."""
    if denom and denom != 0:
        return num / denom
    return None


def _safe_pct(num: float, denom: float) -> Optional[float]:
    """Return num/denom as a ratio, or None."""
    return _safe_div(num, denom)


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_financials(ticker: str, edgar_data: EdgarFinancials) -> FinancialsResult:
    """
    Build full financial statement data and compute key ratios from
    EDGAR data.

    Parameters
    ----------
    ticker     : Stock ticker symbol.
    edgar_data : Pre-fetched EDGAR financial data (oldest→newest).

    Returns
    -------
    FinancialsResult with per-year financial data and computed ratios.
    """
    ticker = ticker.upper()

    if not edgar_data.years:
        raise ValueError(f"No financial data available for {ticker}")

    years: List[FinancialYear] = []

    for ey in edgar_data.years:
        # ── Income Statement fields ──
        revenue = ey.revenue
        cost_of_revenue = ey.cost_of_revenue or 0.0
        gross_profit = ey.gross_profit or (revenue - cost_of_revenue)
        rd_expenses = ey.rd_expenses or 0.0
        sga_expenses = ey.sga_expenses or 0.0
        operating_expenses = ey.operating_expenses or 0.0
        operating_income = ey.operating_income or 0.0
        interest_expense = ey.interest_expense or 0.0
        pretax_income = ey.pretax_income or 0.0
        tax_expense = ey.income_tax or 0.0
        net_income = ey.net_income
        ebitda = ey.ebitda or (operating_income + ey.depreciation_amortization)
        diluted_shares = ey.diluted_shares
        eps = ey.eps or (net_income / diluted_shares if diluted_shares > 0 else 0.0)

        # ── Balance Sheet fields ──
        cash = ey.cash or 0.0
        total_current_assets = ey.current_assets or 0.0
        total_assets = ey.total_assets or 0.0
        total_current_liabilities = ey.current_liabilities or 0.0
        ltd = ey.long_term_debt or 0.0
        std = ey.short_term_debt or 0.0
        total_debt = ltd + std
        total_liabilities = ey.total_liabilities or 0.0
        total_equity = ey.total_equity or 0.0

        # ── Cash Flow fields ──
        operating_cash_flow = ey.operating_cash_flow or 0.0
        capex = ey.capex
        free_cash_flow = ey.fcf or (net_income + ey.depreciation_amortization - capex)
        dividends_paid = ey.dividends_paid or 0.0
        share_repurchases = ey.share_repurchases or 0.0
        da = ey.depreciation_amortization

        # ── Compute Ratios ──
        gross_margin = _safe_pct(gross_profit, revenue)
        operating_margin = _safe_pct(operating_income, revenue)
        net_margin = _safe_pct(net_income, revenue)
        roe = _safe_pct(net_income, total_equity)
        roa = _safe_pct(net_income, total_assets)

        # ROIC = NOPAT / Invested Capital
        tax_rate = tax_expense / pretax_income if pretax_income > 0 else 0.21
        nopat = operating_income * (1 - tax_rate)
        invested_capital = total_equity + total_debt - cash
        roic = _safe_pct(nopat, invested_capital) if invested_capital > 0 else None

        current_ratio = _safe_div(total_current_assets, total_current_liabilities)
        debt_to_equity = _safe_div(total_debt, total_equity) if total_equity > 0 else None
        interest_coverage = _safe_div(operating_income, interest_expense) if interest_expense > 0 else None
        asset_turnover = _safe_div(revenue, total_assets)

        fcf_per_share = _safe_div(free_cash_flow, diluted_shares)

        years.append(FinancialYear(
            year=ey.fiscal_year,
            revenue=revenue,
            cost_of_revenue=cost_of_revenue,
            gross_profit=gross_profit,
            rd_expenses=rd_expenses,
            sga_expenses=sga_expenses,
            operating_expenses=operating_expenses,
            operating_income=operating_income,
            interest_expense=interest_expense,
            pretax_income=pretax_income,
            tax_expense=tax_expense,
            net_income=net_income,
            ebitda=ebitda,
            diluted_shares=diluted_shares,
            eps=eps,
            cash=cash,
            total_current_assets=total_current_assets,
            total_assets=total_assets,
            total_current_liabilities=total_current_liabilities,
            total_debt=total_debt,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            operating_cash_flow=operating_cash_flow,
            capex=capex,
            free_cash_flow=free_cash_flow,
            dividends_paid=dividends_paid,
            share_repurchases=share_repurchases,
            da=da,
            gross_margin=round(gross_margin, 4) if gross_margin is not None else None,
            operating_margin=round(operating_margin, 4) if operating_margin is not None else None,
            net_margin=round(net_margin, 4) if net_margin is not None else None,
            roe=round(roe, 4) if roe is not None else None,
            roa=round(roa, 4) if roa is not None else None,
            roic=round(roic, 4) if roic is not None else None,
            current_ratio=round(current_ratio, 2) if current_ratio is not None else None,
            debt_to_equity=round(debt_to_equity, 2) if debt_to_equity is not None else None,
            interest_coverage=round(interest_coverage, 1) if interest_coverage is not None else None,
            asset_turnover=round(asset_turnover, 2) if asset_turnover is not None else None,
            revenue_growth=None,
            net_income_growth=None,
            eps_growth=None,
            fcf_per_share=round(fcf_per_share, 2) if fcf_per_share is not None else None,
        ))

    # Data is already oldest → newest from EDGAR

    # Compute y/y growth rates
    for i in range(1, len(years)):
        prev = years[i - 1]
        curr = years[i]
        if prev.revenue > 0:
            curr.revenue_growth = round((curr.revenue - prev.revenue) / prev.revenue, 4)
        if prev.net_income > 0:
            curr.net_income_growth = round((curr.net_income - prev.net_income) / prev.net_income, 4)
        if prev.eps > 0:
            curr.eps_growth = round((curr.eps - prev.eps) / prev.eps, 4)

    print(f"[Financials] {ticker}: {len(years)} years loaded ({years[0].year}–{years[-1].year})")
    return FinancialsResult(ticker=ticker, years=years)
