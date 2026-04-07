"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { Spinner } from "@/src/components/Spinner";
import { LeadListFilters } from "@/src/components/leads/list/LeadListFilters";
import { LeadListPagination } from "@/src/components/leads/list/LeadListPagination";
import { LeadListTable } from "@/src/components/leads/list/LeadListTable";
import {
  ApiError,
  deleteLeadsBulk,
  getLatestContext,
  getLeads,
  ingestWebsite,
  runAgent1,
  runAgent2,
  runAgent3
} from "@/src/lib/api";
import { resolveLeadPipeline } from "@/src/lib/leadPipeline";
import { useDebouncedValue } from "@/src/lib/hooks";
import { Lead, LeadListResponse } from "@/src/lib/types";

const PAGE_SIZE = 20;

type QuickFilter = "all" | "needs_ingestion" | "needs_agent1" | "needs_agent2" | "needs_agent3" | "approved" | "needs_review";
type LeadAction = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function matchesQuickFilter(lead: Lead, quickFilter: QuickFilter): boolean {
  const summary = resolveLeadPipeline(lead);
  if (quickFilter === "all") {
    return true;
  }
  if (quickFilter === "needs_ingestion") {
    return !summary.has_snapshot;
  }
  if (quickFilter === "needs_agent1") {
    return summary.has_snapshot && !summary.has_agent1_output;
  }
  if (quickFilter === "needs_agent2") {
    return summary.has_agent1_output && !summary.has_draft;
  }
  if (quickFilter === "needs_agent3") {
    return summary.has_draft && !summary.has_agent3_verdict;
  }
  if (quickFilter === "approved") {
    return summary.computed_stage === "approved";
  }
  if (quickFilter === "needs_review") {
    return summary.computed_stage === "needs_review";
  }
  return true;
}

function nextMissingAction(lead: Lead): LeadAction | null {
  const summary = resolveLeadPipeline(lead);
  if (!summary.has_snapshot) {
    return "ingest";
  }
  if (!summary.has_agent1_output) {
    return "agent1";
  }
  if (!summary.has_draft) {
    return "agent2";
  }
  if (!summary.has_agent3_verdict) {
    return "agent3";
  }
  return null;
}

function actionLabel(action: LeadAction): string {
  if (action === "ingest") {
    return "Bulk Ingest Website";
  }
  if (action === "agent1") {
    return "Run Research";
  }
  if (action === "agent2") {
    return "Generate Drafts";
  }
  if (action === "agent3") {
    return "Verify Drafts";
  }
  return "Bulk Refresh";
}

function isReadyOrDone(lead: Lead): boolean {
  const stage = resolveLeadPipeline(lead).computed_stage;
  return ["approved", "needs_review", "sent", "replied", "converted", "archived"].includes(stage);
}

export default function LeadsPage() {
  const router = useRouter();
  const [leadList, setLeadList] = useState<LeadListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [rowActionState, setRowActionState] = useState<Record<string, { ingest: boolean; runAi: boolean }>>({});
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [bulkProgress, setBulkProgress] = useState<{ label: string; completed: number; total: number } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [statusInput, setStatusInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearchInput = useDebouncedValue(searchInput, 400);

  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [searchFilter, setSearchFilter] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");

  const isBulkRunning = bulkProgress !== null;

  async function fetchRows(nextOffset: number, nextStatus?: string, nextSearch?: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const result = await getLeads(PAGE_SIZE, nextOffset, nextStatus, nextSearch);
      setLeadList(result);
    } catch (fetchError) {
      setError(getErrorMessage(fetchError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchRows(offset, statusFilter, searchFilter);
  }, [offset, statusFilter, searchFilter]);

  useEffect(() => {
    setSearchFilter(debouncedSearchInput.trim() || undefined);
    setOffset(0);
  }, [debouncedSearchInput]);

  function onApplyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const normalizedStatus = statusInput || undefined;
    setStatusFilter(normalizedStatus);
    setOffset(0);
  }

  const leads: Lead[] = leadList?.items ?? [];
  const visibleLeads = useMemo(() => leads.filter((lead) => matchesQuickFilter(lead, quickFilter)), [leads, quickFilter]);
  const visibleLeadIdSet = useMemo(() => new Set(visibleLeads.map((lead) => lead.id)), [visibleLeads]);
  const selectedVisibleIds = useMemo(() => selectedLeadIds.filter((id) => visibleLeadIdSet.has(id)), [selectedLeadIds, visibleLeadIdSet]);
  const allVisibleSelected = visibleLeads.length > 0 && selectedVisibleIds.length === visibleLeads.length;

  useEffect(() => {
    setSelectedLeadIds((prev) => prev.filter((id) => visibleLeadIdSet.has(id)));
  }, [visibleLeadIdSet]);

  const stageCounts = useMemo(() => {
    const counts = {
      total: leads.length,
      imported: 0,
      researching: 0,
      researched: 0,
      draft_ready: 0,
      needs_review: 0,
      approved: 0,
      sent: 0,
      archived: 0
    };

    leads.forEach((lead) => {
      const summary = resolveLeadPipeline(lead);
      const stage = summary.computed_stage;
      if (["sent", "replied", "converted"].includes(stage)) {
        counts.sent += 1;
      } else if (stage === "archived") {
        counts.archived += 1;
      } else if (stage === "approved") {
        counts.approved += 1;
      } else if (stage === "needs_review") {
        counts.needs_review += 1;
      } else if (stage === "draft_ready" || stage === "drafting") {
        counts.draft_ready += 1;
      } else if (stage === "researched") {
        counts.researched += 1;
      } else if (stage === "researching") {
        counts.researching += 1;
      } else {
        counts.imported += 1;
      }
    });

    return counts;
  }, [leads]);

  function toggleSelectLead(leadId: string): void {
    setSelectedLeadIds((prev) => (prev.includes(leadId) ? prev.filter((id) => id !== leadId) : [...prev, leadId]));
  }

  function toggleSelectAllVisible(): void {
    if (allVisibleSelected) {
      setSelectedLeadIds((prev) => prev.filter((id) => !visibleLeadIdSet.has(id)));
      return;
    }
    setSelectedLeadIds((prev) => {
      const next = new Set(prev);
      visibleLeads.forEach((lead) => next.add(lead.id));
      return Array.from(next);
    });
  }

  async function executeAction(leadId: string, action: LeadAction): Promise<void> {
    if (action === "ingest") {
      await ingestWebsite(leadId);
      return;
    }
    if (action === "agent1") {
      await runAgent1(leadId);
      return;
    }
    if (action === "agent2") {
      await runAgent2(leadId);
      return;
    }
    if (action === "agent3") {
      await runAgent3(leadId);
      return;
    }
    await getLatestContext(leadId);
  }

  async function runIngest(leadId: string): Promise<void> {
    if (isBulkRunning) {
      return;
    }
    setRowActionState((prev) => ({ ...prev, [leadId]: { ingest: true, runAi: false } }));
    setError(null);
    setActionMessage(null);
    try {
      await executeAction(leadId, "ingest");
      setActionMessage("Website ingestion completed.");
      await fetchRows(offset, statusFilter, searchFilter);
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setRowActionState((prev) => ({ ...prev, [leadId]: { ingest: false, runAi: false } }));
    }
  }

  async function runNextAiStep(leadId: string): Promise<void> {
    if (isBulkRunning) {
      return;
    }
    const lead = leads.find((item) => item.id === leadId);
    if (!lead) {
      return;
    }
    const nextAction = nextMissingAction(lead);
    if (!nextAction) {
      setActionMessage("Lead already reached final pipeline stage.");
      return;
    }
    if (nextAction === "ingest" && !lead.website_url) {
      setError("Cannot run pipeline: website URL is missing.");
      return;
    }

    setRowActionState((prev) => ({ ...prev, [leadId]: { ingest: false, runAi: true } }));
    setError(null);
    setActionMessage(null);
    try {
      await executeAction(leadId, nextAction);
      setActionMessage(`${nextAction === "ingest" ? "Ingest Website" : `Run ${nextAction.toUpperCase()}`} completed.`);
      await fetchRows(offset, statusFilter, searchFilter);
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setRowActionState((prev) => ({ ...prev, [leadId]: { ingest: false, runAi: false } }));
    }
  }

  async function runBulk(action: LeadAction): Promise<void> {
    const selectedLeads = visibleLeads.filter((lead) => selectedVisibleIds.includes(lead.id));
    if (selectedLeads.length === 0) {
      return;
    }

    setError(null);
    setActionMessage(null);
    const label = actionLabel(action);
    setBulkProgress({ label, completed: 0, total: selectedLeads.length });

    let succeeded = 0;
    let failed = 0;
    const failures: string[] = [];

    for (let index = 0; index < selectedLeads.length; index += 1) {
      const lead = selectedLeads[index];
      if (action === "ingest" && !lead.website_url) {
        failed += 1;
        failures.push(`${lead.company}: missing website URL`);
        setBulkProgress({ label, completed: index + 1, total: selectedLeads.length });
        continue;
      }
      if ((action === "agent1" || action === "agent2" || action === "agent3") && isReadyOrDone(lead)) {
        failed += 1;
        failures.push(`${lead.company}: pipeline already completed`);
        setBulkProgress({ label, completed: index + 1, total: selectedLeads.length });
        continue;
      }
      try {
        await executeAction(lead.id, action);
        succeeded += 1;
      } catch (actionError) {
        failed += 1;
        failures.push(`${lead.company}: ${getErrorMessage(actionError)}`);
      }
      setBulkProgress({ label, completed: index + 1, total: selectedLeads.length });
    }

    await fetchRows(offset, statusFilter, searchFilter);
    setBulkProgress(null);
    setActionMessage(`${label}: ${succeeded} succeeded, ${failed} failed.`);
    if (failures.length > 0) {
      const remaining = failures.length - 3;
      setError(`${failures.slice(0, 3).join(" | ")}${remaining > 0 ? ` | +${remaining} more` : ""}`);
    }
  }

  async function runBulkDelete(): Promise<void> {
    if (selectedVisibleIds.length === 0) return;
    setDeleting(true);
    setError(null);
    setActionMessage(null);
    try {
      const result = await deleteLeadsBulk(selectedVisibleIds);
      setActionMessage(`Deleted ${result.deleted_count} lead(s).`);
      setSelectedLeadIds([]);
      await fetchRows(offset, statusFilter, searchFilter);
    } catch (deleteError) {
      setError(getErrorMessage(deleteError));
    } finally {
      setDeleting(false);
    }
  }

  const canGoPrev = offset > 0;
  const canGoNext = useMemo(() => {
    if (!leadList) {
      return false;
    }
    return offset + PAGE_SIZE < leadList.total;
  }, [leadList, offset]);

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Lead Command Center</h1>
            <p className="page-subtitle">Manage leads and drive each account through the AI outreach pipeline.</p>
          </div>
          <span className="stat-pill">Visible: {visibleLeads.length}</span>
        </header>
      </section>

      <section className="card surface-metrics stack">
        <h2 className="section-title">Pipeline Overview</h2>
        <div className="pipeline-lane pipeline-lane-clean">
          <div className="pipeline-stage pipeline-stage-total">
            <div className="metric-label">Total</div>
            <div className="metric-value">{stageCounts.total}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Imported</div>
            <div className="metric-value">{stageCounts.imported}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Researching</div>
            <div className="metric-value">{stageCounts.researching}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Researched</div>
            <div className="metric-value">{stageCounts.researched}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Draft Ready</div>
            <div className="metric-value">{stageCounts.draft_ready}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Needs Review</div>
            <div className="metric-value">{stageCounts.needs_review}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Approved</div>
            <div className="metric-value">{stageCounts.approved}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Sent</div>
            <div className="metric-value">{stageCounts.sent}</div>
          </div>
          <div className="pipeline-stage">
            <div className="metric-label">Archived</div>
            <div className="metric-value">{stageCounts.archived}</div>
          </div>
        </div>
      </section>

      <LeadListFilters
        statusInput={statusInput}
        searchInput={searchInput}
        activeQuickFilter={quickFilter}
        onStatusChange={setStatusInput}
        onSearchChange={setSearchInput}
        onQuickFilterChange={(value) => setQuickFilter(value as QuickFilter)}
        onApplyFilters={onApplyFilters}
      />

      <div className="card surface-table stack">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Lead List</h2>
          <button type="button" className="btn-secondary" disabled={visibleLeads.length === 0 || isBulkRunning} onClick={toggleSelectAllVisible}>
            {allVisibleSelected ? "Unselect All Visible" : "Select All Visible"}
          </button>
        </div>

        {selectedVisibleIds.length > 0 ? (
          <div className="bulk-action-bar">
            <div>
              <strong>{selectedVisibleIds.length} selected</strong>
              {bulkProgress ? (
                <div className="muted" style={{ marginTop: 6 }}>
                  {bulkProgress.label}: {bulkProgress.completed}/{bulkProgress.total}
                </div>
              ) : null}
            </div>
            <div className="inline-actions">
              <button type="button" className="btn-primary" disabled={isBulkRunning} onClick={() => void runBulk("ingest")}>
                Bulk Ingest Website
              </button>
              <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => void runBulk("agent1")}>
                Run Research
              </button>
              <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => void runBulk("agent2")}>
                Generate Drafts
              </button>
              <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => void runBulk("agent3")}>
                Verify Drafts
              </button>
              <button type="button" className="btn-danger" disabled={isBulkRunning || deleting} onClick={() => void runBulkDelete()}>
                {deleting ? "Deleting..." : "Delete Selected"}
              </button>
              <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => setSelectedLeadIds([])}>
                Clear Selection
              </button>
            </div>
          </div>
        ) : null}

        {loading ? <Spinner label="Refreshing leads..." /> : null}
        {error ? <div className="error">{error}</div> : null}
        {actionMessage ? <div className="success">{actionMessage}</div> : null}

        <LeadListTable
          leads={visibleLeads}
          loading={loading}
          bulkRunning={isBulkRunning}
          selectedLeadIds={selectedLeadIds}
          allVisibleSelected={allVisibleSelected}
          rowActionState={rowActionState}
          onToggleSelectLead={toggleSelectLead}
          onToggleSelectAllVisible={toggleSelectAllVisible}
          onSelectLead={(id) => router.push(`/leads/${id}`)}
          onIngestLead={(id) => void runIngest(id)}
          onRunAiLead={(id) => void runNextAiStep(id)}
        />
        <LeadListPagination
          canGoPrev={canGoPrev}
          canGoNext={canGoNext}
          total={leadList?.total ?? 0}
          loading={loading || isBulkRunning}
          onPrev={() => setOffset((prev) => prev - PAGE_SIZE)}
          onNext={() => setOffset((prev) => prev + PAGE_SIZE)}
        />
      </div>
    </div>
  );
}
