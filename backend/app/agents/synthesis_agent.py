"""
VERITY — Synthesis Agent
Takes all agent outputs and writes a structured, professional research note.
Sections: executive summary, bull thesis, bear thesis, key risks, valuation, conclusion.
"""

import uuid
from datetime import datetime

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, ResearchReport, ResearchState

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a senior equity research analyst at a top-tier investment bank.
Write a structured, professional equity research note based on the provided data.
Your writing should be clear, precise, and backed by the data provided.

Structure your response EXACTLY as follows (use these exact headers):

## EXECUTIVE SUMMARY
[2-3 paragraph overview of the investment case]

## BULL THESIS
[3-4 specific bull case arguments with supporting data]

## BEAR THESIS
[3-4 specific bear case arguments with supporting data]

## KEY RISKS
- [Risk 1]
- [Risk 2]
- [Risk 3]
- [Risk 4]
- [Risk 5]

## VALUATION
[2-3 paragraph valuation analysis with specific multiples and comparisons]

## CONCLUSION
[1 paragraph conclusion with overall view]

Rules:
- Every factual claim must reference the data provided
- Use specific numbers wherever available
- Do not invent figures or events not present in the data
- Be balanced — include both positives and negatives
- Professional tone throughout"""


def _extract_section(text: str, header: str, next_header: str | None = None) -> str:
    """Extract a section from the LLM response between two headers."""
    pattern = f"## {header}"
    start = text.find(pattern)
    if start == -1:
        return ""
    start = text.find("\n", start) + 1

    if next_header:
        end = text.find(f"## {next_header}", start)
        if end == -1:
            end = len(text)
    else:
        end = len(text)

    return text[start:end].strip()


def _extract_risks(risks_text: str) -> list[str]:
    """Extract bullet-pointed risks into a list."""
    risks = []
    for line in risks_text.splitlines():
        line = line.strip().lstrip("•-*").strip()
        if line and len(line) > 10:
            risks.append(line)
    return risks[:8]


class SynthesisAgent(BaseAgent):
    name = AgentName.SYNTHESIS

    async def run(self, state: ResearchState) -> ResearchState:
        ticker = state.ticker
        company_name = state.company_name or ticker
        outputs = state.agent_outputs

        # Assemble all agent outputs into a structured context
        filing_summary = outputs.get("filing", {}).get("summary", "No filing data available.")
        earnings_summary = outputs.get("earnings", {}).get("summary", "No earnings data available.")
        comps_summary = outputs.get("comps", {}).get("summary", "No comps data available.")
        news_summary = outputs.get("news", {}).get("summary", "No news data available.")

        # Format fundamentals if available
        fundamentals_text = ""
        if state.fundamentals:
            f = state.fundamentals
            fundamentals_text = f"""
Fundamentals:
- Market Cap: ${f.market_cap/1e9:.1f}B
- P/E: {f.pe_ratio or 'N/A'}x
- EV/EBITDA: {f.ev_ebitda or 'N/A'}x
- Gross Margin: {f'{f.gross_margin*100:.1f}%' if f.gross_margin else 'N/A'}
- Revenue Growth YoY: {f'{f.revenue_growth_yoy*100:.1f}%' if f.revenue_growth_yoy else 'N/A'}
- Net Margin: {f'{f.net_margin*100:.1f}%' if f.net_margin else 'N/A'}"""

        prompt = f"""RESEARCH SUBJECT: {company_name} ({ticker})
RESEARCH BRIEF: {state.research_brief}
{fundamentals_text}

--- SEC FILINGS ANALYSIS ---
{filing_summary}

--- EARNINGS CALL ANALYSIS ---
{earnings_summary}

--- PEER COMPARISON & VALUATION ---
{comps_summary}

--- NEWS & SENTIMENT ---
{news_summary}

Write a complete equity research note based on all of the above."""

        response = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=3000)

        # Parse sections from response
        executive_summary = _extract_section(response, "EXECUTIVE SUMMARY", "BULL THESIS")
        bull_thesis = _extract_section(response, "BULL THESIS", "BEAR THESIS")
        bear_thesis = _extract_section(response, "BEAR THESIS", "KEY RISKS")
        risks_text = _extract_section(response, "KEY RISKS", "VALUATION")
        valuation = _extract_section(response, "VALUATION", "CONCLUSION")
        conclusion = _extract_section(response, "CONCLUSION")

        key_risks = _extract_risks(risks_text)

        # Fallback: if parsing fails, use the full response
        if not executive_summary:
            executive_summary = response[:500]
        if not conclusion:
            conclusion = response[-300:]

        draft_report = ResearchReport(
            report_id=uuid.uuid4(),
            job_id=state.job_id,
            ticker=ticker,
            company_name=company_name,
            generated_at=datetime.utcnow(),
            executive_summary=executive_summary,
            bull_thesis=bull_thesis,
            bear_thesis=bear_thesis,
            key_risks=key_risks,
            valuation_section=valuation,
            conclusion=conclusion,
            fundamentals=state.fundamentals,
            peer_comparison=state.peer_comparison,
            earnings_analysis=state.earnings_analysis,
            total_input_tokens=sum(
                v.get("input", 0) for v in state.token_usage.values()
            ),
            total_output_tokens=sum(
                v.get("output", 0) for v in state.token_usage.values()
            ),
            total_cost_usd=state.total_cost_usd,
        )

        return state.model_copy(update={
            "draft_report": draft_report,
            "agent_outputs": {
                **state.agent_outputs,
                "synthesis": {"status": "complete", "sections_extracted": 6},
            },
        })


synthesis_agent = SynthesisAgent()


async def synthesis_node(state: ResearchState) -> ResearchState:
    return await synthesis_agent(state)
