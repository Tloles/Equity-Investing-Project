"""
edgar_extractor.py — XBRL financial data extraction from SEC EDGAR.

Uses `edgartools` to extract up to 5 years of financial statement data from
10-K filings via Company.get_financials().  Returns an EdgarFinancials
dataclass consumed by dcf.py, ddm.py, and financials.py.

Requires: pip install edgartools
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .cache import TTLCache
from .industry_profiles import map_sic_to_gics

# Cache: 7-day TTL for EDGAR financials (filings don't change often)
_edgar_cache = TTLCache(default_ttl=604800)


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class EdgarYear:
    fiscal_year: int

    # Income statement
    revenue: float
    cost_of_revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    interest_expense: Optional[float] = None
    pretax_income: Optional[float] = None
    income_tax: Optional[float] = None
    net_income: float = 0.0
    diluted_shares: float = 0.0
    eps: Optional[float] = None

    # Cash flow
    depreciation_amortization: float = 0.0
    capex: float = 0.0                        # positive number (absolute)
    operating_cash_flow: Optional[float] = None
    fcf: Optional[float] = None
    sbc: Optional[float] = None               # stock-based compensation
    dividends_paid: Optional[float] = None

    # Balance sheet
    cash: Optional[float] = None
    long_term_debt: Optional[float] = None
    short_term_debt: Optional[float] = None
    total_equity: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None

    # Extra fields for financials.py
    rd_expenses: Optional[float] = None
    sga_expenses: Optional[float] = None
    operating_expenses: Optional[float] = None
    ebitda: Optional[float] = None
    share_repurchases: Optional[float] = None


@dataclass
class EdgarFinancials:
    ticker: str
    cik: str
    company_name: str
    sector: str
    industry: str
    sic_code: int

    # Per-year data (list, oldest → newest)
    years: List[EdgarYear] = field(default_factory=list)

    # Latest quote data (filled by caller from Alpaca)
    current_price: float = 0.0
    beta: float = 1.0
    shares_outstanding: float = 0.0


# ── Tag lookup helpers ────────────────────────────────────────────────────────
# edgartools DataFrames have concept column like "us-gaap_NetIncomeLoss".
# We strip "us-gaap_" prefix for matching.

def _lookup(concept_map: Dict[str, float], tags: List[str]) -> Optional[float]:
    """Look up the first matching tag from a priority list in a concept→value map."""
    for tag in tags:
        val = concept_map.get(tag)
        if val is not None and val != "":
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _df_to_concept_maps(df, date_cols: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Convert a Statement DataFrame to {date_col: {concept_short: value}} maps.
    Strips 'us-gaap_' prefix from concept names.
    """
    result = {}
    for dcol in date_cols:
        cmap = {}
        for _, row in df.iterrows():
            concept = str(row.get("concept", ""))
            # Strip namespace prefix
            if "_" in concept:
                concept = concept.split("_", 1)[1]
            val = row.get(dcol)
            if val is not None and val != "":
                try:
                    cmap[concept] = float(val)
                except (TypeError, ValueError):
                    pass
        result[dcol] = cmap
    return result


def _get_date_cols(df) -> List[str]:
    """Extract date columns from a Statement DataFrame."""
    skip = {"concept", "label", "level", "abstract", "dimension"}
    return [c for c in df.columns if c not in skip]


# ── Tag priority lists ────────────────────────────────────────────────────────

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "TotalRevenuesAndOtherIncome",
    "InterestAndDividendIncomeOperating",
]

COST_OF_REVENUE_TAGS = [
    "CostOfGoodsAndServicesSold",
    "CostOfRevenue",
    "CostOfGoodsSold",
]

GROSS_PROFIT_TAGS = ["GrossProfit"]

OPERATING_INCOME_TAGS = [
    "OperatingIncomeLoss",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
]

INTEREST_EXPENSE_TAGS = [
    "InterestExpense",
    "InterestExpenseDebt",
    "InterestIncomeExpenseNet",
    "NonoperatingIncomeExpense",
]

PRETAX_INCOME_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]

TAX_TAGS = [
    "IncomeTaxExpenseBenefit",
    "IncomeTaxesPaidNet",
]

NET_INCOME_TAGS = [
    "NetIncomeLoss",
    "NetIncome",
    "ProfitLoss",
]

EPS_TAGS = [
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
]

SHARES_DILUTED_TAGS = [
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
]

RD_TAGS = [
    "ResearchAndDevelopmentExpense",
    "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
]

SGA_TAGS = [
    "SellingGeneralAndAdministrativeExpense",
    "GeneralAndAdministrativeExpense",
]

OPERATING_EXPENSES_TAGS = [
    "OperatingExpenses",
    "CostsAndExpenses",
]

# Cash flow tags
DA_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
]

CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireProductiveAssets",
]

OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByOperatingActivities",
]

SBC_TAGS = [
    "ShareBasedCompensation",
    "AllocatedShareBasedCompensationExpense",
]

DIVIDENDS_PAID_TAGS = [
    "PaymentsOfDividends",
    "PaymentsOfDividendsCommonStock",
    "Dividends",
]

SHARE_REPURCHASE_TAGS = [
    "PaymentsForRepurchaseOfCommonStock",
    "StockRepurchasedDuringPeriodValue",
]

# Balance sheet tags
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsAndShortTermInvestments",
    "Cash",
]

LTD_TAGS = [
    "LongTermDebtNoncurrent",
    "LongTermDebt",
    "LongTermDebtAndCapitalLeaseObligations",
]

STD_TAGS = [
    "LongTermDebtCurrent",
    "ShortTermBorrowings",
    "DebtCurrent",
    "CommercialPaper",
]

EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]

TOTAL_ASSETS_TAGS = ["Assets"]
TOTAL_LIABILITIES_TAGS = ["Liabilities"]
CURRENT_ASSETS_TAGS = ["AssetsCurrent"]
CURRENT_LIABILITIES_TAGS = ["LiabilitiesCurrent"]
SHARES_OUTSTANDING_TAGS = ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]


# ── Extract one year from concept maps ────────────────────────────────────────

def _extract_year(
    date_col: str,
    inc_map: Dict[str, float],
    bs_map: Dict[str, float],
    cf_map: Dict[str, float],
) -> Optional[EdgarYear]:
    """Build an EdgarYear from the three concept maps for one date column."""

    # Parse fiscal year from date column (format: "YYYY-MM-DD")
    try:
        fiscal_year = int(date_col[:4])
    except (ValueError, IndexError):
        return None

    # Income statement
    revenue = _lookup(inc_map, REVENUE_TAGS) or 0.0
    cost_of_revenue = _lookup(inc_map, COST_OF_REVENUE_TAGS)
    if cost_of_revenue is not None:
        cost_of_revenue = abs(cost_of_revenue)
    gross_profit = _lookup(inc_map, GROSS_PROFIT_TAGS)
    if gross_profit is None and cost_of_revenue is not None and revenue > 0:
        gross_profit = revenue - cost_of_revenue

    operating_income = _lookup(inc_map, OPERATING_INCOME_TAGS)
    interest_expense = _lookup(inc_map, INTEREST_EXPENSE_TAGS)
    if interest_expense is not None:
        interest_expense = abs(interest_expense)

    pretax_income = _lookup(inc_map, PRETAX_INCOME_TAGS)
    income_tax = _lookup(inc_map, TAX_TAGS)
    if income_tax is not None:
        income_tax = abs(income_tax)

    net_income = _lookup(inc_map, NET_INCOME_TAGS) or 0.0
    eps = _lookup(inc_map, EPS_TAGS)
    diluted_shares = _lookup(inc_map, SHARES_DILUTED_TAGS) or 0.0

    # Fallback: derive shares from net_income / EPS when tag is missing
    if diluted_shares <= 0 and eps and abs(eps) > 0.001 and net_income != 0:
        diluted_shares = abs(net_income / eps)

    if eps is None and diluted_shares > 0:
        eps = net_income / diluted_shares

    rd_expenses = _lookup(inc_map, RD_TAGS)
    if rd_expenses is not None:
        rd_expenses = abs(rd_expenses)
    sga_expenses = _lookup(inc_map, SGA_TAGS)
    if sga_expenses is not None:
        sga_expenses = abs(sga_expenses)
    operating_expenses = _lookup(inc_map, OPERATING_EXPENSES_TAGS)
    if operating_expenses is not None:
        operating_expenses = abs(operating_expenses)

    # Cash flow
    da = _lookup(cf_map, DA_TAGS) or 0.0
    da = abs(da)

    capex = _lookup(cf_map, CAPEX_TAGS) or 0.0
    capex = abs(capex)

    ocf = _lookup(cf_map, OCF_TAGS)
    sbc = _lookup(cf_map, SBC_TAGS)

    dividends_paid = _lookup(cf_map, DIVIDENDS_PAID_TAGS)
    if dividends_paid is not None:
        dividends_paid = abs(dividends_paid)

    share_repurchases = _lookup(cf_map, SHARE_REPURCHASE_TAGS)
    if share_repurchases is not None:
        share_repurchases = abs(share_repurchases)

    fcf = net_income + da - capex

    # Balance sheet
    cash = _lookup(bs_map, CASH_TAGS)
    ltd = _lookup(bs_map, LTD_TAGS)
    std = _lookup(bs_map, STD_TAGS)
    total_equity = _lookup(bs_map, EQUITY_TAGS)
    total_assets = _lookup(bs_map, TOTAL_ASSETS_TAGS)
    total_liabilities = _lookup(bs_map, TOTAL_LIABILITIES_TAGS)
    current_assets = _lookup(bs_map, CURRENT_ASSETS_TAGS)
    current_liabilities = _lookup(bs_map, CURRENT_LIABILITIES_TAGS)

    # EBITDA
    ebitda = None
    if operating_income is not None:
        ebitda = operating_income + da

    return EdgarYear(
        fiscal_year=fiscal_year,
        revenue=revenue,
        cost_of_revenue=cost_of_revenue,
        gross_profit=gross_profit,
        operating_income=operating_income,
        interest_expense=interest_expense,
        pretax_income=pretax_income,
        income_tax=income_tax,
        net_income=net_income,
        diluted_shares=diluted_shares,
        eps=eps,
        depreciation_amortization=da,
        capex=capex,
        operating_cash_flow=ocf,
        fcf=fcf,
        sbc=sbc,
        dividends_paid=dividends_paid,
        cash=cash,
        long_term_debt=ltd,
        short_term_debt=std,
        total_equity=total_equity,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        rd_expenses=rd_expenses,
        sga_expenses=sga_expenses,
        operating_expenses=operating_expenses,
        ebitda=ebitda,
        share_repurchases=share_repurchases,
    )


def _validate_year(year: EdgarYear, prior_year: Optional[EdgarYear] = None) -> List[str]:
    """Validate an extracted year's data. Returns list of warning strings."""
    warnings = []
    if year.revenue <= 0:
        warnings.append(f"FY{year.fiscal_year}: Revenue is {year.revenue} (non-positive)")
    if year.depreciation_amortization < 0:
        warnings.append(f"FY{year.fiscal_year}: D&A is negative")
    if prior_year and prior_year.revenue > 0 and year.revenue > 0:
        ratio = year.revenue / prior_year.revenue
        if ratio > 10.0 or ratio < 0.1:
            warnings.append(f"FY{year.fiscal_year}: Revenue change is {ratio:.1f}x vs prior year")
    return warnings


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_edgar_financials(ticker: str, years: int = 5) -> EdgarFinancials:
    """
    Fetch financial data from SEC EDGAR via edgartools.

    Uses Financials.extract() on multiple 10-K filings (each gives ~3 years
    of IS/CF data) and stitches them into a single 5-year time series.
    Newer filings take precedence when years overlap.

    Returns EdgarFinancials with company metadata and per-year financial data
    (oldest → newest).
    """
    ticker = ticker.upper()

    # Check cache
    cached = _edgar_cache.get(f"edgar:{ticker}")
    if cached is not None:
        print(f"[EDGAR] Cache hit for {ticker}")
        return cached

    try:
        from edgar import Company, set_identity
    except ImportError:
        raise ImportError("edgartools is required: pip install edgartools")

    set_identity("equity-research-tool research@equityresearch.com")

    # Look up company
    try:
        company = Company(ticker)
    except Exception as exc:
        raise ValueError(f"Could not find company for ticker {ticker}: {exc}")

    company_name = company.name or ticker
    sic_code = int(company.sic) if company.sic else 0
    cik = str(company.cik) if company.cik else ""
    sector, industry = map_sic_to_gics(sic_code)

    print(f"[EDGAR] Found company: {company_name} (CIK: {cik}, SIC: {sic_code})")

    # ── Fetch multiple 10-K filings to get 5 years of data ────────────
    # Each 10-K has ~3 years of IS/CF and ~2 years of BS.
    # 3 filings → 5 unique fiscal years (with overlap).
    # We process filings newest-first; the first filing to provide a given
    # fiscal year wins (most recent data takes precedence).
    try:
        from edgar import Financials
    except ImportError:
        raise ImportError("edgartools >= 4.6 required for Financials.extract")

    # Fetch enough filings: 3 filings covers 5 unique years
    n_filings = 3 if years <= 5 else (years // 2 + 1)
    try:
        all_10k = company.get_filings(form="10-K").latest(n_filings)
    except Exception as exc:
        raise ValueError(f"Could not get 10-K filings for {ticker}: {exc}")

    # Accumulate concept maps across filings (newest filing first = priority)
    inc_maps: Dict[str, Dict[str, float]] = {}  # date_col → concept map
    bs_maps: Dict[str, Dict[str, float]] = {}
    cf_maps: Dict[str, Dict[str, float]] = {}

    for i, filing in enumerate(all_10k):
        try:
            fin = Financials.extract(filing)
        except Exception as exc:
            print(f"[EDGAR] Filing {i} ({filing.period_of_report}) extract failed: {exc}")
            continue

        # Income statement
        try:
            inc_df = fin.income_statement().to_dataframe()
            dcols = _get_date_cols(inc_df)
            maps = _df_to_concept_maps(inc_df, dcols)
            for dc, cmap in maps.items():
                if dc not in inc_maps:  # newer filing takes precedence
                    inc_maps[dc] = cmap
        except Exception:
            inc_df = None

        # Balance sheet
        try:
            bs_df = fin.balance_sheet().to_dataframe()
            dcols = _get_date_cols(bs_df)
            maps = _df_to_concept_maps(bs_df, dcols)
            for dc, cmap in maps.items():
                if dc not in bs_maps:
                    bs_maps[dc] = cmap
        except Exception:
            pass

        # Cash flow statement
        try:
            cf_df = fin.cashflow_statement().to_dataframe()
            dcols = _get_date_cols(cf_df)
            maps = _df_to_concept_maps(cf_df, dcols)
            for dc, cmap in maps.items():
                if dc not in cf_maps:
                    cf_maps[dc] = cmap
        except Exception:
            pass

        period = str(filing.period_of_report or "")
        print(f"[EDGAR] Filing {i} ({period}): "
              f"IS={len(inc_maps)} dates, BS={len(bs_maps)}, CF={len(cf_maps)}")

    if not inc_maps:
        raise ValueError(f"No income statement data available for {ticker}")

    # ── Extract years from concept maps ─────────────────────────────────
    # Use all date columns from income statement (superset)
    all_date_cols = sorted(inc_maps.keys())
    print(f"[EDGAR] All date columns across filings: {all_date_cols}")

    extracted_years: Dict[int, EdgarYear] = {}
    for dcol in all_date_cols:
        inc_map = inc_maps.get(dcol, {})
        bs_map = bs_maps.get(dcol, {})
        cf_map = cf_maps.get(dcol, {})

        year_data = _extract_year(dcol, inc_map, bs_map, cf_map)
        if year_data and year_data.fiscal_year not in extracted_years:
            extracted_years[year_data.fiscal_year] = year_data
            print(f"[EDGAR] FY{year_data.fiscal_year}: rev={year_data.revenue:.0f}  "
                  f"ni={year_data.net_income:.0f}  da={year_data.depreciation_amortization:.0f}  "
                  f"capex={year_data.capex:.0f}  fcf={year_data.fcf:.0f}")

    # Keep only the most recent `years` fiscal years
    all_fy = sorted(extracted_years.keys())
    if len(all_fy) > years:
        keep = all_fy[-years:]
        extracted_years = {k: v for k, v in extracted_years.items() if k in keep}

    if len(extracted_years) < 2:
        raise ValueError(
            f"Insufficient financial data for {ticker}: "
            f"only {len(extracted_years)} years extracted"
        )

    # Sort oldest → newest
    sorted_years = [extracted_years[k] for k in sorted(extracted_years.keys())]

    # Validate
    for i, yr in enumerate(sorted_years):
        prior = sorted_years[i - 1] if i > 0 else None
        for w in _validate_year(yr, prior):
            print(f"[EDGAR] WARNING: {w}")

    # Get shares outstanding
    shares_outstanding = sorted_years[-1].diluted_shares

    result = EdgarFinancials(
        ticker=ticker,
        cik=cik,
        company_name=company_name,
        sector=sector,
        industry=industry,
        sic_code=sic_code,
        years=sorted_years,
        shares_outstanding=shares_outstanding,
    )

    # Cache for 7 days
    _edgar_cache.set(f"edgar:{ticker}", result, ttl=604800)

    print(f"[EDGAR] SUCCESS: {ticker} — {len(sorted_years)} years "
          f"({sorted_years[0].fiscal_year}–{sorted_years[-1].fiscal_year}), "
          f"sector={sector}")

    return result
