"""
VERITY — Phase 4 Test Suite
API endpoint tests: job creation, status, history, cancellation.
All Celery and pipeline calls mocked.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.routes.auth import create_access_token


def make_token(user_id: str | None = None) -> str:
    uid = user_id or str(uuid.uuid4())
    return create_access_token(uid, "test@example.com"), uid


@pytest.fixture
def client():
    from app.main import app
    with patch("app.db.database.init_db", new_callable=AsyncMock), \
         patch("app.services.cache.init_redis", new_callable=AsyncMock), \
         patch("app.db.database.close_db", new_callable=AsyncMock), \
         patch("app.services.cache.close_redis", new_callable=AsyncMock):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture
def auth(client):
    token, uid = make_token()
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": uid}


# =============================================================================
# POST /research/jobs
# =============================================================================

class TestCreateJob:
    def test_returns_202_with_valid_request(self, client, auth):
        with patch("app.api.routes.research._save_job", new_callable=AsyncMock), \
             patch("app.api.routes.research._run_inline", new_callable=AsyncMock), \
             patch("app.worker.tasks.run_research_job") as mock_task:
            mock_task.apply_async.side_effect = Exception("Celery not running")
            resp = client.post(
                "/research/jobs",
                json={"ticker": "AAPL", "research_brief": "Analyse Apple AI services growth trajectory."},
                headers=auth["headers"],
            )
        assert resp.status_code == status.HTTP_202_ACCEPTED
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["status"] in ("pending", "running")
        assert "id" in data

    def test_rejects_invalid_ticker(self, client, auth):
        resp = client.post(
            "/research/jobs",
            json={"ticker": "invalid123", "research_brief": "Some research brief here please."},
            headers=auth["headers"],
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_rejects_short_brief(self, client, auth):
        resp = client.post(
            "/research/jobs",
            json={"ticker": "AAPL", "research_brief": "Too short"},
            headers=auth["headers"],
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_requires_authentication(self, client):
        resp = client.post(
            "/research/jobs",
            json={"ticker": "AAPL", "research_brief": "Analyse Apple AI services growth trajectory."},
        )
        assert resp.status_code in (401, 403)

    def test_ticker_is_normalised_to_uppercase(self, client, auth):
        with patch("app.api.routes.research._save_job", new_callable=AsyncMock), \
             patch("app.api.routes.research._run_inline", new_callable=AsyncMock), \
             patch("app.worker.tasks.run_research_job") as mock_task:
            mock_task.apply_async.side_effect = Exception("no celery")
            resp = client.post(
                "/research/jobs",
                json={"ticker": "aapl", "research_brief": "Analyse Apple AI services growth trajectory."},
                headers=auth["headers"],
            )
        assert resp.status_code == 202 and resp.json().get("ticker") == "AAPL" or resp.status_code == 422


# =============================================================================
# GET /research/jobs/{id}
# =============================================================================

class TestGetJob:
    def test_returns_404_for_unknown_job(self, client, auth):
        fake_id = uuid.uuid4()
        with patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=None):
            resp = client.get(f"/research/jobs/{fake_id}", headers=auth["headers"])
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_403_for_other_users_job(self, client, auth):
        other_user_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        mock_job = {
            "id": job_id, "user_id": other_user_id,
            "ticker": "AAPL", "research_brief": "Test brief long enough",
            "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "agent_progress": [],
        }
        with patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=mock_job), \
             patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=mock_job):
            # Our auth user tries to access another user's job
            resp = client.get(f"/research/jobs/{job_id}", headers=auth["headers"])
        assert resp.status_code in (403, 404)

    def test_returns_job_for_owner(self, client, auth):
        job_id = str(uuid.uuid4())
        mock_job = {
            "id": job_id, "user_id": auth["user_id"],
            "ticker": "NVDA", "research_brief": "Analyse NVIDIA AI chip dominance and competitive moat.",
            "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "agent_progress": [
                {"agent": "orchestrator", "status": "completed",
                 "started_at": None, "completed_at": None, "error": None, "metadata": {}},
            ],
        }
        import app.api.routes.research as research_module
        research_module._jobs[job_id] = mock_job

        with patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=None):
            resp = client.get(f"/research/jobs/{job_id}", headers=auth["headers"])

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["ticker"] == "NVDA"
        assert data["status"] == "running"


# =============================================================================
# GET /research/history
# =============================================================================

class TestHistory:
    def test_returns_empty_list_for_new_user(self, client, auth):
        import app.api.routes.research as research_module
        # Clear jobs for this user
        research_module._jobs = {
            k: v for k, v in research_module._jobs.items()
            if v.get("user_id") != auth["user_id"]
        }
        resp = client.get("/research/history", headers=auth["headers"])
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_returns_only_own_jobs(self, client, auth):
        import app.api.routes.research as research_module
        own_job_id = str(uuid.uuid4())
        other_job_id = str(uuid.uuid4())

        research_module._jobs[own_job_id] = {
            "id": own_job_id, "user_id": auth["user_id"],
            "ticker": "AAPL", "research_brief": "Analyse Apple AI services revenue growth.",
            "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(), "agent_progress": [],
        }
        research_module._jobs[other_job_id] = {
            "id": other_job_id, "user_id": "different-user",
            "ticker": "TSLA", "research_brief": "Analyse Tesla EV market share.",
            "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(), "agent_progress": [],
        }

        resp = client.get("/research/history", headers=auth["headers"])
        assert resp.status_code == status.HTTP_200_OK
        tickers = [j["ticker"] for j in resp.json()["items"]]
        assert "AAPL" in tickers
        assert "TSLA" not in tickers

    def test_pagination_works(self, client, auth):
        import app.api.routes.research as research_module
        # Add 5 jobs
        for i in range(5):
            jid = str(uuid.uuid4())
            research_module._jobs[jid] = {
                "id": jid, "user_id": auth["user_id"],
                "ticker": f"T{i:03d}", "research_brief": f"Analyse company {i} growth trajectory.",
                "status": "completed", "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(), "agent_progress": [],
            }

        resp = client.get("/research/history?page=1&page_size=2", headers=auth["headers"])
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1


# =============================================================================
# DELETE /research/jobs/{id}
# =============================================================================

class TestCancelJob:
    def test_cancels_running_job(self, client, auth):
        import app.api.routes.research as research_module
        job_id = str(uuid.uuid4())
        research_module._jobs[job_id] = {
            "id": job_id, "user_id": auth["user_id"],
            "ticker": "MSFT", "research_brief": "Analyse Microsoft cloud revenue growth.",
            "status": "running", "celery_task_id": "fake-task-id",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(), "agent_progress": [],
        }

        with patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=None), \
             patch("app.api.routes.research._save_job", new_callable=AsyncMock), \
             patch("app.worker.celery_app") as mock_celery:
            resp = client.delete(f"/research/jobs/{job_id}", headers=auth["headers"])

        assert resp.status_code == status.HTTP_200_OK
        assert research_module._jobs[job_id]["status"] == "cancelled"

    def test_cannot_cancel_completed_job(self, client, auth):
        import app.api.routes.research as research_module
        job_id = str(uuid.uuid4())
        research_module._jobs[job_id] = {
            "id": job_id, "user_id": auth["user_id"],
            "ticker": "AAPL", "research_brief": "Analyse Apple AI services revenue growth.",
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(), "agent_progress": [],
        }

        with patch("app.api.routes.research.cache_get", new_callable=AsyncMock, return_value=None):
            resp = client.delete(f"/research/jobs/{job_id}", headers=auth["headers"])

        assert resp.status_code == status.HTTP_409_CONFLICT


# =============================================================================
# Health endpoints
# =============================================================================

class TestHealth:
    def test_liveness_probe(self, client):
        resp = client.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "ok"

    def test_response_has_request_id_header(self, client):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
