"""
industry_profiles.py — Sector-aware configuration for EDGAR-based financial models.

Maps SIC codes to GICS sectors and provides per-sector model configuration
(which models to enable, income metric substitutions, FCF addbacks, etc.).

Extends the existing SectorRules from industry_config.py.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .industry_config import SectorRules, get_sector_rules


@dataclass
class IndustryProfile:
    gics_sector: str

    # Model enablement
    dcf_enabled: bool           # True = show DCF tab
    ddm_enabled: bool           # True = show DDM tab
    dcf_is_primary: bool        # True = DCF is the recommended model
    ddm_is_primary: bool        # True = DDM is the recommended model

    # Input substitutions
    income_metric: str          # "net_income" | "ffo" (REITs)
    da_metric: str              # "depreciation_amortization" | "dda" (Energy)

    # Addbacks
    addback_sbc: bool           # Add SBC back to FCF (Technology)

    # Growth
    growth_model: str           # "multi_stage" | "single_stage"

    # Warnings
    model_warnings: List[str] = field(default_factory=list)

    # Existing SectorRules integration
    sector_rules: Optional[SectorRules] = None


# ── SIC-to-GICS mapping ──────────────────────────────────────────────────────
# Maps SIC code ranges to GICS sector names. Covers major sectors.
# Falls back to "General" for unrecognised SIC codes.

SIC_TO_GICS: List[Tuple[range, str]] = [
    # Technology
    (range(3570, 3580), "Technology"),   # Computer hardware
    (range(3580, 3590), "Technology"),   # Computer peripherals
    (range(3660, 3670), "Technology"),   # Communication equipment
    (range(3670, 3680), "Technology"),   # Electronic components
    (range(3810, 3830), "Technology"),   # Instruments / measuring
    (range(7370, 7380), "Technology"),   # Computer services / software
    (range(3570, 3600), "Technology"),   # Broader computer & office equipment
    (range(3672, 3673), "Technology"),   # Printed circuit boards
    (range(3674, 3675), "Technology"),   # Semiconductors
    (range(3812, 3813), "Technology"),   # Defense electronics
    (range(5045, 5046), "Technology"),   # Computers & peripherals wholesale
    (range(5065, 5066), "Technology"),   # Electronic parts wholesale
    (range(4812, 4814), "Technology"),   # Telephone communications
    (range(4899, 4900), "Technology"),   # Communications services NEC

    # Financials
    (range(6000, 6100), "Financials"),   # Banks & depository institutions
    (range(6100, 6200), "Financials"),   # Non-depository credit institutions
    (range(6200, 6300), "Financials"),   # Securities & commodity brokers
    (range(6300, 6400), "Financials"),   # Insurance carriers
    (range(6400, 6500), "Financials"),   # Insurance agents
    (range(6700, 6770), "Financials"),   # Holding & investment offices

    # Energy
    (range(1310, 1320), "Energy"),       # Crude oil & natural gas
    (range(1380, 1390), "Energy"),       # Oil & gas field services
    (range(1220, 1230), "Energy"),       # Bituminous coal mining
    (range(2910, 2920), "Energy"),       # Petroleum refining
    (range(4922, 4926), "Energy"),       # Natural gas distribution
    (range(5170, 5172), "Energy"),       # Petroleum products wholesale
    (range(1000, 1500), "Energy"),       # Broader mining / extraction

    # Real Estate (REITs)
    (range(6500, 6600), "Real Estate"),  # Real estate operators
    (range(6798, 6799), "Real Estate"),  # REITs

    # Utilities
    (range(4910, 4912), "Utilities"),    # Electric services
    (range(4920, 4926), "Utilities"),    # Gas production & distribution
    (range(4930, 4932), "Utilities"),    # Combination electric & gas
    (range(4940, 4942), "Utilities"),    # Water supply
    (range(4950, 4960), "Utilities"),    # Sanitary services
    (range(4911, 4912), "Utilities"),    # Electric services
    (range(4931, 4932), "Utilities"),    # Electric & gas combo
    (range(4941, 4942), "Utilities"),    # Water supply

    # Consumer Staples
    (range(2000, 2100), "Consumer Staples"),  # Food & beverages
    (range(2100, 2200), "Consumer Staples"),  # Tobacco
    (range(2800, 2830), "Consumer Staples"),  # Chemicals (cleaning products)
    (range(5140, 5160), "Consumer Staples"),  # Groceries wholesale
    (range(5400, 5500), "Consumer Staples"),  # Food stores
    (range(5812, 5813), "Consumer Staples"),  # Eating & drinking places

    # Health Care
    (range(2830, 2837), "Health Care"),  # Pharma
    (range(2840, 2845), "Health Care"),  # Soap & cleaning preparations
    (range(3841, 3842), "Health Care"),  # Surgical & medical instruments
    (range(3844, 3845), "Health Care"),  # X-ray apparatus
    (range(3851, 3852), "Health Care"),  # Ophthalmic goods
    (range(5040, 5050), "Health Care"),  # Professional equipment wholesale
    (range(8000, 8100), "Health Care"),  # Health services
    (range(2833, 2837), "Health Care"),  # Pharma preparations
    (range(3826, 3828), "Health Care"),  # Lab instruments
    (range(3841, 3852), "Health Care"),  # Medical instruments broad
    (range(8731, 8735), "Health Care"),  # Commercial R&D (biotech)

    # Industrials
    (range(3500, 3570), "Industrials"),  # Industrial machinery
    (range(3700, 3720), "Industrials"),  # Transportation equipment
    (range(3720, 3730), "Industrials"),  # Aircraft & parts
    (range(3730, 3740), "Industrials"),  # Ship building
    (range(3740, 3750), "Industrials"),  # Railroad equipment
    (range(3760, 3770), "Industrials"),  # Guided missiles & space
    (range(4000, 4100), "Industrials"),  # Railroad transportation
    (range(4400, 4500), "Industrials"),  # Water transportation
    (range(4500, 4600), "Industrials"),  # Air transportation
    (range(4700, 4800), "Industrials"),  # Transportation services
    (range(1500, 1800), "Industrials"),  # Construction
    (range(3400, 3500), "Industrials"),  # Fabricated metal products

    # Consumer Discretionary (mapped to General for profile purposes)
    (range(5300, 5400), "Consumer Discretionary"),  # General merchandise
    (range(5600, 5700), "Consumer Discretionary"),  # Apparel retail
    (range(5700, 5740), "Consumer Discretionary"),  # Home furnishing retail
    (range(5900, 6000), "Consumer Discretionary"),  # Retail stores NEC
    (range(7800, 7900), "Consumer Discretionary"),  # Amusement & recreation
    (range(7900, 8000), "Consumer Discretionary"),  # Other services
]


def map_sic_to_gics(sic_code: int) -> Tuple[str, str]:
    """
    Map a SIC code to a GICS (sector, industry) tuple.
    Returns ("General", "General") for unknown SIC codes.
    """
    for sic_range, sector in SIC_TO_GICS:
        if sic_code in sic_range:
            return sector, sector  # industry = sector as approximation
    return "General", "General"


# ── Industry profiles ─────────────────────────────────────────────────────────

PROFILES: Dict[str, IndustryProfile] = {
    "Technology": IndustryProfile(
        gics_sector="Technology",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=True,
        ddm_is_primary=False,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=True,
        growth_model="multi_stage",
        model_warnings=[],
        sector_rules=get_sector_rules("Technology"),
    ),
    "Financials": IndustryProfile(
        gics_sector="Financials",
        dcf_enabled=True,     # show but warn
        ddm_enabled=True,
        dcf_is_primary=False,
        ddm_is_primary=True,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="single_stage",
        model_warnings=[
            "DCF is structurally unreliable for financial companies — "
            "debt is part of the operating model. Prefer P/B and DDM."
        ],
        sector_rules=get_sector_rules("Financial Services"),
    ),
    "Energy": IndustryProfile(
        gics_sector="Energy",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=True,
        ddm_is_primary=False,
        income_metric="net_income",
        da_metric="dda",       # DD&A for E&P companies
        addback_sbc=False,
        growth_model="multi_stage",
        model_warnings=[
            "Energy valuations are highly sensitive to commodity prices. "
            "Consider EV/EBITDA multiples alongside DCF."
        ],
        sector_rules=get_sector_rules("Energy"),
    ),
    "Real Estate": IndustryProfile(
        gics_sector="Real Estate",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=False,
        ddm_is_primary=True,
        income_metric="ffo",   # FFO for REITs
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="single_stage",
        model_warnings=[
            "REIT valuations use FFO (Funds From Operations) instead of net income. "
            "P/FFO and dividend yield are primary valuation metrics."
        ],
        sector_rules=get_sector_rules("Real Estate"),
    ),
    "Utilities": IndustryProfile(
        gics_sector="Utilities",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=False,
        ddm_is_primary=True,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="single_stage",
        model_warnings=[],
        sector_rules=get_sector_rules("Utilities"),
    ),
    "Consumer Staples": IndustryProfile(
        gics_sector="Consumer Staples",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=True,
        ddm_is_primary=False,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="multi_stage",
        model_warnings=[],
        sector_rules=get_sector_rules("Consumer Staples"),
    ),
    "Health Care": IndustryProfile(
        gics_sector="Health Care",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=True,
        ddm_is_primary=False,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="multi_stage",
        model_warnings=[
            "Biotech/pharma projections carry elevated uncertainty due to "
            "binary regulatory outcomes and patent-cliff risk."
        ],
        sector_rules=get_sector_rules("Healthcare"),
    ),
    "Industrials": IndustryProfile(
        gics_sector="Industrials",
        dcf_enabled=True,
        ddm_enabled=True,
        dcf_is_primary=True,
        ddm_is_primary=False,
        income_metric="net_income",
        da_metric="depreciation_amortization",
        addback_sbc=False,
        growth_model="multi_stage",
        model_warnings=[],
        sector_rules=get_sector_rules("Industrials"),
    ),
}

# Default profile for sectors not in the map
_DEFAULT_PROFILE = IndustryProfile(
    gics_sector="General",
    dcf_enabled=True,
    ddm_enabled=True,
    dcf_is_primary=True,
    ddm_is_primary=False,
    income_metric="net_income",
    da_metric="depreciation_amortization",
    addback_sbc=False,
    growth_model="multi_stage",
    model_warnings=[],
    sector_rules=get_sector_rules(""),
)


def get_industry_profile(sector: str) -> IndustryProfile:
    """
    Return the IndustryProfile for the given sector string.
    Falls back to a default general profile if not found.
    """
    if sector in PROFILES:
        return PROFILES[sector]

    # Try case-insensitive substring matching
    s = sector.lower()
    for key, profile in PROFILES.items():
        if key.lower() in s or s in key.lower():
            return profile

    return _DEFAULT_PROFILE
