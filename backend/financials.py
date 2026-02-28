"""
financials.py — fetches full income statement, balance sheet, and cash flow
data from FMP and computes key financial ratios for the Financials tab.

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv

from .config import ACTUALS_YEARS

load_dotenv(find_dotenv(), override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"


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

def _get_api_key() -> str:
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")
    return key


def _fetch(endpoint: str, api_key: str, **params) -> list:
    params["apikey"] = api_key
    url = f"{FMP_BASE_URL}/{endpoint}"
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"FMP returned empty data for: {endpoint}")
    return data


def _safe_div(num: float, denom: float) -> Optional[float]:
    """Return num/denom or None if denom is zero or negative."""
    if denom and denom != 0:
        return num / denom
    return None


def _safe_pct(num: float, denom: float) -> Optional[float]:
    """Return num/denom as a ratio, or None."""
    return _safe_div(num, denom)


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_financials(ticker: str) -> FinancialsResult:
    """
    Fetch full financial statements from FMP and compute key ratios.

    Returns
    -------
    FinancialsResult with per-year financial data and computed ratios.
    """
    api_key = _get_api_key()
    ticker = ticker.upper()

    # Fetch all three statements
    income_stmts = _fetch("income-statement", api_key, symbol=ticker, limit=ACTUALS_YEARS)
    cash_flows = _fetch("cash-flow-statement", api_key, symbol=ticker, limit=ACTUALS_YEARS)
    balance_sheets = _fetch("balance-sheet-statement", api_key, symbol=ticker, limit=ACTUALS_YEARS)

    n = min(len(income_stmts), len(cash_flows), len(balance_sheets))
    if n < 1:
        raise ValueError(f"Insufficient financial data for {ticker}")

    years: List[FinancialYear] = []

    for idx in range(n):
        stmt = income_stmts[idx]
        cf = cash_flows[idx]
        bs = balance_sheets[idx]

        _yr_raw = stmt.get("calendarYear") or (stmt.get("date") or "")[:4]
        year = int(_yr_raw) if str(_yr_raw).isdigit() else 0

        # ── Income Statement fields ──
        revenue = float(stmt.get("revenue") or 0)
        cost_of_revenue = float(stmt.get("costOfRevenue") or 0)
        gross_profit = float(stmt.get("grossProfit") or 0)
        rd_expenses = float(stmt.get("researchAndDevelopmentExpenses") or 0)
        sga_expenses = float(stmt.get("sellingGeneralAndAdministrativeExpenses") or 0)
        operating_expenses = float(stmt.get("operatingExpenses") or 0)
        operating_income = float(stmt.get("operatingIncome") or 0)
        interest_expense = abs(float(stmt.get("interestExpense") or 0))
        pretax_income = float(stmt.get("incomeBeforeTax") or 0)
        tax_expense = abs(float(stmt.get("incomeTaxExpense") or 0))
        net_income = float(stmt.get("netIncome") or 0)
        ebitda = float(stmt.get("ebitda") or 0)
        diluted_shares = float(stmt.get("weightedAverageShsOutDil") or 0)
        eps = float(stmt.get("epsDiluted") or 0)

        # ── Balance Sheet fields ──
        cash = float(
            bs.get("cashAndCashEquivalents")
            or bs.get("cashAndShortTermInvestments")
            or 0
        )
        total_current_assets = float(bs.get("totalCurrentAssets") or 0)
        total_assets = float(bs.get("totalAssets") or 0)
        total_current_liabilities = float(bs.get("totalCurrentLiabilities") or 0)
        long_term_debt = float(bs.get("longTermDebt") or 0)
        short_term_debt = float(bs.get("shortTermDebt") or 0)
        total_debt = long_term_debt + short_term_debt
        total_liabilities = float(bs.get("totalLiabilities") or 0)
        total_equity = float(bs.get("totalStockholdersEquity") or 0)

        # ── Cash Flow fields ──
        operating_cash_flow = float(cf.get("operatingCashFlow") or 0)
        capex = abs(float(cf.get("capitalExpenditure") or 0))
        free_cash_flow = float(cf.get("freeCashFlow") or (operating_cash_flow - capex))
        dividends_paid = abs(float(cf.get("dividendsPaid") or 0))
        share_repurchases = abs(float(cf.get("commonStockRepurchased") or 0))
        da = float(cf.get("depreciationAndAmortization") or 0)

        # ── Compute Ratios ──
        gross_margin = _safe_pct(gross_profit, revenue)
        operating_margin = _safe_pct(operating_income, revenue)
        net_margin = _safe_pct(net_income, revenue)
        roe = _safe_pct(net_income, total_equity)
        roa = _safe_pct(net_income, total_assets)

        # ROIC = NOPAT / Invested Capital
        # NOPAT = operating_income * (1 - tax_rate)
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
            year=year,
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

    # Reverse to oldest → newest
    years.reverse()

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
