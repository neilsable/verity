// =============================================================================
// VERITY — API Client
// Type-safe HTTP client for all backend endpoints.
// =============================================================================

import type {
  PaginatedResponse,
  ResearchJob,
  ResearchReport,
  TokenResponse,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {},
): Promise<T> {
  const { token, ...fetchOptions } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${API_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new APIError(
      resp.status,
      body.error_code ?? "UNKNOWN_ERROR",
      body.message ?? "An unexpected error occurred",
    );
  }

  return resp.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  login: (email: string, password: string): Promise<TokenResponse> =>
    request<TokenResponse>(`/auth/login?email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`, {
      method: "POST",
    }),

  register: (email: string, password: string, fullName?: string): Promise<{ id: string; email: string }> =>
    request(`/auth/register`, {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    }),
};

// ---------------------------------------------------------------------------
// Research
// ---------------------------------------------------------------------------

export const researchApi = {
  createJob: (
    ticker: string,
    researchBrief: string,
    token: string,
  ): Promise<ResearchJob> =>
    request<ResearchJob>("/research/jobs", {
      method: "POST",
      body: JSON.stringify({ ticker, research_brief: researchBrief }),
      token,
    }),

  getJob: (jobId: string, token: string): Promise<ResearchJob> =>
    request<ResearchJob>(`/research/jobs/${jobId}`, { token }),

  getReport: (jobId: string, token: string): Promise<ResearchReport> =>
    request<ResearchReport>(`/research/reports/${jobId}`, { token }),

  getHistory: (
    token: string,
    page = 1,
    pageSize = 20,
  ): Promise<PaginatedResponse<ResearchJob>> =>
    request<PaginatedResponse<ResearchJob>>(
      `/research/history?page=${page}&page_size=${pageSize}`,
      { token },
    ),

  cancelJob: (jobId: string, token: string): Promise<{ message: string }> =>
    request(`/research/jobs/${jobId}`, { method: "DELETE", token }),

  /**
   * Subscribe to real-time job progress via SSE.
   * Returns a cleanup function — call it to unsubscribe.
   */
  streamProgress: (
    jobId: string,
    token: string,
    onEvent: (event: unknown) => void,
    onError?: (error: Event) => void,
  ): (() => void) => {
    const url = `${API_URL}/research/jobs/${jobId}/stream`;
    const es = new EventSource(`${url}?token=${token}`);

    es.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data));
      } catch {
        // Malformed JSON — skip
      }
    };

    if (onError) {
      es.onerror = onError;
    }

    return () => es.close();
  },
};
