"""
VERITY — Core Pydantic Data Models
All data contracts for the platform. Pydantic v2 throughout.
These are the source of truth for DB schemas, API responses, and agent I/O.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentName(StrEnum):
    ORCHESTRATOR = "orchestrator"
    FILING = "filing"
    EARNINGS = "earnings"
    COMPS = "comps"
    NEWS = "news"
    SYNTHESIS = "synthesis"
    CRITIQUE = "critique"
    CITATION = "citation"


class FilingType(StrEnum):
    ANNUAL_REPORT = "10-K"
    QUARTERLY_REPORT = "10-Q"
    CURRENT_REPORT = "8-K"
    PROXY = "DEF 14A"


class SentimentScore(StrEnum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    VERY_NEGATIVE = "very_negative"


# =============================================================================
# Base Models
# =============================================================================


class VERITYBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        validate_assignment=True,
    )


# =============================================================================
# User & Auth Models
# =============================================================================


class UserBase(VERITYBaseModel):
    email: str
    full_name: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserResponse(UserBase):
    id: uuid.UUID
    created_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(VERITYBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# =============================================================================
# Research Job Models
# =============================================================================


class ResearchJobCreate(VERITYBaseModel):
    ticker: str = Field(
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z]{1,10}$",
        description="Stock ticker symbol (e.g. AAPL)",
    )
    research_brief: str = Field(
        default="Provide a comprehensive equity research analysis.",
        min_length=10,
        max_length=2000,
        description="What to focus on in the research",
    )
    include_agents: list[AgentName] = Field(
        default_factory=lambda: list(AgentName),
        description="Which agents to run (defaults to all)",
    )

    @field_validator("ticker")
    @classmethod
    def normalise_ticker(cls, v: str) -> str:
        return v.upper().strip()


class AgentProgress(VERITYBaseModel):
    agent: AgentName
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchJobResponse(VERITYBaseModel):
    id: uuid.UUID
    ticker: str
    research_brief: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    agent_progress: list[AgentProgress] = Field(default_factory=list)
    error_message: str | None = None
    cost_usd: float | None = None
    total_tokens: int | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Document / Filing Models
# =============================================================================


class SECFiling(VERITYBaseModel):
    ticker: str
    cik: str
    filing_type: FilingType
    filing_date: datetime
    period_of_report: datetime | None = None
    accession_number: str
    document_url: str
    full_text_url: str | None = None


class DocumentChunk(VERITYBaseModel):
    chunk_id: str
    document_id: str
    ticker: str
    source_type: str  # "10-K" | "10-Q" | "transcript" | "news"
    source_url: str
    filing_date: datetime
    page_number: int | None = None
    chunk_index: int
    text: str
    token_count: int
    embedding: list[float] | None = None  # None until embedded


class EmbeddedChunk(DocumentChunk):
    embedding: list[float]  # Required — always present after embedding
    pinecone_id: str


# =============================================================================
# Financial / Comps Models
# =============================================================================


class CompanyFundamentals(VERITYBaseModel):
    ticker: str
    company_name: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    revenue_ttm: float | None = None
    revenue_growth_yoy: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    price_to_book: float | None = None
    price_to_sales: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    free_cash_flow_yield: float | None = None
    as_of_date: datetime = Field(default_factory=datetime.utcnow)
    data_source: str = "yfinance"


class PeerComparisonTable(VERITYBaseModel):
    subject_ticker: str
    peers: list[CompanyFundamentals]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Earnings / Transcript Models
# =============================================================================


class EarningsCallAnalysis(VERITYBaseModel):
    ticker: str
    call_date: datetime
    quarter: str  # e.g. "Q1 2024"
    management_tone_score: float = Field(
        ge=-1.0, le=1.0, description="-1 very negative, +1 very positive"
    )
    hedge_word_density: float = Field(
        ge=0.0, description="Hedge words per 100 words"
    )
    evasion_score: float = Field(
        ge=0.0, le=1.0, description="Q&A evasion score 0-1"
    )
    forward_guidance_statements: list[str] = Field(default_factory=list)
    key_topics: list[str] = Field(default_factory=list)
    sentiment: SentimentScore = SentimentScore.NEUTRAL
    source_url: str | None = None
    raw_transcript_excerpt: str | None = None


# =============================================================================
# News Models
# =============================================================================


class NewsArticle(VERITYBaseModel):
    article_id: str
    ticker: str
    title: str
    description: str | None = None
    url: str
    published_at: datetime
    source_name: str
    sentiment_score: float = Field(
        ge=-1.0, le=1.0, default=0.0, description="-1 very negative, +1 very positive"
    )
    temporal_weight: float = Field(
        ge=0.0, le=1.0, default=1.0, description="Decay-adjusted weight"
    )
    is_material: bool = False
    materiality_reason: str | None = None


# =============================================================================
# Agent Output Models
# =============================================================================


class Citation(VERITYBaseModel):
    citation_id: str
    claim_text: str
    source_document: str
    source_url: str
    filing_date: datetime | None = None
    page_number: int | None = None
    passage: str  # The exact passage supporting the claim
    confidence: float = Field(ge=0.0, le=1.0)


class CritiqueFlag(VERITYBaseModel):
    flag_id: str
    claim_text: str
    flag_type: str  # "unsupported" | "contradicted" | "low_confidence"
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_correction: str | None = None


class ResearchReport(VERITYBaseModel):
    report_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    job_id: uuid.UUID
    ticker: str
    company_name: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Report sections
    executive_summary: str
    bull_thesis: str
    bear_thesis: str
    key_risks: list[str] = Field(default_factory=list)
    valuation_section: str
    conclusion: str

    # Supporting data
    fundamentals: CompanyFundamentals | None = None
    peer_comparison: PeerComparisonTable | None = None
    earnings_analysis: EarningsCallAnalysis | None = None

    # Quality assurance
    citations: list[Citation] = Field(default_factory=list)
    critique_flags: list[CritiqueFlag] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)

    # Cost tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0


# =============================================================================
# LangGraph State Model
# =============================================================================


class ResearchState(VERITYBaseModel):
    """
    The shared state passed between all LangGraph nodes.
    Every agent reads from and writes to this state.
    """

    job_id: uuid.UUID
    ticker: str
    research_brief: str
    company_name: str | None = None

    # Data collected by each agent
    sec_filings: list[SECFiling] = Field(default_factory=list)
    relevant_chunks: list[DocumentChunk] = Field(default_factory=list)
    fundamentals: CompanyFundamentals | None = None
    peer_comparison: PeerComparisonTable | None = None
    earnings_analysis: EarningsCallAnalysis | None = None
    news_articles: list[NewsArticle] = Field(default_factory=list)

    # Synthesis outputs
    draft_report: ResearchReport | None = None
    final_report: ResearchReport | None = None

    # Execution metadata
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    token_usage: dict[str, dict[str, int]] = Field(default_factory=dict)
    total_cost_usd: float = 0.0


# =============================================================================
# API Response Wrappers
# =============================================================================


class SuccessResponse(VERITYBaseModel):
    success: bool = True
    message: str
    data: Any | None = None


class ErrorResponse(VERITYBaseModel):
    success: bool = False
    error_code: str
    message: str
    details: Any | None = None


class PaginatedResponse(VERITYBaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_more: bool
