"""
industry_config.py — per-sector valuation rules applied by the DCF model.

Call get_sector_rules(sector_string) to retrieve the SectorRules appropriate
for the sector string returned by FMP's company profile endpoint.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SectorRules:
    sector_label: str            # Human-readable label used in logs and warnings

    # Growth rate controls
    growth_recency_bias: float   # Extra multiplier for the most-recent year's weight.
                                 # 1.0 = standard weighting; 2.0 = recent year counts double.
    growth_cap: float            # Upper bound on revenue growth rate.
    growth_floor: float          # Lower bound (overrides MIN_GROWTH_RATE from config).

    # WACC controls
    wacc_cap: Optional[float]    # Hard cap on WACC. None = no cap.

    # DCF appropriateness
    dcf_appropriate: bool        # False for sectors where DCF is structurally unreliable.
    dcf_warning: Optional[str]   # Surfaced in the UI when set.

    # Analyst prompt guidance injected into the Claude prompt
    analyst_guidance: str


# ── Sector definitions ────────────────────────────────────────────────────────

_TECHNOLOGY = SectorRules(
    sector_label        = "Technology",
    growth_recency_bias = 2.0,    # recent growth is the strongest signal for tech
    growth_cap          = 0.40,
    growth_floor        = 0.05,   # tech rarely shrinks structurally
    wacc_cap            = 0.14,   # cap at 14% — high ERP shouldn't over-penalise growth cos
    dcf_appropriate     = True,
    dcf_warning         = None,
    analyst_guidance    = (
        "Focus on competitive moats, R&D investment efficiency, and market share dynamics. "
        "Assess customer switching costs, network effects, and the risk of disruption by "
        "new entrants or platform shifts. Evaluate management's guidance on revenue growth "
        "deceleration or re-acceleration, and scrutinise stock-based compensation relative "
        "to free cash flow."
    ),
)

_ENERGY = SectorRules(
    sector_label        = "Energy",
    growth_recency_bias = 1.0,
    growth_cap          = 0.30,   # commodity cycles distort growth; cap lower
    growth_floor        = 0.02,   # can be low in weak commodity environments
    wacc_cap            = None,
    dcf_appropriate     = True,
    dcf_warning         = (
        "Energy companies are highly sensitive to commodity prices. DCF projections carry "
        "elevated uncertainty; consider EV/EBITDA multiples alongside this intrinsic value "
        "estimate. Commodity price assumptions embedded in management guidance should be "
        "treated sceptically."
    ),
    analyst_guidance    = (
        "Emphasise commodity price sensitivity, reserve life and depletion rates, and capex "
        "intensity. Assess balance sheet resilience through commodity down-cycles and any "
        "hedging programmes that smooth near-term cash flows. Highlight ESG and energy-"
        "transition risks, including stranded-asset exposure and regulatory carbon costs."
    ),
)

_FINANCIALS = SectorRules(
    sector_label        = "Financial Services",
    growth_recency_bias = 1.0,
    growth_cap          = 0.25,
    growth_floor        = 0.02,
    wacc_cap            = None,
    dcf_appropriate     = False,
    dcf_warning         = (
        "DCF valuation is not appropriate for financial companies. Debt is part of the "
        "operating model rather than just the capital structure, making free cash flow "
        "unreliable as a valuation input. Prefer Price/Book ratio, Return on Equity (ROE), "
        "and net interest margin trends for valuation."
    ),
    analyst_guidance    = (
        "Focus on credit quality, net interest margin, capital adequacy ratios (CET1 / Tier 1), "
        "and loan-loss provisioning. Assess exposure to interest rate movements and credit cycles. "
        "Highlight any regulatory capital requirements, enforcement actions, or dividend "
        "sustainability concerns. For insurers, evaluate the combined ratio and reserve adequacy."
    ),
)

_HEALTHCARE = SectorRules(
    sector_label        = "Healthcare / Biotech",
    growth_recency_bias = 1.0,
    growth_cap          = 0.40,
    growth_floor        = 0.03,
    wacc_cap            = None,
    dcf_appropriate     = True,
    dcf_warning         = (
        "Healthcare and biotech projections carry elevated uncertainty due to binary "
        "regulatory outcomes and patent-cliff risk. Treat this DCF range as wide; "
        "scenario analysis around pipeline success rates is advisable."
    ),
    analyst_guidance    = (
        "Emphasise drug pipeline risk, FDA/EMA regulatory approval probabilities, and patent "
        "expiry timelines. Assess reimbursement and pricing pressure from payers and government "
        "programmes. For pure-play biotechs with no approved products, note that DCF assumptions "
        "are highly speculative and binary outcomes dominate valuation."
    ),
)

_CONSUMER_STAPLES = SectorRules(
    sector_label        = "Consumer Staples / Retail",
    growth_recency_bias = 1.0,
    growth_cap          = 0.20,   # staples and retail rarely grow fast
    growth_floor        = 0.02,
    wacc_cap            = None,
    dcf_appropriate     = True,
    dcf_warning         = None,
    analyst_guidance    = (
        "Focus on pricing power relative to input cost inflation, brand loyalty, and "
        "private-label competitive pressure. Assess supply chain resilience and inventory "
        "management discipline. For retailers, evaluate same-store sales growth, e-commerce "
        "transition progress, and store footprint rationalisation."
    ),
)

_DEFAULT = SectorRules(
    sector_label        = "General",
    growth_recency_bias = 1.0,
    growth_cap          = 0.40,
    growth_floor        = 0.03,
    wacc_cap            = None,
    dcf_appropriate     = True,
    dcf_warning         = None,
    analyst_guidance    = (
        "Provide a balanced assessment of the company's competitive positioning, revenue "
        "growth sustainability, margin trajectory, and capital allocation efficiency."
    ),
)


# ── Lookup ─────────────────────────────────────────────────────────────────────

def get_sector_rules(sector: str) -> SectorRules:
    """
    Return the SectorRules for the given FMP sector string.
    Matching is case-insensitive and uses substring checks for robustness.
    Returns _DEFAULT if no sector matches.
    """
    s = sector.lower()

    if any(k in s for k in ("tech", "software", "semiconductor", "information")):
        return _TECHNOLOGY
    if any(k in s for k in ("energy", "oil", "gas", "mining")):
        return _ENERGY
    if any(k in s for k in ("financial", "bank", "insurance", "asset management", "brokerage")):
        return _FINANCIALS
    if any(k in s for k in ("health", "biotech", "pharma", "life science", "medical")):
        return _HEALTHCARE
    if any(k in s for k in ("consumer staple", "consumer defensive", "food", "beverage",
                             "household", "retail")):
        return _CONSUMER_STAPLES
    return _DEFAULT
