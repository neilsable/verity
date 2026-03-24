# VERITY — Autonomous Equity Research Agent Platform

> Production-grade multi-agent system for automated equity research, powered by Claude claude-sonnet-4-20250514.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VERITY Platform                              │
│                                                                     │
│  ┌────────────────┐    ┌──────────────────────────────────────┐    │
│  │  Next.js 14    │    │         FastAPI Backend               │    │
│  │  Frontend      │───▶│  Auth │ Rate Limit │ Logging │ SSE   │    │
│  │  (Vercel)      │    └──────────────┬───────────────────────┘    │
│  └────────────────┘                   │                             │
│                                       ▼                             │
│                         ┌─────────────────────────┐                │
│                         │   Celery Task Queue      │                │
│                         │   (Upstash Redis)        │                │
│                         └──────────┬──────────────┘                │
│                                    │                                │
│                         ┌──────────▼──────────────┐                │
│                         │    LangGraph Agents       │               │
│                         │                           │               │
│                         │  ┌─────────────────────┐ │               │
│                         │  │  Orchestrator Agent  │ │               │
│                         │  └──────────┬──────────┘ │               │
│                         │             │             │               │
│                         │  ┌──────────▼──────────┐ │               │
│                         │  │   Parallel Agents    │ │               │
│                         │  │  ┌───────┐ ┌──────┐  │ │              │
│                         │  │  │Filing │ │Comps │  │ │              │
│                         │  │  └───────┘ └──────┘  │ │              │
│                         │  │  ┌──────┐  ┌──────┐  │ │              │
│                         │  │  │Earn. │  │News  │  │ │              │
│                         │  │  └──────┘  └──────┘  │ │              │
│                         │  └──────────┬──────────┘ │               │
│                         │             │             │               │
│                         │  ┌──────────▼──────────┐ │               │
│                         │  │  Synthesis → Critique│ │               │
│                         │  │  → Citation Agent    │ │               │
│                         │  └─────────────────────┘ │               │
│                         └──────────────────────────┘               │
│                                                                     │
│  External Services                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │Supabase  │ │Pinecone  │ │Anthropic │ │ OpenAI   │              │
│  │PostgreSQL│ │Vector DB │ │ Claude   │ │ GPT-4o   │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │SEC EDGAR │ │yfinance  │ │ NewsAPI  │                            │
│  │ (free)   │ │ (free)   │ │ (free)   │                            │
│  └──────────┘ └──────────┘ └──────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Agent Pipeline

```
Orchestrator
    │
    ├── Filing Agent    → SEC 10-K/10-Q/8-K ingestion, RAG retrieval
    ├── Earnings Agent  → Transcript tone/evasion scoring
    ├── Comps Agent     → Fundamentals + peer comparison tables
    └── News Agent      → Sentiment + materiality scoring
    │
    ▼
Synthesis Agent   → Structured research note (bull/bear/risks/valuation)
    │
    ▼
Critique Agent    → Hallucination detection, confidence scoring
    │
    ▼
Citation Agent    → Source mapping for every factual claim
    │
    ▼
Final Report      → Delivered to API + stored in Supabase
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Agent Orchestration | LangGraph, LangChain |
| Primary LLM | Anthropic claude-sonnet-4-20250514 |
| Fallback LLM | OpenAI GPT-4o |
| Vector Database | Pinecone (free tier) |
| Relational DB | Supabase PostgreSQL |
| Cache / Queue | Upstash Redis + Celery |
| Task Worker | Celery |
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Auth | Supabase Auth + JWT |
| Deployment | Railway (API), Vercel (Frontend) |
| CI/CD | GitHub Actions |

---

## Local Setup

### Prerequisites

- Docker Desktop
- Python 3.12+
- Node.js 20+
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd verity

# Copy env file and fill in your API keys
cp .env.example .env
```

Open `.env` and fill in at minimum:
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `FMP_API_KEY`
- `NEWS_API_KEY`
- `APP_SECRET_KEY` (run: `openssl rand -hex 32`)

For **local dev**, the Supabase variables can be set to your local DB:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/verity
SUPABASE_URL=http://localhost:8000  # Not used locally
SUPABASE_ANON_KEY=placeholder
SUPABASE_SERVICE_ROLE_KEY=placeholder
```

### 2. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 3. Install Python dependencies

```bash
cd backend
uv pip install -e ".[dev]"
```

### 4. Run database migrations

```bash
psql postgresql://postgres:postgres@localhost:5432/verity -f scripts/init_db.sql
```

### 5. Start the API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 6. Start the Celery worker (new terminal)

```bash
cd backend
celery -A app.worker.celery_app worker --loglevel=debug -Q research,default
```

### 7. Start the frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

**Services running:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- Celery Flower: http://localhost:5555

### Full Docker stack (optional)

```bash
# Runs everything in Docker
docker compose up --build
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

---

## API Reference

### Create Research Job
```
POST /research/jobs
Authorization: Bearer <token>

{
  "ticker": "AAPL",
  "research_brief": "Focus on AI services revenue growth and margin expansion."
}
```

### Poll Job Status
```
GET /research/jobs/{job_id}
```

### Stream Progress (SSE)
```
GET /research/jobs/{job_id}/stream
```

### Get Report
```
GET /research/reports/{job_id}
```

---

## Deployment

### Railway (Backend)
```bash
railway login
railway init
railway up
```

### Vercel (Frontend)
```bash
cd frontend
vercel deploy --prod
```

Set all env vars in Railway and Vercel dashboards (never in code).

---

## Free Tier Limits

| Service | Free Limit | Notes |
|---|---|---|
| Anthropic | Pay-per-use | ~$0.05–0.30 per research report |
| Pinecone | 1 index, 100k vectors | Sufficient for ~200 companies |
| Supabase | 500MB DB, 50k MAU | More than enough for MVP |
| Upstash Redis | 10k commands/day | Increase if throughput grows |
| FMP API | 250 calls/day | Cache aggressively |
| NewsAPI | 100 calls/day | Cache aggressively |
| SEC EDGAR | Unlimited | Rate limit: 10 req/sec |

---

## Commit Checklist

After each Phase milestone, commit:
```bash
git add .
git commit -m "feat: Phase X — description"
git push origin main
```
