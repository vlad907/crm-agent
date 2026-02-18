import { Lead } from "@/src/lib/types";

interface LeadListTableProps {
  leads: Lead[];
  loading: boolean;
  onSelectLead: (id: string) => void;
}

function toLocalDate(value?: string): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
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

export function LeadListTable({ leads, loading, onSelectLead }: LeadListTableProps) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Status</th>
            <th>Website</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={4} className="muted">
                Loading leads...
              </td>
            </tr>
          ) : leads.length === 0 ? (
            <tr>
              <td colSpan={4} className="muted">
                No leads found.
              </td>
            </tr>
          ) : (
            leads.map((lead) => (
              <tr key={lead.id} className="clickable-row" onClick={() => onSelectLead(lead.id)}>
                <td>
                  <strong>{lead.company}</strong>
                </td>
                <td>
                  <span className={statusClass(lead.status)}>{lead.status || "new"}</span>
                </td>
                <td>
                  {lead.website_url ? (
                    <a className="external-link" href={lead.website_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                      {lead.website_url}
                    </a>
                  ) : (
                    <span className="muted">-</span>
                  )}
                </td>
                <td>{toLocalDate(lead.updated_at)}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
