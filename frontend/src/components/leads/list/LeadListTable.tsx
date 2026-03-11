import { useMemo, useState } from "react";

import { Spinner } from "@/src/components/Spinner";
import { resolveLeadPipeline, stageLabel } from "@/src/lib/leadPipeline";
import { Lead } from "@/src/lib/types";

type SortColumn = "company" | "status" | "updated_at";
type SortDirection = "asc" | "desc";

interface LeadListTableProps {
  leads: Lead[];
  loading: boolean;
  bulkRunning: boolean;
  selectedLeadIds: string[];
  allVisibleSelected: boolean;
  rowActionState: Record<string, { ingest: boolean; runAi: boolean }>;
  onToggleSelectLead: (id: string) => void;
  onToggleSelectAllVisible: () => void;
  onSelectLead: (id: string) => void;
  onIngestLead: (id: string) => void;
  onRunAiLead: (id: string) => void;
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

function statusClass(stage: string): string {
  if (stage === "approved" || stage === "sent" || stage === "replied" || stage === "converted") {
    return "status-badge status-send";
  }
  if (stage === "needs_review" || stage === "archived") {
    return "status-badge status-hold";
  }
  if (stage === "drafting" || stage === "draft_ready") {
    return "status-badge status-draft";
  }
  if (stage === "researching" || stage === "researched") {
    return "status-badge status-research";
  }
  return "status-badge status-new";
}

function getRunAiDisabledReason(lead: Lead): string | null {
  const summary = resolveLeadPipeline(lead);
  if (!summary.has_snapshot && !lead.website_url) {
    return "Website URL required before AI pipeline can start.";
  }
  if (["approved", "needs_review", "sent", "replied", "converted", "archived"].includes(summary.computed_stage)) {
    return "Pipeline already completed for this lead.";
  }
  return null;
}

function sortKeyForStatus(lead: Lead): string {
  return resolveLeadPipeline(lead).computed_stage;
}

export function LeadListTable({
  leads,
  loading,
  bulkRunning,
  selectedLeadIds,
  allVisibleSelected,
  rowActionState,
  onToggleSelectLead,
  onToggleSelectAllVisible,
  onSelectLead,
  onIngestLead,
  onRunAiLead
}: LeadListTableProps) {
  const [sortColumn, setSortColumn] = useState<SortColumn>("updated_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  function onSort(column: SortColumn): void {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === "company" ? "asc" : "desc");
  }

  const sortedLeads = useMemo(() => {
    const cloned = [...leads];
    cloned.sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;
      if (sortColumn === "company") {
        return dir * (a.company || "").localeCompare(b.company || "");
      }
      if (sortColumn === "status") {
        return dir * sortKeyForStatus(a).localeCompare(sortKeyForStatus(b));
      }
      const aTime = a.updated_at ? new Date(a.updated_at).getTime() : 0;
      const bTime = b.updated_at ? new Date(b.updated_at).getTime() : 0;
      return dir * (aTime - bTime);
    });
    return cloned;
  }, [leads, sortColumn, sortDirection]);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ width: 42 }}>
              <input
                type="checkbox"
                checked={allVisibleSelected}
                onChange={() => onToggleSelectAllVisible()}
                title="Select all visible"
                aria-label="Select all visible"
              />
            </th>
            <th className="sortable-th" onClick={() => onSort("company")} title="Sort by company">
              Company
            </th>
            <th className="sortable-th" onClick={() => onSort("status")} title="Sort by pipeline status">
              Status
            </th>
            <th>Pipeline</th>
            <th>Website</th>
            <th className="sortable-th" onClick={() => onSort("updated_at")} title="Sort by updated time">
              Updated
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={7} className="muted">
                <Spinner label="Loading leads..." />
              </td>
            </tr>
          ) : sortedLeads.length === 0 ? (
            <tr>
              <td colSpan={7}>
                <div className="empty-state">No leads yet. Import prospects or create a lead manually.</div>
              </td>
            </tr>
          ) : (
            sortedLeads.map((lead) => {
              const rowState = rowActionState[lead.id] ?? { ingest: false, runAi: false };
              const summary = resolveLeadPipeline(lead);
              const runAiDisabledReason = getRunAiDisabledReason(lead);
              const runAiDisabled = bulkRunning || rowState.ingest || rowState.runAi || !!runAiDisabledReason;
              const ingestDisabled = bulkRunning || rowState.ingest || rowState.runAi || !lead.website_url;

              return (
                <tr key={lead.id} className="clickable-row" onClick={() => onSelectLead(lead.id)}>
                  <td onClick={(event) => event.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedLeadIds.includes(lead.id)}
                      onChange={() => onToggleSelectLead(lead.id)}
                      aria-label={`Select ${lead.company}`}
                    />
                  </td>
                  <td>
                    <strong>{lead.company}</strong>
                  </td>
                  <td>
                    <span className={statusClass(summary.computed_stage)}>{stageLabel(summary.computed_stage)}</span>
                  </td>
                  <td>
                    <div className="pipeline-mini">
                      <span className={`pipeline-flag ${summary.has_snapshot ? "done" : ""}`}>Ingested</span>
                      <span className={`pipeline-flag ${summary.has_agent1_output ? "done" : ""}`}>A1</span>
                      <span className={`pipeline-flag ${summary.has_draft ? "done" : ""}`}>A2</span>
                      <span className={`pipeline-flag ${summary.has_agent3_verdict ? "done" : ""}`}>A3</span>
                      <span
                        className={`pipeline-flag ${
                          summary.final_decision === "send"
                            ? "done-send"
                            : summary.final_decision === "hold"
                              ? "done-hold"
                              : ""
                        }`}
                      >
                        {summary.final_decision === "send" ? "Approved" : summary.final_decision === "hold" ? "Review" : "-"}
                      </span>
                    </div>
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
                  <td onClick={(event) => event.stopPropagation()}>
                    <div className="lead-row-actions">
                      <button
                        type="button"
                        className="action-btn"
                        title={lead.website_url ? "Fetch website pages and update snapshot" : "Website URL required"}
                        disabled={ingestDisabled}
                        onClick={() => onIngestLead(lead.id)}
                      >
                        {rowState.ingest ? <Spinner size="sm" label="Ingesting" /> : "Ingest"}
                      </button>
                      <button
                        type="button"
                        className="action-btn action-btn-primary"
                        title={runAiDisabledReason ?? "Run next missing AI step"}
                        disabled={runAiDisabled}
                        onClick={() => onRunAiLead(lead.id)}
                      >
                        {rowState.runAi ? <Spinner size="sm" label="Running" /> : "Run AI"}
                      </button>
                      <button
                        type="button"
                        className="action-btn"
                        title="Open lead detail"
                        onClick={() => onSelectLead(lead.id)}
                      >
                        Open
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
