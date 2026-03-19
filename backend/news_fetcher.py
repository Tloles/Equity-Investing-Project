"""
news_fetcher.py — fetches recent news headlines for a given ticker via
Google News RSS to provide real-time context for the Claude analysis.

Returns a NewsResult with structured headlines and a pre-formatted text block.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List

import requests


@dataclass
class NewsItem:
    headline: str
    source: str
    date: str
    url: str
    snippet: str = ""


@dataclass
class SocialPost:
    text: str
    source: str
    date: str = ""
    author: str = ""
    engagement: str = ""


@dataclass
class NewsResult:
    ticker: str
    news_items: List[NewsItem] = field(default_factory=list)
    social_posts: List[SocialPost] = field(default_factory=list)
    news_summary_text: str = ""  # pre-formatted text block for Claude


# ── Google News RSS ───────────────────────────────────────────────────────────

def _fetch_google_news_rss(ticker: str, max_items: int = 15) -> List[NewsItem]:
    """Fetch recent news from Google News RSS feed."""
    url = (
        f"https://news.google.com/rss/search"
        f"?q={requests.utils.quote(ticker + ' stock')}"
        f"&hl=en-US&gl=US&ceid=US:en"
    )
    headers = {"User-Agent": "equity-research-tool/1.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        items = []
        for item in root.findall(".//item")[:max_items]:
            title  = (item.findtext("title")   or "").strip()
            link   = (item.findtext("link")    or "").strip()
            date   = (item.findtext("pubDate") or "").strip()
            source_el = item.find("source")
            source = (source_el.text or "").strip() if source_el is not None else ""

            if not title:
                continue
            items.append(NewsItem(headline=title, source=source, date=date, url=link))

        print(f"[News] Google RSS: {len(items)} articles for {ticker}")
        return items

    except Exception as exc:
        print(f"[News] Google RSS failed for {ticker}: {type(exc).__name__}: {exc}")
        return []


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_news(ticker: str) -> NewsResult:
    """
    Fetch recent news headlines for a ticker via Google News RSS.

    Returns a NewsResult containing headlines and a pre-formatted text block
    ready to insert into Claude's prompt.
    """
    ticker = ticker.upper()

    news_items = _fetch_google_news_rss(ticker)

    lines = [
        f"[{i}] [{item.source}] {item.headline} ({item.date})"
        for i, item in enumerate(news_items)
    ]
    summary = "\n".join(lines)[:6000]

    print(f"[News] {ticker}: {len(news_items)} headlines")

    return NewsResult(
        ticker=ticker,
        news_items=news_items,
        social_posts=[],
        news_summary_text=summary,
    )
