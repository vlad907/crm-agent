"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { LeadListFilters } from "@/src/components/leads/list/LeadListFilters";
import { LeadListPagination } from "@/src/components/leads/list/LeadListPagination";
import { LeadListTable } from "@/src/components/leads/list/LeadListTable";
import { ApiError, getLeads } from "@/src/lib/api";
import { Lead, LeadListResponse } from "@/src/lib/types";

const PAGE_SIZE = 20;

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function LeadsPage() {
  const router = useRouter();
  const [leadList, setLeadList] = useState<LeadListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusInput, setStatusInput] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [searchFilter, setSearchFilter] = useState<string | undefined>(undefined);
  const [offset, setOffset] = useState(0);

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

  function onApplyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const normalizedStatus = statusInput || undefined;
    const normalizedSearch = searchInput.trim() || undefined;
    setStatusFilter(normalizedStatus);
    setSearchFilter(normalizedSearch);
    setOffset(0);
  }

  const leads: Lead[] = leadList?.items ?? [];
  const newCount = leads.filter((lead) => (lead.status ?? "").toLowerCase() === "new").length;
  const draftCount = leads.filter((lead) => (lead.status ?? "").toLowerCase() === "draft").length;
  const sendCount = leads.filter((lead) => (lead.status ?? "").toLowerCase() === "send").length;
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
          <span className="stat-pill">Visible: {leads.length}</span>
        </header>
      </section>

      <section className="stats-grid">
        <div className="metric-card">
          <div className="metric-label">Total Matches</div>
          <div className="metric-value">{leadList?.total ?? 0}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">New</div>
          <div className="metric-value">{newCount}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Draft</div>
          <div className="metric-value">{draftCount}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Ready To Send</div>
          <div className="metric-value">{sendCount}</div>
        </div>
      </section>

      <LeadListFilters
        statusInput={statusInput}
        searchInput={searchInput}
        onStatusChange={setStatusInput}
        onSearchChange={setSearchInput}
        onApplyFilters={onApplyFilters}
      />

      <div className="card stack">
        <h2>Lead List</h2>
        {error ? <div className="error">{error}</div> : null}
        <LeadListTable leads={leads} loading={loading} onSelectLead={(id) => router.push(`/leads/${id}`)} />
        <LeadListPagination
          canGoPrev={canGoPrev}
          canGoNext={canGoNext}
          total={leadList?.total ?? 0}
          loading={loading}
          onPrev={() => setOffset((prev) => prev - PAGE_SIZE)}
          onNext={() => setOffset((prev) => prev + PAGE_SIZE)}
        />
      </div>
    </div>
  );
}
