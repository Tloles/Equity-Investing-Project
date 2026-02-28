"""
FMP transcript fetcher — retrieves the latest earnings call transcript
for a ticker using the Financial Modeling Prep (FMP) API.

Requires FMP_API_KEY in the environment (loaded from .env).
"""

import os
import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"


def fetch_latest_transcript(ticker: str) -> dict:
    """
    Fetch the most recent earnings call transcript for `ticker`.

    Returns a dict with keys:
      - ticker
      - quarter   (int)
      - year      (int)
      - date      (str, ISO-like datetime)
      - content   (str, full transcript text)

    Raises ValueError if no transcript is found.
    Raises EnvironmentError if FMP_API_KEY is not set.
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "FMP_API_KEY is not set. Add it to your .env file."
        )

    url = f"{FMP_BASE_URL}/earning_call_transcript/{ticker.upper()}"
    params = {
        "limit": 1,
        "apikey": api_key,
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    # FMP returns an empty list when the ticker is invalid or has no transcripts
    if not data:
        raise ValueError(
            f"No earnings call transcripts found for ticker '{ticker}'."
        )

    latest = data[0]

    return {
        "ticker": latest.get("symbol", ticker.upper()),
        "quarter": latest.get("quarter"),
        "year": latest.get("year"),
        "date": latest.get("date", ""),
        "content": latest.get("content", ""),
    }
