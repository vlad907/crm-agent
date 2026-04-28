import { Lead } from "@/src/lib/types";
import { resolveLeadPipeline, stageLabel } from "@/src/lib/leadPipeline";

interface LeadSummaryCardProps {
  lead: Lead | null;
  loading: boolean;
  draftsCount?: number;
  hasSnapshot?: boolean;
}

function toRelative(value?: string): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return d.toLocaleDateString();
}

function toDate(value?: string): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function initials(name?: string | null, company?: string | null): string {
  const n = (name || "").trim();
  const c = (company || "").trim();
  if (n) {
    const parts = n.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return n.slice(0, 2).toUpperCase();
  }
  if (c) return c.slice(0, 2).toUpperCase();
  return "??";
}

function stageColor(stage: string): string {
  if (["approved", "sent", "replied", "converted"].includes(stage)) return "green";
  if (["needs_review", "archived"].includes(stage)) return "amber";
  if (["draft_ready", "drafting"].includes(stage)) return "purple";
  return "blue";
}

export function LeadSummaryCard({ lead, loading, draftsCount = 0, hasSnapshot = false }: LeadSummaryCardProps) {
  const pipeline = lead ? resolveLeadPipeline(lead) : null;
  const stage = pipeline?.computed_stage ?? "imported";
  const color = stageColor(stage);

  if (loading) {
    return (
      <section className="ld-summary-card">
        <div className="ld-summary-top">
          <div className="ld-avatar ld-avatar-skeleton" />
          <div className="ld-summary-info">
            <div className="ld-skeleton-line" style={{ width: "60%", height: 20 }} />
            <div className="ld-skeleton-line" style={{ width: "40%", height: 14, marginTop: 8 }} />
            <div className="ld-skeleton-line" style={{ width: "50%", height: 12, marginTop: 6 }} />
          </div>
        </div>
      </section>
    );
  }

  if (!lead) {
    return (
      <section className="ld-summary-card">
        <div className="muted" style={{ padding: 24 }}>Lead not found.</div>
      </section>
    );
  }

  return (
    <section className="ld-summary-card">
      {/* Top row: avatar + info + stage */}
      <div className="ld-summary-top">
        <div className="ld-avatar" aria-hidden>{initials(lead.name, lead.company)}</div>

        <div className="ld-summary-info">
          <h2 className="ld-company">{lead.company || lead.name}</h2>
          {lead.company && lead.name && lead.name !== lead.company && (
            <div className="ld-contact-name">{lead.name}{lead.title ? ` · ${lead.title}` : ""}</div>
          )}
          <div className="ld-meta-row">
            {lead.industry && <span className="ld-meta-chip">{lead.industry}</span>}
            {lead.location && <span className="ld-meta-chip">{lead.location}</span>}
            {lead.source && <span className="ld-meta-chip ld-meta-chip-muted">{lead.source}</span>}
          </div>
        </div>

        <div className="ld-summary-right">
          <span className={`ld-stage-badge ld-stage-${color}`}>{stageLabel(stage)}</span>
          <div className="ld-dates">
            <div className="ld-date-item">
              <span className="ld-date-label">Created</span>
              <span className="ld-date-value">{toDate(lead.created_at)}</span>
            </div>
            <div className="ld-date-item">
              <span className="ld-date-label">Updated</span>
              <span className="ld-date-value">{toRelative(lead.updated_at)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Contact details row */}
      <div className="ld-contact-row">
        {lead.website_url && (
          <a href={lead.website_url} target="_blank" rel="noreferrer" className="ld-contact-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
            <span>{lead.website_url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")}</span>
          </a>
        )}
        {lead.email && (
          <a href={`mailto:${lead.email}`} className="ld-contact-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
            <span>{lead.email}</span>
          </a>
        )}
        {lead.phone && (
          <a href={`tel:${lead.phone}`} className="ld-contact-item">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
            <span>{lead.phone}</span>
          </a>
        )}
      </div>

      {/* Quick stats */}
      <div className="ld-quick-stats">
        <div className="ld-stat">
          <span className="ld-stat-value">{hasSnapshot ? "Yes" : "—"}</span>
          <span className="ld-stat-label">Ingested</span>
        </div>
        <div className="ld-stat">
          <span className="ld-stat-value">{pipeline?.has_agent1_output ? "Yes" : "—"}</span>
          <span className="ld-stat-label">Researched</span>
        </div>
        <div className="ld-stat">
          <span className="ld-stat-value">{draftsCount || "—"}</span>
          <span className="ld-stat-label">Drafts</span>
        </div>
        <div className="ld-stat">
          <span className="ld-stat-value">{pipeline?.has_agent3_verdict ? (pipeline.final_decision === "send" ? "Approved" : "Hold") : "—"}</span>
          <span className="ld-stat-label">Verdict</span>
        </div>
      </div>
    </section>
  );
}
