// =============================================================================
// VERITY — Frontend TypeScript Types
// Mirror the backend Pydantic schemas exactly.
// Keep in sync with backend/app/models/schemas.py
// =============================================================================

export type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type AgentName =
  | "orchestrator"
  | "filing"
  | "earnings"
  | "comps"
  | "news"
  | "synthesis"
  | "critique"
  | "citation";

export interface AgentProgress {
  agent: AgentName;
  status: JobStatus;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  metadata: Record<string, unknown>;
}

export interface ResearchJob {
  id: string;
  ticker: string;
  research_brief: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  agent_progress: AgentProgress[];
  error_message: string | null;
  cost_usd: number | null;
  total_tokens: number | null;
}

export interface CompanyFundamentals {
  ticker: string;
  company_name: string;
  sector: string | null;
  industry: string | null;
  market_cap: number | null;
  enterprise_value: number | null;
  revenue_ttm: number | null;
  revenue_growth_yoy: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  pe_ratio: number | null;
  ev_ebitda: number | null;
  price_to_book: number | null;
  price_to_sales: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  return_on_equity: number | null;
  return_on_assets: number | null;
  free_cash_flow_yield: number | null;
  as_of_date: string;
  data_source: string;
}

export interface Citation {
  citation_id: string;
  claim_text: string;
  source_document: string;
  source_url: string;
  filing_date: string | null;
  page_number: number | null;
  passage: string;
  confidence: number;
}

export interface CritiqueFlag {
  flag_id: string;
  claim_text: string;
  flag_type: "unsupported" | "contradicted" | "low_confidence";
  explanation: string;
  confidence: number;
  suggested_correction: string | null;
}

export interface ResearchReport {
  report_id: string;
  job_id: string;
  ticker: string;
  company_name: string;
  generated_at: string;
  executive_summary: string;
  bull_thesis: string;
  bear_thesis: string;
  key_risks: string[];
  valuation_section: string;
  conclusion: string;
  fundamentals: CompanyFundamentals | null;
  citations: Citation[];
  critique_flags: CritiqueFlag[];
  overall_confidence: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// SSE progress events from the stream endpoint
export type ProgressEvent =
  | { event: "job_started"; job_id: string; ticker: string }
  | { event: "agent_started"; agent: AgentName; job_id: string }
  | { event: "agent_completed"; agent: AgentName; job_id: string; duration_ms: number }
  | { event: "agent_failed"; agent: AgentName; job_id: string; error: string }
  | { event: "job_completed"; job_id: string; cost_usd: number }
  | { event: "job_failed"; job_id: string; error: string };
