"""
VERITY — Application Configuration
All settings loaded from environment variables with validation.
Never import settings directly; use get_settings() for proper caching.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App -------------------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = Field(min_length=32)
    app_debug: bool = False
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    app_cors_origins: list[str] = ["http://localhost:3000"]

    # --- API Server ------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # --- Database --------------------------------------------------------------
    database_url: str  # asyncpg URL
    database_direct_url: str = ""  # sync URL for migrations

    # --- Supabase --------------------------------------------------------------
    supabase_url: HttpUrl
    supabase_anon_key: str
    supabase_service_role_key: str

    # --- Redis -----------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""

    # --- Pinecone --------------------------------------------------------------
    pinecone_api_key: str
    pinecone_environment: str = "gcp-starter"
    pinecone_index_name: str = "verity-research"

    # --- LLM Providers ---------------------------------------------------------
    anthropic_api_key: str
    openai_api_key: str
    llm_primary_model: str = "claude-sonnet-4-20250514"
    llm_fallback_model: str = "gpt-4o"
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=4096, ge=256, le=8192)
    llm_timeout_seconds: int = Field(default=120, ge=10)
    llm_max_retries: int = Field(default=3, ge=1, le=5)

    # --- Financial Data APIs ---------------------------------------------------
    fmp_api_key: str
    fmp_base_url: str = "https://financialmodelingprep.com/api/v3"
    alpha_vantage_api_key: str = ""
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    news_api_key: str
    news_api_base_url: str = "https://newsapi.org/v2"
    sec_edgar_user_agent: str
    sec_edgar_base_url: str = "https://efts.sec.gov/LATEST/search-index"
    sec_edgar_submissions_url: str = "https://data.sec.gov/submissions"

    # --- Embedding -------------------------------------------------------------
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 100
    chunk_size: int = 512
    chunk_overlap: int = 64

    # --- Rate Limiting ---------------------------------------------------------
    rate_limit_requests_per_minute: int = 60
    rate_limit_requests_per_day: int = 1000

    # --- Cost Tracking (USD per 1M tokens) -------------------------------------
    anthropic_input_cost_per_1m: float = 3.00
    anthropic_output_cost_per_1m: float = 15.00
    openai_input_cost_per_1m: float = 5.00
    openai_output_cost_per_1m: float = 15.00
    openai_embedding_cost_per_1m: float = 0.02

    # --- Job Configuration -----------------------------------------------------
    research_job_timeout_seconds: int = 600
    max_concurrent_jobs: int = 5
    job_retention_days: int = 90

    # --- Observability ---------------------------------------------------------
    dd_api_key: str = ""
    dd_service: str = "verity-backend"
    dd_env: str = "development"
    sentry_dsn: str = ""

    @field_validator("app_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    def anthropic_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for an Anthropic API call."""
        return (
            input_tokens * self.anthropic_input_cost_per_1m / 1_000_000
            + output_tokens * self.anthropic_output_cost_per_1m / 1_000_000
        )

    def openai_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD for an OpenAI API call."""
        return (
            input_tokens * self.openai_input_cost_per_1m / 1_000_000
            + output_tokens * self.openai_output_cost_per_1m / 1_000_000
        )

    def embedding_cost_usd(self, total_tokens: int) -> float:
        """Calculate cost in USD for embedding API call."""
        return total_tokens * self.openai_embedding_cost_per_1m / 1_000_000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings. Use this everywhere."""
    return Settings()
