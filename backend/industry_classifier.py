"""
industry_classifier.py — provides company sector, industry, and beta information.

Uses EDGAR data (SIC code) for sector/industry classification and Alpaca for
beta. Retains the SectorInfo dataclass interface for backward compatibility
with existing callers.
"""

from dataclasses import dataclass
from typing import Optional

from .alpaca_client import AlpacaQuote
from .config import DEFAULT_BETA
from .edgar_extractor import EdgarFinancials
from .industry_profiles import map_sic_to_gics


@dataclass
class SectorInfo:
    ticker: str
    sector: str        # e.g. "Technology"
    industry: str      # e.g. "Technology" (approximation from SIC)
    beta: float        # from Alpaca (0.0 if not available)
    company_name: str  # from EDGAR


def fetch_sector_info(
    ticker: str,
    edgar_data: Optional[EdgarFinancials] = None,
    quote: Optional[AlpacaQuote] = None,
) -> SectorInfo:
    """
    Build SectorInfo from EDGAR data and Alpaca quote.

    If edgar_data and quote are provided, uses them directly (no API calls).
    If not provided, fetches them (backward-compat for callers that don't
    yet pass pre-fetched data).

    Parameters
    ----------
    ticker     : Stock ticker symbol.
    edgar_data : Pre-fetched EDGAR financial data (optional).
    quote      : Pre-fetched Alpaca quote (optional).

    Returns
    -------
    SectorInfo with sector, industry, beta, and company name.
    """
    ticker = ticker.upper()

    if edgar_data is not None:
        # Use pre-fetched data
        sector = edgar_data.sector
        industry = edgar_data.industry
        company_name = edgar_data.company_name

        beta = DEFAULT_BETA
        if quote is not None and quote.beta and quote.beta > 0:
            beta = quote.beta

        print(f"[industry] {ticker}: sector={sector!r}  industry={industry!r}  "
              f"beta={beta}  company={company_name!r}")

        return SectorInfo(
            ticker=ticker,
            sector=sector,
            industry=industry,
            beta=beta,
            company_name=company_name,
        )

    # Fallback: fetch from EDGAR + Alpaca if data not provided
    from .edgar_extractor import fetch_edgar_financials
    from .alpaca_client import fetch_quote

    ed = fetch_edgar_financials(ticker)
    q = fetch_quote(ticker)

    return fetch_sector_info(ticker, edgar_data=ed, quote=q)
