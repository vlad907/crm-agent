import { Lead } from "@/src/lib/types";
import { LeadStage, resolveLeadPipeline, stageLabel } from "@/src/lib/leadPipeline";

interface LeadSummaryCardProps {
  lead: Lead | null;
  loading: boolean;
}

function statusClass(status?: string): string {
  switch ((status ?? "").toLowerCase()) {
    case "ready":
    case "send":
    case "sent":
      return "status-badge status-send";
    case "hold":
      return "status-badge status-hold";
    case "agent2":
    case "agent3":
    case "draft":
      return "status-badge status-draft";
    default:
      return "status-badge status-new";
  }
}

function toLocalDate(value?: string): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function LeadSummaryCard({ lead, loading }: LeadSummaryCardProps) {
  const stage = lead ? resolveLeadPipeline(lead).computed_stage : "new";

  return (
    <section className="card stack">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2>Lead Profile</h2>
        <div className="inline-actions">
          {lead ? <span className={statusClass(stage)}>{stageLabel(stage as LeadStage)}</span> : null}
          <button type="button" className="btn-danger" disabled title="Delete flow coming soon">
            Delete Lead
          </button>
        </div>
      </div>
      {loading ? (
        <div className="muted">Loading lead...</div>
      ) : lead ? (
        <div className="kv-grid">
          <div className="kv">
            <strong>Name</strong>
            {lead.name || "-"}
          </div>
          <div className="kv">
            <strong>Company</strong>
            {lead.company || "-"}
          </div>
          <div className="kv">
            <strong>Current Stage</strong>
            {stageLabel(stage as LeadStage)}
          </div>
          <div className="kv">
            <strong>Website</strong>
            {lead.website_url ? (
              <a className="external-link" href={lead.website_url} target="_blank" rel="noreferrer">
                {lead.website_url}
              </a>
            ) : (
              "-"
            )}
          </div>
          <div className="kv">
            <strong>Email</strong>
            {lead.email || "-"}
          </div>
          <div className="kv">
            <strong>Phone</strong>
            {lead.phone || "-"}
          </div>
          <div className="kv">
            <strong>Industry</strong>
            {lead.industry || "-"}
          </div>
          <div className="kv">
            <strong>Location</strong>
            {lead.location || "-"}
          </div>
          <div className="kv">
            <strong>Source</strong>
            {lead.source || "-"}
          </div>
          <div className="kv">
            <strong>Lead ID</strong>
            {lead.id}
          </div>
          <div className="kv">
            <strong>Created</strong>
            {toLocalDate(lead.created_at)}
          </div>
          <div className="kv">
            <strong>Updated</strong>
            {toLocalDate(lead.updated_at)}
          </div>
        </div>
      ) : (
        <div className="muted">Lead not found.</div>
      )}
    </section>
  );
}
