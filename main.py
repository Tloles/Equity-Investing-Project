"""
Equity Analysis API — FastAPI entry point.

Wires together:
  - backend.sec_fetcher        (SEC EDGAR 10-K — no API key)
  - backend.transcript_fetcher (Motley Fool earnings call transcript)
  - backend.analyzer           (Claude bull/bear analysis)
  - backend.dcf                (DCF intrinsic value)

Run with:
    uvicorn main:app --reload
"""

import asyncio
import json
import os
from dataclasses import asdict
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from backend.analyzer import analyze, analyze_industry
from backend.comps import fetch_comps
from backend.config import PROJECTION_YEARS
from backend.dcf import fetch_dcf
from backend.ddm import fetch_ddm
from backend.financials import fetch_financials
from backend.industry_classifier import fetch_sector_info
from backend.industry_config import get_sector_rules
from backend.news_fetcher import fetch_news
from backend.sec_fetcher import fetch_10k_sections
from backend.transcript_fetcher import fetch_latest_transcript

load_dotenv(find_dotenv())

# ── Constants ──────────────────────────────────────────────────────────────────

STATIC_DIR      = "frontend"
EDGAR_DATA_URL  = "https://data.sec.gov"
FRED_URL        = "https://fred.stlouisfed.org"
HTTP_USER_AGENT = "equity-research-tool research@equityresearch.com"

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Equity Analysis API",
    description=(
        "Fetches a company's latest 10-K (MD&A + Risk Factors) and earnings call "
        "transcript, then produces a structured bull/bear analysis via Claude."
    ),
    version="0.1.0",
)


# ── Exception handlers ─────────────────────────────────────────────────────────


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {exc}"},
    )


# ── Response schemas ───────────────────────────────────────────────────────────


class FilingLink(BaseModel):
    year: int
    url: str


class TranscriptLink(BaseModel):
    quarter: Optional[int] = None
    year: Optional[int] = None
    url: str


class YearData(BaseModel):
    """One fiscal year of actuals (income statement + cash flow + balance sheet)."""
    year: int
    revenue: float
    operating_income: float
    interest_expense: float
    pretax_income: float
    tax_expense: float
    net_income: float
    diluted_shares: float          # weighted average diluted count (absolute)
    eps: float                     # diluted EPS in dollars
    capex: float                   # capital expenditures (positive = outflow)
    da: float                      # depreciation & amortisation
    fcf: float                     # net_income + da − capex
    revenue_growth: Optional[float] = None   # y/y; null for oldest year
    shares_growth: Optional[float]  = None   # y/y; null for oldest year
    cash: float
    long_term_debt: float
    short_term_debt: float
    net_debt: float                # long_term_debt + short_term_debt − cash


class DCFModel(BaseModel):
    # CAPM
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float

    # Historical actuals (oldest → newest, len == ACTUALS_YEARS or fewer)
    actuals: List[YearData]

    # Projection base assumptions
    base_revenue_growth: float
    base_op_margin: float
    base_interest_expense: float
    base_tax_rate: float
    base_capex_pct: float
    base_da_pct: float
    base_shares_growth: float
    exit_pe_multiple: float
    base_diluted_shares: float

    # Initial valuation bridge
    pv_fcfs: float
    pv_terminal_value: float
    equity_value: float


class PorterForceItem(BaseModel):
    rating: str
    explanation: str


class IndustryKPI(BaseModel):
    metric: str
    why_it_matters: str


class IndustryAnalysis(BaseModel):
    threat_of_new_entrants: PorterForceItem
    bargaining_power_of_suppliers: PorterForceItem
    bargaining_power_of_buyers: PorterForceItem
    threat_of_substitutes: PorterForceItem
    competitive_rivalry: PorterForceItem
    industry_structure: str
    competitive_position: str
    key_kpis: List[IndustryKPI]
    tailwinds: List[str]
    headwinds: List[str]


class DDMDividendYear(BaseModel):
    year: int
    annual_dps: float
    payout_ratio: Optional[float] = None
    dps_growth: Optional[float] = None


class DDMModel(BaseModel):
    pays_dividends: bool

    # Cost of equity (same as DCF)
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float

    # History
    history: List[DDMDividendYear] = []

    # Derived assumptions
    latest_annual_dps: float
    avg_dps_growth: float
    weighted_dps_growth: float
    avg_payout_ratio: float
    current_yield: float

    # Gordon Growth Model
    ggm_growth_rate: float
    ggm_d1: float
    ggm_intrinsic_value: float
    ggm_upside_downside: float

    # Two-Stage DDM
    ts_high_growth_rate: float
    ts_high_growth_years: int
    ts_terminal_growth_rate: float
    ts_intrinsic_value: float
    ts_pv_stage1: float
    ts_pv_terminal: float
    ts_upside_downside: float


class FinancialsYearModel(BaseModel):
    year: int
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
    cash: float
    total_current_assets: float
    total_assets: float
    total_current_liabilities: float
    total_debt: float
    total_liabilities: float
    total_equity: float
    operating_cash_flow: float
    capex: float
    free_cash_flow: float
    dividends_paid: float
    share_repurchases: float
    da: float
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    roic: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    interest_coverage: Optional[float] = None
    asset_turnover: Optional[float] = None
    revenue_growth: Optional[float] = None
    net_income_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    fcf_per_share: Optional[float] = None


class CompEntryModel(BaseModel):
    ticker: str
    company_name: str
    market_cap: float
    sector: str
    industry: str
    price: float
    pe_ratio: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    price_to_sales: Optional[float] = None
    price_to_book: Optional[float] = None
    ev_to_revenue: Optional[float] = None
    peg_ratio: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    roe: Optional[float] = None
    roic: Optional[float] = None
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    debt_to_equity: Optional[float] = None
    is_target: bool = False


class CompsModel(BaseModel):
    peers: List[CompEntryModel]
    median_pe: Optional[float] = None
    median_ev_ebitda: Optional[float] = None
    median_ps: Optional[float] = None
    median_pb: Optional[float] = None


class AnalysisResponse(BaseModel):
    ticker: str

    # 10-K metadata
    filing_date: str
    cik: str

    # Transcript metadata
    transcript_available: bool
    transcript_date: Optional[str] = None
    transcript_quarter: Optional[int] = None
    transcript_year: Optional[int] = None

    # Sector / industry classification (best-effort — None if profile unavailable)
    sector: Optional[str] = None
    industry: Optional[str] = None

    # Source document links
    filing_urls: List[FilingLink] = []
    transcript_urls: List[TranscriptLink] = []

    # Price widget / DCF (best-effort — None if FMP data unavailable)
    dcf_available: bool
    current_price: Optional[float] = None
    intrinsic_value: Optional[float] = None
    upside_downside: Optional[float] = None
    dcf_model: Optional[DCFModel] = None
    dcf_warning: Optional[str] = None

    # Claude analysis
    overall_rating: str = "Neutral"
    thesis_statement: str = ""
    key_metrics: list = []
    bull_case: list
    bear_case: list
    downplayed_risks: list
    recent_catalysts: list = []
    sentiment_summary: str = ""
    analyst_summary: str

    # Industry analysis (best-effort — None if Claude call fails)
    industry_analysis: Optional[IndustryAnalysis] = None

    # DDM (best-effort — None if dividend data unavailable)
    ddm_available: bool = False
    ddm_model: Optional[DDMModel] = None

    # Financials (best-effort — None if FMP data unavailable)
    financials_available: bool = False
    financials: Optional[List[FinancialsYearModel]] = None

    # Comps (best-effort — None if peers unavailable)
    comps_available: bool = False
    comps: Optional[CompsModel] = None


class RecalculateRequest(BaseModel):
    base_revenue: float
    base_diluted_shares: float
    interest_expense: float
    growth_rates: List[float]     # 5 per-year y/y revenue growth rates
    op_margins: List[float]       # 5 per-year operating margins
    tax_rates: List[float]        # 5 per-year tax rates
    capex_pcts: List[float]       # 5 per-year capex as % of revenue
    da_pcts: List[float]          # 5 per-year D&A as % of revenue
    shares_growths: List[float]   # 5 per-year diluted shares y/y change
    exit_pe_multiple: float
    cost_of_equity: float
    current_price: float


class RecalculateResponse(BaseModel):
    intrinsic_value: float
    upside_downside: float
    pv_fcfs: float
    pv_terminal_value: float
    equity_value: float


class DDMRecalcRequest(BaseModel):
    """Client-overridden DDM assumptions."""
    latest_annual_dps: float
    current_price: float
    cost_of_equity: float
    # Gordon Growth
    ggm_growth_rate: float
    # Two-Stage
    ts_high_growth_rate: float
    ts_high_growth_years: int
    ts_terminal_growth_rate: float


class DDMRecalcResponse(BaseModel):
    ggm_d1: float
    ggm_intrinsic_value: float
    ggm_upside_downside: float
    ts_intrinsic_value: float
    ts_pv_stage1: float
    ts_pv_terminal: float
    ts_upside_downside: float


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Returns liveness and data-source reachability status."""
    checks: dict = {}

    # FMP — key presence only (avoids consuming API quota)
    checks["fmp"] = "ok" if os.getenv("FMP_API_KEY") else "missing_api_key"

    # FRED — lightweight connectivity check
    try:
        r = await asyncio.to_thread(
            requests.head, FRED_URL,
            timeout=5, headers={"User-Agent": HTTP_USER_AGENT},
        )
        checks["fred"] = "ok" if r.status_code < 500 else f"http_{r.status_code}"
    except Exception as exc:
        checks["fred"] = f"unreachable ({type(exc).__name__})"

    # SEC EDGAR — lightweight connectivity check
    try:
        r = await asyncio.to_thread(
            requests.head, EDGAR_DATA_URL,
            timeout=5, headers={"User-Agent": HTTP_USER_AGENT},
        )
        checks["sec"] = "ok" if r.status_code < 500 else f"http_{r.status_code}"
    except Exception as exc:
        checks["sec"] = f"unreachable ({type(exc).__name__})"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "sources": checks}


@app.post(
    "/dcf/recalculate/{ticker}",
    response_model=RecalculateResponse,
    tags=["analysis"],
    summary="Recompute DCF with overridden per-year assumptions",
)
async def recalculate_dcf(ticker: str, req: RecalculateRequest) -> RecalculateResponse:
    """
    Recompute intrinsic value using per-year assumptions from the client.

    FCF per year = Net Income + D&A − Capex
    Discount rate = cost_of_equity (equity-basis, no WACC)
    Terminal value = Year-5 Net Income × exit_pe_multiple
    IV per share = (PV of FCFs + PV of Terminal Value) / base_diluted_shares
    """
    n = PROJECTION_YEARS
    list_fields = [
        ("growth_rates",   req.growth_rates),
        ("op_margins",     req.op_margins),
        ("tax_rates",      req.tax_rates),
        ("capex_pcts",     req.capex_pcts),
        ("da_pcts",        req.da_pcts),
        ("shares_growths", req.shares_growths),
    ]
    for name, lst in list_fields:
        if len(lst) != n:
            raise HTTPException(
                status_code=422,
                detail=f"{name} must have exactly {n} values (got {len(lst)}).",
            )

    prev_revenue = req.base_revenue
    prev_shares  = req.base_diluted_shares
    pv_fcfs      = 0.0
    last_net_income = 0.0

    for i in range(n):
        revenue    = prev_revenue * (1.0 + req.growth_rates[i])
        op_income  = revenue * req.op_margins[i]
        pretax     = op_income - req.interest_expense
        tax        = pretax * req.tax_rates[i] if pretax > 0 else 0.0
        net_income = pretax - tax
        shares     = prev_shares * (1.0 + req.shares_growths[i])
        capex      = revenue * req.capex_pcts[i]
        da         = revenue * req.da_pcts[i]
        fcf        = net_income + da - capex
        pv_fcfs   += fcf / (1.0 + req.cost_of_equity) ** (i + 1)
        prev_revenue    = revenue
        prev_shares     = shares
        last_net_income = net_income

    tv            = last_net_income * req.exit_pe_multiple
    pv_tv         = tv / (1.0 + req.cost_of_equity) ** n
    equity_value  = pv_fcfs + pv_tv
    intrinsic_value = (
        equity_value / req.base_diluted_shares if req.base_diluted_shares > 0 else 0.0
    )
    upside_downside = (
        (intrinsic_value - req.current_price) / req.current_price * 100
        if req.current_price > 0 else 0.0
    )

    return RecalculateResponse(
        intrinsic_value   = round(intrinsic_value, 2),
        upside_downside   = round(upside_downside, 1),
        pv_fcfs           = round(pv_fcfs, 0),
        pv_terminal_value = round(pv_tv, 0),
        equity_value      = round(equity_value, 0),
    )


@app.post(
    "/ddm/recalculate/{ticker}",
    response_model=DDMRecalcResponse,
    tags=["analysis"],
    summary="Recompute DDM with overridden assumptions",
)
async def recalculate_ddm(ticker: str, req: DDMRecalcRequest) -> DDMRecalcResponse:
    """
    Recompute both Gordon Growth and Two-Stage DDM intrinsic values
    using client-overridden assumptions.
    """
    re = req.cost_of_equity
    dps = req.latest_annual_dps
    price = req.current_price

    # Gordon Growth Model
    ggm_g = req.ggm_growth_rate
    ggm_d1 = dps * (1.0 + ggm_g)
    denom = re - ggm_g
    ggm_iv = (ggm_d1 / denom) if denom > 0 and ggm_d1 > 0 else 0.0
    ggm_upside = (ggm_iv - price) / price * 100 if price > 0 and ggm_iv > 0 else 0.0

    # Two-Stage DDM
    g1 = req.ts_high_growth_rate
    n = req.ts_high_growth_years
    g2 = req.ts_terminal_growth_rate

    pv_stage1 = 0.0
    div = dps
    for t in range(1, n + 1):
        div *= (1.0 + g1)
        pv_stage1 += div / (1.0 + re) ** t

    d_terminal = div * (1.0 + g2)
    denom2 = re - g2
    if denom2 > 0:
        tv = d_terminal / denom2
        pv_terminal = tv / (1.0 + re) ** n
    else:
        pv_terminal = 0.0

    ts_iv = pv_stage1 + pv_terminal
    ts_upside = (ts_iv - price) / price * 100 if price > 0 and ts_iv > 0 else 0.0

    return DDMRecalcResponse(
        ggm_d1              = round(ggm_d1, 4),
        ggm_intrinsic_value = round(ggm_iv, 2),
        ggm_upside_downside = round(ggm_upside, 1),
        ts_intrinsic_value  = round(ts_iv, 2),
        ts_pv_stage1        = round(pv_stage1, 2),
        ts_pv_terminal      = round(pv_terminal, 2),
        ts_upside_downside  = round(ts_upside, 1),
    )


@app.get(
    "/analyze/{ticker}",
    response_model=AnalysisResponse,
    tags=["analysis"],
    summary="Full bull/bear analysis for a ticker",
)
async def analyze_ticker(ticker: str) -> AnalysisResponse:
    """
    1. Fetch the latest 10-K MD&A + Risk Factors from SEC EDGAR.
    2. Fetch the latest earnings call transcript from Motley Fool (best-effort).
    3. Send both to Claude and return a structured bull/bear analysis.

    Both upstream fetches run concurrently. If the transcript or DCF is
    unavailable the analysis continues with whatever data is available.
    """
    ticker = ticker.upper()

    # ------------------------------------------------------------------
    # Phase 0: sector classification (single fast call — result is used
    # to adapt DCF assumptions and the Claude analysis prompt)
    # ------------------------------------------------------------------
    try:
        sector_info = await asyncio.to_thread(fetch_sector_info, ticker)
    except Exception as exc:
        print(f"[main] sector info fetch failed — {type(exc).__name__}: {exc}")
        sector_info = None

    sector_rules = get_sector_rules(sector_info.sector if sector_info else "")

    # ------------------------------------------------------------------
    # Phase 1: fetch 10-K, transcript, and DCF data concurrently
    # ------------------------------------------------------------------
    results = await asyncio.gather(
        asyncio.to_thread(fetch_10k_sections, ticker),
        asyncio.to_thread(
            fetch_latest_transcript, ticker,
            sector_info.company_name if sector_info else "",
        ),
        asyncio.to_thread(fetch_dcf, ticker, sector_info),
        asyncio.to_thread(fetch_ddm, ticker, sector_info),
        asyncio.to_thread(fetch_financials, ticker),
        asyncio.to_thread(fetch_comps, ticker),
        asyncio.to_thread(fetch_news, ticker),
        return_exceptions=True,
    )
    tenk_result, transcript_result, dcf_result, ddm_result, financials_result, comps_result, news_result = results

    # 10-K is mandatory — map known exception types to HTTP errors
    if isinstance(tenk_result, ValueError):
        raise HTTPException(status_code=404, detail=str(tenk_result))
    if isinstance(tenk_result, EnvironmentError):
        raise HTTPException(status_code=500, detail=str(tenk_result))
    if isinstance(tenk_result, requests.HTTPError):
        raise HTTPException(
            status_code=502, detail=f"SEC EDGAR upstream error: {tenk_result}"
        )
    if isinstance(tenk_result, Exception):
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch 10-K: {tenk_result}"
        )

    tenk_data: dict = tenk_result  # type: ignore[assignment]

    # Transcript is optional — degrade gracefully if missing or errored
    transcript_available = not isinstance(transcript_result, Exception)
    transcript_data: Optional[dict] = (
        transcript_result if transcript_available else None  # type: ignore[assignment]
    )

    # DCF is optional — degrade gracefully if FMP data is unavailable
    if isinstance(dcf_result, Exception):
        print(f"[main] DCF failed — {type(dcf_result).__name__}: {dcf_result}")
        dcf_available = False
        dcf_data = None
    else:
        print(
            f"[main] DCF succeeded — intrinsic_value={dcf_result.intrinsic_value}, "  # type: ignore[union-attr]
            f"current_price={dcf_result.current_price}"  # type: ignore[union-attr]
        )
        dcf_available = True
        dcf_data = dcf_result  # type: ignore[assignment]

    # DDM is optional — degrade gracefully
    if isinstance(ddm_result, Exception):
        print(f"[main] DDM failed — {type(ddm_result).__name__}: {ddm_result}")
        ddm_available = False
        ddm_data = None
    else:
        ddm_data = ddm_result  # type: ignore[assignment]
        ddm_available = ddm_data.pays_dividends
        print(
            f"[main] DDM {'succeeded' if ddm_available else 'N/A (no dividends)'}"
            f" — ticker={ticker}"
        )

    # Financials are optional — degrade gracefully
    if isinstance(financials_result, Exception):
        print(f"[main] Financials failed — {type(financials_result).__name__}: {financials_result}")
        financials_available = False
        financials_data = None
    else:
        financials_data = financials_result  # type: ignore[assignment]
        financials_available = len(financials_data.years) > 0
        print(f"[main] Financials succeeded — {len(financials_data.years)} years")

    # Comps are optional — degrade gracefully
    if isinstance(comps_result, Exception):
        print(f"[main] Comps failed — {type(comps_result).__name__}: {comps_result}")
        comps_available = False
        comps_data = None
    else:
        comps_data = comps_result  # type: ignore[assignment]
        comps_available = len(comps_data.peers) > 1
        print(f"[main] Comps succeeded — {len(comps_data.peers)} entries")

    # News is optional — degrade gracefully
    news_text = ""
    if isinstance(news_result, Exception):
        print(f"[main] News failed — {type(news_result).__name__}: {news_result}")
        news_data = None
    else:
        news_data = news_result  # type: ignore[assignment]
        news_text = news_data.news_summary_text
        total = len(news_data.news_items) + len(news_data.social_posts)
        print(f"[main] News succeeded — {total} items")

    # ------------------------------------------------------------------
    # Phase 2: build combined text inputs and run both Claude analyses
    # concurrently (bull/bear + industry)
    # ------------------------------------------------------------------
    tenk_text = "\n\n".join(
        filter(None, [tenk_data.get("mda"), tenk_data.get("risk_factors")])
    )
    transcript_text = transcript_data["content"] if transcript_data else ""

    _sector = sector_info.sector if sector_info else ""

    claude_results = await asyncio.gather(
        asyncio.to_thread(
            analyze, ticker, tenk_text, transcript_text,
            _sector, sector_rules.analyst_guidance, news_text,
        ),
        asyncio.to_thread(
            analyze_industry, ticker, tenk_text, transcript_text, _sector,
        ),
        return_exceptions=True,
    )
    analysis_result, industry_result = claude_results

    if isinstance(analysis_result, EnvironmentError):
        raise HTTPException(status_code=500, detail=str(analysis_result))
    if isinstance(analysis_result, Exception):
        print(f"[main] Analysis FAILED — {type(analysis_result).__name__}: {analysis_result}")
        import traceback
        traceback.print_exception(type(analysis_result), analysis_result, analysis_result.__traceback__)
        raise HTTPException(status_code=500, detail=str(analysis_result))

    result = analysis_result  # type: ignore[assignment]

    if isinstance(industry_result, Exception):
        print(f"[main] Industry analysis failed — {type(industry_result).__name__}: {industry_result}")
        industry_data = None
    else:
        industry_data = industry_result  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Phase 3: assemble and return response
    # ------------------------------------------------------------------
    dcf_model_payload: Optional[DCFModel] = None
    if dcf_data is not None:
        dcf_model_payload = DCFModel(
            risk_free_rate        = dcf_data.risk_free_rate,
            equity_risk_premium   = dcf_data.equity_risk_premium,
            beta                  = dcf_data.beta,
            cost_of_equity        = dcf_data.cost_of_equity,
            actuals               = [YearData(**asdict(a)) for a in dcf_data.actuals],
            base_revenue_growth   = dcf_data.base_revenue_growth,
            base_op_margin        = dcf_data.base_op_margin,
            base_interest_expense = dcf_data.base_interest_expense,
            base_tax_rate         = dcf_data.base_tax_rate,
            base_capex_pct        = dcf_data.base_capex_pct,
            base_da_pct           = dcf_data.base_da_pct,
            base_shares_growth    = dcf_data.base_shares_growth,
            exit_pe_multiple      = dcf_data.exit_pe_multiple,
            base_diluted_shares   = dcf_data.base_diluted_shares,
            pv_fcfs               = dcf_data.pv_fcfs,
            pv_terminal_value     = dcf_data.pv_terminal_value,
            equity_value          = dcf_data.equity_value,
        )

    ddm_model_payload: Optional[DDMModel] = None
    if ddm_data is not None:
        ddm_model_payload = DDMModel(
            pays_dividends       = ddm_data.pays_dividends,
            risk_free_rate       = ddm_data.risk_free_rate,
            equity_risk_premium  = ddm_data.equity_risk_premium,
            beta                 = ddm_data.beta,
            cost_of_equity       = ddm_data.cost_of_equity,
            history              = [
                DDMDividendYear(
                    year=h.year,
                    annual_dps=h.annual_dps,
                    payout_ratio=h.payout_ratio,
                    dps_growth=h.dps_growth,
                )
                for h in ddm_data.history
            ],
            latest_annual_dps    = ddm_data.latest_annual_dps,
            avg_dps_growth       = ddm_data.avg_dps_growth,
            weighted_dps_growth  = ddm_data.weighted_dps_growth,
            avg_payout_ratio     = ddm_data.avg_payout_ratio,
            current_yield        = ddm_data.current_yield,
            ggm_growth_rate      = ddm_data.ggm_growth_rate,
            ggm_d1               = ddm_data.ggm_d1,
            ggm_intrinsic_value  = ddm_data.ggm_intrinsic_value,
            ggm_upside_downside  = ddm_data.ggm_upside_downside,
            ts_high_growth_rate  = ddm_data.ts_high_growth_rate,
            ts_high_growth_years = ddm_data.ts_high_growth_years,
            ts_terminal_growth_rate = ddm_data.ts_terminal_growth_rate,
            ts_intrinsic_value   = ddm_data.ts_intrinsic_value,
            ts_pv_stage1         = ddm_data.ts_pv_stage1,
            ts_pv_terminal       = ddm_data.ts_pv_terminal,
            ts_upside_downside   = ddm_data.ts_upside_downside,
        )

    return AnalysisResponse(
        ticker=result.ticker,
        filing_date=tenk_data["filing_date"],
        cik=tenk_data["cik"],
        sector=sector_info.sector if sector_info else None,
        industry=sector_info.industry if sector_info else None,
        filing_urls=[FilingLink(**f) for f in tenk_data.get("filing_urls", [])],
        transcript_available=transcript_available,
        transcript_date=transcript_data["date"] if transcript_data else None,
        transcript_quarter=transcript_data["quarter"] if transcript_data else None,
        transcript_year=transcript_data["year"] if transcript_data else None,
        transcript_urls=[
            TranscriptLink(**t)
            for t in (transcript_data.get("all_transcripts") or [])
        ] if transcript_data else [],
        dcf_available=dcf_available,
        current_price=dcf_data.current_price if dcf_data else None,
        intrinsic_value=dcf_data.intrinsic_value if dcf_data else None,
        upside_downside=dcf_data.upside_downside if dcf_data else None,
        dcf_model=dcf_model_payload,
        dcf_warning=sector_rules.dcf_warning,
        overall_rating=result.overall_rating,
        thesis_statement=result.thesis_statement,
        key_metrics=result.key_metrics,
        bull_case=result.bull_case,
        bear_case=result.bear_case,
        downplayed_risks=result.downplayed_risks,
        recent_catalysts=result.recent_catalysts,
        sentiment_summary=result.sentiment_summary,
        analyst_summary=result.analyst_summary,
        industry_analysis=IndustryAnalysis(
            threat_of_new_entrants=PorterForceItem(
                rating=industry_data.threat_of_new_entrants.rating,
                explanation=industry_data.threat_of_new_entrants.explanation,
            ),
            bargaining_power_of_suppliers=PorterForceItem(
                rating=industry_data.bargaining_power_of_suppliers.rating,
                explanation=industry_data.bargaining_power_of_suppliers.explanation,
            ),
            bargaining_power_of_buyers=PorterForceItem(
                rating=industry_data.bargaining_power_of_buyers.rating,
                explanation=industry_data.bargaining_power_of_buyers.explanation,
            ),
            threat_of_substitutes=PorterForceItem(
                rating=industry_data.threat_of_substitutes.rating,
                explanation=industry_data.threat_of_substitutes.explanation,
            ),
            competitive_rivalry=PorterForceItem(
                rating=industry_data.competitive_rivalry.rating,
                explanation=industry_data.competitive_rivalry.explanation,
            ),
            industry_structure=industry_data.industry_structure,
            competitive_position=industry_data.competitive_position,
            key_kpis=[
                IndustryKPI(metric=k.metric, why_it_matters=k.why_it_matters)
                for k in industry_data.key_kpis
            ],
            tailwinds=industry_data.tailwinds,
            headwinds=industry_data.headwinds,
        ) if industry_data else None,
        ddm_available=ddm_available,
        ddm_model=ddm_model_payload,
        financials_available=financials_available,
        financials=[
            FinancialsYearModel(**{
                k: getattr(y, k) for k in FinancialsYearModel.model_fields
            })
            for y in financials_data.years
        ] if financials_data and financials_available else None,
        comps_available=comps_available,
        comps=CompsModel(
            peers=[
                CompEntryModel(**{
                    k: getattr(e, k) for k in CompEntryModel.model_fields
                })
                for e in comps_data.peers
            ],
            median_pe=comps_data.median_pe,
            median_ev_ebitda=comps_data.median_ev_ebitda,
            median_ps=comps_data.median_ps,
            median_pb=comps_data.median_pb,
        ) if comps_data and comps_available else None,
    )


# ── Static frontend — mounted last so API routes take precedence ───────────────

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
