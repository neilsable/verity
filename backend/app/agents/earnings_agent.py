"""
VERITY — Earnings Agent
Analyses earnings call transcripts (via SEC 8-K or scraped sources).
Scores management tone, hedge-word density, Q&A evasion.
Extracts forward guidance statements.
"""

import re

import structlog

from app.agents.base import BaseAgent
from app.models.schemas import AgentName, EarningsCallAnalysis, ResearchState, SentimentScore
from app.services.sec_edgar import get_recent_filings
from app.services.sec_edgar import fetch_filing_text

logger = structlog.get_logger(__name__)

# Hedge words: language that softens or qualifies statements
HEDGE_WORDS = {
    "approximately", "roughly", "about", "around", "estimate", "estimated",
    "expect", "expected", "anticipate", "anticipates", "believe", "believes",
    "may", "might", "could", "should", "potentially", "likely", "unlikely",
    "possibly", "perhaps", "uncertain", "uncertainty", "subject to", "depends",
    "if", "assuming", "provided that", "to the extent", "we think", "we feel",
}

SYSTEM_PROMPT = """You are an expert financial analyst specialising in earnings call analysis.
Analyse the provided earnings call transcript excerpt and extract:

1. KEY_THEMES: The 3-5 main topics management discussed
2. FORWARD_GUIDANCE: Exact quotes or paraphrases of any forward-looking statements
3. TONE_ASSESSMENT: Overall management tone (confident/cautious/defensive/evasive)
4. NOTABLE_QUOTES: 2-3 most significant statements from management
5. ANALYST_CONCERNS: Key concerns raised by analysts in Q&A

Format each section with its label on its own line, followed by bullet points.
Be factual and direct. Note any evasiveness or contradictions you observe."""


def _score_hedge_density(text: str) -> float:
    """Count hedge words per 100 words."""
    words = text.lower().split()
    if not words:
        return 0.0
    hedge_count = sum(1 for w in words if w.rstrip(".,;:") in HEDGE_WORDS)
    return round((hedge_count / len(words)) * 100, 2)


def _score_evasion(qa_text: str) -> float:
    """
    Simple Q&A evasion scorer.
    Detects patterns like: answering a different question, deflection phrases,
    excessive forward-looking disclaimers in response to direct questions.
    Score: 0.0 (fully direct) to 1.0 (highly evasive).
    """
    if not qa_text:
        return 0.0

    evasion_patterns = [
        r"we don't provide guidance on",
        r"we're not going to comment on",
        r"i'll let .* answer that",
        r"as i mentioned earlier",
        r"we feel good about",
        r"stay tuned",
        r"we'll cross that bridge",
        r"i think the important thing",
        r"what i can tell you is",
        r"at the end of the day",
    ]

    text_lower = qa_text.lower()
    hits = sum(1 for p in evasion_patterns if re.search(p, text_lower))
    score = min(1.0, hits / 5.0)
    return round(score, 3)


class EarningsAgent(BaseAgent):
    name = AgentName.EARNINGS

    async def run(self, state: ResearchState) -> ResearchState:
        ticker = state.ticker
        log = self.log.bind(ticker=ticker)

        # Fetch 8-K filings — earnings releases are filed as 8-K
        try:
            from app.models.schemas import FilingType
            filings = await get_recent_filings(
                ticker,
                filing_types=[FilingType.CURRENT_REPORT],
                max_per_type=3,
            )
        except Exception as e:
            log.warning("earnings_filing_fetch_failed", error=str(e))
            filings = []

        transcript_text = ""
        call_date = None

        # Try to get transcript from most recent 8-K
        for filing in filings:
            try:
                text = await fetch_filing_text(filing.document_url)
                # Check if this 8-K contains earnings call language
                if any(kw in text.lower() for kw in ["earnings call", "conference call", "q&a", "operator:"]):
                    transcript_text = text[:50_000]  # Cap to control tokens
                    call_date = filing.filing_date
                    log.info("earnings_transcript_found", date=str(call_date))
                    break
            except Exception as e:
                log.warning("earnings_fetch_failed", error=str(e))
                continue

        # If no transcript found, use a brief LLM analysis based on general knowledge
        if not transcript_text:
            log.info("earnings_no_transcript_using_general_analysis")
            prompt = f"""Provide a brief earnings analysis for {state.company_name or ticker} ({ticker}).
Research focus: {state.research_brief}

Based on publicly available information, describe:
1. Recent earnings performance trends
2. Management's typical forward guidance style
3. Key metrics analysts focus on for this company

Keep it factual and note that this is based on general knowledge, not a specific transcript."""
            analysis_text = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=800)

            return state.model_copy(update={
                "earnings_analysis": EarningsCallAnalysis(
                    ticker=ticker,
                    call_date=call_date or state.agent_outputs.get("orchestrator", {}).get("as_of", __import__("datetime").datetime.utcnow()),
                    quarter="Recent",
                    management_tone_score=0.0,
                    hedge_word_density=0.0,
                    evasion_score=0.0,
                    forward_guidance_statements=[],
                    key_topics=[],
                    sentiment=SentimentScore.NEUTRAL,
                    source_url=None,
                    raw_transcript_excerpt=None,
                ),
                "agent_outputs": {
                    **state.agent_outputs,
                    "earnings": {"summary": analysis_text, "transcript_found": False},
                },
            })

        # Score the transcript
        hedge_density = _score_hedge_density(transcript_text)

        # Find Q&A section
        qa_match = re.search(r"(Q&A|QUESTION|ANALYST|OPERATOR:)(.*)", transcript_text, re.DOTALL | re.IGNORECASE)
        qa_text = qa_match.group(2)[:10_000] if qa_match else ""
        evasion_score = _score_evasion(qa_text)

        # LLM analysis of the transcript
        prompt = f"""Company: {state.company_name or ticker} ({ticker})
Earnings call date: {call_date}
Research focus: {state.research_brief}

Transcript excerpt:
{transcript_text[:8_000]}

Analyse this earnings call transcript."""

        analysis_text = await self.llm(prompt, SYSTEM_PROMPT, state, max_tokens=1500)

        # Extract forward guidance statements
        guidance_statements: list[str] = []
        for line in analysis_text.splitlines():
            if any(kw in line.lower() for kw in ["expect", "guidance", "outlook", "anticipate", "forecast"]):
                clean = line.strip().lstrip("•-*123456789. ")
                if len(clean) > 20:
                    guidance_statements.append(clean)

        # Determine sentiment from hedge density and evasion
        if hedge_density > 8 or evasion_score > 0.6:
            tone_score = -0.3
            sentiment = SentimentScore.NEGATIVE
        elif hedge_density < 4 and evasion_score < 0.2:
            tone_score = 0.4
            sentiment = SentimentScore.POSITIVE
        else:
            tone_score = 0.0
            sentiment = SentimentScore.NEUTRAL

        from datetime import datetime
        analysis = EarningsCallAnalysis(
            ticker=ticker,
            call_date=call_date or datetime.utcnow(),
            quarter="Recent",
            management_tone_score=tone_score,
            hedge_word_density=hedge_density,
            evasion_score=evasion_score,
            forward_guidance_statements=guidance_statements[:10],
            key_topics=[],
            sentiment=sentiment,
            source_url=filings[0].document_url if filings else None,
            raw_transcript_excerpt=transcript_text[:500],
        )

        return state.model_copy(update={
            "earnings_analysis": analysis,
            "agent_outputs": {
                **state.agent_outputs,
                "earnings": {
                    "summary": analysis_text,
                    "transcript_found": True,
                    "hedge_density": hedge_density,
                    "evasion_score": evasion_score,
                    "guidance_count": len(guidance_statements),
                },
            },
        })


earnings_agent = EarningsAgent()


async def earnings_node(state: ResearchState) -> ResearchState:
    return await earnings_agent(state)
