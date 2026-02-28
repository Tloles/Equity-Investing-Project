"""
Analyzer — sends 10-K sections and earnings call transcript text to Claude
and returns a structured bull/bear investment analysis.

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass

import anthropic
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

MODEL = "claude-sonnet-4-6"

# Tool schema used to force structured JSON output from Claude
_ANALYSIS_TOOL = {
    "name": "provide_investment_analysis",
    "description": (
        "Provide a structured bull/bear investment analysis based on a company's "
        "10-K filing and latest earnings call transcript."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "bull_case": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Exactly 3 distinct bull case arguments supporting "
                    "a positive investment thesis."
                ),
            },
            "bear_case": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Exactly 3 distinct bear case arguments representing "
                    "key risks and headwinds."
                ),
            },
            "downplayed_risks": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Key risks or challenges that management appears to be "
                    "understating, glossing over, or omitting in their communications."
                ),
            },
            "analyst_summary": {
                "type": "string",
                "description": (
                    "A single concise paragraph (3–5 sentences) summarising "
                    "the overall investment picture, weighing the bull and bear "
                    "cases and offering an objective analyst perspective."
                ),
            },
        },
        "required": ["bull_case", "bear_case", "downplayed_risks", "analyst_summary"],
    },
}


@dataclass
class AnalysisResult:
    ticker: str
    bull_case: list[str]
    bear_case: list[str]
    downplayed_risks: list[str]
    analyst_summary: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "downplayed_risks": self.downplayed_risks,
            "analyst_summary": self.analyst_summary,
        }


def _build_prompt(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
    analyst_guidance: str = "",
) -> str:
    tenk_snippet = tenk_text[:12_000] if tenk_text else "(not available)"
    transcript_snippet = transcript_text[:8_000] if transcript_text else "(not available)"

    sector_block = ""
    if sector:
        sector_block = f"""--- COMPANY SECTOR ---
Sector: {sector}
Sector-specific analyst focus areas:
{analyst_guidance}

"""

    return f"""You are an experienced equity research analyst. Analyze the following
source materials for {ticker} and produce a rigorous investment analysis.

{sector_block}--- 10-K EXCERPTS (MD&A + Risk Factors) ---
{tenk_snippet}

--- LATEST EARNINGS CALL TRANSCRIPT ---
{transcript_snippet}

Based solely on these materials, use the `provide_investment_analysis` tool to return:
1. Three specific, evidence-backed bull case arguments
2. Three specific, evidence-backed bear case arguments
3. Key risks that management appears to be downplaying or omitting
4. A balanced one-paragraph analyst summary

Ground every point in specific details from the documents above."""


def analyze(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
    analyst_guidance: str = "",
) -> AnalysisResult:
    """
    Send 10-K and transcript text to Claude and return a structured
    AnalysisResult with bull/bear arguments, downplayed risks, and a summary.

    Parameters
    ----------
    ticker:           Company ticker symbol (used for labelling only).
    tenk_text:        Combined MD&A + Risk Factors text from the 10-K.
    transcript_text:  Full earnings call transcript text.

    Returns
    -------
    AnalysisResult dataclass instance.

    Raises
    ------
    EnvironmentError  if ANTHROPIC_API_KEY is not set.
    ValueError        if Claude does not return the expected tool call.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(ticker, tenk_text, transcript_text)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[_ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "provide_investment_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the tool_use block from the response
    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError("Claude did not return an analysis tool call.")

    data = tool_use_block.input

    return AnalysisResult(
        ticker=ticker.upper(),
        bull_case=data["bull_case"],
        bear_case=data["bear_case"],
        downplayed_risks=data["downplayed_risks"],
        analyst_summary=data["analyst_summary"],
    )


# ── Industry analysis ──────────────────────────────────────────────────────────


def _porter_force_schema(name: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "rating": {
                "type": "string",
                "enum": ["Low", "Medium", "High"],
                "description": f"Competitive intensity rating for {name}.",
            },
            "explanation": {
                "type": "string",
                "description": (
                    f"2-3 sentences explaining the {name} rating, "
                    "grounded in specific evidence from the source documents."
                ),
            },
        },
        "required": ["rating", "explanation"],
    }


_INDUSTRY_TOOL = {
    "name": "provide_industry_analysis",
    "description": (
        "Provide a structured industry analysis including Porter's Five Forces, "
        "competitive position, key KPIs, and macro tailwinds/headwinds."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "threat_of_new_entrants":        _porter_force_schema("Threat of New Entrants"),
            "bargaining_power_of_suppliers": _porter_force_schema("Bargaining Power of Suppliers"),
            "bargaining_power_of_buyers":    _porter_force_schema("Bargaining Power of Buyers"),
            "threat_of_substitutes":         _porter_force_schema("Threat of Substitutes"),
            "competitive_rivalry":           _porter_force_schema("Competitive Rivalry"),
            "industry_structure": {
                "type": "string",
                "description": (
                    "2-3 paragraph overview of the overall industry dynamics, "
                    "competitive structure, and key forces at play."
                ),
            },
            "competitive_position": {
                "type": "string",
                "description": (
                    "Where this company sits relative to competitors: its moats, "
                    "differentiation, and relative strengths/weaknesses."
                ),
            },
            "key_kpis": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "description": "KPI name, e.g. 'Net Revenue Retention'.",
                        },
                        "why_it_matters": {
                            "type": "string",
                            "description": (
                                "1-2 sentences explaining why this metric is critical "
                                "for this specific industry."
                            ),
                        },
                    },
                    "required": ["metric", "why_it_matters"],
                },
                "description": "The 3-5 most important KPIs to track for this industry/sector.",
            },
            "tailwinds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 macro or structural trends benefiting the industry.",
            },
            "headwinds": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Exactly 3 macro or structural trends threatening the industry.",
            },
        },
        "required": [
            "threat_of_new_entrants", "bargaining_power_of_suppliers",
            "bargaining_power_of_buyers", "threat_of_substitutes",
            "competitive_rivalry", "industry_structure", "competitive_position",
            "key_kpis", "tailwinds", "headwinds",
        ],
    },
}


@dataclass
class PorterForce:
    rating: str       # "Low", "Medium", or "High"
    explanation: str


@dataclass
class IndustryKPI:
    metric: str
    why_it_matters: str


@dataclass
class IndustryAnalysisResult:
    ticker: str
    threat_of_new_entrants: PorterForce
    bargaining_power_of_suppliers: PorterForce
    bargaining_power_of_buyers: PorterForce
    threat_of_substitutes: PorterForce
    competitive_rivalry: PorterForce
    industry_structure: str
    competitive_position: str
    key_kpis: list
    tailwinds: list
    headwinds: list


def _build_industry_prompt(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
) -> str:
    tenk_snippet       = tenk_text[:12_000]       if tenk_text       else "(not available)"
    transcript_snippet = transcript_text[:8_000]   if transcript_text else "(not available)"

    sector_line = f"Sector: {sector}\n\n" if sector else ""

    return f"""You are an experienced industry analyst. Analyze the following source
materials for {ticker} and produce a rigorous industry analysis.

{sector_line}--- 10-K EXCERPTS (MD&A + Risk Factors) ---
{tenk_snippet}

--- LATEST EARNINGS CALL TRANSCRIPT ---
{transcript_snippet}

Based solely on these materials, use the `provide_industry_analysis` tool to return:
1. Porter's Five Forces — rate each force (Low/Medium/High) with a 2-3 sentence
   evidence-backed explanation drawn from the documents.
2. Industry Structure — 2-3 paragraphs on overall industry dynamics.
3. Competitive Position — where {ticker} sits vs peers; its moats and differentiators.
4. Key Industry KPIs — 3-5 metrics most critical to monitor for this sector.
5. Industry Tailwinds — exactly 3 macro or structural trends benefiting the industry.
6. Industry Headwinds — exactly 3 macro or structural trends threatening the industry.

Ground every point in specific details from the documents above."""


def analyze_industry(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
) -> "IndustryAnalysisResult":
    """
    Send 10-K and transcript text to Claude and return a structured
    IndustryAnalysisResult covering Porter's Five Forces, industry structure,
    competitive position, key KPIs, tailwinds, and headwinds.

    Raises
    ------
    EnvironmentError  if ANTHROPIC_API_KEY is not set.
    ValueError        if Claude does not return the expected tool call.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env file."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_industry_prompt(ticker, tenk_text, transcript_text, sector)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        tools=[_INDUSTRY_TOOL],
        tool_choice={"type": "tool", "name": "provide_industry_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError("Claude did not return an industry analysis tool call.")

    d = tool_use_block.input

    def _pf(key: str) -> PorterForce:
        return PorterForce(
            rating=d[key]["rating"],
            explanation=d[key]["explanation"],
        )

    return IndustryAnalysisResult(
        ticker=ticker.upper(),
        threat_of_new_entrants=_pf("threat_of_new_entrants"),
        bargaining_power_of_suppliers=_pf("bargaining_power_of_suppliers"),
        bargaining_power_of_buyers=_pf("bargaining_power_of_buyers"),
        threat_of_substitutes=_pf("threat_of_substitutes"),
        competitive_rivalry=_pf("competitive_rivalry"),
        industry_structure=d["industry_structure"],
        competitive_position=d["competitive_position"],
        key_kpis=[
            IndustryKPI(metric=k["metric"], why_it_matters=k["why_it_matters"])
            for k in d["key_kpis"]
        ],
        tailwinds=d["tailwinds"],
        headwinds=d["headwinds"],
    )
