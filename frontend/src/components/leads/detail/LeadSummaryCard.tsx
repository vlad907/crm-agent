import { Lead } from "@/src/lib/types";

interface LeadSummaryCardProps {
  lead: Lead | null;
  loading: boolean;
}

function statusClass(status?: string): string {
  switch ((status ?? "").toLowerCase()) {
    case "send":
      return "status-badge status-send";
    case "hold":
      return "status-badge status-hold";
    case "draft":
      return "status-badge status-draft";
    default:
      return "status-badge status-new";
  }
}

export function LeadSummaryCard({ lead, loading }: LeadSummaryCardProps) {
  return (
    <section className="card stack">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h2>Lead Profile</h2>
        {lead ? <span className={statusClass(lead.status)}>{lead.status || "new"}</span> : null}
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
        </div>
      ) : (
        <div className="muted">Lead not found.</div>
      )}
    </section>
  );
}
