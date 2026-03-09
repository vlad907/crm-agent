export type JsonObject = Record<string, unknown>;

export interface LeadPipelineSummary {
  has_snapshot: boolean;
  has_agent1_output: boolean;
  has_draft: boolean;
  has_agent3_verdict: boolean;
  final_decision?: string | null;
  computed_stage: string;
}

export interface Lead {
  id: string;
  name: string;
  company: string;
  status: string;
  source: string;
  phone?: string | null;
  website_url?: string | null;
  email?: string | null;
  location?: string | null;
  industry?: string | null;
  title?: string | null;
  created_at?: string;
  updated_at?: string;
  pipeline_summary?: LeadPipelineSummary | null;
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
  prepared_context?: JsonObject | null;
  [key: string]: unknown;
}

export interface WebsiteIngestResult {
  id: string;
  fetched_at: string;
  raw_text_length: number;
  pages_saved?: number;
  emails_found?: string[];
  phones_found?: string[];
  [key: string]: unknown;
}

export interface WebsitePage {
  id: string;
  workspace_id: string;
  lead_id: string;
  url: string;
  page_type: "home" | "about" | "contact" | "other" | string;
  raw_text: string;
  extracted_emails: string[];
  extracted_phones: string[];
  created_at: string;
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

export interface DevLoginPayload {
  email: string;
  name?: string | null;
}

export interface DevLoginResult {
  workspace_id: string;
  user_id: string;
  email: string;
  name?: string | null;
  created: boolean;
  [key: string]: unknown;
}

export interface CreateLeadPayload {
  name: string;
  company: string;
  source: string;
  status: string;
  phone?: string | null;
  website_url?: string | null;
  email?: string | null;
  location?: string | null;
  industry?: string | null;
  title?: string | null;
  [key: string]: unknown;
}

export interface LeadImportItem {
  name?: string | null;
  title?: string | null;
  company?: string | null;
  industry?: string | null;
  location?: string | null;
  website_url?: string | null;
  email?: string | null;
  source?: string | null;
  status?: string | null;
}

export interface LeadImportPayload {
  source: string;
  items: LeadImportItem[];
  dedupe_by_website?: boolean;
  dedupe_by_company_location?: boolean;
}

export interface LeadImportDuplicate {
  row_index: number;
  reason: string;
  company?: string | null;
  location?: string | null;
  website_url?: string | null;
}

export interface LeadImportError {
  row_index: number;
  reason: string;
  company?: string | null;
  location?: string | null;
  website_url?: string | null;
}

export interface LeadImportResponse {
  source: string;
  total_received: number;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  imported: Lead[];
  duplicates: LeadImportDuplicate[];
  errors: LeadImportError[];
}

export interface Prospect {
  id: string;
  workspace_id: string;
  source: string;
  external_id?: string | null;
  company_name: string;
  category?: string | null;
  address: string;
  phone?: string | null;
  website_url?: string | null;
  rating?: number | null;
  review_count?: number | null;
  raw_source_payload?: JsonObject;
  import_status: "new" | "selected" | "imported" | "skipped" | string;
  created_at: string;
  updated_at: string;
}

export interface ProspectListResponse {
  items: Prospect[];
  total: number;
  offset: number;
  limit: number;
}

export interface ProspectImportItem {
  source: string;
  external_id?: string | null;
  company_name?: string | null;
  category?: string | null;
  address?: string | null;
  phone?: string | null;
  website_url?: string | null;
  rating?: number | null;
  review_count?: number | null;
  raw_source_payload?: JsonObject | null;
  import_status?: string | null;
}

export interface ProspectImportPayload {
  items: ProspectImportItem[];
}

export interface ProspectImportSkipped {
  row_index: number;
  reason: string;
  source?: string | null;
  external_id?: string | null;
  company_name?: string | null;
  address?: string | null;
}

export interface ProspectImportResponse {
  total_received: number;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  imported: Prospect[];
  skipped: ProspectImportSkipped[];
  errors: ProspectImportSkipped[];
}

export interface ProspectSearchPayload {
  location: string;
  radius: number;
  categories: string[];
  keyword?: string;
  missing_website_only?: boolean;
  limit?: number;
}

export interface ProspectSearchResponse {
  fetched_count: number;
  import_result: ProspectImportResponse;
}

export interface ConvertProspectsPayload {
  prospect_ids: string[];
  require_website?: boolean;
}

export interface ConvertProspectsResponse {
  requested_count: number;
  found_count: number;
  converted_count: number;
  skipped_count: number;
  converted_leads: Lead[];
  skipped: Array<{
    prospect_id: string;
    reason: string;
    company_name: string;
    address: string;
    website_url?: string | null;
  }>;
}

export interface WorkspaceSettings {
  workspace_id: string;
  openai_api_key?: string | null;
  google_places_api_key?: string | null;
  gmail_connected?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WorkspaceSettingsUpdate {
  openai_api_key?: string | null;
  google_places_api_key?: string | null;
  gmail_connected?: boolean | null;
}

export interface WorkspaceProfile {
  workspace_id: string;
  business_name?: string | null;
  business_description?: string | null;
  industries_served: string[];
  service_specialties: string[];
  service_area?: string | null;
  preferred_tone?: string | null;
  outreach_style?: string | null;
  preferred_cta?: string | null;
  do_not_mention: string[];
  created_at?: string | null;
  updated_at?: string | null;
}

export interface WorkspaceProfileUpdate {
  business_name?: string | null;
  business_description?: string | null;
  industries_served?: string[] | null;
  service_specialties?: string[] | null;
  service_area?: string | null;
  preferred_tone?: string | null;
  outreach_style?: string | null;
  preferred_cta?: string | null;
  do_not_mention?: string[] | null;
}
