"""
Equity Analysis API — FastAPI entry point.

Wires together:
  - backend.sec_fetcher        (SEC EDGAR 10-K — no API key)
  - backend.transcript_fetcher (FMP earnings call transcript)
  - backend.analyzer           (Claude bull/bear analysis)
  - backend.dcf                (DCF intrinsic value)

Run with:
    uvicorn main:app --reload
"""

import asyncio
import os
from typing import List, Optional

import requests
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.analyzer import analyze
from backend.dcf import fetch_dcf
from backend.industry_classifier import fetch_sector_info
from backend.industry_config import get_sector_rules
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


class DCFModel(BaseModel):
    # CAPM / cost-of-capital inputs
    risk_free_rate: float
    equity_risk_premium: float
    beta: float
    cost_of_equity: float
    cost_of_debt: float

    # Model assumptions
    revenue_growth_rate: float
    fcf_margin: float
    wacc: float
    terminal_growth_rate: float
    projected_fcf: List[float]
    pv_projected_fcf: List[float]
    pv_fcfs: float
    pv_terminal_value: float
    enterprise_value: float
    net_cash: float
    equity_value: float
    shares_outstanding: float


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

    # Price widget / DCF (best-effort — None if FMP data unavailable)
    dcf_available: bool
    current_price: Optional[float] = None
    intrinsic_value: Optional[float] = None
    upside_downside: Optional[float] = None
    dcf_model: Optional[DCFModel] = None
    dcf_warning: Optional[str] = None

    # Claude analysis
    bull_case: list
    bear_case: list
    downplayed_risks: list
    analyst_summary: str


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


@app.get(
    "/analyze/{ticker}",
    response_model=AnalysisResponse,
    tags=["analysis"],
    summary="Full bull/bear analysis for a ticker",
)
async def analyze_ticker(ticker: str) -> AnalysisResponse:
    """
    1. Fetch the latest 10-K MD&A + Risk Factors from SEC EDGAR.
    2. Fetch the latest earnings call transcript from FMP (best-effort).
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
        asyncio.to_thread(fetch_latest_transcript, ticker),
        asyncio.to_thread(fetch_dcf, ticker, sector_info),
        return_exceptions=True,
    )
    tenk_result, transcript_result, dcf_result = results

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

    # ------------------------------------------------------------------
    # Phase 2: build combined text inputs and run Claude analysis
    # ------------------------------------------------------------------
    tenk_text = "\n\n".join(
        filter(None, [tenk_data.get("mda"), tenk_data.get("risk_factors")])
    )
    transcript_text = transcript_data["content"] if transcript_data else ""

    try:
        result = await asyncio.to_thread(
            analyze, ticker, tenk_text, transcript_text,
            sector_info.sector if sector_info else "",
            sector_rules.analyst_guidance,
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # ------------------------------------------------------------------
    # Phase 3: assemble and return response
    # ------------------------------------------------------------------
    return AnalysisResponse(
        ticker=result.ticker,
        filing_date=tenk_data["filing_date"],
        cik=tenk_data["cik"],
        sector=sector_info.sector if sector_info else None,
        industry=sector_info.industry if sector_info else None,
        transcript_available=transcript_available,
        transcript_date=transcript_data["date"] if transcript_data else None,
        transcript_quarter=transcript_data["quarter"] if transcript_data else None,
        transcript_year=transcript_data["year"] if transcript_data else None,
        dcf_available=dcf_available,
        current_price=dcf_data.current_price if dcf_data else None,
        intrinsic_value=dcf_data.intrinsic_value if dcf_data else None,
        upside_downside=dcf_data.upside_downside if dcf_data else None,
        dcf_model=DCFModel(
            risk_free_rate=dcf_data.risk_free_rate,
            equity_risk_premium=dcf_data.equity_risk_premium,
            beta=dcf_data.beta,
            cost_of_equity=dcf_data.cost_of_equity,
            cost_of_debt=dcf_data.cost_of_debt,
            revenue_growth_rate=dcf_data.revenue_growth_rate,
            fcf_margin=dcf_data.fcf_margin,
            wacc=dcf_data.wacc,
            terminal_growth_rate=dcf_data.terminal_growth_rate,
            projected_fcf=dcf_data.projected_fcf,
            pv_projected_fcf=dcf_data.pv_projected_fcf,
            pv_fcfs=dcf_data.pv_fcfs,
            pv_terminal_value=dcf_data.pv_terminal_value,
            enterprise_value=dcf_data.enterprise_value,
            net_cash=dcf_data.net_cash,
            equity_value=dcf_data.equity_value,
            shares_outstanding=dcf_data.shares_outstanding,
        ) if dcf_data else None,
        dcf_warning=sector_rules.dcf_warning,
        bull_case=result.bull_case,
        bear_case=result.bear_case,
        downplayed_risks=result.downplayed_risks,
        analyst_summary=result.analyst_summary,
    )


# ── Static frontend — mounted last so API routes take precedence ───────────────

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
