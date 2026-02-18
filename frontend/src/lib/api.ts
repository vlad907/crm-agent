import {
  Agent1RunResult,
  Agent3RunResult,
  CreateLeadPayload,
  Draft,
  Lead,
  LeadListResponse,
  LatestContext,
  WebsiteIngestResult
} from "@/src/lib/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  const rawText = await response.text();
  const data = rawText ? tryParseJson(rawText) : null;

  if (!response.ok) {
    const detail = data && typeof data === "object" ? (data as Record<string, unknown>).detail : rawText;
    const message = typeof detail === "string" ? detail : `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, detail);
  }

  return data as T;
}

function tryParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function buildLeadsQuery(limit: number, offset: number, status?: string, q?: string): string {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (status) {
    params.set("status", status);
  }
  if (q) {
    params.set("q", q);
  }
  return params.toString();
}

export function getLeads(limit: number, offset: number, status?: string, q?: string): Promise<LeadListResponse> {
  const query = buildLeadsQuery(limit, offset, status, q);
  return apiFetch<LeadListResponse>(`/api/v1/leads?${query}`);
}

export function createLead(payload: CreateLeadPayload): Promise<Lead> {
  return apiFetch<Lead>("/api/v1/leads", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getLead(id: string): Promise<Lead> {
  return apiFetch<Lead>(`/api/v1/leads/${id}`);
}

export function ingestWebsite(id: string): Promise<WebsiteIngestResult> {
  return apiFetch<WebsiteIngestResult>(`/api/v1/leads/${id}/ingest-website`, {
    method: "POST"
  });
}

export function runAgent1(id: string): Promise<Agent1RunResult> {
  return apiFetch<Agent1RunResult>(`/api/v1/leads/${id}/run-agent1`, {
    method: "POST"
  });
}

export function runAgent2(id: string): Promise<Draft> {
  return apiFetch<Draft>(`/api/v1/leads/${id}/run-agent2`, {
    method: "POST"
  });
}

export function runAgent3(id: string): Promise<Agent3RunResult> {
  return apiFetch<Agent3RunResult>(`/api/v1/leads/${id}/run-agent3`, {
    method: "POST"
  });
}

export function getLatestContext(id: string): Promise<LatestContext> {
  return apiFetch<LatestContext>(`/api/v1/leads/${id}/latest-context`);
}

export function getLeadDrafts(id: string, limit = 20, offset = 0): Promise<Draft[]> {
  return apiFetch<Draft[]>(`/api/v1/leads/${id}/drafts?limit=${limit}&offset=${offset}`);
}
