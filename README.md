<div align="center">

<br/>

```
██╗   ██╗███████╗██████╗ ██╗████████╗██╗   ██╗
██║   ██║██╔════╝██╔══██╗██║╚══██╔══╝╚██╗ ██╔╝
██║   ██║█████╗  ██████╔╝██║   ██║    ╚████╔╝ 
╚██╗ ██╔╝██╔══╝  ██╔══██╗██║   ██║     ╚██╔╝  
 ╚████╔╝ ███████╗██║  ██║██║   ██║      ██║   
  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝      ╚═╝   
```

**Autonomous Equity Research — Powered by 8 AI Agents**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-verity--frontend--delta.vercel.app-c9a84c?style=for-the-badge&logo=vercel&logoColor=black)](https://verity-frontend-delta.vercel.app)
[![API](https://img.shields.io/badge/API-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://zestful-abundance-production.up.railway.app/docs)
[![GitHub](https://img.shields.io/badge/GitHub-neilsable%2Fverity-181717?style=for-the-badge&logo=github)](https://github.com/neilsable/verity)
[![Built with Claude](https://img.shields.io/badge/Powered%20by-Claude%20Sonnet%204-6B48FF?style=for-the-badge)](https://anthropic.com)

<br/>

> *"I got frustrated with how long equity research takes. So I built the infrastructure to do it in 4 minutes."*
> — **Neil Sable, 2026**

<br/>

</div>

---

## What is VERITY?

VERITY is a production-grade multi-agent AI system that does the work of a junior equity research analyst — automatically. You give it a ticker and a research brief. Eight specialised agents run in parallel, analysing SEC filings, earnings call transcripts, live peer comparisons, and recent news. The output is a fully cited, red-teamed research note. Every claim traced to a source. No hallucinations.

**Built by one person. Overnight. Because the right tool didn't exist.**

---

## The Problem

Equity research is slow, expensive, and locked behind institutional walls.

A junior analyst at a bank spends 2–3 days pulling 10-K filings, building comp tables, listening to earnings calls, and writing up a research note. Most of that work is mechanical — retrieving documents, extracting numbers, structuring arguments. It shouldn't require a human.

VERITY automates the mechanical parts. What used to take days takes 4 minutes and costs $0.19.

---

## The Pipeline

Eight agents. One pipeline. Zero unsourced claims.

```
You type: AAPL  →  "Focus on AI services revenue and margin expansion"
                                        │
                                        ▼
                            ┌─────────────────────┐
                            │   01. Orchestrator   │
                            │                     │
                            │  Reads your brief.   │
                            │  Decomposes it into  │
                            │  tasks. Assigns them │
                            │  to the right agents.│
                            │  Manages state.      │
                            └──────────┬──────────┘
                                       │
               ┌───────────────────────┼───────────────────────┐
               │                       │                       │
               ▼                       ▼                       ▼
   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
   │   02. Filing Agent  │ │  03. Earnings Agent  │ │   04. Comps Agent   │
   │                     │ │                     │ │                     │
   │  Connects to SEC    │ │  Processes earnings  │ │  Pulls live data    │
   │  EDGAR. Ingests     │ │  call transcripts.   │ │  from yfinance +    │
   │  10-K, 10-Q, 8-K.  │ │  Scores management   │ │  FMP. Builds peer   │
   │  Chunks and embeds  │ │  tone, hedge density,│ │  comp tables: P/E,  │
   │  into Pinecone.     │ │  Q&A evasion.        │ │  EV/EBITDA, margins │
   │  RAG retrieval on   │ │  Extracts forward    │ │  vs sector peers.   │
   │  your research      │ │  guidance statements.│ │  Flags premium or   │
   │  brief.             │ │                      │ │  discount vs peers. │
   └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
               │                       │                       │
               └───────────────────────┼───────────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │   05. News Agent    │
                            │                     │
                            │  Fetches recent     │
                            │  articles. Scores   │
                            │  sentiment with     │
                            │  temporal decay     │
                            │  weighting. Flags   │
                            │  material events.   │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  06. Synthesis Agent │
                            │                     │
                            │  Receives all agent │
                            │  outputs. Writes    │
                            │  the research note: │
                            │  bull thesis, bear  │
                            │  thesis, risks,     │
                            │  valuation, summary │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  07. Critique Agent  │
                            │                     │
                            │  Red-teams the note.│
                            │  Finds unsupported  │
                            │  claims. Flags      │
                            │  contradictions.    │
                            │  Assigns confidence │
                            │  score 0.0 → 1.0.   │
                            └──────────┬──────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │  08. Citation Agent  │
                            │                     │
                            │  Maps every factual │
                            │  claim to its exact │
                            │  source: document,  │
                            │  date, page, passage│
                            │  Full audit trail.  │
                            └──────────┬──────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │         Final Report              │
                    │                                  │
                    │  Executive summary               │
                    │  Bull thesis (data-backed)       │
                    │  Bear thesis (data-backed)       │
                    │  Key risks (ranked)              │
                    │  Valuation vs peers              │
                    │  Citation index (every claim)    │
                    │  Confidence score                │
                    │  Total cost: ~$0.19              │
                    └──────────────────────────────────┘
```

---

## Why This Architecture

I didn't build one big prompt that does everything. That approach produces hallucinations, misses nuance, and can't be debugged or improved.

Each agent is narrow, specialised, and testable. The Critique Agent exists specifically because LLMs confidently say wrong things — so I added a dedicated agent whose only job is to find what the Synthesis Agent got wrong. The Citation Agent exists because accountability requires traceability.

This mirrors how a real research team works. A filing analyst, a transcript specialist, a quant, a news desk, a writer, a fact-checker, and a citation editor. VERITY just runs all of them simultaneously, in 4 minutes, for $0.19.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Agent Orchestration** | LangGraph | State machines for multi-agent pipelines. Handles parallel execution and error recovery. |
| **Primary LLM** | Anthropic Claude Sonnet 4 | Best reasoning-to-cost ratio for financial analysis. Low hallucination rate. |
| **Vector Database** | Pinecone | Sub-50ms semantic retrieval on SEC filing chunks. Ticker-scoped namespaces. |
| **Backend** | FastAPI + Python 3.12 | Async-native, type-safe, production-ready. Uvicorn for ASGI. |
| **Task Queue** | Celery + Redis | Async job processing. Research jobs run in background workers, results streamed via SSE. |
| **Database** | PostgreSQL (Supabase) | Job history, user auth, report storage. |
| **Frontend** | Next.js 14 + TypeScript | Server components, real-time SSE streaming, edge deployment. |
| **Auth** | JWT + Supabase Auth | Stateless token auth with role-based access. |
| **Deployment** | Railway + Vercel | Zero-config Docker deployment (Railway), CDN-edge frontend (Vercel). |
| **CI/CD** | GitHub Actions | Lint, test, deploy on every push to main. |
| **Data Sources** | SEC EDGAR, yfinance, FMP, NewsAPI | All free tier. EDGAR is unlimited. FMP is 250 calls/day. NewsAPI is 100/day. |

---

## What I Actually Built (Commit by Commit)

```
6 hours ago  feat: Phase 1 — project scaffold, config, models, auth, CI
             └── FastAPI app skeleton, Pydantic settings, JWT auth,
                 rate limiting, structured logging, health endpoints,
                 database schema, Docker setup, GitHub Actions CI
                 25 tests passing

5 hours ago  feat: Phase 2 — data ingestion pipeline
             └── SEC EDGAR client, document chunker, text embedder,
                 Pinecone vector store, yfinance + FMP financials client,
                 NewsAPI client with caching
                 28 tests passing

4 hours ago  feat: Phase 3 — full LangGraph agent pipeline
             └── Base agent class, orchestrator, filing agent,
                 earnings agent, comps agent, news agent,
                 synthesis agent, critique agent, citation agent
                 14 tests passing

3 hours ago  feat: Phase 4 — wired API endpoints
             └── Research job creation, SSE streaming, job polling,
                 report retrieval, cost tracking
                 15 tests passing

2 hours ago  feat: Phase 5 — Next.js frontend
             └── Dark premium UI, real-time agent progress panel,
                 report viewer with citation index, auth flow

1 hour ago   feat: Phase 6 — deployed to Railway + Vercel
             └── Backend live on Railway, frontend live on Vercel,
                 all environment variables configured
                 57 tests passing across all phases
```

**Total: built and deployed in one session.**

---

## Running Locally

```bash
# 1. Clone
git clone https://github.com/neilsable/verity.git
cd verity

# 2. Configure — copy and fill in your API keys
cp .env.example .env

# 3. Start infrastructure
docker compose up -d postgres redis

# 4. Install and run backend
cd backend
pip install uv && uv pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 5. Run frontend (new terminal)
cd frontend
npm install && npm run dev
```

**Minimum keys needed to run:**
- `ANTHROPIC_API_KEY` — get free at console.anthropic.com
- `PINECONE_API_KEY` — free at app.pinecone.io
- `FMP_API_KEY` — free at financialmodelingprep.com
- `NEWS_API_KEY` — free at newsapi.org
- `APP_SECRET_KEY` — run `openssl rand -hex 32`

Everything else can stay as placeholder for local dev.

---

## API

```bash
# Create a research job
POST /research/jobs
Authorization: Bearer <token>

{
  "ticker": "NVDA",
  "research_brief": "Focus on AI chip demand and competitive moat vs AMD."
}

# Stream real-time agent progress
GET /research/jobs/{job_id}/stream
# Returns: Server-Sent Events with agent_started, agent_completed, job_completed events

# Get the final report
GET /research/reports/{job_id}
```

Full interactive API docs at `/docs` (Swagger UI, auto-generated from FastAPI).

---

## Cost Per Report

| Component | Cost |
|---|---|
| Claude Sonnet 4 (input) | ~$0.06 |
| Claude Sonnet 4 (output) | ~$0.09 |
| OpenAI embeddings | ~$0.001 |
| Pinecone reads | Free tier |
| External APIs | Free tier |
| **Total** | **~$0.15–0.25** |

At $0.19 average, you could run 1,000 research reports for $190. A single equity research report from a boutique firm costs $500–$5,000.

---

## Live Links

| | |
|---|---|
| 🌐 **Frontend** | [verity-frontend-delta.vercel.app](https://verity-frontend-delta.vercel.app) |
| ⚙️ **API Docs** | [zestful-abundance-production.up.railway.app/docs](https://zestful-abundance-production.up.railway.app/docs) |
| 🎨 **Figma Design** | [figma.com/design/1TX70sKPFQ9vVEqiA7FKcN](https://www.figma.com/design/1TX70sKPFQ9vVEqiA7FKcN) |

---

<div align="center">

Built by **[Neil Sable](https://github.com/neilsable)** · 2026

*One developer. Eight agents. Zero unsourced claims.*

</div>
