"""
Transcript fetcher — retrieves up to 12 quarters of earnings call transcripts
from SEC EDGAR 8-K filings (no API key required).

Strategy
--------
1. Resolve ticker → CIK via sec_fetcher.get_cik()
2. Fetch the submissions JSON for the company
3. Filter 8-K / 8-K/A filings whose "items" field contains 2.02 or 7.01
4. For each candidate, parse the filing index page to locate the best EX-99
   exhibit (prefer those with "transcript" / "earnings call" in description/type)
5. Fetch and parse the exhibit text
6. Infer the earnings quarter and year from text content (or fall back to
   the filing date)

Returns at most MAX_TRANSCRIPTS results, newest first.
"""

import re
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from .sec_fetcher import EDGAR_ARCHIVE_URL, EDGAR_DATA_URL, HEADERS, get_cik

MAX_TRANSCRIPTS   = 12
_TRANSCRIPT_ITEMS = frozenset({"2.02", "7.01"})
_SKIP_KEYWORDS    = ("press release", "news release", "financial results")


# ── Helper: fetch submissions JSON ────────────────────────────────────────────

def _fetch_submissions(cik: str) -> dict:
    url  = f"{EDGAR_DATA_URL}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Helper: find candidate 8-K filings ───────────────────────────────────────

def _candidate_8ks(submissions: dict) -> List[Tuple[str, str]]:
    """
    Return (accession_number, filing_date) tuples for 8-K / 8-K/A filings
    whose 'items' field contains at least one transcript-related item (2.02 / 7.01),
    newest first, up to 2*MAX_TRANSCRIPTS candidates.
    """
    recent     = submissions["filings"]["recent"]
    forms      = recent["form"]
    accessions = recent["accessionNumber"]
    dates      = recent["filingDate"]
    items_list = recent.get("items", [""] * len(forms))

    results: List[Tuple[str, str]] = []
    for i, form in enumerate(forms):
        if form not in ("8-K", "8-K/A"):
            continue
        filing_items = set(re.split(r"[,\s]+", items_list[i]))
        if filing_items & _TRANSCRIPT_ITEMS:
            results.append((accessions[i], dates[i]))
            if len(results) >= 2 * MAX_TRANSCRIPTS:
                break

    return results


# ── Helper: find the best exhibit URL from a filing's index page ──────────────

def _find_exhibit_url(cik_int: int, accession: str) -> Optional[str]:
    """
    Fetch the filing's index page and return the URL of the best EX-99 exhibit.

    Priority 0 (preferred): description or type contains 'transcript' or 'earnings call'
    Priority 1 (fallback):  any EX-99.x exhibit not obviously a press release
    """
    acc_clean = accession.replace("-", "")
    index_url = (
        f"{EDGAR_ARCHIVE_URL}/{cik_int}/{acc_clean}/{accession}-index.htm"
    )

    try:
        resp = requests.get(index_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        print(
            f"[transcript] Index fetch failed ({index_url}): "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    soup  = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="tableFile")
    if not table:
        return None

    priority_0: List[str] = []
    priority_1: List[str] = []

    for row in table.find_all("tr")[1:]:   # skip header row
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        doc_type = cells[3].get_text(strip=True)
        desc     = cells[1].get_text(strip=True).lower()
        link_tag = cells[2].find("a", href=True)
        if not link_tag:
            continue

        href     = link_tag["href"]
        full_url = (
            href if href.startswith("http") else "https://www.sec.gov" + href
        )

        if "99" not in doc_type:
            continue

        # Skip obvious press releases
        if any(kw in desc for kw in _SKIP_KEYWORDS):
            continue

        if "transcript" in desc or "earnings call" in desc:
            priority_0.append(full_url)
        else:
            priority_1.append(full_url)

    if priority_0:
        return priority_0[0]
    if priority_1:
        return priority_1[0]
    return None


# ── Helper: fetch and clean exhibit text ──────────────────────────────────────

def _fetch_exhibit_text(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        print(f"[transcript] Article fetch status: {resp.status_code}")
        resp.raise_for_status()
    except Exception as exc:
        print(
            f"[transcript] Article fetch failed ({url}): "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
    print(f"[transcript] Text length extracted: {len(text)} chars")
    return text if text else None


# ── Helper: infer quarter and year ────────────────────────────────────────────

_QTR_NAMES = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
}

# Approximate mapping: month of 8-K filing → earnings quarter being reported.
# Jan–Feb 8-Ks are Q4 results from the prior fiscal year.
_MONTH_TO_QUARTER = {
    1: 4,  2: 4,            # Q4 of prior year
    3: 1,  4: 1,  5: 1,    # Q1
    6: 2,  7: 2,  8: 2,    # Q2
    9: 3, 10: 3, 11: 3, 12: 3,  # Q3
}


def _parse_quarter_year(
    text: str, filing_date: str
) -> Tuple[Optional[int], Optional[int]]:
    """
    Infer the earnings quarter and fiscal year from transcript text.
    Falls back to filing date heuristics if text parsing fails.
    """
    sample = text[:3000]

    # Pattern: "Q3 2024", "Q4 2023"
    m = re.search(r"\bQ([1-4])\s+(20\d{2})\b", sample, re.I)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Pattern: "Third Quarter 2024", "First Quarter Fiscal 2025"
    m = re.search(
        r"\b(first|second|third|fourth)\s+quarter(?:\s+fiscal)?\s+(20\d{2})\b",
        sample, re.I,
    )
    if m:
        q = _QTR_NAMES.get(m.group(1).lower())
        return q, int(m.group(2))

    # Fall back to filing date
    try:
        parts = filing_date.split("-")
        month = int(parts[1])
        year  = int(parts[0])
        q     = _MONTH_TO_QUARTER[month]
        if month in (1, 2):   # Q4 of the preceding calendar year
            year -= 1
        return q, year
    except Exception:
        return None, None


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_latest_transcript(ticker: str, company_name: str = "") -> dict:
    """
    Fetch up to 12 quarters of earnings call transcripts for `ticker` from
    SEC EDGAR 8-K filings.

    Returns a dict with keys:
      - ticker
      - quarter          (int or None — most recent transcript)
      - year             (int or None — most recent transcript)
      - date             (str — always empty; filing dates aren't exposed here)
      - content          (str — all transcripts concatenated, newest first)
      - url              (str — most recent transcript exhibit URL)
      - all_transcripts  (list of {quarter, year, url} for every found transcript)

    Raises ValueError if no transcripts can be found.
    """
    t = ticker.upper()
    print(f"[transcript] Attempting SEC EDGAR 8-K fetch for {t}")

    cik     = get_cik(t)
    cik_int = int(cik)
    print(f"[transcript] Resolved CIK: {cik_int}")

    submissions = _fetch_submissions(cik)
    candidates  = _candidate_8ks(submissions)
    print(
        f"[transcript] Found {len(candidates)} candidate 8-K filings "
        f"with Items 2.02/7.01"
    )

    if not candidates:
        raise ValueError(
            f"No 8-K filings with Items 2.02 or 7.01 found for '{t}' on SEC EDGAR."
        )

    transcripts = []
    for accession, filing_date in candidates:
        if len(transcripts) >= MAX_TRANSCRIPTS:
            break

        exhibit_url = _find_exhibit_url(cik_int, accession)
        if not exhibit_url:
            print(f"[transcript] No suitable exhibit found in {accession} — skipping")
            continue

        print(f"[transcript] Search URL being fetched: {exhibit_url}")
        text = _fetch_exhibit_text(exhibit_url)
        if not text:
            continue

        quarter, year = _parse_quarter_year(text, filing_date)
        transcripts.append({
            "quarter": quarter,
            "year":    year,
            "url":     exhibit_url,
            "content": text,
        })

    print(f"[transcript] Found {len(transcripts)} transcripts for {t}")

    if not transcripts:
        print(f"[transcript] FAILED — all exhibit fetches returned empty")
        raise ValueError(
            f"All 8-K transcript exhibits for '{t}' failed to parse or "
            f"contained no text."
        )

    # Sort newest first (year desc, quarter desc; None-dated entries last)
    transcripts.sort(
        key=lambda x: (x["year"] or 0, x["quarter"] or 0), reverse=True
    )

    combined = "\n\n".join(
        f"--- Q{tr['quarter']} {tr['year']} Earnings Call ---\n{tr['content']}"
        for tr in transcripts
    )

    latest = transcripts[0]
    print(
        f"[transcript] SUCCESS — {len(transcripts)} transcripts, "
        f"{len(combined)} combined chars, latest: Q{latest['quarter']} {latest['year']}"
    )

    return {
        "ticker":          t,
        "quarter":         latest["quarter"],
        "year":            latest["year"],
        "date":            "",
        "content":         combined,
        "url":             latest["url"],
        "all_transcripts": [
            {"quarter": x["quarter"], "year": x["year"], "url": x["url"]}
            for x in transcripts
        ],
    }
