import {
  Agent1RunResult,
  Agent3RunResult,
  ConvertProspectsPayload,
  ConvertProspectsResponse,
  CreateLeadPayload,
  DevLoginPayload,
  DevLoginResult,
  Draft,
  DraftReviewQueueItem,
  DraftReviewQueueSummary,
  DraftReviewUpdateResponse,
  GmailConnectUrlResponse,
  GmailDraftActionResponse,
  GmailSendResponse,
  GmailStatusResponse,
  Lead,
  LeadImportPayload,
  LeadImportResponse,
  LeadListResponse,
  LatestContext,
  ProspectImportPayload,
  ProspectImportResponse,
  ProspectListResponse,
  ProspectSearchPayload,
  ProspectSearchResponse,
  WorkspaceSettings,
  WorkspaceProfile,
  WorkspaceProfileUpdate,
  WorkspaceAiStrategy,
  WorkspaceAiStrategyUpdate,
  WorkspaceAutomationSettings,
  WorkspaceAutomationSettingsUpdate,
  WorkspaceSettingsUpdate,
  WebsitePage,
  WebsiteIngestResult
} from "@/src/lib/types";
import { getUserId, getWorkspaceId } from "@/src/lib/identity";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

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

type ApiFetchInit = RequestInit & {
  requireIdentity?: boolean;
};

export async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  const { requireIdentity = true, ...fetchInit } = init ?? {};
  const headers = new Headers(fetchInit.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const workspaceId = (headers.get("X-Workspace-Id") ?? "").trim() || getWorkspaceId();
  const userId = (headers.get("X-User-Id") ?? "").trim() || getUserId();
  if (requireIdentity && (!workspaceId || !userId)) {
    throw new ApiError("Missing Workspace/User ID. Set them in Settings.", 400);
  }

  if (workspaceId) {
    headers.set("X-Workspace-Id", workspaceId);
  }
  if (userId) {
    headers.set("X-User-Id", userId);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchInit,
    headers,
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

export function importLeads(payload: LeadImportPayload): Promise<LeadImportResponse> {
  return apiFetch<LeadImportResponse>("/api/v1/leads/imports", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

function buildProspectsQuery(
  limit: number,
  offset: number,
  status?: string,
  category?: string,
  q?: string
): string {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (status) {
    params.set("status", status);
  }
  if (category) {
    params.set("category", category);
  }
  if (q) {
    params.set("q", q);
  }
  return params.toString();
}

export function getProspects(
  limit: number,
  offset: number,
  status?: string,
  category?: string,
  q?: string
): Promise<ProspectListResponse> {
  return apiFetch<ProspectListResponse>(`/api/v1/prospects?${buildProspectsQuery(limit, offset, status, category, q)}`);
}

export function importProspects(payload: ProspectImportPayload): Promise<ProspectImportResponse> {
  return apiFetch<ProspectImportResponse>("/api/v1/prospects/import", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function runProspectSearch(payload: ProspectSearchPayload): Promise<ProspectSearchResponse> {
  return apiFetch<ProspectSearchResponse>("/api/v1/prospects/search", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function convertProspectsToLeads(payload: ConvertProspectsPayload): Promise<ConvertProspectsResponse> {
  return apiFetch<ConvertProspectsResponse>("/api/v1/prospects/convert-to-leads", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getWorkspaceSettings(): Promise<WorkspaceSettings> {
  return apiFetch<WorkspaceSettings>("/api/v1/settings");
}

export function patchWorkspaceSettings(payload: WorkspaceSettingsUpdate): Promise<WorkspaceSettings> {
  return apiFetch<WorkspaceSettings>("/api/v1/settings", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function getAutomationSettings(): Promise<WorkspaceAutomationSettings> {
  return apiFetch<WorkspaceAutomationSettings>("/api/v1/automation-settings");
}

export function patchAutomationSettings(payload: WorkspaceAutomationSettingsUpdate): Promise<WorkspaceAutomationSettings> {
  return apiFetch<WorkspaceAutomationSettings>("/api/v1/automation-settings", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function getGmailConnectUrl(): Promise<GmailConnectUrlResponse> {
  return apiFetch<GmailConnectUrlResponse>("/api/v1/integrations/gmail/connect-url");
}

export function getGmailStatus(): Promise<GmailStatusResponse> {
  return apiFetch<GmailStatusResponse>("/api/v1/integrations/gmail/status");
}

export function getWorkspaceProfile(): Promise<WorkspaceProfile> {
  return apiFetch<WorkspaceProfile>("/api/v1/workspace-profile");
}

export function patchWorkspaceProfile(payload: WorkspaceProfileUpdate): Promise<WorkspaceProfile> {
  return apiFetch<WorkspaceProfile>("/api/v1/workspace-profile", {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function getWorkspaceAiStrategy(): Promise<WorkspaceAiStrategy> {
  return apiFetch<WorkspaceAiStrategy>("/api/v1/workspace-ai-strategy");
}

export function generateWorkspaceAiStrategy(): Promise<WorkspaceAiStrategy> {
  return apiFetch<WorkspaceAiStrategy>("/api/v1/workspace-ai-strategy/generate", {
    method: "POST"
  });
}

export function patchWorkspaceAiStrategy(payload: WorkspaceAiStrategyUpdate): Promise<WorkspaceAiStrategy> {
  return apiFetch<WorkspaceAiStrategy>("/api/v1/workspace-ai-strategy", {
    method: "PATCH",
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

export function getLeadWebsitePages(id: string, limit = 50, offset = 0): Promise<WebsitePage[]> {
  return apiFetch<WebsitePage[]>(`/api/v1/leads/${id}/website-pages?limit=${limit}&offset=${offset}`);
}

export function getDraftReviewQueue(limit = 25, offset = 0, includeApproved = false): Promise<DraftReviewQueueItem[]> {
  return apiFetch<DraftReviewQueueItem[]>(
    `/api/v1/drafts/review-queue?limit=${limit}&offset=${offset}&include_approved=${includeApproved ? "true" : "false"}`
  );
}

export function getDraftReviewQueueSummary(): Promise<DraftReviewQueueSummary> {
  return apiFetch<DraftReviewQueueSummary>("/api/v1/drafts/review-queue-summary");
}

export function approveDraft(draftId: string): Promise<DraftReviewUpdateResponse> {
  return apiFetch<DraftReviewUpdateResponse>(`/api/v1/drafts/${draftId}/approve`, {
    method: "POST"
  });
}

export function rejectDraft(draftId: string): Promise<DraftReviewUpdateResponse> {
  return apiFetch<DraftReviewUpdateResponse>(`/api/v1/drafts/${draftId}/reject`, {
    method: "POST"
  });
}

export function createGmailDraft(draftId: string): Promise<GmailDraftActionResponse> {
  return apiFetch<GmailDraftActionResponse>(`/api/v1/drafts/${draftId}/create-gmail-draft`, {
    method: "POST"
  });
}

export function sendDraft(draftId: string): Promise<GmailSendResponse> {
  return apiFetch<GmailSendResponse>(`/api/v1/drafts/${draftId}/send`, {
    method: "POST"
  });
}

export function devLogin(payload: DevLoginPayload): Promise<DevLoginResult> {
  return apiFetch<DevLoginResult>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
    requireIdentity: false
  });
}
