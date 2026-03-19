**Bloomberg Equity Analysis Platform**

Product Requirements Document

Version 1.0 --- Internal Development Reference

  --------------------------- -------------------------------------------
  **Author**                  Theodore Loles

  **Course**                  Equity Investing --- Georgia Tech Scheller
                              College of Business

  **Status**                  Active Development --- Data Layer Rework In
                              Progress

  **Stack**                   FastAPI (Python) + React

  **Last Updated**            March 19, 2026
  --------------------------- -------------------------------------------

**1. Executive Summary**

The Bloomberg Equity Analysis Platform is an AI-powered equity research
tool built as a Georgia Tech Scheller College of Business class project
for an equity investing course. The platform replicates a professional
equity analyst workflow --- from data gathering and financial modeling
through investment thesis generation and formal research report
production --- in a single, largely automated application.

The core insight driving the platform is that equity analysis is a
two-layer problem: quantitative accuracy (getting the financial model
right) and qualitative depth (synthesizing the investment narrative from
earnings calls, filings, and market intelligence). Most student tools
handle neither well. This platform is designed to handle both
rigorously.

The application is organized into five integrated components:

-   Analysis Tab --- AI-generated bull/bear case and risk assessment,
    synthesized from 10-K filings, earnings call transcripts, and recent
    news

-   DCF Model Tab --- Discounted cash flow model with industry-aware
    input extraction, editable assumptions, and live cascading
    calculations

-   DDM Model Tab --- Dividend discount model with multi-stage growth
    support and sector-appropriate configuration

-   Industry Analysis Tab --- Porter\'s Five Forces framework with
    AI-researched competitive dynamics

-   Report Tab (planned) --- Full equity research report reproducing the
    structure of a professional initiation report, with PDF export

*MVP Goal: Deliver a tool where a user enters a ticker, and the platform
auto-extracts verified financial data from SEC EDGAR, runs
industry-aware DCF and DDM models, synthesizes a qualitative investment
thesis from primary sources, and produces a formatted research report
--- all in under 60 seconds.*

**2. Mission**

***Compress hours of equity research into seconds by combining
authoritative financial data extraction, industry-aware valuation
modeling, and AI-powered qualitative synthesis into a single,
production-quality research platform.***

**Core Principles**

-   Accuracy before intelligence --- the financial model must be correct
    before AI analysis adds value. Garbage in, garbage out.

-   Industry context is not optional --- DCF inputs, model selection,
    and growth assumptions must adapt automatically to the company\'s
    sector.

-   Primary sources only --- qualitative analysis must be grounded in
    10-K filings, earnings call transcripts, and verifiable news, not
    hallucinated summaries.

-   Production quality --- every output should be presentable to a
    recruiter, professor, or investment committee without modification.

-   Automation with transparency --- every extracted number should be
    traceable to its source; every AI judgment should be legible and
    editable.

**3. Target Users**

**Primary: Equity Investing Student (Author)**

  --------------------------- -------------------------------------------
  **Context**                 Georgia Tech Scheller College of Business
                              equity investing course

  **Technical comfort**       Strong --- comfortable with Python, React,
                              financial APIs, Claude Code

  **Primary goal**            Automate the equity research workflow
                              taught in class into a replicable,
                              production-quality tool

  **Key pain points**         FMP API rate limits breaking data
                              pipelines; manual financial model
                              construction; qualitative research
                              scattered across dozens of sources; no
                              unified report output
  --------------------------- -------------------------------------------

**Secondary: Recruiters / Interviewers**

The platform doubles as a portfolio piece demonstrating both financial
knowledge and software engineering capability. Every design decision
should be defensible to a technical interviewer at an investment firm or
fintech company.

**4. Current State**

**What Is Built**

-   React frontend with Analysis, DCF Model, DDM Model, and Industry
    Analysis tabs

-   FastAPI backend with streaming and non-streaming routes

-   SEC EDGAR integration for 10-K filings and 8-K earnings call
    transcripts

-   FRED API integration for live risk-free rate (Rf) used in WACC and
    CAPM

-   FMP API integration for financial statements (active but hitting
    rate limits)

-   AI-powered bull/bear case generation and Porter\'s Five Forces
    analysis

-   Step-based progress indicator for long-running AI analysis requests

-   .claude folder framework with CLAUDE.md and six slash commands for
    Claude Code sessions

**Active Rework**

-   Data layer migration: FMP as primary source is being replaced due to
    rate limit constraints

-   \~300 lines of duplication between streaming and non-streaming
    routes in main.py flagged for refactor

-   Bloomberg Terminal integration partially underway via Excel export
    workflow (school license constraints prevent direct blpapi
    installation)

**Known Technical Debt**

-   main.py: \~300-line duplication between streaming and non-streaming
    routes

-   No caching layer --- repeated analysis of the same ticker burns API
    budget

-   Bloomberg field coverage gaps under school license not yet fully
    audited (v3 template pending)

-   FMP dependency not yet fully replaced in all routes

**5. Data Architecture**

The platform uses a tiered data source architecture. Each tier serves a
distinct data type, eliminating single-source dependency and rate limit
fragility.

  ---------------------------------------------------------------------------
  **Tier**       **Source**       **Data Provided**       **Notes**
  -------------- ---------------- ----------------------- -------------------
  1 --- Primary  SEC EDGAR        Financial statements,   No API key, no rate
  fundamentals   (edgartools)     10-K sections, 8-K      limits,
                                  transcripts             authoritative

  2 --- Live     Alpaca Markets   Real-time quotes, OHLCV Free tier: 10,000
  prices         API              history (7yr+),         calls/min, requires
                                  intraday bars           API key

  3 ---          FRED API         10-year Treasury yield  Already integrated,
  Risk-free rate                  for WACC / CAPM         remains unchanged

  4 ---          Finviz           Screener data, sector   Fallback for fields
  Supplemental                    tags, quick             not covered by
                                  fundamentals            EDGAR

  5 --- Reserved FMP              Peer comparison ratios, Retained for
                                  pre-built DCF outputs   low-frequency calls
                                                          only

  6 ---          Web search       Recent news, analyst    Used for Report tab
  Qualitative    (AI-powered)     commentary, market      thesis generation
                                  events                  
  ---------------------------------------------------------------------------

**Sources Evaluated and Rejected**

-   yfinance --- Rejected. Unofficial scraper, not a real API. Rate
    limits are undocumented and enforcement tightened significantly in
    late 2024. Unsuitable for a production portfolio piece.

-   Bloomberg Terminal (blpapi) --- Blocked by school license
    environment. Excel COM automation (win32com) is the practical path;
    v3 template audit pending.

-   Alpha Vantage --- 25 calls/day on free tier. Too restrictive for
    development.

**6. EDGAR Extraction Layer**

The edgar_extractor.py module is the highest-priority engineering work
in the current rework. All DCF and DDM accuracy depends on correct
extraction. The module must handle four distinct challenges:

**6.1 XBRL Tag Resolution**

Revenue alone can appear under a dozen different XBRL tags depending on
company and sector. The extractor must implement a tag resolution
hierarchy --- trying tags in priority order and validating the result is
plausible before accepting it. Key fields requiring resolution
hierarchies:

-   Revenue: Revenues →
    RevenueFromContractWithCustomerExcludingAssessedTax →
    SalesRevenueNet → custom extension

-   D&A: DepreciationDepletionAndAmortization →
    DepreciationAndAmortization → sector-specific (DD&A for E&P)

-   Capex: PaymentsToAcquirePropertyPlantAndEquipment →
    PaymentsForCapitalImprovements

-   Net income: NetIncomeLoss → NetIncome → ProfitLoss

**6.2 Industry Profile System**

The extractor auto-detects GICS sector from the DEI section of the EDGAR
filing and loads an industry profile that controls model behavior.
Profiles are defined per sector and specify:

-   Which models are enabled (e.g., DCF disabled for Financials/Banks,
    DDM disabled for early-stage Tech)

-   Input substitutions (e.g., FFO replaces net income for REITs; DD&A
    replaces D&A for Energy E&P)

-   Required addbacks (e.g., stock-based compensation for Technology)

-   Growth model type (single-stage Gordon Growth vs. multi-stage DCF)

-   UI warnings surfaced when model assumptions may be unreliable

  ------------------------------------------------------------------------------
  **Industry**   **DCF**     **DDM**     **Key Adaptations**
  -------------- ----------- ----------- ---------------------------------------
  Technology     Primary     Avoid       Add back SBC; normalize lumpy capex;
                                         multi-stage growth

  Financials /   Avoid       Primary     FCF undefined; use book equity + ROE
  Banks                                  vs. Ke spread

  Energy (E&P)   Primary     Avoid       DD&A replaces D&A; normalize capex over
                                         commodity cycle

  REITs          Secondary   Primary     FFO replaces net income (NI + D&A -
                                         gains on sales)

  Utilities      Secondary   Primary     Growth tied to rate cases, not revenue
                                         momentum

  Consumer       Primary     Primary     Both models valid; watch working
  Staples                                capital FCF distortions

  Healthcare /   Primary     Rare        Pipeline probability-weight future cash
  Pharma                                 flows; multi-scenario

  Industrials    Primary     Secondary   Normalize earnings over full cycle, not
                                         peak or trough
  ------------------------------------------------------------------------------

**6.3 Multi-Period Stitching**

DCF and DDM models require 5 years of historical data. edgartools\' XBRL
stitching API is used to combine multiple annual 10-K filings into a
consistent time series. DDM growth rate is computed from ROE × retention
ratio OR multi-year dividend CAGR across stitched filings.

**6.4 Extraction Validation**

Every extracted field must pass plausibility checks before being used in
a model. Validation rules include sign checks (capex must be negative in
cash flow statement), magnitude checks (revenue should be positive and
within an order of magnitude of prior year), and cross-statement
consistency checks (net income on income statement should match cash
flow starting point).

**7. Feature Scope by Tab**

**7.1 Analysis Tab**

Generates a structured bull/bear investment thesis from primary sources.
This is the qualitative engine of the platform.

**Qualitative Sources (in synthesis order)**

-   SEC 10-K --- Item 1 (Business), Item 1A (Risk Factors), Item 7
    (MD&A)

-   SEC 8-K --- Earnings call transcripts (Exhibit 99.1), most recent 4
    quarters

-   Web search --- Recent news articles, analyst commentary, sector
    developments

-   Analyst consensus --- Forward EPS estimates, price targets, rating
    distribution

**Output Structure**

-   Bull case: 3--5 thesis points grounded in specific filing citations
    and recent catalysts

-   Bear case: 3--5 risk factors sourced from Risk Factors section and
    earnings call language

-   Initiation stance: Hold / Buy / Sell with stated rationale

-   Key catalysts: Upcoming events that could validate or invalidate the
    thesis

-   Risk assessment: Quantified where possible (e.g., commodity price
    sensitivity, leverage ratio)

**7.2 DCF Model Tab**

Industry-aware discounted cash flow model using Net Income + D&A − Capex
methodology with P/E exit multiples. All inputs extracted from EDGAR;
all assumptions editable with live cascading recalculation.

**Inputs (EDGAR-extracted)**

-   Net income --- 5-year historical from income statement (with sector
    substitutions per industry profile)

-   Depreciation & amortization --- from cash flow statement non-cash
    addbacks

-   Capital expenditures --- from investing activities section

-   Shares outstanding --- from DEI / cover page

-   Net debt --- long-term debt + short-term debt - cash (balance sheet)

-   Revenue --- for growth rate estimation and margin validation

**Assumptions (user-editable, AI-suggested)**

-   Revenue growth rate (years 1--5)

-   Target P/E exit multiple

-   WACC (auto-populated via CAPM: FRED Rf + beta × ERP)

-   Terminal growth rate

**7.3 DDM Model Tab**

Dividend discount model supporting both Gordon Growth (single-stage) and
multi-stage approaches. Automatically suppressed with a warning for
sectors where dividends are not applicable (early-stage Tech, E&P).

**Inputs (EDGAR-extracted)**

-   Dividends per share --- from income statement, multi-year history

-   Payout ratio --- dividends / net income

-   Book equity --- from balance sheet

-   Return on equity --- net income / book equity

**Derived Computations**

-   Sustainable growth rate: g = ROE × (1 − payout ratio)

-   Required return (Ke): CAPM = Rf + beta × ERP

-   Intrinsic value: D1 / (Ke − g) for Gordon Growth; stage-weighted for
    multi-stage

**7.4 Industry Analysis Tab**

Porter\'s Five Forces framework with AI-researched competitive dynamics.
Each force is rated and supported by evidence from 10-K filings and web
research.

-   Threat of new entrants

-   Bargaining power of suppliers

-   Bargaining power of buyers

-   Threat of substitutes

-   Competitive rivalry

**7.5 Report Tab (Planned)**

The Report tab is the culminating feature --- a formatted equity
research report matching the structure of a professional initiation
report. The reference artifact is the CNX Resources initiation report
authored during the course.

**Report Sections**

-   Cover block: ticker, current price, target price, 52-week range,
    market cap, shares outstanding, initiation stance

-   Narrative thesis: 2--3 paragraph investment thesis synthesized from
    qualitative sources with bull/bear framing

-   Financial model table: Income statement, FCF bridge, balance sheet
    --- 5 years historical + 5 years projected

-   Peer comps table: Key trading multiples (P/E, EV/EBITDA, P/FCF, FCF
    yield, net debt/EBITDA) vs. sector peers

-   Valuation section: P/E target methodology, intrinsic value
    calculation, % upside/downside

-   Technical snapshot: YTD performance, % change from 200-day moving
    average

**Delivery**

-   In-app rendered report view (React) --- for review and editing

-   PDF export --- for submission and portfolio use

**Qualitative Synthesis Pipeline**

The report narrative is generated in two stages. Stage 1 extracts a
structured financial fingerprint (key facts, trends, management guidance
language) from EDGAR filings and earnings transcripts. Stage 2 passes
the fingerprint plus recent news context to Claude to generate the
narrative thesis. This two-stage approach produces more consistent,
citation-grounded output than single-prompt generation.

**8. Technical Architecture**

**8.1 Stack**

  --------------------------- -------------------------------------------
  **Frontend**                React (component-based, tab navigation,
                              live recalculation)

  **Backend**                 FastAPI (Python) --- REST + streaming
                              routes

  **AI layer**                Anthropic Claude API (claude-sonnet-4-6)
                              --- analysis, thesis generation, report
                              narrative

  **Primary data**            SEC EDGAR via edgartools (no API key, no
                              rate limits)

  **Live prices**             Alpaca Markets API (free tier, 10,000
                              calls/min)

  **Risk-free rate**          FRED API (10-year Treasury yield)

  **Supplemental**            Finviz (sector data, screener fallback)

  **Dev environment**         Claude Code with .claude folder framework
                              (CLAUDE.md + 6 slash commands)

  **Version control**         GitHub
  --------------------------- -------------------------------------------

**8.2 Key Modules (Planned / In Progress)**

-   edgar_extractor.py --- XBRL extraction with tag resolution
    hierarchy, industry profile system, multi-period stitching, and
    validation layer

-   industry_profiles.py --- Sector config keyed by GICS sector code;
    controls model selection, input substitutions, addbacks, and UI
    warnings

-   alpaca_client.py --- Live price and historical OHLCV fetching;
    replaces FMP for all price-related calls

-   report_generator.py --- Two-stage qualitative synthesis pipeline;
    produces structured JSON fingerprint → narrative report

-   cache.py --- TTL-based caching (prices: 15min, fundamentals: 24hr,
    statements: 7 days) to eliminate redundant API calls

**8.3 Planned Refactor**

-   main.py: Extract shared logic from \~300 lines of duplicated
    streaming/non-streaming routes into shared service functions

-   Centralize all data source calls behind an abstract data_service
    layer so sources can be swapped without touching route logic

**9. Phase Roadmap**

  ------------------------------------------------------------------------------
  **Phase**   **Name**           **Key Deliverables**               **Status**
  ----------- ------------------ ---------------------------------- ------------
  1           Data layer rework  edgar_extractor.py with XBRL tag   In progress
                                 resolution, industry profile       
                                 system, multi-period stitching,    
                                 Alpaca price client, caching       
                                 layer, FMP dependency removal      

  2           Model accuracy     Validated DCF and DDM extraction   Planned
                                 for all 8 industry profiles;       
                                 cross-statement validation;        
                                 industry-aware UI warnings; test   
                                 suite against known companies      

  3           Qualitative        Two-stage report pipeline;         Planned
              synthesis          earnings call transcript parser;   
                                 news synthesis; analyst consensus  
                                 integration; citation traceability 

  4           Report tab         In-app report renderer; PDF        Planned
                                 export; peer comps table;          
                                 technical snapshot; full report    
                                 matching CNX initiation report     
                                 structure                          

  5           Polish & portfolio main.py refactor; Bloomberg v3     Planned
                                 template audit; performance        
                                 optimization; error handling;      
                                 README; demo video                 
  ------------------------------------------------------------------------------

**10. Success Criteria**

**Model Accuracy**

-   DCF and DDM outputs validated against manual calculation for at
    least 5 companies across 3 different sectors

-   Revenue extraction correct for companies using non-standard XBRL
    tags (e.g., RevenueFromContractWithCustomerExcludingAssessedTax)

-   Industry profile system correctly suppresses inapplicable models and
    surfaces appropriate warnings

**Report Quality**

-   Generated report matches the structure and information density of
    the CNX Resources initiation report

-   Every quantitative claim in the narrative is traceable to an
    extracted figure or cited source

-   PDF export is presentation-ready without manual formatting

**Performance**

-   Full analysis (data extraction + AI synthesis) completes within 60
    seconds

-   Scenario assumption changes recalculate DCF/DDM within 100ms

-   Application loads in under 2 seconds

**Portfolio Standard**

-   Codebase is clean, modular, and documented --- defensible in a
    technical interview

-   No hardcoded API keys; .env pattern throughout

-   Data sources are authoritative and traceable --- no yfinance
    scraping

**11. Risks & Mitigations**

  ---------------------------------------------------------------------------
  **Risk**              **Impact**   **Mitigation**
  --------------------- ------------ ----------------------------------------
  XBRL tag variance     High         Tag resolution hierarchy with fallback
  breaks extraction for              chain; plausibility validation; manual
  non-standard filers                override UI

  Industry profile      High         Prominent UI warnings; user-visible
  misconfiguration                   sector detection; ability to override
  produces wrong model               detected sector

  AI qualitative        High         Two-stage pipeline --- extract facts
  synthesis produces                 first, then generate narrative; source
  hallucinated                       attribution required in output
  citations                          

  Alpaca free tier      Medium       Free tier covers historical OHLCV and
  limitations for                    delayed quotes; sufficient for class
  real-time data                     use; upgrade path available

  Bloomberg field gaps  Medium       v3 template audit will map coverage
  under school license               empirically; EDGAR is primary and
                                     Bloomberg is supplemental

  main.py duplication   Medium       Refactor to shared service layer before
  causes bugs during                 adding new routes; flagged as Phase 5
  rework                             task

  Peer comps data       Low          Use EDGAR + Alpaca for peer financials;
  quality (no                        clearly label as self-computed vs.
  institutional data                 consensus
  source)                            
  ---------------------------------------------------------------------------

**12. Future Considerations**

**Post-MVP Data Enhancements**

-   Bloomberg Terminal live integration via win32com Excel COM
    automation (\~30s end-to-end, acceptable with progress indicator)

-   Schwab Trader API for live options data and implied volatility as
    sentiment overlay

-   Paid fundamental data source (EODHD or Tiingo) if EDGAR coverage
    proves insufficient for edge cases

**Feature Extensions**

-   Monte Carlo simulation --- probabilistic DCF across correlated
    assumption distributions

-   Multi-ticker comparison --- side-by-side DCF/DDM and peer comps for
    competing investments

-   Portfolio tracker --- Schwab API position integration with live
    intrinsic value vs. market price monitoring

-   Sector screener --- Stock Hacker equivalent using computed
    indicators and fundamental filters

**Technical Improvements**

-   PostgreSQL persistence --- save analyses, track assumption changes
    over time

-   Authentication --- user accounts with saved ticker watchlists

-   WebSocket streaming --- real-time price updates in DCF without page
    refresh

-   Test suite --- unit tests for all financial calculations;
    integration tests for extraction pipeline
