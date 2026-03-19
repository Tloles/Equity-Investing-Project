"""Simple in-memory cache with TTL for financial data and market data."""

import time
from typing import Any, Optional, Tuple

# ── Named TTL constants (seconds) ────────────────────────────────────────────
TTL_EDGAR_FINANCIALS = 604800    # 7 days — XBRL filings don't change often
TTL_ALPACA_QUOTE     = 900       # 15 minutes — live price data
TTL_SECTOR_PROFILE   = 2592000   # 30 days — SIC codes are stable
TTL_MARKET_DATA      = 86400     # 24 hours — risk-free rate, ERP


class TTLCache:
    """In-memory cache with per-entry time-to-live (TTL)."""

    def __init__(self, default_ttl: int = 3600) -> None:
        self._store: dict = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Return cached value or None if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["ts"] > entry["ttl"]:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with an optional custom TTL (seconds)."""
        self._store[key] = {
            "value": value,
            "ts": time.time(),
            "ttl": ttl if ttl is not None else self.default_ttl,
        }

    def is_fresh(self, key: str) -> bool:
        """Return True if the key exists and has not expired."""
        return self.get(key) is not None

    def get_with_source(self, key: str) -> Optional[Tuple[Any, str]]:
        """Return (value, source) tuple or None if missing or expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["ts"] > entry["ttl"]:
            del self._store[key]
            return None
        return entry["value"], entry.get("source", "")

    def set_with_source(
        self, key: str, value: Any, source: str, ttl: Optional[int] = None
    ) -> None:
        """Store a value with source metadata and optional TTL."""
        self._store[key] = {
            "value": value,
            "source": source,
            "ts": time.time(),
            "ttl": ttl if ttl is not None else self.default_ttl,
        }
