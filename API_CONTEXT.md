# API Context Reference

> **Purpose:** Accurate API signatures, gotchas, and rate limits for every data source used in the Bloomberg Equity Analysis Platform. Read this before writing any code that touches external data. Last verified March 2026.

---

## Table of Contents

1. [edgartools](#1-edgartools)
2. [SEC EDGAR REST API (data.sec.gov)](#2-sec-edgar-rest-api-datasecgov)
3. [Alpaca Markets](#3-alpaca-markets)
4. [FRED (Federal Reserve Economic Data)](#4-fred-federal-reserve-economic-data)
5. [Finviz](#5-finviz)

---

## 1. edgartools

**Package:** `edgartools` (MIT, free, no API key)  
**Install:** `pip install edgartools`  
**Docs:** https://edgartools.readthedocs.io  
**Rate limits:** No hard limit, but respect SEC fair-use policy — add 0.5s delay between filing fetches. Do not hammer EDGAR in loops.

### Setup (required before any call)

```python
from edgar import Company, set_identity

# REQUIRED — SEC requires a user-agent identifying your app
set_identity("your.name@example.com")
```

---

### Company object

```python
company = Company("AAPL")       # by ticker (case-insensitive)
company = Company(320193)       # by CIK integer
company = Company("0000320193") # by CIK string (zero-padded ok)

# Key properties
company.name                    # "Apple Inc."
company.cik                     # "0000320193"
company.sic                     # 3571 (integer SIC code)
company.industry                # "Electronic Computers"
company.fiscal_year_end         # "0930" (MMDD)
company.shares_outstanding      # 15115785000.0
company.public_float            # float (USD)
```

---

### Getting financials (HIGH-LEVEL — preferred path)

```python
# Get multi-period financials directly from company (stitches multiple filings)
financials = company.get_financials()

# Access statements — returns Statement objects (printable, DataFrame-exportable)
income_stmt  = financials.income_statement()
balance      = financials.balance_sheet()
cash_flow    = financials.cashflow_statement()

# Export to pandas DataFrame
df = income_stmt.to_dataframe()
# DataFrame columns: label, level, parent_concept, standard_concept, value, ...

# Access via standardized concept (works across all companies)
# standard_concept normalizes ~2,000 XBRL tags to 95 consistent labels
# e.g., "Revenue", "NetIncome", "CommonEquity"
revenue_row = df[df['standard_concept'] == 'Revenue']
```

> **GOTCHA:** `company.get_financials()` stitches multiple annual filings automatically. This is the preferred path for 5-year historical data. Do NOT manually loop over filings and call `filing.xbrl()` unless you need raw control.

---

### Getting filings + XBRL (LOW-LEVEL — use when get_financials() insufficient)

```python
# Get latest 10-K
filing = company.latest("10-K")               # returns single Filing
filings = company.latest("10-K", n=5)         # returns List[Filing]

# Get filings with filters
filings = company.get_filings(form="10-K")
filings = company.get_filings(form=["10-K", "10-Q"])
filings = company.get_filings(form="8-K", filing_date="2024-01-01:")
filings = company.get_filings(year=2024, quarter=4)
filings = company.get_filings(is_xbrl=True)

# CRITICAL: Do NOT call filing.financials — Filing base class has no financials property
# WRONG:
financials = filing.financials  # AttributeError

# RIGHT option 1 — get form-specific object first
tenk = filing.obj()             # returns TenK object
if tenk.financials:
    income = tenk.financials.income_statement
    balance = tenk.financials.balance_sheet
    cashflow = tenk.financials.cash_flow_statement

# RIGHT option 2 — use XBRL directly
xbrl = filing.xbrl()           # returns XBRL object (or None if no XBRL)
if xbrl:
    statements = xbrl.statements
    income  = statements.income_statement()
    balance = statements.balance_sheet()
    cashflow = statements.cash_flow_statement()
    df = income.to_dataframe()
```

---

### XBRL facts querying (for tag-level access)

```python
# Query raw XBRL facts by concept name
xbrl = filing.xbrl()
facts = xbrl.facts                              # FactsView object

# Query by standard concept label (preferred — normalized across companies)
revenue_facts = facts.by_concept("Revenue")

# Convert all facts to DataFrame
facts_df = facts.to_dataframe()
# columns: concept, label, value, unit, period_start, period_end, instant, ...

# Get specific statement by type string
stmt = xbrl.get_statement("IncomeStatement")   # or "BalanceSheet", "CashFlowStatement"
```

---

### Multi-period stitching

```python
from edgar.xbrl import XBRLS

# Stitch 5 years of 10-K filings into a single comparative view
filings = company.get_filings(form="10-K").latest(n=5)
xbrls = XBRLS(filings)                         # stitches all filings
stitched_income = xbrls.income_statement()
stitched_balance = xbrls.balance_sheet()
df = stitched_income.to_dataframe()             # multi-year DataFrame
```

---

### 8-K earnings call transcripts

```python
# Earnings transcripts are filed as 8-K Exhibit 99.1
filings_8k = company.get_filings(form="8-K").latest(n=4)  # last 4 quarters

for filing in filings_8k:
    eightk = filing.obj()
    # Get full text of the filing as markdown (LLM-optimized)
    text = filing.markdown()
    # Or search for specific content
    results = filing.search("guidance")
    results = filing.search("revenue")
```

---

### 10-K section extraction

```python
tenk = company.latest("10-K").obj()

# Access key sections as text
# Sections: "1" Business, "1A" Risk Factors, "7" MD&A, "7A" Market Risk
section_text = tenk.item("1A")    # Risk Factors as plain text
section_html = tenk.item("7")     # MD&A as HTML
```

---

### XBRL sign conventions

> **CRITICAL — read before building edgar_extractor.py**

edgartools returns **raw XBRL values** by default (not presentation-adjusted):
- Revenue: **positive**
- Net income: **positive** (negative for losses)
- Capex (`PaymentsToAcquirePropertyPlantAndEquipment`): **positive** in XBRL even though it is a cash outflow — store as positive absolute value and subtract in FCF formula
- D&A: **positive** (it's an addback in cash flow statement)
- Debt repayment: can be positive or negative depending on tag

Do NOT blindly apply `abs()` — validate each field's sign logic individually.

---

### Error handling

```python
from edgar.xbrl import XBRLFilingWithNoXbrlData
from edgar import CompanyNotFoundError

try:
    company = Company("INVALIDTICKER")
except CompanyNotFoundError:
    print("Ticker not found in EDGAR")

try:
    xbrl = XBRL.from_filing(filing)
except XBRLFilingWithNoXbrlData:
    print("Filing predates XBRL requirement (pre-2009) or is non-standard")
except Exception as e:
    print(f"XBRL parse error: {e}")

# Always check before accessing
if xbrl and xbrl.statements.income_statement():
    income = xbrl.statements.income_statement()
```

---

## 2. SEC EDGAR REST API (data.sec.gov)

**Base URL:** `https://data.sec.gov`  
**Auth:** None required — no API key  
**Rate limits:** ~10 requests/second max. Must include `User-Agent` header. Requests without a user-agent may be blocked.  
**Headers required:**
```python
headers = {"User-Agent": "YourAppName yourname@email.com"}
```

> **Note:** edgartools wraps this API. Use edgartools directly for most tasks. Use the raw REST API only when you need bulk data, CIK lookups, or the frames endpoint.

---

### Ticker → CIK lookup

```python
import requests

headers = {"User-Agent": "EquityPlatform theo@example.com"}

# Get mapping of all tickers to CIKs
r = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers)
tickers = r.json()
# Structure: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}

# Build reverse lookup
ticker_to_cik = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in tickers.values()}
cik = ticker_to_cik["AAPL"]  # "0000320193"
```

---

### Submissions endpoint (filing history)

```python
# GET https://data.sec.gov/submissions/CIK{cik}.json
r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers)
data = r.json()

# Key fields
data["name"]           # company name
data["sic"]            # SIC code (string)
data["sicDescription"] # SIC description
data["tickers"]        # list of ticker symbols

# Filing history
filings = data["filings"]["recent"]
# Arrays (parallel): accessionNumber, filingDate, form, primaryDocument, isXBRL
```

---

### Company Facts endpoint (all XBRL data for a company)

```python
# GET https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
r = requests.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=headers)
facts = r.json()

# Structure:
# facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"] = [
#   {"accn": "...", "fy": 2024, "fp": "FY", "form": "10-K",
#    "filed": "2024-11-01", "start": "2023-10-01", "end": "2024-09-28",
#    "val": 391035000000},
#   ...
# ]

# Get revenue facts filtered to annual 10-K only
revenue_facts = facts["facts"]["us-gaap"].get("Revenues", {}).get("units", {}).get("USD", [])
annual = [f for f in revenue_facts if f.get("form") == "10-K" and f.get("fp") == "FY"]
```

> **GOTCHA — duplicate values:** EDGAR returns a fact for every filing that mentions it. A 10-K includes prior-year comparatives, so you'll see the same value reported in multiple filings. Filter on `form == "10-K"` AND `fp == "FY"` AND deduplicate by `end` date (keep latest `filed` date per period).

---

### Company Concept endpoint (single tag for a company)

```python
# GET https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json
r = requests.get(
    f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/NetIncomeLoss.json",
    headers=headers
)
concept = r.json()
# Same structure as company facts but scoped to one tag
```

---

### Bulk data (for caching / offline use)

```python
# Download all company facts (nightly updated ZIP, ~1GB uncompressed)
# https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip

# Download all submissions
# https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip
```

---

### Key XBRL tags for DCF / DDM

| Field | Primary tag | Fallback tags |
|---|---|---|
| Revenue | `Revenues` | `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`, `SalesRevenueGoodsNet` |
| Net income | `NetIncomeLoss` | `NetIncome`, `ProfitLoss` |
| D&A | `DepreciationDepletionAndAmortization` | `DepreciationAndAmortization`, `Depreciation` |
| Capex | `PaymentsToAcquirePropertyPlantAndEquipment` | `PaymentsForCapitalImprovements` |
| Diluted shares | `WeightedAverageNumberOfDilutedSharesOutstanding` | `CommonStockSharesOutstanding` |
| Cash | `CashAndCashEquivalentsAtCarryingValue` | `Cash` |
| LT Debt | `LongTermDebt` | `LongTermDebtNoncurrent` |
| ST Debt | `ShortTermBorrowings` | `DebtCurrent` |
| Total equity | `StockholdersEquity` | `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |
| SBC | `ShareBasedCompensation` | `AllocatedShareBasedCompensationExpense` |
| Dividends paid | `PaymentsOfDividends` | `PaymentsOfDividendsCommonStock` |
| DPS | `CommonStockDividendsPerShareDeclared` | `CommonStockDividendsPerShareCashPaid` |

---

## 3. Alpaca Markets

**Package:** `alpaca-py`  
**Install:** `pip install alpaca-py`  
**Docs:** https://docs.alpaca.markets  
**Auth:** Requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` env vars (paper or live account)  
**Free tier (Basic):** 200 requests/min, historical data since 2016, IEX real-time feed only  
**Algo Trader Plus:** 10,000 requests/min, all exchanges, $99/month

---

### Authentication

```python
import os
from alpaca.data import StockHistoricalDataClient

client = StockHistoricalDataClient(
    api_key=os.environ["ALPACA_API_KEY"],
    secret_key=os.environ["ALPACA_SECRET_KEY"]
)
```

---

### Latest quote (current price)

```python
from alpaca.data.requests import StockLatestQuoteRequest

params = StockLatestQuoteRequest(symbol_or_symbols="AAPL")
quote = client.get_stock_latest_quote(params)

price = quote["AAPL"].ask_price    # latest ask
bid   = quote["AAPL"].bid_price    # latest bid
mid   = (price + bid) / 2          # mid price (use for valuation)

# Multi-symbol
params = StockLatestQuoteRequest(symbol_or_symbols=["AAPL", "MSFT", "GOOGL"])
quotes = client.get_stock_latest_quote(params)
```

> **GOTCHA — free tier real-time:** Free Basic plan only includes the IEX exchange feed, not the full consolidated tape. For historical data (used in DCF), this makes no difference. For live price display, the IEX quote may differ slightly from NBBO.

---

### Historical bars (OHLCV)

```python
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

params = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame.Day,
    start=datetime.now() - timedelta(days=365),
    end=datetime.now()
)
bars = client.get_stock_bars(params)

# Convert to pandas DataFrame
df = bars.df
# columns: open, high, low, close, volume, trade_count, vwap
# index: MultiIndex (symbol, timestamp)

# For single symbol
aapl_df = bars.df.loc["AAPL"]
```

---

### Beta computation (from historical returns)

Alpaca does not provide beta directly — compute it from daily bar data:

```python
import numpy as np

def compute_beta(ticker: str, benchmark: str = "SPY", days: int = 252) -> float:
    params = StockBarsRequest(
        symbol_or_symbols=[ticker, benchmark],
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=days + 10),
        end=datetime.now()
    )
    bars = client.get_stock_bars(params).df
    
    stock_returns = bars.loc[ticker]["close"].pct_change().dropna()
    bench_returns = bars.loc[benchmark]["close"].pct_change().dropna()
    
    # Align dates
    aligned = stock_returns.align(bench_returns, join="inner")
    stock_r, bench_r = aligned[0], aligned[1]
    
    covariance = np.cov(stock_r, bench_r)[0][1]
    variance = np.var(bench_r)
    return covariance / variance
```

> **Note:** Self-computed beta may differ from Bloomberg/FMP beta (which uses different lookback periods and return frequencies). Document this clearly in the UI. Allow manual override.

---

### Available timeframes

```python
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

TimeFrame.Minute        # 1-minute bars
TimeFrame.Hour          # 1-hour bars
TimeFrame.Day           # daily bars  ← use this for beta computation
TimeFrame.Week          # weekly bars
TimeFrame.Month         # monthly bars

# Custom (e.g., 5-minute bars)
TimeFrame(5, TimeFrameUnit.Minute)
```

---

### Error handling

```python
from alpaca.common.exceptions import APIError

try:
    quote = client.get_stock_latest_quote(params)
except APIError as e:
    print(f"Alpaca API error: {e.status_code} — {e.message}")
```

---

## 4. FRED (Federal Reserve Economic Data)

**Base URL:** `https://api.stlouisfed.org/fred`  
**Auth:** Requires `FRED_API_KEY` env var — free key at https://fred.stlouisfed.org/docs/api/api_key.html  
**Rate limits:** ~120 requests/minute. Violations trigger a 20-second cooldown (not a ban).  
**Format:** JSON (pass `file_type=json` in all requests)

---

### Key series IDs for this platform

| Series ID | Description | Frequency | Use in platform |
|---|---|---|---|
| `DGS10` | 10-Year Treasury Constant Maturity Rate (%) | Daily | Risk-free rate (Rf) for WACC/CAPM |
| `DGS3MO` | 3-Month Treasury Bill Rate (%) | Daily | Short-term Rf alternative |
| `FEDFUNDS` | Federal Funds Effective Rate (%) | Monthly | Macro context |
| `CPIAUCSL` | Consumer Price Index (All Urban) | Monthly | Inflation context |
| `UNRATE` | Unemployment Rate (%) | Monthly | Macro context |
| `GDP` | Gross Domestic Product (billions USD) | Quarterly | Macro context |

---

### Fetching observations

```python
import requests
import os

FRED_BASE = "https://api.stlouisfed.org/fred"
FRED_KEY = os.environ["FRED_API_KEY"]

def get_fred_series(series_id: str, limit: int = 1) -> float:
    """Get the most recent observation for a FRED series."""
    r = requests.get(
        f"{FRED_BASE}/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
    )
    r.raise_for_status()
    data = r.json()
    # Returns {"observations": [{"date": "2026-03-14", "value": "4.21"}, ...]}
    obs = data["observations"]
    # Filter out missing values (FRED uses "." for missing)
    valid = [o for o in obs if o["value"] != "."]
    return float(valid[0]["value"]) if valid else None

# Get current 10-year Treasury yield
rf = get_fred_series("DGS10")  # e.g., 4.20 (percent, not decimal)
rf_decimal = rf / 100           # convert to 0.0420 for CAPM
```

---

### Fetching historical range

```python
def get_fred_history(series_id: str, start: str, end: str = None) -> list:
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "observation_start": start,  # "YYYY-MM-DD"
    }
    if end:
        params["observation_end"] = end
    
    r = requests.get(f"{FRED_BASE}/series/observations", params=params)
    r.raise_for_status()
    return r.json()["observations"]
    # [{"date": "2024-01-02", "value": "3.96"}, ...]
```

---

### Response format

```json
{
  "realtime_start": "2026-03-18",
  "realtime_end": "2026-03-18",
  "observation_start": "1600-01-01",
  "observation_end": "9999-12-31",
  "units": "Percent",
  "observations": [
    {"realtime_start": "...", "realtime_end": "...", "date": "2026-03-14", "value": "4.21"}
  ]
}
```

> **GOTCHA — missing values:** FRED uses `"."` (a period string) to denote missing observations. Always filter these out before parsing to float.

> **GOTCHA — DGS10 is in percent:** The value `4.21` means 4.21%, not 0.0421. Divide by 100 before using in CAPM formula.

---

## 5. Finviz

**Status:** No official API. Data is scraped from finviz.com.  
**Library (preferred):** `finvizfinance` (`pip install finvizfinance`)  
**Alternative:** `finviz` (`pip install finviz`)  
**Rate limits:** Undocumented. Respect the site — add delays for bulk requests. Finviz Elite (paid) provides faster access.  
**Data lag:** Prices delayed 15 minutes (NASDAQ) and 20 minutes (NYSE/AMEX).  
**Terms:** Using scrapers may violate Finviz ToS. Use for research/development only, not production trading.

---

### Single stock fundamentals (finvizfinance)

```python
from finvizfinance.quote import finvizfinance

stock = finvizfinance("AAPL")

# Fundamentals dict — all values as strings, parse manually
fundamentals = stock.ticker_fundament()
# Keys include: "Sector", "Industry", "Market Cap", "P/E", "Forward P/E",
#   "P/S", "P/B", "EPS (ttm)", "EPS next Y", "Beta", "52W High", "52W Low",
#   "RSI (14)", "Avg Volume", "Short Float", "Insider Own", "Inst Own",
#   "ROE", "ROI", "Gross Margin", "Oper. Margin", "Profit Margin",
#   "Dividend", "Dividend %", "Payout Ratio"

sector = fundamentals["Sector"]           # "Technology"
industry = fundamentals["Industry"]       # "Consumer Electronics"
beta = float(fundamentals["Beta"])        # 1.24
pe = float(fundamentals["P/E"])           # 28.5

# News
news = stock.ticker_news()               # DataFrame with Title, Date, Link, Source

# Insider trades
insider = stock.ticker_inside_trader()   # DataFrame
```

---

### Single stock fundamentals (finviz alternative)

```python
import finviz

stock = finviz.get_stock("AAPL")
# Returns dict with same fields as finvizfinance
print(stock["P/E"], stock["Market Cap"], stock["Sector"])

# News
news = finviz.get_news("AAPL")
# Returns list of (timestamp, headline, url, source) tuples

# Analyst targets
targets = finviz.get_analyst_price_targets("AAPL")
# Returns list of dicts: {analyst, rating, target_to, target_from, ...}
```

---

### Screener

```python
from finvizfinance.screener.overview import Overview

foverview = Overview()
foverview.set_filter(filters_dict={
    "Sector": "Technology",
    "Market Cap.": "+Mid (over $2bln)",
    "Country": "USA"
})
df = foverview.screener_view()   # pandas DataFrame
# columns: Ticker, Company, Sector, Industry, Country, Market Cap, P/E, Price, Change, Volume
```

---

### What Finviz is useful for (in this platform)

Finviz is the **supplemental fallback** only. Use it for:
- Sector/industry classification when EDGAR SIC mapping is ambiguous
- Beta (when Alpaca beta computation is unavailable)
- Quick fundamental sanity checks (P/E, market cap) against EDGAR-derived values
- Analyst price target aggregation for the Report tab

Do NOT use Finviz as a primary source for any financial statement data (income statement, balance sheet, cash flows). EDGAR is authoritative; Finviz is a convenience layer.

---

## Cross-API Notes

### Data source priority by field

| Field | Primary | Fallback |
|---|---|---|
| Financial statements (IS, BS, CF) | edgartools | SEC EDGAR REST API |
| Sector / industry | edgartools (`company.sic`, `company.industry`) | Finviz |
| Current price | Alpaca `get_stock_latest_quote` | Finviz |
| Historical OHLCV | Alpaca `get_stock_bars` | — |
| Beta | Alpaca (self-computed, 252-day) | Finviz |
| Risk-free rate | FRED `DGS10` | — |
| 10-K narrative sections | edgartools `tenk.item("1A")` | — |
| Earnings transcripts | edgartools 8-K `.markdown()` | — |
| Recent news | Finviz / web search | — |
| Analyst targets | Finviz `get_analyst_price_targets` | — |

### Environment variables required

```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
FRED_API_KEY=your_key_here
# No keys needed for edgartools or SEC EDGAR REST API
```

### Caching TTLs (backend/cache.py)

| Data type | TTL | Rationale |
|---|---|---|
| EDGAR financial statements | 7 days | Quarterly filing cadence |
| EDGAR company metadata (SIC, name) | 30 days | Almost never changes |
| Alpaca quotes | 15 minutes | Stale enough for research, fresh enough for display |
| Alpaca historical bars (beta) | 24 hours | Daily data, no need to refetch intraday |
| FRED series (DGS10) | 24 hours | Updated once daily |
| Finviz fundamentals | 6 hours | Delayed data anyway |
