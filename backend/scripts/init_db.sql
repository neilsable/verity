-- =============================================================================
-- VERITY — Database Schema
-- Run this in Supabase SQL editor OR via psql for local development.
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- Users (extends Supabase auth.users)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- For local dev without Supabase auth, use this simplified version:
CREATE TABLE IF NOT EXISTS public.users_local (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL UNIQUE,
    full_name       TEXT,
    hashed_password TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Research Jobs
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.research_jobs (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID NOT NULL,
    ticker           TEXT NOT NULL,
    research_brief   TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','running','completed','failed','cancelled')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ,
    error_message    TEXT,
    cost_usd         NUMERIC(10, 6),
    total_tokens     INTEGER,
    celery_task_id   TEXT
);

CREATE INDEX IF NOT EXISTS idx_research_jobs_user_id ON public.research_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_research_jobs_ticker ON public.research_jobs(ticker);
CREATE INDEX IF NOT EXISTS idx_research_jobs_status ON public.research_jobs(status);
CREATE INDEX IF NOT EXISTS idx_research_jobs_created_at ON public.research_jobs(created_at DESC);

-- =============================================================================
-- Agent Progress (one row per agent per job)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.agent_progress (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id       UUID NOT NULL REFERENCES public.research_jobs(id) ON DELETE CASCADE,
    agent_name   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','running','completed','failed')),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error        TEXT,
    metadata     JSONB DEFAULT '{}'::jsonb,
    UNIQUE(job_id, agent_name)
);

CREATE INDEX IF NOT EXISTS idx_agent_progress_job_id ON public.agent_progress(job_id);

-- =============================================================================
-- Research Reports
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.research_reports (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id               UUID NOT NULL UNIQUE REFERENCES public.research_jobs(id) ON DELETE CASCADE,
    ticker               TEXT NOT NULL,
    company_name         TEXT,
    executive_summary    TEXT,
    bull_thesis          TEXT,
    bear_thesis          TEXT,
    key_risks            JSONB DEFAULT '[]'::jsonb,
    valuation_section    TEXT,
    conclusion           TEXT,
    fundamentals         JSONB,
    peer_comparison      JSONB,
    earnings_analysis    JSONB,
    citations            JSONB DEFAULT '[]'::jsonb,
    critique_flags       JSONB DEFAULT '[]'::jsonb,
    overall_confidence   NUMERIC(4, 3) CHECK (overall_confidence BETWEEN 0 AND 1),
    total_input_tokens   INTEGER DEFAULT 0,
    total_output_tokens  INTEGER DEFAULT 0,
    total_cost_usd       NUMERIC(10, 6) DEFAULT 0,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_reports_ticker ON public.research_reports(ticker);
CREATE INDEX IF NOT EXISTS idx_research_reports_job_id ON public.research_reports(job_id);

-- =============================================================================
-- Token Usage Tracking (per LLM call)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.token_usage_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id          UUID REFERENCES public.research_jobs(id) ON DELETE SET NULL,
    agent_name      TEXT,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    cost_usd        NUMERIC(10, 6) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_job_id ON public.token_usage_log(job_id);
CREATE INDEX IF NOT EXISTS idx_token_usage_created_at ON public.token_usage_log(created_at DESC);

-- =============================================================================
-- API Keys (for external access)
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.api_keys (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,  -- SHA-256 of the actual key
    key_prefix   TEXT NOT NULL,         -- First 8 chars for display
    name         TEXT NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON public.api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON public.api_keys(key_hash);

-- =============================================================================
-- Updated-at trigger function
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_research_jobs_updated_at
    BEFORE UPDATE ON public.research_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Row Level Security (Supabase)
-- =============================================================================

ALTER TABLE public.research_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users see own jobs" ON public.research_jobs
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users see own reports" ON public.research_reports
    FOR ALL USING (
        job_id IN (SELECT id FROM public.research_jobs WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own agent progress" ON public.agent_progress
    FOR ALL USING (
        job_id IN (SELECT id FROM public.research_jobs WHERE user_id = auth.uid())
    );

CREATE POLICY "Users see own API keys" ON public.api_keys
    FOR ALL USING (auth.uid() = user_id);
