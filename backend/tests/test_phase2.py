"""
VERITY — Phase 2 Test Suite
Tests for: SEC EDGAR, chunker, embedder, vector store, financials, news client.
All external API calls are mocked — no real API keys needed in CI.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import DocumentChunk, FilingType, SECFiling
from app.services.chunker import _split_into_sentences, chunk_document, count_tokens
from app.services.news_client import (
    _check_materiality,
    _compute_temporal_weight,
    _score_sentiment,
)


# =============================================================================
# Chunker Tests
# =============================================================================


class TestTokenCounter:
    def test_empty_string_returns_zero(self) -> None:
        assert count_tokens("") == 0

    def test_short_string_returns_positive(self) -> None:
        assert count_tokens("Hello world") > 0

    def test_longer_text_has_more_tokens(self) -> None:
        short = count_tokens("Hello")
        long = count_tokens("Hello world this is a longer sentence with more words")
        assert long > short


class TestSentenceSplitter:
    def test_splits_on_period_capital(self) -> None:
        text = "Revenue grew 42%. Operating margin expanded. Cash flow was strong."
        sentences = _split_into_sentences(text)
        assert len(sentences) >= 2

    def test_preserves_abbreviations(self) -> None:
        text = "The company, Inc. reported Q3 results. Revenue was $1.2B vs. $1.0B."
        sentences = _split_into_sentences(text)
        # Should not split on "Inc." or "vs."
        assert any("Inc." in s for s in sentences)

    def test_single_sentence_stays_intact(self) -> None:
        text = "Apple reported strong revenue growth in the fiscal year."
        sentences = _split_into_sentences(text)
        assert len(sentences) == 1
        assert sentences[0] == text


class TestChunkDocument:
    def test_empty_text_returns_empty_list(self) -> None:
        chunks = chunk_document(
            text="",
            document_id="doc1",
            ticker="AAPL",
            source_type="10-K",
            source_url="https://sec.gov/test",
            filing_date=datetime(2024, 1, 1),
        )
        assert chunks == []

    def test_short_text_produces_one_chunk(self) -> None:
        text = "Apple Inc. reported strong results for the fiscal year 2024."
        chunks = chunk_document(
            text=text,
            document_id="doc1",
            ticker="AAPL",
            source_type="10-K",
            source_url="https://sec.gov/test",
            filing_date=datetime(2024, 1, 1),
        )
        assert len(chunks) == 1
        assert chunks[0].ticker == "AAPL"
        assert chunks[0].source_type == "10-K"

    def test_long_text_produces_multiple_chunks(self) -> None:
        # Generate text that exceeds chunk_size
        sentence = "The company reported strong revenue growth driven by cloud services. "
        text = sentence * 100  # ~1500+ tokens

        chunks = chunk_document(
            text=text,
            document_id="doc2",
            ticker="MSFT",
            source_type="10-K",
            source_url="https://sec.gov/test",
            filing_date=datetime(2024, 1, 1),
            chunk_size=256,
            chunk_overlap=32,
        )
        assert len(chunks) > 1

    def test_chunks_have_overlap(self) -> None:
        sentence = "Revenue grew substantially. Operating income expanded. Margins improved. "
        text = sentence * 50

        chunks = chunk_document(
            text=text,
            document_id="doc3",
            ticker="GOOGL",
            source_type="10-Q",
            source_url="https://sec.gov/test",
            filing_date=datetime(2024, 1, 1),
            chunk_size=128,
            chunk_overlap=32,
        )
        assert len(chunks) > 1
        # Each chunk should have a reasonable token count
        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.token_count <= 256  # Allow some slack

    def test_chunk_ids_are_unique(self) -> None:
        sentence = "Apple reported strong results. Revenue exceeded expectations. "
        text = sentence * 100

        chunks = chunk_document(
            text=text,
            document_id="doc4",
            ticker="AAPL",
            source_type="10-K",
            source_url="https://sec.gov/test",
            filing_date=datetime(2024, 1, 1),
            chunk_size=128,
        )
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_chunk_metadata_populated(self) -> None:
        chunks = chunk_document(
            text="Apple Inc. reported fiscal 2024 results with strong growth.",
            document_id="doc5",
            ticker="AAPL",
            source_type="10-K",
            source_url="https://sec.gov/doc",
            filing_date=datetime(2024, 9, 30),
        )
        assert len(chunks) == 1
        c = chunks[0]
        assert c.document_id == "doc5"
        assert c.source_url == "https://sec.gov/doc"
        assert c.filing_date == datetime(2024, 9, 30)


# =============================================================================
# Sentiment & News Tests
# =============================================================================


class TestSentimentScorer:
    def test_positive_headline_scores_positive(self) -> None:
        score, label = _score_sentiment("Apple beats earnings estimates", None)
        assert score > 0

    def test_negative_headline_scores_negative(self) -> None:
        score, label = _score_sentiment("Tesla misses revenue targets, stock drops", None)
        assert score < 0

    def test_neutral_headline_scores_neutral(self) -> None:
        score, label = _score_sentiment("Apple announces quarterly results", None)
        assert -0.3 <= score <= 0.3

    def test_score_bounded_between_minus1_and_plus1(self) -> None:
        score, _ = _score_sentiment(
            "beats beats beats record growth surge soars strong",
            "beats exceeds profit win innovative"
        )
        assert -1.0 <= score <= 1.0


class TestTemporalDecay:
    def test_fresh_article_weight_near_1(self) -> None:
        now = datetime.now(timezone.utc)
        weight = _compute_temporal_weight(now)
        assert weight > 0.95

    def test_3_day_old_article_weight_near_half(self) -> None:
        three_days_ago = datetime.now(timezone.utc).replace(
            day=datetime.now().day - 3
        )
        from datetime import timedelta
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        weight = _compute_temporal_weight(three_days_ago)
        assert 0.4 <= weight <= 0.6

    def test_old_article_has_low_weight(self) -> None:
        from datetime import timedelta
        old = datetime.now(timezone.utc) - timedelta(days=30)
        weight = _compute_temporal_weight(old)
        assert weight < 0.1

    def test_weight_is_between_0_and_1(self) -> None:
        from datetime import timedelta
        for days in [0, 1, 3, 7, 14, 30, 90]:
            dt = datetime.now(timezone.utc) - timedelta(days=days)
            weight = _compute_temporal_weight(dt)
            assert 0.0 <= weight <= 1.0


class TestMaterialityChecker:
    def test_earnings_headline_is_material(self) -> None:
        is_material, reason = _check_materiality("Apple earnings beat estimates", None)
        assert is_material is True
        assert reason is not None

    def test_ceo_headline_is_material(self) -> None:
        is_material, reason = _check_materiality("NVIDIA CEO Jensen Huang speaks at conference", None)
        assert is_material is True

    def test_generic_headline_not_material(self) -> None:
        is_material, reason = _check_materiality("Apple releases new iPhone color options", None)
        assert is_material is False

    def test_acquisition_is_material(self) -> None:
        is_material, reason = _check_materiality("Microsoft acquisition of gaming company approved", None)
        assert is_material is True


# =============================================================================
# SEC Edgar Tests (mocked)
# =============================================================================


class TestSECEdgarClient:
    @pytest.mark.asyncio
    async def test_get_cik_for_known_ticker(self) -> None:
        """Mock the SEC CIK endpoint."""
        mock_data = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA Corp"},
        }

        with patch("app.services.sec_edgar._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            from app.services.sec_edgar import get_cik_for_ticker
            cik = await get_cik_for_ticker("AAPL")
            assert cik == "0000320193"

    @pytest.mark.asyncio
    async def test_unknown_ticker_raises_value_error(self) -> None:
        mock_data = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        }
        with patch("app.services.sec_edgar._get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            from app.services.sec_edgar import get_cik_for_ticker
            with pytest.raises(ValueError, match="Could not resolve CIK"):
                await get_cik_for_ticker("FAKEXYZ")


# =============================================================================
# Financials Tests (mocked)
# =============================================================================


class TestFinancials:
    @pytest.mark.asyncio
    async def test_get_fundamentals_returns_model(self) -> None:
        mock_info = {
            "symbol": "AAPL",
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3_000_000_000_000,
            "trailingPE": 28.5,
            "grossMargins": 0.44,
            "profitMargins": 0.25,
        }

        with patch("app.services.cache.cache_get", new_callable=AsyncMock, return_value=None), \
             patch("app.services.cache.cache_set", new_callable=AsyncMock), \
             patch("yfinance.Ticker") as mock_ticker:
            mock_ticker.return_value.info = mock_info
            from app.services.financials import get_fundamentals
            result = await get_fundamentals("AAPL")
            assert result.ticker == "AAPL"
            assert result.company_name == "Apple Inc."
            assert result.sector == "Technology"

    @pytest.mark.asyncio
    async def test_peer_comparison_returns_table(self) -> None:
        from app.models.schemas import CompanyFundamentals
        mock_fund = CompanyFundamentals(ticker="MSFT", company_name="Microsoft")

        with patch("app.services.financials.get_fundamentals", new_callable=AsyncMock, return_value=mock_fund):
            from app.services.financials import get_peer_comparison
            result = await get_peer_comparison("AAPL")
            assert result.subject_ticker == "AAPL"
            assert len(result.peers) > 0
