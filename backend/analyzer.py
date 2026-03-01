"""
Analyzer — sends 10-K sections and earnings call transcript text to Claude
and returns a structured bull/bear investment analysis.

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""

import os
from dataclasses import dataclass
from typing import Optional

import anthropic
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

MODEL = "claude-sonnet-4-6"

# Tool schema used to force structured JSON output from Claude
_ANALYSIS_TOOL = {
    "name": "provide_investment_analysis",
    "description": (
        "Provide a structured bull/bear investment analysis based on a company's "
        "10-K filing, earnings call transcript, recent news, and social media sentiment."
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
            "recent_catalysts": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "2-4 recent events, news developments, or catalysts that could "
                    "materially impact the stock price in the near term. "
                    "Drawn from the news headlines and social media sentiment provided. "
                    "If no news or social data is available, return an empty array."
                ),
            },
            "sentiment_summary": {
                "type": "string",
                "description": (
                    "1-2 sentences describing the current market sentiment and narrative "
                    "around the stock based on recent news and social media. "
                    "Note any disconnect between market sentiment and fundamentals. "
                    "If no news or social data is available, return an empty string."
                ),
            },
            "analyst_summary": {
                "type": "string",
                "description": (
                    "A single concise paragraph (4–6 sentences) summarising "
                    "the overall investment picture, weighing the bull and bear "
                    "cases, recent catalysts, and market sentiment, and offering "
                    "an objective analyst perspective."
                ),
            },
        },
        "required": [
            "bull_case", "bear_case", "downplayed_risks",
            "recent_catalysts", "sentiment_summary", "analyst_summary",
        ],
    },
}


@dataclass
class AnalysisResult:
    ticker: str
    bull_case: list[str]
    bear_case: list[str]
    downplayed_risks: list[str]
    recent_catalysts: list[str]
    sentiment_summary: str
    analyst_summary: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "downplayed_risks": self.downplayed_risks,
            "recent_catalysts": self.recent_catalysts,
            "sentiment_summary": self.sentiment_summary,
            "analyst_summary": self.analyst_summary,
        }


def _build_prompt(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
    analyst_guidance: str = "",
    news_text: str = "",
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

    news_block = ""
    if news_text:
        # Cap news context to avoid blowing up the prompt
        news_snippet = news_text[:6_000]
        news_block = f"""--- RECENT NEWS & SOCIAL MEDIA ---
{news_snippet}

"""

    return f"""You are an experienced equity research analyst. Analyze the following
source materials for {ticker} and produce a rigorous investment analysis.

{sector_block}{news_block}--- 10-K EXCERPTS (MD&A + Risk Factors) ---
{tenk_snippet}

--- LATEST EARNINGS CALL TRANSCRIPT ---
{transcript_snippet}

Based on ALL the materials above (10-K, transcript, news, and social media), use the
`provide_investment_analysis` tool to return:
1. Three specific, evidence-backed bull case arguments
2. Three specific, evidence-backed bear case arguments
3. Key risks that management appears to be downplaying or omitting
4. Recent catalysts — 2-4 near-term events or developments from the news/social data
   that could materially impact the stock (leave empty if no news data was provided)
5. A 1-2 sentence sentiment summary describing the current market narrative and mood
   around the stock (leave empty if no news data was provided)
6. A balanced analyst summary paragraph that synthesizes fundamentals, recent
   developments, and market sentiment into an objective investment perspective

Ground bull/bear points in specific details from the 10-K and transcript.
Ground catalysts and sentiment in the news headlines and social posts.
If news or social data is not available, focus on the fundamental analysis."""


def analyze(
    ticker: str,
    tenk_text: str,
    transcript_text: str,
    sector: str = "",
    analyst_guidance: str = "",
    news_text: str = "",
) -> AnalysisResult:
    """
    Send 10-K, transcript, and news/social context to Claude and return a
    structured AnalysisResult with bull/bear arguments, catalysts, sentiment,
    downplayed risks, and a summary.

    Parameters
    ----------
    ticker:           Company ticker symbol (used for labelling only).
    tenk_text:        Combined MD&A + Risk Factors text from the 10-K.
    transcript_text:  Full earnings call transcript text.
    sector:           GICS sector label.
    analyst_guidance: Sector-specific focus areas.
    news_text:        Pre-formatted news headlines + social media posts.

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
    prompt = _build_prompt(
        ticker, tenk_text, transcript_text,
        sector, analyst_guidance, news_text,
    )

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
        recent_catalysts=data.get("recent_catalysts") or [],
        sentiment_summary=data.get("sentiment_summary") or "",
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

Use the `provide_industry_analysis` tool. You MUST populate ALL 10 fields listed
below — the tool call is invalid if any field is missing or empty.

REQUIRED FIELDS (all 10 must be present):

1. threat_of_new_entrants       — object with "rating" (Low/Medium/High) and "explanation" (2-3 sentences)
2. bargaining_power_of_suppliers — object with "rating" (Low/Medium/High) and "explanation" (2-3 sentences)
3. bargaining_power_of_buyers   — object with "rating" (Low/Medium/High) and "explanation" (2-3 sentences)
4. threat_of_substitutes        — object with "rating" (Low/Medium/High) and "explanation" (2-3 sentences)
5. competitive_rivalry          — object with "rating" (Low/Medium/High) and "explanation" (2-3 sentences)
6. industry_structure           — a PLAIN STRING (not an object, not nested JSON) of 2-3 paragraphs
                                   describing overall industry dynamics. Use "\\n\\n" between paragraphs.
7. competitive_position         — a PLAIN STRING describing where {ticker} sits vs competitors,
                                   its moats, and its key differentiators.
8. key_kpis                     — array of 3-5 objects, each with exactly two string fields:
                                     "metric"         (KPI name, e.g. "Net Revenue Retention")
                                     "why_it_matters" (1-2 sentence explanation)
9. tailwinds                    — array of EXACTLY 3 strings, each a macro/structural trend
                                   benefiting the industry
10. headwinds                   — array of EXACTLY 3 strings, each a macro/structural trend
                                   threatening the industry

EXAMPLE of the exact shape required (use real content, not these placeholders):
{{
  "threat_of_new_entrants":        {{"rating": "Low",    "explanation": "..."}},
  "bargaining_power_of_suppliers": {{"rating": "Medium", "explanation": "..."}},
  "bargaining_power_of_buyers":    {{"rating": "High",   "explanation": "..."}},
  "threat_of_substitutes":         {{"rating": "Low",    "explanation": "..."}},
  "competitive_rivalry":           {{"rating": "High",   "explanation": "..."}},
  "industry_structure":   "Paragraph one.\\n\\nParagraph two.\\n\\nParagraph three.",
  "competitive_position": "Single block of text describing competitive standing.",
  "key_kpis": [
    {{"metric": "Annual Recurring Revenue", "why_it_matters": "..."}},
    {{"metric": "Net Revenue Retention",    "why_it_matters": "..."}},
    {{"metric": "Customer Acquisition Cost","why_it_matters": "..."}}
  ],
  "tailwinds": ["Trend one.", "Trend two.", "Trend three."],
  "headwinds": ["Risk one.",  "Risk two.",  "Risk three."]
}}

Ground every point in specific details from the source documents above."""


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

    import json as _json
    print(f"[industry] Raw Claude response:\n{_json.dumps(d, indent=2)}")
    print(f"[industry] Keys found: {list(d.keys())}")

    # ── Defensive key resolution helpers ──────────────────────────────────────

    def _pick(candidates: list, default=None):
        """Return d[first matching key] or default."""
        for k in candidates:
            if k in d:
                return d[k]
        return default

    def _pick_nested(parent_candidates: list, child_candidates: list, default=None):
        """
        Try each parent key; if found, try each child key inside it.
        Useful for Porter forces that may be nested under 'porter_five_forces'.
        """
        for pk in parent_candidates:
            if pk in d and isinstance(d[pk], dict):
                for ck in child_candidates:
                    if ck in d[pk]:
                        return d[pk][ck]
        return default

    def _pf(top_keys: list, nested_keys: Optional[list] = None) -> PorterForce:
        """
        Resolve a Porter force object.  Tries the top-level keys first; if not
        found, falls back to looking inside a 'porter_five_forces' wrapper dict.
        """
        raw = _pick(top_keys)
        if raw is None and nested_keys:
            raw = _pick_nested(
                ["porter_five_forces", "porters_five_forces", "five_forces"],
                nested_keys,
            )
        if not isinstance(raw, dict):
            raw = {}
        rating = raw.get("rating") or raw.get("level") or raw.get("score") or "Medium"
        explanation = (
            raw.get("explanation")
            or raw.get("description")
            or raw.get("details")
            or raw.get("analysis")
            or ""
        )
        return PorterForce(rating=rating, explanation=explanation)

    def _parse_kpis(raw_list: list) -> list:
        """Normalise KPI item dicts regardless of key names used."""
        result = []
        for item in (raw_list or []):
            if not isinstance(item, dict):
                continue
            metric = (
                item.get("metric")
                or item.get("name")
                or item.get("kpi")
                or item.get("kpi_name")
                or item.get("indicator")
                or ""
            )
            why = (
                item.get("why_it_matters")
                or item.get("description")
                or item.get("importance")
                or item.get("rationale")
                or item.get("why")
                or item.get("reason")
                or ""
            )
            if metric:
                result.append(IndustryKPI(metric=metric, why_it_matters=why))
        return result

    # ── Resolve each field with fallback aliases ───────────────────────────────

    threat_new_entrants = _pf(
        ["threat_of_new_entrants", "new_entrants", "threat_new_entrants", "entrants"],
        ["threat_of_new_entrants", "new_entrants"],
    )
    supplier_power = _pf(
        ["bargaining_power_of_suppliers", "supplier_power", "suppliers",
         "bargaining_power_suppliers"],
        ["bargaining_power_of_suppliers", "supplier_power", "suppliers"],
    )
    buyer_power = _pf(
        ["bargaining_power_of_buyers", "buyer_power", "buyers",
         "bargaining_power_buyers", "customer_power"],
        ["bargaining_power_of_buyers", "buyer_power", "buyers"],
    )
    threat_subs = _pf(
        ["threat_of_substitutes", "substitutes", "threat_substitutes",
         "substitute_products"],
        ["threat_of_substitutes", "substitutes"],
    )
    rivalry = _pf(
        ["competitive_rivalry", "rivalry", "industry_rivalry",
         "rivalry_among_competitors"],
        ["competitive_rivalry", "rivalry"],
    )

    industry_structure_raw = _pick(
        ["industry_structure", "structure", "industry_overview",
         "market_structure", "overview"],
        default="",
    )
    # Claude occasionally returns a nested object instead of a plain string;
    # flatten it to text so the frontend always receives a string.
    if isinstance(industry_structure_raw, dict):
        import json as _json2
        industry_structure = " ".join(
            str(v) for v in industry_structure_raw.values() if v
        )
        print(f"[industry] WARNING: industry_structure was a dict, flattened to string")
    elif isinstance(industry_structure_raw, list):
        industry_structure = "\n\n".join(str(item) for item in industry_structure_raw if item)
        print(f"[industry] WARNING: industry_structure was a list, joined to string")
    else:
        industry_structure = industry_structure_raw

    competitive_position = _pick(
        ["competitive_position", "position", "company_position",
         "competitive_positioning", "competitive_standing"],
        default="",
    )

    raw_kpis = _pick(
        ["key_kpis", "kpis", "key_metrics", "industry_kpis",
         "metrics", "key_performance_indicators"],
        default=[],
    )

    tailwinds = _pick(
        ["tailwinds", "industry_tailwinds", "macro_tailwinds",
         "growth_drivers", "positive_trends"],
        default=[],
    )

    headwinds = _pick(
        ["headwinds", "industry_headwinds", "macro_headwinds",
         "risks", "negative_trends", "challenges"],
        default=[],
    )

    return IndustryAnalysisResult(
        ticker=ticker.upper(),
        threat_of_new_entrants=threat_new_entrants,
        bargaining_power_of_suppliers=supplier_power,
        bargaining_power_of_buyers=buyer_power,
        threat_of_substitutes=threat_subs,
        competitive_rivalry=rivalry,
        industry_structure=industry_structure,
        competitive_position=competitive_position if isinstance(competitive_position, str) else str(competitive_position),
        key_kpis=_parse_kpis(raw_kpis) if isinstance(raw_kpis, list) else [],
        tailwinds=[str(t) for t in tailwinds] if isinstance(tailwinds, list) else [],
        headwinds=[str(h) for h in headwinds] if isinstance(headwinds, list) else [],
    )
