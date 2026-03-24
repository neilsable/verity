"""
VERITY — Phase 3 Test Suite
Tests for all 8 agents. Every LLM call and external API call is mocked.
Agents must handle: empty data, LLM failures, malformed responses gracefully.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import (
    AgentName,
    CompanyFundamentals,
    DocumentChunk,
    EarningsCallAnalysis,
    NewsArticle,
    PeerComparisonTable,
    ResearchState,
    SECFiling,
    FilingType,
    SentimentScore,
)


def make_state(**kwargs) -> ResearchState:
    defaults = dict(
        job_id=uuid.uuid4(),
        ticker="AAPL",
        research_brief="Analyse Apple's AI strategy and services revenue growth.",
    )
    defaults.update(kwargs)
    return ResearchState(**defaults)


# =============================================================================
# Base Agent Tests
# =============================================================================


class TestBaseAgent:
    @pytest.mark.asyncio
    async def test_agent_records_error_in_state_on_failure(self) -> None:
        """If an agent fails, it should record the error in state and NOT raise."""
        from app.agents.orchestrator import OrchestratorAgent

        agent = OrchestratorAgent()
        state = make_state()

        with patch.object(agent, "run", new_callable=AsyncMock, side_effect=ValueError("LLM timeout")), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert "orchestrator" in result.errors
        assert "LLM timeout" in result.errors["orchestrator"]

    @pytest.mark.asyncio
    async def test_llm_falls_back_to_openai_on_anthropic_failure(self) -> None:
        """When Anthropic fails, the fallback to OpenAI should work."""
        from app.agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        state = make_state()

        with patch.object(agent, "_call_anthropic", new_callable=AsyncMock, side_effect=Exception("Anthropic down")), \
             patch.object(agent, "_call_openai", new_callable=AsyncMock, return_value="COMPANY_NAME: Apple Inc.\nSECTOR: Technology\nKEY_QUESTIONS:\n1. Revenue growth?"), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        # Should succeed via fallback
        assert result.company_name is not None

    @pytest.mark.asyncio
    async def test_token_tracking_accumulates(self) -> None:
        from app.agents.base import BaseAgent
        from app.models.schemas import AgentName

        class DummyAgent(BaseAgent):
            name = AgentName.ORCHESTRATOR
            async def run(self, state): return state

        agent = DummyAgent()
        state = make_state()
        agent._track_tokens(state, "claude-sonnet-4-20250514", 1000, 500, 0.01)
        agent._track_tokens(state, "claude-sonnet-4-20250514", 500, 250, 0.005)

        assert state.token_usage["orchestrator"]["input"] == 1500
        assert state.token_usage["orchestrator"]["output"] == 750
        assert round(state.total_cost_usd, 4) == 0.015


# =============================================================================
# Orchestrator Agent Tests
# =============================================================================


class TestOrchestratorAgent:
    @pytest.mark.asyncio
    async def test_parses_company_name(self) -> None:
        from app.agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        state = make_state()

        mock_response = (
            "COMPANY_NAME: Apple Inc.\n"
            "SECTOR: Technology\n"
            "KEY_QUESTIONS:\n"
            "1. How is AI contributing to revenue?\n"
            "2. What is the services growth trajectory?\n"
            "3. How do margins compare to peers?\n"
        )

        with patch.object(agent, "llm", new_callable=AsyncMock, return_value=mock_response), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.company_name == "Apple Inc."
        assert "orchestrator" in result.agent_outputs
        assert len(result.agent_outputs["orchestrator"]["key_questions"]) == 3

    @pytest.mark.asyncio
    async def test_falls_back_to_ticker_if_parse_fails(self) -> None:
        from app.agents.orchestrator import OrchestratorAgent
        agent = OrchestratorAgent()
        state = make_state(ticker="NVDA")

        with patch.object(agent, "llm", new_callable=AsyncMock, return_value="Malformed response with no headers"), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        # company_name should fall back to ticker
        assert result.company_name == "NVDA"


# =============================================================================
# Filing Agent Tests
# =============================================================================


class TestFilingAgent:
    @pytest.mark.asyncio
    async def test_handles_no_filings_gracefully(self) -> None:
        from app.agents.filing_agent import FilingAgent
        agent = FilingAgent()
        state = make_state()

        with patch("app.agents.filing_agent.get_recent_filings", new_callable=AsyncMock, return_value=[]), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.agent_outputs["filing"]["chunks_indexed"] == 0

    @pytest.mark.asyncio
    async def test_chunks_and_indexes_filings(self) -> None:
        from app.agents.filing_agent import FilingAgent
        agent = FilingAgent()
        state = make_state()

        mock_filing = SECFiling(
            ticker="AAPL", cik="0000320193",
            filing_type=FilingType.ANNUAL_REPORT,
            filing_date=datetime(2024, 10, 1),
            accession_number="0000320193-24-000123",
            document_url="https://sec.gov/test",
        )
        mock_chunk = DocumentChunk(
            chunk_id="test_chunk_1", document_id="doc1", ticker="AAPL",
            source_type="10-K", source_url="https://sec.gov/test",
            filing_date=datetime(2024, 10, 1), chunk_index=0,
            text="Apple reported revenue of $383B in fiscal 2024.", token_count=50,
        )

        with patch("app.agents.filing_agent.get_recent_filings", new_callable=AsyncMock, return_value=[mock_filing]), \
             patch("app.agents.filing_agent.fetch_filing_text", new_callable=AsyncMock, return_value="Apple reported revenue of $383B in fiscal 2024. " * 50), \
             patch("app.agents.filing_agent.chunk_document", return_value=[mock_chunk]), \
             patch("app.agents.filing_agent.embed_chunks", new_callable=AsyncMock, return_value=([], {"chunks_embedded": 1, "cost_usd": 0.001})), \
             patch("app.agents.filing_agent.upsert_chunks", new_callable=AsyncMock), \
             patch("app.agents.filing_agent.query_similar", new_callable=AsyncMock, return_value=[mock_chunk]), \
             patch.object(agent, "llm", new_callable=AsyncMock, return_value="Strong revenue growth driven by services."), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.agent_outputs["filing"]["filings_processed"] == 1
        assert len(result.relevant_chunks) == 1


# =============================================================================
# Comps Agent Tests
# =============================================================================


class TestCompsAgent:
    @pytest.mark.asyncio
    async def test_builds_peer_comparison(self) -> None:
        from app.agents.comps_agent import CompsAgent
        agent = CompsAgent()
        state = make_state()

        mock_subject = CompanyFundamentals(
            ticker="AAPL", company_name="Apple Inc.",
            pe_ratio=28.5, ev_ebitda=20.1, gross_margin=0.44,
            market_cap=3_000_000_000_000,
        )
        mock_peer = CompanyFundamentals(ticker="MSFT", company_name="Microsoft", pe_ratio=32.0)
        mock_table = PeerComparisonTable(subject_ticker="AAPL", peers=[mock_peer])

        with patch("app.agents.comps_agent.get_fundamentals", new_callable=AsyncMock, return_value=mock_subject), \
             patch("app.agents.comps_agent.get_peer_comparison", new_callable=AsyncMock, return_value=mock_table), \
             patch.object(agent, "llm", new_callable=AsyncMock, return_value="AAPL trades at a discount to MSFT on P/E."), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.fundamentals.ticker == "AAPL"
        assert result.peer_comparison.subject_ticker == "AAPL"
        assert result.agent_outputs["comps"]["peers_analysed"] == 1


# =============================================================================
# News Agent Tests
# =============================================================================


class TestNewsAgent:
    @pytest.mark.asyncio
    async def test_handles_no_news(self) -> None:
        from app.agents.news_agent import NewsAgent
        agent = NewsAgent()
        state = make_state()

        with patch("app.agents.news_agent.get_news", new_callable=AsyncMock, return_value=[]), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.agent_outputs["news"]["articles"] == 0

    @pytest.mark.asyncio
    async def test_processes_news_articles(self) -> None:
        from app.agents.news_agent import NewsAgent
        agent = NewsAgent()
        state = make_state()

        mock_articles = [
            NewsArticle(
                article_id="abc123", ticker="AAPL",
                title="Apple beats Q4 earnings estimates",
                url="https://bloomberg.com/test",
                published_at=datetime.now(timezone.utc),
                source_name="Bloomberg",
                sentiment_score=0.6,
                temporal_weight=0.95,
                is_material=True,
                materiality_reason="Contains earnings keyword",
            )
        ]

        with patch("app.agents.news_agent.get_news", new_callable=AsyncMock, return_value=mock_articles), \
             patch.object(agent, "llm", new_callable=AsyncMock, return_value="Positive news sentiment. Earnings beat drives bullish tone."), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.agent_outputs["news"]["articles"] == 1
        assert result.agent_outputs["news"]["material_events"] == 1


# =============================================================================
# Synthesis Agent Tests
# =============================================================================


class TestSynthesisAgent:
    @pytest.mark.asyncio
    async def test_creates_draft_report(self) -> None:
        from app.agents.synthesis_agent import SynthesisAgent
        agent = SynthesisAgent()
        state = make_state(
            company_name="Apple Inc.",
            agent_outputs={
                "filing": {"summary": "Strong revenue from services."},
                "comps": {"summary": "Trades at slight premium to peers."},
                "earnings": {"summary": "Management tone confident."},
                "news": {"summary": "Positive sentiment."},
            }
        )

        mock_response = """## EXECUTIVE SUMMARY
Apple Inc. continues to demonstrate strong financial performance.

## BULL THESIS
Services revenue growing at 15% YoY.

## BEAR THESIS
Hardware growth slowing in China.

## KEY RISKS
- Regulatory pressure in EU
- China revenue uncertainty
- Competition from Samsung

## VALUATION
Trading at 28x P/E vs peers at 30x.

## CONCLUSION
Overall positive outlook with manageable risks."""

        with patch.object(agent, "llm", new_callable=AsyncMock, return_value=mock_response), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.draft_report is not None
        assert result.draft_report.ticker == "AAPL"
        assert "Services revenue" in result.draft_report.bull_thesis
        assert len(result.draft_report.key_risks) >= 2

    @pytest.mark.asyncio
    async def test_handles_malformed_llm_response(self) -> None:
        from app.agents.synthesis_agent import SynthesisAgent
        agent = SynthesisAgent()
        state = make_state(agent_outputs={})

        with patch.object(agent, "llm", new_callable=AsyncMock, return_value="This is a plain response without headers."), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        # Should still create a report, just with fallback content
        assert result.draft_report is not None


# =============================================================================
# Critique Agent Tests
# =============================================================================


class TestCritiqueAgent:
    @pytest.mark.asyncio
    async def test_parses_confidence_score(self) -> None:
        from app.agents.critique_agent import CritiqueAgent
        from app.models.schemas import ResearchReport
        agent = CritiqueAgent()

        mock_report = ResearchReport(
            job_id=uuid.uuid4(), ticker="AAPL", company_name="Apple Inc.",
            executive_summary="Apple grew revenue 8% YoY.",
            bull_thesis="Services up 15%.", bear_thesis="Hardware slowing.",
            key_risks=["China risk"], valuation_section="28x P/E.",
            conclusion="Buy.",
        )
        state = make_state(draft_report=mock_report, agent_outputs={
            "filing": {"summary": "Revenue grew 8% YoY per 10-K."},
        })

        mock_critique = """CONFIDENCE_SCORE: 0.88

UNSUPPORTED_CLAIMS:
- Services grew 20% | REASON: Source data shows 15%, not 20%

CONTRADICTED_CLAIMS:

LOW_CONFIDENCE_SECTIONS:

OVERALL_ASSESSMENT:
Report is well-supported with minor discrepancy in services growth figure."""

        with patch.object(agent, "llm", new_callable=AsyncMock, return_value=mock_critique), \
             patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert result.draft_report.overall_confidence == pytest.approx(0.88)
        assert len(result.draft_report.critique_flags) == 1

    @pytest.mark.asyncio
    async def test_handles_missing_draft_report(self) -> None:
        from app.agents.critique_agent import CritiqueAgent
        agent = CritiqueAgent()
        state = make_state(draft_report=None)

        with patch.object(agent, "_publish_progress", new_callable=AsyncMock):
            result = await agent(state)

        assert "critique" in result.errors
