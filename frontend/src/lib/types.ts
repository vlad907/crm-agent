export type JsonObject = Record<string, unknown>;

export interface Lead {
  id: string;
  name: string;
  company: string;
  status: string;
  source: string;
  website_url?: string | null;
  email?: string | null;
  location?: string | null;
  industry?: string | null;
  title?: string | null;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  offset: number;
  limit: number;
  [key: string]: unknown;
}

export interface Snapshot {
  id: string;
  url: string;
  raw_text: string;
  fetched_at: string;
  [key: string]: unknown;
}

export interface Draft {
  id: string;
  lead_id: string;
  subject: string;
  body: string;
  decision: string;
  agent1_output?: JsonObject | null;
  agent3_verdict?: JsonObject | null;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface FinalEmail {
  subject: string;
  email_body: string;
  [key: string]: unknown;
}

export interface LatestContext {
  lead_id: string;
  snapshot: Snapshot;
  agent1_output?: JsonObject | null;
  agent3_decision?: string | null;
  agent3_issues?: string[] | null;
  final_email?: FinalEmail | null;
  [key: string]: unknown;
}

export interface WebsiteIngestResult {
  id: string;
  fetched_at: string;
  raw_text_length: number;
  [key: string]: unknown;
}

export interface Agent1RunResult {
  lead_id: string;
  snapshot_id: string;
  agent1_output: JsonObject;
  [key: string]: unknown;
}

export interface Agent3RunResult {
  lead_id: string;
  draft_id: string;
  decision: "send" | "hold";
  issues: string[];
  final_email: FinalEmail;
  [key: string]: unknown;
}

export interface CreateLeadPayload {
  name: string;
  company: string;
  source: string;
  status: string;
  website_url?: string | null;
  email?: string | null;
  location?: string | null;
  industry?: string | null;
  title?: string | null;
  [key: string]: unknown;
}
