"""
Analyzer — sends 10-K sections and earnings call transcript text to Claude
and returns a structured bull/bear investment analysis.

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""

import os
import json
from dataclasses import dataclass

import anthropic
from dotenv import load_dotenv

load_dotenv()

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
