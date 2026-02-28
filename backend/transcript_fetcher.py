"""
Transcript fetcher — scrapes up to 12 quarters of earnings call transcripts
from Motley Fool, combining them for Claude analysis.

Strategy (tried in order for URL discovery)
--------------------------------------------
1. Motley Fool ticker-filtered listing page (paginated, up to 4 pages):
     https://www.fool.com/earnings-call-transcripts/?ticker={ticker}&page={n}
2. Google search restricted to fool.com (paginated, up to 2 pages):
     https://www.google.com/search?q={ticker}+earnings+call+transcript+site:fool.com&start={n}

Each candidate URL is validated against the ticker and company name before
being scraped.  Up to MAX_TRANSCRIPTS articles are fetched and their content
is combined into a single string for the analysis pipeline.

No API key required.
"""

import re
from typing import List, Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MF_LISTING_URL    = "https://www.fool.com/earnings-call-transcripts/"
GOOGLE_SEARCH_URL = "https://www.google.com/search"
MAX_TRANSCRIPTS   = 12


# ── Ticker / company match validation ─────────────────────────────────────────

def _validate_match(ticker: str, company_name: str, url: str) -> bool:
    """
    Return True if `url` plausibly refers to the given ticker / company.

    Checks:
    - ticker.lower() as a substring of the URL path (reliable for 3+ char tickers)
    - First long word (>= 4 chars) of company_name in the URL path
      (handles cases where the URL slug uses the company name, not the ticker,
       e.g. ticker "F" → slug "ford", ticker "GOOGL" → slug "alphabet")
    """
    slug = url.lower()
    t    = ticker.lower()

    if len(t) >= 3 and t in slug:
        return True

    if company_name:
        # Strip common corporate suffixes and pick the first substantive word
        cleaned = re.sub(
            r"\b(inc|corp|llc|ltd|co|the|plc|sa|ag|nv|group|holdings|company)\b",
            "", company_name, flags=re.I,
        )
        words = [w for w in re.split(r"[\s,./]+", cleaned) if len(w) >= 4]
        if words and words[0].lower() in slug:
            return True

    # Short ticker (1–2 chars): require it as a hyphen-delimited slug segment
    if len(t) < 3:
        if re.search(rf"(?:^|[-/]){re.escape(t)}(?:[-/]|$)", slug):
            return True

    return False


# ── URL collection — Motley Fool listing pages ────────────────────────────────

def _collect_mf_urls(ticker: str, company_name: str) -> List[str]:
    """
    Paginate through the Motley Fool ticker-filtered transcript listing and
    return validated article URLs (newest first, up to MAX_TRANSCRIPTS).
    """
    urls: List[str] = []
    seen: set       = set()

    for page in range(1, 5):                           # try up to 4 pages
        if len(urls) >= MAX_TRANSCRIPTS:
            break

        listing_url = f"{MF_LISTING_URL}?ticker={ticker}&page={page}"
        print(f"[transcript] Search URL being fetched: {listing_url}")

        try:
            resp = requests.get(listing_url, headers=_HEADERS, timeout=15)
            print(f"[transcript] Search response status: {resp.status_code}")
            if resp.status_code != 200:
                break
        except Exception as exc:
            print(f"[transcript] Search request failed: {type(exc).__name__}: {exc}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        found_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "transcript" not in href.lower():
                continue
            if not (href.startswith("https://www.fool.com") or href.startswith("/")):
                continue

            full = href if href.startswith("http") else "https://www.fool.com" + href
            if full in seen:
                continue
            seen.add(full)

            match = _validate_match(ticker, company_name, full)
            print(
                f"[transcript] Validating match for {ticker}: {full} "
                f"— {'MATCH' if match else 'SKIP'}"
            )
            if match:
                urls.append(full)
                found_this_page += 1
                if len(urls) >= MAX_TRANSCRIPTS:
                    break

        if found_this_page == 0:
            break                                      # no new results — stop paging

    return urls


# ── URL collection — Google search fallback ───────────────────────────────────

def _collect_google_urls(ticker: str, company_name: str) -> List[str]:
    """
    Search Google restricted to fool.com and return validated transcript URLs
    (up to MAX_TRANSCRIPTS, across two result pages).
    """
    urls: List[str] = []
    seen: set       = set()
    query = f"{ticker} earnings call transcript site:fool.com"

    for start in (0, 10):                              # two Google result pages
        if len(urls) >= MAX_TRANSCRIPTS:
            break

        search_url = (
            f"{GOOGLE_SEARCH_URL}?q={query.replace(' ', '+')}"
            + (f"&start={start}" if start else "")
        )
        print(f"[transcript] Search URL being fetched: {search_url}")

        try:
            resp = requests.get(
                GOOGLE_SEARCH_URL,
                params={"q": query, **({"start": start} if start else {})},
                headers=_HEADERS,
                timeout=15,
            )
            print(f"[transcript] Search response status: {resp.status_code}")
            if resp.status_code != 200:
                break
        except Exception as exc:
            print(f"[transcript] Search request failed: {type(exc).__name__}: {exc}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        found_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Unwrap Google's /url?q=https://... redirect wrapper
            if href.startswith("/url?q="):
                m = re.search(r"/url\?q=(https://www\.fool\.com[^&]+)", href)
                if m:
                    href = unquote(m.group(1))

            if not (
                href.startswith("https://www.fool.com")
                and "transcript" in href.lower()
            ):
                continue
            if href in seen:
                continue
            seen.add(href)

            match = _validate_match(ticker, company_name, href)
            print(
                f"[transcript] Validating match for {ticker}: {href} "
                f"— {'MATCH' if match else 'SKIP'}"
            )
            if match:
                urls.append(href)
                found_this_page += 1
                if len(urls) >= MAX_TRANSCRIPTS:
                    break

        if found_this_page == 0 and start > 0:
            break                                      # no new results on page 2

    return urls


# ── Single article scraper ────────────────────────────────────────────────────

def _scrape_one(article_url: str) -> Optional[dict]:
    """
    Fetch and parse one Motley Fool transcript article.
    Returns a dict with quarter, year, url, content, or None on any failure.
    """
    try:
        resp = requests.get(article_url, headers=_HEADERS, timeout=20)
        print(f"[transcript] Article fetch status: {resp.status_code}")
        resp.raise_for_status()
    except Exception as exc:
        print(f"[transcript] Article fetch failed ({article_url}): {type(exc).__name__}: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    body = (
        soup.find("div", class_=re.compile(r"article-body", re.I))
        or soup.find("div", {"id": re.compile(r"article-body", re.I)})
        or soup.find("article")
    )

    if not body:
        print(f"[transcript] Article body not found: {article_url}")
        return None

    text = re.sub(r"\s+", " ", body.get_text(separator=" ", strip=True))
    print(f"[transcript] Text length extracted: {len(text)} chars")

    if not text:
        print(f"[transcript] Empty article body: {article_url}")
        return None

    # Parse quarter and year from the URL path (e.g. /2024/q3/aapl-…)
    quarter, year = None, None
    m = re.search(r"/(\d{4})/q(\d)/", article_url, re.I)
    if m:
        year, quarter = int(m.group(1)), int(m.group(2))

    return {"quarter": quarter, "year": year, "url": article_url, "content": text}


# ── Public entry point ────────────────────────────────────────────────────────

def fetch_latest_transcript(ticker: str, company_name: str = "") -> dict:
    """
    Fetch up to 12 quarters of earnings call transcripts for `ticker` from
    Motley Fool.  Tries the MF listing page first; falls back to Google search.

    Returns a dict with keys:
      - ticker
      - quarter          (int or None — most recent transcript)
      - year             (int or None — most recent transcript)
      - date             (str — always empty; scraped results have no timestamp)
      - content          (str — all transcripts concatenated, newest first)
      - url              (str — most recent transcript article URL)
      - all_transcripts  (list of {quarter, year, url} for every found transcript)

    Raises ValueError if no transcripts can be found via either method.
    """
    t  = ticker.upper()
    cn = company_name.strip()
    print(f"[transcript] Attempting Motley Fool scrape for {t}")

    # ── Approach 1: Motley Fool listing pages ─────────────────────────────────
    article_urls = _collect_mf_urls(t, cn)

    if not article_urls:
        print("[transcript] First result URL found: no results found")

        # ── Approach 2: Google search ─────────────────────────────────────────
        print(f"[transcript] Attempting Google search scraping for {t}")
        article_urls = _collect_google_urls(t, cn)

    if not article_urls:
        print("[transcript] First result URL found: no results found")
        print(f"[transcript] FAILED — no transcript URLs found via Motley Fool or Google")
        raise ValueError(
            f"No transcript found for '{t}' via Motley Fool listing or Google search."
        )

    print(f"[transcript] First result URL found: {article_urls[0]}")

    # ── Scrape each article ───────────────────────────────────────────────────
    transcripts = []
    for url in article_urls:
        result = _scrape_one(url)
        if result:
            transcripts.append(result)

    print(f"[transcript] Found {len(transcripts)} transcripts for {t}")

    if not transcripts:
        print(f"[transcript] FAILED — all article scrapes returned empty")
        raise ValueError(f"All transcript articles for '{t}' failed to parse.")

    # Sort newest first (year desc, quarter desc); put None-dated entries last
    transcripts.sort(
        key=lambda x: (x["year"] or 0, x["quarter"] or 0), reverse=True
    )

    # Combine content with section headers so Claude can orient itself
    combined = "\n\n".join(
        f"--- Q{t['quarter']} {t['year']} Earnings Call ---\n{t['content']}"
        for t in transcripts
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
