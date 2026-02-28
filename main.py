"""
Equity Analysis API — FastAPI entry point.

Wires together:
  - backend.sec_fetcher        (SEC EDGAR 10-K — no API key)
  - backend.transcript_fetcher (FMP earnings call transcript)
  - backend.analyzer           (Claude bull/bear analysis)

Run with:
    uvicorn main:app --reload
"""

import asyncio

import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.analyzer import analyze
from backend.sec_fetcher import fetch_10k_sections
from backend.transcript_fetcher import fetch_latest_transcript

app = FastAPI(
    title="Equity Analysis API",
    description=(
        "Fetches a company's latest 10-K (MD&A + Risk Factors) and earnings call "
        "transcript, then produces a structured bull/bear analysis via Claude."
    ),
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class AnalysisResponse(BaseModel):
    ticker: str

    # 10-K metadata
    filing_date: str
    cik: str

    # Transcript metadata
    transcript_available: bool
    transcript_date: str | None = None
    transcript_quarter: int | None = None
    transcript_year: int | None = None

    # Claude analysis
    bull_case: list[str]
    bear_case: list[str]
    downplayed_risks: list[str]
    analyst_summary: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health():
    """Liveness check."""
    return {"status": "ok"}


@app.get(
    "/analyze/{ticker}",
    response_model=AnalysisResponse,
    tags=["analysis"],
    summary="Full bull/bear analysis for a ticker",
)
async def analyze_ticker(ticker: str):
    """
    1. Fetch the latest 10-K MD&A + Risk Factors from SEC EDGAR.
    2. Fetch the latest earnings call transcript from FMP (best-effort).
    3. Send both to Claude and return a structured bull/bear analysis.

    Both upstream fetches run concurrently. If the transcript is unavailable
    the analysis continues on 10-K data alone.
    """
    ticker = ticker.upper()

    # ------------------------------------------------------------------
    # Step 1 & 2: fetch 10-K and transcript concurrently
    # ------------------------------------------------------------------
    results = await asyncio.gather(
        asyncio.to_thread(fetch_10k_sections, ticker),
        asyncio.to_thread(fetch_latest_transcript, ticker),
        return_exceptions=True,
    )
    tenk_result, transcript_result = results

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
    transcript_data: dict | None = transcript_result if transcript_available else None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Step 3: build combined text inputs and run Claude analysis
    # ------------------------------------------------------------------
    tenk_text = "\n\n".join(
        filter(None, [tenk_data.get("mda"), tenk_data.get("risk_factors")])
    )
    transcript_text = transcript_data["content"] if transcript_data else ""

    try:
        result = await asyncio.to_thread(
            analyze, ticker, tenk_text, transcript_text
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # ------------------------------------------------------------------
    # Step 4: assemble and return response
    # ------------------------------------------------------------------
    return AnalysisResponse(
        ticker=result.ticker,
        filing_date=tenk_data["filing_date"],
        cik=tenk_data["cik"],
        transcript_available=transcript_available,
        transcript_date=transcript_data["date"] if transcript_data else None,
        transcript_quarter=transcript_data["quarter"] if transcript_data else None,
        transcript_year=transcript_data["year"] if transcript_data else None,
        bull_case=result.bull_case,
        bear_case=result.bear_case,
        downplayed_risks=result.downplayed_risks,
        analyst_summary=result.analyst_summary,
    )


# ---------------------------------------------------------------------------
# Static frontend — must be mounted AFTER all API routes so the API takes
# precedence over the catch-all static file handler.
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
