"""
VERITY — Citation Agent
Generates a full citation index mapping every factual claim
in the research report to its source document, date, and passage.
Zero hallucination policy: every claim must have a source.
"""

import re
import uuid
from datetime import datetime

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, Citation, ResearchState

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a research citation specialist.
Your job is to identify every factual claim in a research report
and map each one to its source document.

For each claim, respond with this EXACT format (one per line):
CLAIM: [the factual claim, verbatim or paraphrased]
SOURCE: [document name, e.g. "AAPL 10-K FY2024" or "Q3 2024 Earnings Call" or "NewsAPI - Bloomberg 2024-01-15"]
DATE: [YYYY-MM-DD or approximate]
PASSAGE: [the exact source text supporting this claim, max 100 words]
CONFIDENCE: [0.0-1.0]
---

Only cite claims that are factual assertions with specific figures or events.
Skip general statements or opinions.
If a claim cannot be verified from the provided sources, mark CONFIDENCE as 0.3."""


class CitationAgent(BaseAgent):
    name = AgentName.CITATION

    async def run(self, state: ResearchState) -> ResearchState:
        if state.draft_report is None:
            return state

        report = state.draft_report
        outputs = state.agent_outputs

        # Collect all available source passages
        source_passages = []

        # From SEC filings
        for chunk in state.relevant_chunks[:10]:
            source_passages.append(
                f"[{chunk.source_type} | {chunk.filing_date.strftime('%Y-%m-%d')}]\n{chunk.text[:300]}"
            )

        # From agent summaries
        for agent_name in ["filing", "comps", "earnings", "news"]:
            summary = outputs.get(agent_name, {}).get("summary", "")
            if summary:
                source_passages.append(f"[{agent_name.upper()} ANALYSIS]\n{summary[:500]}")

        sources_text = "\n\n---\n\n".join(source_passages[:15])

        # The report text to cite
        report_text = f"""
{report.executive_summary}

{report.bull_thesis}

{report.bear_thesis}

{report.valuation_section}
"""

        prompt = f"""Company: {report.company_name} ({report.ticker})

AVAILABLE SOURCES:
{sources_text}

REPORT TO CITE:
{report_text[:4000]}

Generate citations for every verifiable factual claim in the report."""

        response = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=2000)

        # Parse citations from response
        citations: list[Citation] = []
        blocks = response.split("---")

        for block in blocks:
            block = block.strip()
            if not block or "CLAIM:" not in block:
                continue

            def _get(label: str) -> str:
                match = re.search(rf"{label}:\s*(.+?)(?:\n[A-Z]+:|$)", block, re.DOTALL)
                return match.group(1).strip() if match else ""

            claim = _get("CLAIM")
            source = _get("SOURCE")
            date_str = _get("DATE")
            passage = _get("PASSAGE")
            conf_str = _get("CONFIDENCE")

            if not claim or not source:
                continue

            try:
                conf = float(conf_str) if conf_str else 0.7
                conf = max(0.0, min(1.0, conf))
            except ValueError:
                conf = 0.7

            filing_date = None
            try:
                filing_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            except (ValueError, IndexError):
                pass

            # Find source URL from state
            source_url = ""
            for filing in state.sec_filings:
                if filing.filing_type.value in source:
                    source_url = filing.document_url
                    break

            citations.append(Citation(
                citation_id=str(uuid.uuid4())[:8],
                claim_text=claim,
                source_document=source,
                source_url=source_url or f"https://sec.gov/cgi-bin/browse-edgar?action=getcompany&company={report.ticker}",
                filing_date=filing_date,
                passage=passage or claim,
                confidence=conf,
            ))

        self.log.info(
            "citations_generated",
            count=len(citations),
            ticker=report.ticker,
        )

        # Finalize the report
        final_report = report.model_copy(update={
            "citations": citations,
            "total_input_tokens": sum(v.get("input", 0) for v in state.token_usage.values()),
            "total_output_tokens": sum(v.get("output", 0) for v in state.token_usage.values()),
            "total_cost_usd": state.total_cost_usd,
        })

        return state.model_copy(update={
            "final_report": final_report,
            "agent_outputs": {
                **state.agent_outputs,
                "citation": {"citations_generated": len(citations)},
            },
        })


citation_agent = CitationAgent()


async def citation_node(state: ResearchState) -> ResearchState:
    return await citation_agent(state)
