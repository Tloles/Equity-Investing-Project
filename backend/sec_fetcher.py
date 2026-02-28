"""
SEC EDGAR fetcher — retrieves MD&A (Item 7) and Risk Factors (Item 1A)
from a company's latest 10-K filing using the public EDGAR API (no key required).

Public exports reused by other modules
---------------------------------------
  get_cik(ticker)     — resolve ticker → zero-padded CIK string
  HEADERS             — SEC-mandated User-Agent header dict
  EDGAR_DATA_URL      — https://data.sec.gov
  EDGAR_ARCHIVE_URL   — https://www.sec.gov/Archives/edgar/data
"""

import re
import requests
from bs4 import BeautifulSoup

# SEC requires a descriptive User-Agent header for all API calls
HEADERS = {"User-Agent": "equity-research-tool research@equityresearch.com"}

EDGAR_DATA_URL = "https://data.sec.gov"
EDGAR_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data"


def get_cik(ticker: str) -> str:
    """
    Resolve a ticker symbol to a zero-padded 10-digit CIK string
    using SEC's company tickers JSON file.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    ticker_upper = ticker.upper()
    for entry in resp.json().values():
        if entry["ticker"] == ticker_upper:
            return str(entry["cik_str"]).zfill(10)

    raise ValueError(f"Ticker '{ticker}' not found in SEC EDGAR company tickers.")


def _get_recent_10ks(cik: str, n: int = 3) -> list:
    """
    Fetch the submissions JSON for a company and return up to n
    (accession_number, primary_document_filename, filing_date) tuples
    for the most recent 10-K filings, newest first.
    """
    url = f"{EDGAR_DATA_URL}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    recent = data["filings"]["recent"]
    forms = recent["form"]
    accessions = recent["accessionNumber"]
    primary_docs = recent["primaryDocument"]
    dates = recent["filingDate"]

    results = []
    for i, form in enumerate(forms):
        if form == "10-K":
            results.append((accessions[i], primary_docs[i], dates[i]))
            if len(results) >= n:
                break

    if not results:
        raise ValueError(f"No 10-K filing found for CIK {cik}.")
    return results


def fetch_document_text(cik: str, accession_number: str, primary_doc: str) -> str:
    """
    Download the primary 10-K document and return clean plain text
    with scripts/styles removed.
    """
    cik_int = int(cik)  # strip leading zeros for the archive path
    acc_no_dashes = accession_number.replace("-", "")
    doc_url = f"{EDGAR_ARCHIVE_URL}/{cik_int}/{acc_no_dashes}/{primary_doc}"

    resp = requests.get(doc_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Collapse runs of whitespace/newlines into a single space
    text = re.sub(r"\s+", " ", text)
    return text


def extract_section(
    text: str,
    start_pattern: str,
    end_pattern: str,
    max_chars: int = 15_000,
) -> str:
    """
    Extract a section of a 10-K by finding the start heading and the
    next item heading.  Returns up to `max_chars` characters.
    """
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""

    start_pos = start_match.start()
    # Search for the end pattern in the remainder of the document
    end_match = re.search(end_pattern, text[start_pos + 200 :], re.IGNORECASE)

    if end_match:
        end_pos = start_pos + 200 + end_match.start()
    else:
        end_pos = start_pos + max_chars

    return text[start_pos:end_pos][:max_chars]


def fetch_10k_sections(ticker: str) -> dict:
    """
    Main entry point.  Returns a dict with keys:
      - ticker
      - filing_date      (most recent 10-K)
      - cik
      - accession_number (most recent 10-K)
      - risk_factors     (Item 1A text, up to 15 000 chars)
      - mda              (Item 7 text, up to 15 000 chars)
      - filing_urls      list of {year, url} for up to 3 recent 10-Ks
    """
    cik = get_cik(ticker)
    filings = _get_recent_10ks(cik, n=3)
    accession_number, primary_doc, filing_date = filings[0]  # most recent
    text = fetch_document_text(cik, accession_number, primary_doc)

    # Build direct EDGAR archive URLs for each filing
    cik_int = int(cik)
    filing_urls = []
    for acc, doc, date in filings:
        acc_clean = acc.replace("-", "")
        filing_urls.append({
            "year": int(date[:4]),
            "url": f"{EDGAR_ARCHIVE_URL}/{cik_int}/{acc_clean}/{doc}",
        })

    # Item 1A — Risk Factors (ends at Item 1B or Item 2)
    risk_factors = extract_section(
        text,
        start_pattern=r"item\s+1a[\.\s–\-]*risk\s+factor",
        end_pattern=r"item\s+1b[\.\s–\-]|item\s+2[\.\s–\-]",
        max_chars=15_000,
    )

    # Item 7 — MD&A (ends at Item 7A or Item 8)
    mda = extract_section(
        text,
        start_pattern=r"item\s+7[\.\s–\-]*management.{0,30}discussion",
        end_pattern=r"item\s+7a[\.\s–\-]|item\s+8[\.\s–\-]",
        max_chars=15_000,
    )

    return {
        "ticker": ticker.upper(),
        "filing_date": filing_date,
        "cik": cik,
        "accession_number": accession_number,
        "risk_factors": risk_factors,
        "mda": mda,
        "filing_urls": filing_urls,
    }
