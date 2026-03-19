# 10-K Analysis Framework for Equity Research

> **Purpose:** This document tells Claude how to read a 10-K like a professional equity analyst. It defines what to extract from each section, what signals matter, how each section connects to the DCF/DDM models, and how to build a defensible bull/bear investment thesis. It synthesizes the CFA Institute financial statement analysis framework, Damodaran's valuation-focused reading approach, and the structure of professional sell-side initiation reports.
>
> **How to use this:** When analyzing a 10-K for the platform's Analysis tab or Report tab, Claude should work through each section below in order, extracting the specified signals and mapping them to the output categories defined at the end.

---

## Foundational Principle: Read for Value Drivers, Not Just Numbers

Per Damodaran's framework, every element of a 10-K should be read through the lens of four questions:
1. **What are the current cash flows?** (base year for DCF)
2. **How fast will cash flows grow?** (growth rate assumptions)
3. **How long will above-average growth last?** (competitive advantage period)
4. **How risky are these cash flows?** (discount rate, bull/bear risk framing)

The financial statements answer question 1. The narrative sections — especially Item 1, 1A, and 7 — answer questions 2, 3, and 4.

---

## Section-by-Section Reading Guide

### Item 1 — Business Description

**What it is:** The company's own description of what it does, how it makes money, and where it competes.

**What to extract:**

*Revenue model*
- How does the company generate revenue? (subscription, transactional, project-based, asset-based)
- What percentage of revenue is recurring vs. one-time?
- Are revenues diversified across customers, geographies, and products — or concentrated?
- Customer concentration: does any single customer represent >10% of revenue? (Required disclosure if so)

*Competitive position*
- What does management claim is its competitive advantage? (cost leadership, differentiation, network effects, switching costs, regulatory moat)
- How many competitors are named, and how are they characterized?
- What barriers to entry does management describe?

*Business segments*
- Are there multiple segments? Which is growing fastest? Which has the highest margins?
- Are segment margins disclosed? (A key signal — management sometimes buries a low-margin drag segment)

*Operational model*
- Is the business capital-intensive or asset-light?
- Does it own or lease its key assets?
- What are the key inputs (labor, raw materials, energy)? Are these inputs commodity-priced or proprietary?

**DCF/DDM connection:**
- Revenue model → growth rate assumption quality (recurring revenue = more predictable growth)
- Competitive position → length of high-growth period (strong moat = longer runway)
- Capital intensity → capex as % of revenue (asset-heavy = higher maintenance capex drag on FCF)

**Bull signals:** Recurring revenue, high switching costs, expanding addressable market, pricing power, customer concentration below 10%
**Bear signals:** Commoditized product, no named competitive advantage, heavy customer concentration, declining segment disclosed

---

### Item 1A — Risk Factors

**What it is:** Legally required disclosure of material risks. Companies are incentivized to be comprehensive here (liability protection), so this section is unusually candid.

**What to extract:**

*Operational risks*
- Supply chain dependencies (single-source suppliers, geographic concentration)
- Key person risk (named executives identified as critical)
- Technology obsolescence risk
- Cybersecurity and data breach exposure

*Financial risks*
- Debt covenant risks and refinancing exposure
- Interest rate sensitivity (floating rate debt)
- Foreign currency exposure (% of revenue from non-USD markets)
- Pension obligations and underfunding

*Regulatory and legal risks*
- Active litigation (especially if quantified)
- Regulatory approval dependencies (critical for pharma, utilities, financials)
- Environmental liability exposure

*Market and competitive risks*
- Named competitors gaining share
- Pricing pressure from new entrants or substitutes
- End-market cyclicality or demand concentration

**Reading technique:** Scan for risks that are *specific and quantified* rather than generic boilerplate. A risk factor that says "cybersecurity incidents could harm our business" is boilerplate. A risk factor that says "we rely on a single third-party supplier in Taiwan for 60% of our key component" is material and specific — extract it.

**DCF/DDM connection:**
- Financial risks → discount rate adjustment (higher leverage risk = higher beta = higher Ke)
- Operational risks → bear case scenario construction
- Regulatory risks → may cap growth rate or create binary outcome scenarios (pharma pipeline)

**Bull signals:** Risk factors are generic / mostly boilerplate, limited quantified exposures
**Bear signals:** Specific quantified risks (customer concentration, covenant headroom, supply chain single-sourcing), litigation with named damages, named competitors cited as superior

---

### Item 2 — Properties

**What it is:** Description of physical locations, facilities, and whether they are owned or leased.

**What to extract:**
- Own vs. lease ratio (high lease exposure = operating leverage, fixed cost risk)
- Geographic concentration of facilities
- Capacity utilization disclosures (if provided)
- Any sale-leaseback transactions (can signal balance sheet pressure)

**DCF connection:** Lease obligations feed into adjusted net debt for enterprise value calculation. Operating lease capitalization adjusts EBITDA and net debt.

---

### Item 3 — Legal Proceedings

**What it is:** Material pending legal proceedings not already covered in Risk Factors.

**What to extract:**
- Any proceedings with quantified potential damages
- Pattern of litigation (is this a one-time event or systemic?)
- SEC investigations or regulatory enforcement actions

**Bear signal:** Undisclosed or quantified contingent liabilities not reflected on the balance sheet

---

### Item 7 — Management's Discussion and Analysis (MD&A)

**What it is:** Management's own narrative explanation of the financial results. This is the most important qualitative section for understanding performance drivers. Unlike Risk Factors, MD&A reflects management's optimistic framing — read critically.

**What to extract:**

*Revenue drivers*
- What drove revenue growth or decline in the period? (Volume vs. price vs. mix vs. FX)
- Which segments or geographies outperformed? Which underperformed?
- What does management say about the sustainability of growth drivers?

*Margin analysis*
- What drove gross margin expansion or compression?
- Are operating expense increases investments (R&D, sales force) or cost overruns?
- Management's explanation of one-time items — are they truly non-recurring?

*Cash flow quality*
- Compare net income to operating cash flow. A persistent large gap (income >> cash) is a quality of earnings red flag.
- Working capital changes: is receivables growth outpacing revenue growth? (Potential channel stuffing or collection risk)
- Capex: is it maintenance or growth? Management often characterizes this in the MD&A.

*Guidance and forward-looking language*
- What does management say about the outlook? (Specific guidance, qualitative commentary, or silence?)
- Are they raising or lowering guidance vs. prior periods?
- Tone analysis: count hedging language ("may," "could," "subject to") vs. confident language ("expect," "will," "committed to")

*Capital allocation commentary*
- Dividend policy changes
- Share repurchase authorization and pace
- M&A strategy and pipeline commentary

**Damodaran principle:** MD&A is where you find the "normalized" earnings story. Strip out the noise management describes (one-time charges, restructuring costs, FX) and ask: what is the underlying business earning in a normal year?

**DCF connection:**
- Revenue driver analysis → growth rate assumption grounding
- Capex characterization → maintenance vs. growth capex split
- Cash flow quality → whether reported FCF is a reliable base

**Bull signals:** Volume-driven growth (not just price), expanding margins with explained investment rationale, cash flow conversion >90% of net income, raised guidance
**Bear signals:** Price-only growth in a commoditized market, margin compression with no recovery plan, receivables growing faster than revenue, guidance cuts or removal, heavy one-time item reliance

---

### Item 7A — Quantitative and Qualitative Disclosures About Market Risk

**What it is:** Sensitivity disclosures for interest rate risk, foreign currency risk, and commodity price risk.

**What to extract:**
- Interest rate sensitivity: impact of 100bp rate move on interest expense (especially for floating rate borrowers)
- FX sensitivity: impact of 10% USD strengthening on revenue/earnings
- Commodity sensitivity: for energy, materials, and agriculture companies, cost impact of price moves

**DCF connection:** These feed directly into bear case stress testing. A company with 80% floating rate debt and 40% international revenue has two major macro sensitivities to model.

---

### Item 8 — Financial Statements and Notes

**What it is:** The audited financial statements. The statements themselves are extracted by the platform's EDGAR module. The **footnotes** are where the qualitative work happens.

**Critical footnotes to read:**

*Revenue recognition (Note 1 / Significant Accounting Policies)*
- When does the company recognize revenue? (At shipment, at delivery, over contract term?)
- Any changes in revenue recognition policy vs. prior year?
- Deferred revenue balances — is backlog growing or shrinking?

*Debt and credit facilities*
- What are the covenants? (Leverage ratio, interest coverage minimums)
- When does debt mature? (Near-term maturities = refinancing risk)
- What is the blended interest rate on debt?
- Are there any springing covenants or PIK (payment-in-kind) features?

*Goodwill and intangibles*
- Large goodwill relative to total assets = acquisition-heavy history
- Any goodwill impairment charges? (A signal that past acquisitions are underperforming)
- Intangible amortization schedule — this flows through earnings as a non-cash charge

*Stock-based compensation*
- Annual SBC expense as % of revenue (>5% for non-tech companies is elevated)
- Diluted share count vs. basic share count (large gap = significant option/warrant dilution)

*Pension obligations*
- Funded status: are pension assets > pension obligations?
- Discount rate assumption used (higher rate = lower stated liability, but sensitivity matters)
- Near-term pension funding requirements

*Operating vs. capital leases*
- Total operating lease obligations (now on-balance sheet under ASC 842)
- Lease maturity schedule

*Segment information*
- Segment revenue, operating income, and assets by business unit
- This is often the most important note — segment margins reveal which businesses are carrying the others

**Damodaran principle on footnotes:** The footnotes tell you what the income statement is hiding. Non-cash charges, deferred revenue, pension obligations, and lease commitments are the "real" economics that GAAP income often obscures.

---

### Item 9A — Controls and Procedures

**What it is:** Management's assessment of internal controls over financial reporting.

**What to extract:**
- Any "material weakness" disclosures (serious red flag — indicates unreliable financial reporting)
- Auditor opinion: clean, qualified, or adverse?
- Any restatements disclosed

**Bear signal:** Material weakness in internal controls is a significant governance red flag, especially combined with complex revenue recognition or international operations.

---

## Earnings Call Transcript Reading Guide

Earnings calls provide what the 10-K cannot: real-time management tone, analyst pushback, and unscripted answers.

**Prepared remarks — what to extract:**
- Which metrics does management lead with? (They emphasize their strongest numbers)
- What do they *not* mention that was prominent in prior quarters? (Silence on a previously highlighted metric is a signal)
- New initiatives or strategic pivots announced
- Capital allocation decisions (buybacks, dividends, M&A)

**Q&A section — the most valuable part:**
- What questions do analysts ask repeatedly? (Reveals what the buy-side is worried about)
- How does management handle tough questions? (Deflection, vague answers, or specific quantified responses?)
- Any questions about guidance, margins, or specific segment performance that management declines to answer specifically?

**Tone analysis across quarters:**
- Compare language quarter-over-quarter. Shift from "strong" to "resilient" to "navigating headwinds" is a degradation pattern
- Watch for increasing use of non-GAAP metrics over time (can signal deteriorating GAAP performance)

**Bull signals:** Management proactively addresses bear concerns with data, specific quantified guidance, analysts asking about upside scenarios
**Bear signals:** Repeated analyst questions about the same concern, management deflection on margins or cash flow, reduction in specificity of guidance over time

---

## Form 4 — Insider Transaction Signals

**What it is:** SEC-required disclosure when executives or directors buy or sell company stock.

**Reading framework:**
- **Buying is more informative than selling** — insiders sell for many reasons (diversification, taxes, planned sales). Buying is almost always a conviction signal.
- Open market purchases (not option exercises) are the strongest signal
- Cluster buying (multiple insiders buying simultaneously) is particularly bullish
- Pattern matters more than single transactions — consistent selling by the CEO over 18 months is more meaningful than one trade

**Bull signals:** Open market purchases by CEO/CFO/directors, cluster buying during a price decline
**Bear signals:** Heavy insider selling not related to pre-planned 10b5-1 programs, selling at prices well below recent highs, zero insider ownership

---

## Output Mapping: From 10-K to Platform

### Bull Case Construction
Draw from: Item 1 (competitive moat), Item 7 (growth drivers, margin expansion), earnings call prepared remarks (management confidence), Form 4 (insider buying)

Structure: 3-5 specific thesis points, each grounded in a cited section:
- "Management's exclusive supplier relationships (Item 1) create pricing power that supported 200bp gross margin expansion in FY2025 (Item 7)"
- "The company's 81% hedge book coverage (Item 7A) insulates 2026 FCF from commodity price volatility"

### Bear Case Construction
Draw from: Item 1A (risk factors, specific quantified risks), Item 7 (margin headwinds, guidance), earnings call Q&A (analyst concerns), Item 3 (legal proceedings), footnotes (covenant proximity, debt maturity)

Structure: 3-5 specific risk points with quantification where available:
- "Customer concentration risk: top 3 customers represent 62% of revenue (Item 1), creating single-point-of-failure exposure"
- "Debt covenant: leverage ratio covenant of 4.0x against current 3.8x net debt/EBITDA leaves minimal cushion (Note X)"

### DCF Growth Rate Grounding
Draw from: Item 7 (management's revenue growth explanation), Item 1 (TAM and market position), earnings call (guidance), industry context from Item 1

The growth rate is not just a number — it needs a narrative:
- "5% revenue CAGR based on: (1) management's 5-7% organic growth guidance, (2) modest market share gains in the Southeast region noted in Q4 call, (3) offset by pricing pressure in the legacy product line disclosed in Item 7"

### Valuation / Intrinsic Value Narrative
Draw from: Item 7A (macro sensitivity), peer comps, DCF output

Frame the valuation with context:
- What multiple does the current price imply?
- Is the market pricing in the bull or bear case?
- What is the margin of safety at the current price?

### Catalyst Identification
Draw from: Item 7 (pending events), Item 1A (regulatory timelines), earnings call (management guidance on upcoming events)

Catalysts are specific, time-bounded events that could validate or invalidate the thesis:
- Upcoming earnings reports where guidance will be updated
- Regulatory decisions (drug approvals, rate case outcomes, antitrust reviews)
- Debt maturity dates or refinancing windows
- Contract renewal or expirations
- Product launches or capacity additions

---

## Quality of Earnings Checklist

Before finalizing any financial model, run through these checks:

| Check | Green flag | Red flag |
|---|---|---|
| Cash conversion | Operating CF / Net Income > 90% | Persistent gap between income and cash |
| Receivables growth | In line with revenue | Growing faster than revenue |
| Inventory build | Proportional to COGS | Inventory growing faster than sales |
| Gross margin trend | Stable or expanding | Compressing without explanation |
| Non-GAAP adjustments | Small and consistent | Large, growing, or changing year-over-year |
| Audit opinion | Clean (unqualified) | Qualified, adverse, or material weakness |
| Revenue recognition | Consistent policy | Policy changes or aggressive deferred revenue draw-down |
| Goodwill | Small relative to equity | >50% of total assets; impairments |
| SBC | <3% of revenue for non-tech | >5% in mature companies |
| Insider activity | Open market purchases | Consistent heavy selling |

---

## Industry-Specific Reading Notes

### Technology
- R&D expense is the real capex — treat capitalized software development costs carefully
- Deferred revenue growth = strong future revenue visibility (bull signal)
- SBC can be 10-20% of revenue for high-growth companies — adjust FCF accordingly
- Customer churn rate / net revenue retention are the most important metrics, often disclosed in MD&A or earnings calls but not required in the 10-K

### Energy (E&P)
- Reserve replacement ratio is the core value driver — disclosed in supplemental oil and gas information
- DD&A (depletion, depreciation, and amortization) is the primary non-cash charge, not standard D&A
- Hedge book coverage and realized price vs. benchmark price are critical to FCF accuracy
- Finding and development costs (F&D) per BOE measures capital efficiency

### Financials / Banks
- Net interest margin (NIM) is the core profitability metric — not gross margin
- Loan loss provisions and NPL (non-performing loan) ratios signal credit quality
- Tier 1 capital ratio is the primary solvency metric
- Standard DCF is not applicable — use DDM or excess return model

### REITs
- Funds from Operations (FFO = Net Income + D&A - Gains on Sales) is the relevant earnings metric
- Same-store NOI growth measures organic performance
- Occupancy rates and lease expiration schedules drive future FFO
- Dividend sustainability: payout ratio against AFFO (Adjusted FFO), not net income

### Healthcare / Pharma
- Pipeline probability weighting is essential — a Phase 3 drug has different value than Phase 1
- Patent expiration dates create cliff risk — model revenue drop-off explicitly
- R&D as % of revenue and pipeline breadth determine long-term growth sustainability
- FDA approval timelines and PDUFA dates are key catalysts

### Industrials / Manufacturing
- Mid-cycle normalization: avoid modeling off peak earnings in an up-cycle or trough in a down-cycle
- Order backlog growth is a leading indicator of revenue
- Pricing vs. volume decomposition in revenue growth is critical
- Raw material cost pass-through ability determines margin resilience

---

## CNX Resources — Worked Example

The following demonstrates how this framework applies to the CNX initiation report produced as course work.

**Item 1 reading:** CNX's ownership of gathering and compression infrastructure (midstream self-sufficiency) was identified as the primary competitive moat, reflected in industry-leading fully burdened cash costs of ~$1.11/Mcfe. This fed directly into the bull case and justified the premium FCF yield relative to peers.

**Item 1A reading:** The key quantified risks identified were natural gas price volatility (the primary bear case driver) and net debt of $2.41B (leverage risk in a down-cycle). These grounded the bear case and the Hold initiation stance.

**Item 7 reading:** The 81% hedge coverage for 2026 at $2.75/Mcf was the most important piece of information in the MD&A — it made the 2026 FCF estimate highly reliable regardless of spot price movements. The Apex Energy II acquisition rationale and integration update provided the growth narrative.

**Item 7A reading:** Commodity price sensitivity was the dominant market risk, which informed the use of strip pricing as the base case rather than spot prices.

**Earnings call:** Management's commentary on LNG export demand build as the 2027+ thesis anchor was extracted from the prepared remarks and used as a catalyst in the initiation report.

**Valuation:** The 12.5x P/E target (vs. 18.3x current) reflected sector-wide multiple compression from commodity price uncertainty — the MD&A provided the context for why the spread between price and intrinsic value was narrow, supporting the Hold rather than Buy stance.

---

## Citation Rules for AI-Generated Analysis

### Output Mapping (Section → Thesis Category)

| Thesis Category | Primary Source | Secondary Source | Citation Tag |
|----------------|---------------|-----------------|--------------|
| Revenue growth drivers | Item 7 (MD&A) | Earnings Call (prepared remarks) | `[Item 7]` or `[Earnings Call]` |
| Margin trends | Item 7 (MD&A) | Item 1 (Business) | `[Item 7]` |
| Competitive risks | Item 1A (Risk Factors) | Item 1 (Business) | `[Item 1A]` |
| Regulatory/legal risks | Item 1A (Risk Factors) | Item 7 (MD&A) | `[Item 1A]` |
| Capital allocation | Item 7 (MD&A) | Earnings Call Q&A | `[Item 7]` or `[Q&A]` |
| Management guidance | Earnings Call (prepared) | Item 7 (MD&A) | `[Earnings Call]` |
| Industry dynamics | Item 1 (Business) | Item 1A (Risk Factors) | `[Item 1]` |
| Macro/FX exposure | Item 1A + Item 7A | Earnings Call | `[Item 1A]` |

### Citation Format Rules

- **Every bull/bear detail paragraph MUST contain at least one bracketed citation tag**
- Allowed tags: `[Item 1]`, `[Item 1A]`, `[Item 7]`, `[Item 7A]`, `[Earnings Call]`, `[Q&A]`, `[News]`
- Multiple citations per point are encouraged when evidence spans sources
- If no source material is available for a claim, prefix with `[Analyst Estimate]`

### Quality Criteria for Thesis Points

- Each bull/bear point must reference a specific fact, figure, or quote from source material
- Downplayed risks must cite the specific Item 1A language being contrasted with reality
- Porter's Five Forces explanations must cite specific competitive dynamics from Item 1 or Item 1A
- Recent catalysts drawn from news should use `[News]` tag
