"""
industry_classifier.py — fetches company sector, industry, and beta from the
FMP company profile endpoint.

Returns a SectorInfo dataclass.  Beta is included so callers can avoid a
separate profile request.

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass

import requests
from dotenv import find_dotenv, load_dotenv

_dotenv_path = find_dotenv()
load_dotenv(_dotenv_path, override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"


@dataclass
class SectorInfo:
    ticker: str
    sector: str        # e.g. "Technology"
    industry: str      # e.g. "Software—Application"
    beta: float        # 0.0 if not available from profile
    company_name: str  # e.g. "Apple Inc." — used for transcript validation


def fetch_sector_info(ticker: str) -> SectorInfo:
    """
    Fetch sector, industry, and beta from the FMP company profile endpoint.

    Raises
    ------
    EnvironmentError    if FMP_API_KEY is not set.
    ValueError          if FMP returns no data for the ticker.
    requests.HTTPError  if the API request fails.
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise EnvironmentError("FMP_API_KEY is not set. Add it to your .env file.")

    ticker = ticker.upper()
    url = f"{FMP_BASE_URL}/profile"
    params = {"symbol": ticker, "apikey": api_key}

    resp = requests.get(url, params=params, timeout=10)
    print(f"[industry] GET {resp.url} → {resp.status_code}")
    resp.raise_for_status()

    data = resp.json()
    if not data:
        raise ValueError(f"FMP profile returned empty data for {ticker}")

    profile      = data[0]
    sector       = profile.get("sector")      or ""
    industry     = profile.get("industry")    or ""
    beta         = float(profile.get("beta")  or 0)
    company_name = profile.get("companyName") or ""

    print(f"[industry] {ticker}: sector={sector!r}  industry={industry!r}  beta={beta}  company={company_name!r}")
    return SectorInfo(ticker=ticker, sector=sector, industry=industry, beta=beta, company_name=company_name)
