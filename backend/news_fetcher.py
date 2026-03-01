"""
news_fetcher.py — fetches recent news headlines and Twitter/X posts
for a given ticker to provide real-time context for the Claude analysis.

Sources:
  1. FMP stock_news endpoint (recent financial news headlines)
  2. Web scraping for Twitter/X sentiment (via requests to nitter/search)

Returns a NewsResult with structured headlines and social posts.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), override=True)

FMP_BASE_URL = "https://financialmodelingprep.com/stable"
MAX_NEWS = 15
MAX_TWEETS = 10


@dataclass
class NewsItem:
    title: str
    source: str
    date: str
    url: str
    snippet: str = ""


@dataclass
class SocialPost:
    text: str
    source: str  # "twitter", "stocktwits", etc.
    date: str = ""
    author: str = ""
    engagement: str = ""  # e.g. "1.2K likes"


@dataclass
class NewsResult:
    ticker: str
    news_items: List[NewsItem] = field(default_factory=list)
    social_posts: List[SocialPost] = field(default_factory=list)
    news_summary_text: str = ""  # pre-formatted text block for Claude


def _get_api_key() -> str:
    key = os.getenv("FMP_API_KEY")
    if not key:
        raise EnvironmentError("FMP_API_KEY is not set.")
    return key


# ── FMP News ──────────────────────────────────────────────────────────────────

def _fetch_fmp_news(ticker: str, api_key: str) -> List[NewsItem]:
    """Fetch recent news from FMP stock-news endpoint."""
    items = []
    try:
        url = f"{FMP_BASE_URL}/stock-news"
        params = {
            "symbol": ticker,
            "limit": MAX_NEWS,
            "apikey": api_key,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data or not isinstance(data, list):
            # Try legacy endpoint format
            url = f"https://financialmodelingprep.com/api/v3/stock_news"
            params = {
                "tickers": ticker,
                "limit": MAX_NEWS,
                "apikey": api_key,
            }
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

        for article in (data or [])[:MAX_NEWS]:
            title = article.get("title") or ""
            if not title:
                continue
            items.append(NewsItem(
                title=title,
                source=article.get("site") or article.get("source") or "",
                date=article.get("publishedDate") or article.get("date") or "",
                url=article.get("url") or article.get("link") or "",
                snippet=article.get("text") or article.get("snippet") or "",
            ))

        print(f"[News] FMP: {len(items)} headlines for {ticker}")

    except Exception as exc:
        print(f"[News] FMP news fetch failed: {type(exc).__name__}: {exc}")

    return items


# ── Twitter/X via web search ─────────────────────────────────────────────────

def _fetch_twitter_posts(ticker: str) -> List[SocialPost]:
    """
    Attempt to find recent Twitter/X posts about a stock via web search.
    Uses Google search to find tweets since Twitter API is paywalled.
    Falls back to StockTwits if Twitter fails.
    """
    posts = []

    # Try Google search for recent tweets
    try:
        cashtag = f"${ticker}"
        query = f'"{cashtag}" OR "{ticker} stock" site:x.com'
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        }
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num=10&tbs=qdr:w"
        resp = requests.get(search_url, headers=headers, timeout=10)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Google search results
            for g in soup.select("div.g, div.tF2Cxc"):
                title_el = g.select_one("h3")
                snippet_el = g.select_one("span.aCOpRe, div.VwiC3b, span")
                link_el = g.select_one("a[href]")

                if title_el:
                    text = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    if snippet and len(snippet) > len(text):
                        text = snippet

                    # Only include if it looks tweet-like
                    if any(k in text.lower() for k in [ticker.lower(), cashtag.lower(), "stock", "shares", "earnings"]):
                        posts.append(SocialPost(
                            text=text[:300],
                            source="twitter",
                            author="",
                        ))

            print(f"[News] Twitter (Google): {len(posts)} posts for {ticker}")

    except Exception as exc:
        print(f"[News] Twitter search failed: {type(exc).__name__}: {exc}")

    # Fallback: StockTwits API (free, no auth required for public stream)
    if len(posts) < 3:
        try:
            st_url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
            resp = requests.get(st_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                messages = data.get("messages") or []
                for msg in messages[:MAX_TWEETS]:
                    body = msg.get("body") or ""
                    if not body:
                        continue
                    created = msg.get("created_at") or ""
                    user = msg.get("user", {}).get("username") or ""
                    sentiment = msg.get("entities", {}).get("sentiment", {})
                    sent_label = sentiment.get("basic") if sentiment else ""

                    posts.append(SocialPost(
                        text=body[:300],
                        source="stocktwits",
                        date=created,
                        author=user,
                        engagement=sent_label or "",
                    ))

                print(f"[News] StockTwits: {len(messages[:MAX_TWEETS])} posts for {ticker}")

        except Exception as exc:
            print(f"[News] StockTwits failed: {type(exc).__name__}: {exc}")

    return posts[:MAX_TWEETS]


# ── Build text block for Claude ──────────────────────────────────────────────

def _build_news_text(news_items: List[NewsItem], social_posts: List[SocialPost]) -> str:
    """Format news and social posts into a text block for Claude's prompt."""
    sections = []

    if news_items:
        lines = ["RECENT NEWS HEADLINES:"]
        for i, item in enumerate(news_items, 1):
            date_str = f" ({item.date[:10]})" if item.date else ""
            source_str = f" — {item.source}" if item.source else ""
            lines.append(f"  {i}. {item.title}{source_str}{date_str}")
            if item.snippet:
                # Truncate snippet
                snip = item.snippet[:200].strip()
                if snip:
                    lines.append(f"     {snip}")
        sections.append("\n".join(lines))

    if social_posts:
        lines = ["SOCIAL MEDIA SENTIMENT:"]
        for i, post in enumerate(social_posts, 1):
            source_label = post.source.capitalize()
            author_str = f" @{post.author}" if post.author else ""
            sent_str = f" [{post.engagement}]" if post.engagement else ""
            lines.append(f"  {i}. [{source_label}{author_str}]{sent_str} {post.text[:250]}")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_news(ticker: str) -> NewsResult:
    """
    Fetch recent news and social media posts for a ticker.

    Returns a NewsResult containing headlines, social posts, and a
    pre-formatted text block ready to insert into Claude's prompt.
    """
    ticker = ticker.upper()
    api_key = _get_api_key()

    # Fetch both sources
    news_items = _fetch_fmp_news(ticker, api_key)
    social_posts = _fetch_twitter_posts(ticker)

    # Build combined text
    news_text = _build_news_text(news_items, social_posts)

    result = NewsResult(
        ticker=ticker,
        news_items=news_items,
        social_posts=social_posts,
        news_summary_text=news_text,
    )

    total = len(news_items) + len(social_posts)
    print(f"[News] {ticker}: {len(news_items)} news + {len(social_posts)} social = {total} total items")

    return result
