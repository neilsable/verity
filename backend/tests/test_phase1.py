"""
VERITY — Phase 1 Test Suite
Tests for: config, models, auth routes, health endpoints.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core.config import Settings, get_settings
from app.models.schemas import (
    AgentName,
    CompanyFundamentals,
    JobStatus,
    ResearchJobCreate,
    ResearchReport,
    ResearchState,
    UserCreate,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for tests — never use real API keys in CI."""
    return Settings(
        app_env="development",
        app_secret_key="test-secret-key-for-testing-at-least-32-chars",
        app_debug=True,
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/verity_test",
        supabase_url="https://placeholder.supabase.co",
        supabase_anon_key="placeholder",
        supabase_service_role_key="placeholder",
        redis_url="redis://localhost:6379/0",
        celery_broker_url="redis://localhost:6379/1",
        celery_result_backend="redis://localhost:6379/2",
        pinecone_api_key="placeholder",
        anthropic_api_key="sk-placeholder",
        openai_api_key="sk-placeholder",
        fmp_api_key="placeholder",
        news_api_key="placeholder",
        sec_edgar_user_agent="VERITY Test test@test.com",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    """FastAPI test client with mocked dependencies."""
    from app.main import app

    with patch("app.db.database.init_db", new_callable=AsyncMock), \
         patch("app.services.cache.init_redis", new_callable=AsyncMock), \
         patch("app.db.database.close_db", new_callable=AsyncMock), \
         patch("app.services.cache.close_redis", new_callable=AsyncMock):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Get a valid JWT token for test requests."""
    from app.api.routes.auth import create_access_token
    token = create_access_token(str(uuid.uuid4()), "test@example.com")
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Config Tests
# =============================================================================


class TestSettings:
    def test_cors_origins_parsed_from_string(self) -> None:
        """Comma-separated CORS origins should be split into a list."""
        s = Settings(
            app_env="development",
            app_secret_key="a" * 32,
            app_cors_origins="http://localhost:3000,https://app.verity.com",
            database_url="postgresql+asyncpg://u:p@localhost/db",
            supabase_url="https://x.supabase.co",
            supabase_anon_key="x",
            supabase_service_role_key="x",
            pinecone_api_key="x",
            anthropic_api_key="x",
            openai_api_key="x",
            fmp_api_key="x",
            news_api_key="x",
            sec_edgar_user_agent="x x@x.com",
        )
        assert s.app_cors_origins == ["http://localhost:3000", "https://app.verity.com"]

    def test_anthropic_cost_calculation(self, test_settings: Settings) -> None:
        cost = test_settings.anthropic_cost_usd(1_000_000, 500_000)
        assert cost == pytest.approx(3.00 + 7.50, rel=1e-3)

    def test_openai_cost_calculation(self, test_settings: Settings) -> None:
        cost = test_settings.openai_cost_usd(1_000_000, 1_000_000)
        assert cost == pytest.approx(5.00 + 15.00, rel=1e-3)

    def test_embedding_cost_calculation(self, test_settings: Settings) -> None:
        cost = test_settings.embedding_cost_usd(1_000_000)
        assert cost == pytest.approx(0.02, rel=1e-3)

    def test_is_production_flag(self, test_settings: Settings) -> None:
        assert test_settings.is_production is False
        assert test_settings.is_development is True

    def test_secret_key_min_length_enforced(self) -> None:
        with pytest.raises(Exception):
            Settings(
                app_secret_key="tooshort",  # < 32 chars
                database_url="postgresql+asyncpg://u:p@localhost/db",
                supabase_url="https://x.supabase.co",
                supabase_anon_key="x",
                supabase_service_role_key="x",
                pinecone_api_key="x",
                anthropic_api_key="x",
                openai_api_key="x",
                fmp_api_key="x",
                news_api_key="x",
                sec_edgar_user_agent="x x@x.com",
            )


# =============================================================================
# Pydantic Model Tests
# =============================================================================


class TestResearchJobCreate:
    def test_ticker_normalised_to_uppercase(self) -> None:
        job = ResearchJobCreate(ticker="aapl")
        assert job.ticker == "AAPL"

    def test_ticker_strips_whitespace(self) -> None:
        job = ResearchJobCreate(ticker="  MSFT  ")
        assert job.ticker == "MSFT"

    def test_ticker_rejects_invalid_format(self) -> None:
        with pytest.raises(Exception):
            ResearchJobCreate(ticker="AAPL123")  # digits not allowed

    def test_ticker_max_length_enforced(self) -> None:
        with pytest.raises(Exception):
            ResearchJobCreate(ticker="TOOLONGTICKERX")

    def test_research_brief_min_length_enforced(self) -> None:
        with pytest.raises(Exception):
            ResearchJobCreate(ticker="AAPL", research_brief="Hi")

    def test_default_includes_all_agents(self) -> None:
        job = ResearchJobCreate(ticker="AAPL")
        assert AgentName.ORCHESTRATOR in job.include_agents


class TestResearchState:
    def test_state_initialises_with_empty_collections(self) -> None:
        state = ResearchState(
            job_id=uuid.uuid4(),
            ticker="AAPL",
            research_brief="Analyse AAPL",
        )
        assert state.sec_filings == []
        assert state.news_articles == []
        assert state.errors == {}
        assert state.total_cost_usd == 0.0

    def test_cost_accumulates_correctly(self) -> None:
        state = ResearchState(
            job_id=uuid.uuid4(),
            ticker="TSLA",
            research_brief="Analyse Tesla",
            total_cost_usd=0.15,
        )
        state.total_cost_usd += 0.05
        assert state.total_cost_usd == pytest.approx(0.20)


class TestCompanyFundamentals:
    def test_all_optional_fields_default_to_none(self) -> None:
        f = CompanyFundamentals(ticker="AAPL", company_name="Apple Inc.")
        assert f.pe_ratio is None
        assert f.ev_ebitda is None
        assert f.market_cap is None

    def test_data_source_defaults_to_yfinance(self) -> None:
        f = CompanyFundamentals(ticker="AAPL", company_name="Apple Inc.")
        assert f.data_source == "yfinance"


# =============================================================================
# Auth Route Tests
# =============================================================================


class TestAuthRoutes:
    def test_register_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "test@example.com", "full_name": "Test User", "password": "securepassword"},
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert "hashed_password" not in data
        assert "id" in data

    def test_login_returns_token(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/login",
            params={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_me_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/auth/me")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_me_returns_user_with_valid_token(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        assert "email" in resp.json()

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Health Route Tests
# =============================================================================


class TestHealthRoutes:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "ok"

    def test_health_includes_service_name(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.json()["service"] == "verity-api"


# =============================================================================
# Research Route Tests
# =============================================================================


class TestResearchRoutes:
    def test_create_job_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/research/jobs",
            json={"ticker": "AAPL", "research_brief": "Analyse this company please."},
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_create_job_returns_202_with_valid_auth(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.post(
            "/research/jobs",
            json={
                "ticker": "AAPL",
                "research_brief": "Focus on AI services and cloud revenue growth trajectory.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_job_rejects_invalid_ticker(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.post(
            "/research/jobs",
            json={"ticker": "invalid123", "research_brief": "Some research brief here."},
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_nonexistent_job_returns_404(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        fake_id = uuid.uuid4()
        resp = client.get(f"/research/jobs/{fake_id}", headers=auth_headers)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_history_returns_empty_list(
        self, client: TestClient, auth_headers: dict
    ) -> None:
        resp = client.get("/research/history", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


# =============================================================================
# JWT Tests
# =============================================================================


class TestJWT:
    def test_token_encode_decode_roundtrip(self) -> None:
        from app.api.routes.auth import create_access_token, decode_token
        user_id = str(uuid.uuid4())
        email = "jwt@test.com"
        token = create_access_token(user_id, email)
        payload = decode_token(token)
        assert payload["sub"] == user_id
        assert payload["email"] == email

    def test_tampered_token_raises(self) -> None:
        from fastapi import HTTPException
        from app.api.routes.auth import decode_token
        with pytest.raises(HTTPException) as exc_info:
            decode_token("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.INVALID")
        assert exc_info.value.status_code == 401
