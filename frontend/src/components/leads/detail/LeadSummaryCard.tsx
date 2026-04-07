import { Lead } from "@/src/lib/types";
import { resolveLeadPipeline, stageLabel } from "@/src/lib/leadPipeline";

interface LeadSummaryCardProps {
  lead: Lead | null;
  loading: boolean;
}

function toLocalDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
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

export function LeadSummaryCard({ lead, loading }: LeadSummaryCardProps) {
  const stage = lead ? resolveLeadPipeline(lead).computed_stage : "imported";

  return (
    <section className="card lead-profile-card">
      {loading ? (
        <div className="lead-profile-header lead-profile-skeleton">
          <div className="lead-profile-avatar" aria-hidden />
          <div className="lead-profile-info">
            <div className="lead-profile-name">Loading...</div>
            <div className="lead-profile-company">—</div>
            <div className="lead-profile-meta">—</div>
          </div>
        </div>
      ) : lead ? (
        <>
          <div className="lead-profile-header">
            <div className="lead-profile-avatar" aria-hidden>
              {initials(lead.name, lead.company)}
            </div>
            <div className="lead-profile-info">
              <h2 className="lead-profile-name">{lead.name || "—"}</h2>
              <div className="lead-profile-company">{lead.company || "—"}</div>
              <div className="lead-profile-meta">
                {lead.industry && <span>{lead.industry}</span>}
                {lead.location && <span> · {lead.location}</span>}
                {lead.source && <span> · {lead.source}</span>}
              </div>
            </div>
            <div className="lead-profile-stage">
              <span className="lead-profile-stage-label">Stage</span>
              <span className="lead-profile-stage-value">{stageLabel(stage)}</span>
            </div>
          </div>
          <div className="lead-profile-details">
            <div className="lead-profile-section">
              <h3 className="lead-profile-section-title">Contact</h3>
              <div className="lead-profile-fields">
                {lead.website_url && (
                  <div className="lead-profile-field">
                    <span className="lead-profile-field-label">Website</span>
                    <a className="external-link" href={lead.website_url} target="_blank" rel="noreferrer">
                      {lead.website_url}
                    </a>
                  </div>
                )}
                {lead.email && (
                  <div className="lead-profile-field">
                    <span className="lead-profile-field-label">Email</span>
                    <a href={`mailto:${lead.email}`}>{lead.email}</a>
                  </div>
                )}
                {lead.phone && (
                  <div className="lead-profile-field">
                    <span className="lead-profile-field-label">Phone</span>
                    <a href={`tel:${lead.phone}`}>{lead.phone}</a>
                  </div>
                )}
                {!lead.website_url && !lead.email && !lead.phone && (
                  <span className="muted">No contact info</span>
                )}
              </div>
            </div>
            <div className="lead-profile-section">
              <h3 className="lead-profile-section-title">Details</h3>
              <div className="lead-profile-fields">
                <div className="lead-profile-field">
                  <span className="lead-profile-field-label">Source</span>
                  <span>{lead.source || "—"}</span>
                </div>
                <div className="lead-profile-field">
                  <span className="lead-profile-field-label">Created</span>
                  <span>{toLocalDate(lead.created_at)}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="muted" style={{ padding: 24 }}>Lead not found.</div>
      )}
    </section>
  );
}
