"""
VERITY — Critique Agent
Red-teams the synthesis output.
Verifies every factual claim against source documents.
Assigns confidence scores and flags unsupported claims.
"""

import re
import uuid

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, CritiqueFlag, ResearchState

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a rigorous fact-checker and research quality analyst.
You have been given a draft equity research note and the underlying source data.
Your job is to:
1. Identify any factual claims that are NOT supported by the provided source data
2. Flag any figures that appear incorrect or inconsistent
3. Note any one-sided analysis that ignores contradictory evidence
4. Assign an overall confidence score from 0.0 to 1.0

Respond in this EXACT format:

CONFIDENCE_SCORE: [0.0-1.0]

UNSUPPORTED_CLAIMS:
- [claim text] | REASON: [why it's unsupported]

CONTRADICTED_CLAIMS:
- [claim text] | CORRECTION: [what the data actually shows]

LOW_CONFIDENCE_SECTIONS:
- [section name] | REASON: [why confidence is low]

OVERALL_ASSESSMENT:
[1-2 sentences on overall report quality]"""


class CritiqueAgent(BaseAgent):
    name = AgentName.CRITIQUE

    async def run(self, state: ResearchState) -> ResearchState:
        if state.draft_report is None:
            return state.model_copy(update={
                "errors": {**state.errors, "critique": "No draft report to critique"},
            })

        report = state.draft_report
        outputs = state.agent_outputs

        # Compile source data for verification
        source_context = f"""
VERIFIED SOURCE DATA:
SEC Filings Analysis: {outputs.get('filing', {}).get('summary', 'N/A')[:2000]}
Comps Analysis: {outputs.get('comps', {}).get('summary', 'N/A')[:1000]}
News Analysis: {outputs.get('news', {}).get('summary', 'N/A')[:1000]}
Earnings Analysis: {outputs.get('earnings', {}).get('summary', 'N/A')[:1000]}
"""

        report_text = f"""
DRAFT REPORT TO CRITIQUE:

EXECUTIVE SUMMARY:
{report.executive_summary}

BULL THESIS:
{report.bull_thesis}

BEAR THESIS:
{report.bear_thesis}

VALUATION:
{report.valuation_section}
"""

        prompt = f"""Company: {report.company_name} ({report.ticker})

{source_context}

{report_text}

Review the draft report against the source data and identify any issues."""

        response = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=1500)

        # Parse confidence score
        confidence = 0.75  # default
        conf_match = re.search(r"CONFIDENCE_SCORE:\s*([\d.]+)", response)
        if conf_match:
            try:
                confidence = max(0.0, min(1.0, float(conf_match.group(1))))
            except ValueError:
                pass

        # Parse flags
        flags: list[CritiqueFlag] = []

        def _parse_flags(section_header: str, flag_type: str) -> None:
            section_match = re.search(
                rf"{section_header}:\n(.*?)(?:\n[A-Z_]+:|$)",
                response,
                re.DOTALL,
            )
            if not section_match:
                return
            section_text = section_match.group(1)
            for line in section_text.splitlines():
                line = line.strip().lstrip("•-* ")
                if "|" in line and len(line) > 10:
                    parts = line.split("|", 1)
                    claim = parts[0].strip()
                    reason = parts[1].strip().replace("REASON:", "").replace("CORRECTION:", "").strip()
                    if claim:
                        flags.append(CritiqueFlag(
                            flag_id=str(uuid.uuid4())[:8],
                            claim_text=claim,
                            flag_type=flag_type,
                            explanation=reason,
                            confidence=confidence,
                        ))

        _parse_flags("UNSUPPORTED_CLAIMS", "unsupported")
        _parse_flags("CONTRADICTED_CLAIMS", "contradicted")
        _parse_flags("LOW_CONFIDENCE_SECTIONS", "low_confidence")

        # Update the draft report with critique results
        updated_report = report.model_copy(update={
            "critique_flags": flags,
            "overall_confidence": confidence,
        })

        self.log.info(
            "critique_complete",
            confidence=confidence,
            flags=len(flags),
            ticker=report.ticker,
        )

        return state.model_copy(update={
            "draft_report": updated_report,
            "agent_outputs": {
                **state.agent_outputs,
                "critique": {
                    "confidence": confidence,
                    "flags": len(flags),
                    "assessment": response[-300:],
                },
            },
        })


critique_agent = CritiqueAgent()


async def critique_node(state: ResearchState) -> ResearchState:
    return await critique_agent(state)
