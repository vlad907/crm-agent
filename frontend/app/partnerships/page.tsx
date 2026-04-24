"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Spinner } from "@/src/components/Spinner";
import {
  deletePartnerCandidate,
  discoverPartner,
  generatePartnerOutreach,
  getPartnerCandidates,
  searchPartners,
  sendPartnerOutreach,
  updatePartnerCandidate,
} from "@/src/lib/api";
import type { PartnerCandidate } from "@/src/lib/types";

function fitScoreColor(score: number | null): string {
  if (score === null) return "";
  if (score >= 0.7) return "var(--green)";
  if (score >= 0.4) return "var(--amber)";
  return "var(--text-muted)";
}

function statusBadge(status: string): string {
  const map: Record<string, string> = {
    new: "stage-active", reviewed: "stage-done", contacted: "stage-done",
    replied: "stage-done", active_partner: "stage-done", ignored: "stage-pending",
  };
  return map[status] || "";
}

const STATUS_OPTIONS = ["new", "reviewed", "contacted", "replied", "active_partner", "ignored"];

export default function PartnershipsPage() {
  const [candidates, setCandidates] = useState<PartnerCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const [searchIntent, setSearchIntent] = useState("");
  const [searching, setSearching] = useState(false);
  const [maxResults, setMaxResults] = useState(10);
  const [minFit, setMinFit] = useState(0.3);

  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discovering, setDiscovering] = useState(false);
  const [showManual, setShowManual] = useState(false);

  const [generatingOutreach, setGeneratingOutreach] = useState(false);
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<PartnerCandidate | null>(null);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkProgress, setBulkProgress] = useState<{ label: string; completed: number; total: number } | null>(null);

  const isBulkRunning = bulkProgress !== null;

  const fetchCandidates = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await getPartnerCandidates(50, 0);
      setCandidates(data.items); setTotal(data.total);
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to load candidates"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void fetchCandidates(); }, [fetchCandidates]);

  const allSelected = candidates.length > 0 && candidates.every(c => selectedIds.has(c.id));

  function toggleSelect(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(candidates.map(c => c.id)));
    }
  }

  async function handleSearch() {
    if (!searchIntent.trim()) return;
    setSearching(true); setError(null); setMessage(null);
    try {
      const result = await searchPartners({
        discovery_intent: searchIntent,
        max_results: maxResults,
        min_fit_score: minFit,
      });
      const p = result.progress;
      setMessage(
        `Search complete: ${p.total_found} found, ${p.analyzed} analyzed, ${p.qualified} qualified` +
        (p.errors > 0 ? `, ${p.errors} errors` : "")
      );
      await fetchCandidates();
    } catch (e) { setError(e instanceof Error ? e.message : "Search failed"); }
    finally { setSearching(false); }
  }

  async function handleDiscover() {
    if (!discoveryQuery.trim()) return;
    setDiscovering(true); setError(null); setMessage(null);
    try {
      const result = await discoverPartner({ query: discoveryQuery });
      setMessage(`Discovered: ${result.company_name} (fit: ${((result.fit_score || 0) * 100).toFixed(0)}%)`);
      setDiscoveryQuery(""); await fetchCandidates();
    } catch (e) { setError(e instanceof Error ? e.message : "Discovery failed"); }
    finally { setDiscovering(false); }
  }

  async function handleStatusChange(id: string, newStatus: string) {
    try {
      const updated = await updatePartnerCandidate(id, { status: newStatus });
      await fetchCandidates();
      if (selectedCandidate?.id === id) setSelectedCandidate(updated);
    } catch (e) { setError(e instanceof Error ? e.message : "Update failed"); }
  }

  async function handleDelete(id: string) {
    try {
      await deletePartnerCandidate(id);
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
      setSelectedIds(prev => { const n = new Set(prev); n.delete(id); return n; });
      await fetchCandidates();
    } catch (e) { setError(e instanceof Error ? e.message : "Delete failed"); }
  }

  async function handleGenerateOutreach() {
    if (!selectedCandidate) return;
    setGeneratingOutreach(true); setError(null);
    try {
      const updated = await generatePartnerOutreach(selectedCandidate.id);
      setSelectedCandidate(updated); setMessage("Outreach draft generated"); await fetchCandidates();
    } catch (e) { setError(e instanceof Error ? e.message : "Outreach generation failed"); }
    finally { setGeneratingOutreach(false); }
  }

  async function handleSendOutreach() {
    if (!selectedCandidate) return;
    setSendingOutreach(true); setError(null);
    try {
      const updated = await sendPartnerOutreach(selectedCandidate.id);
      setSelectedCandidate(updated); setMessage("Gmail draft created"); await fetchCandidates();
    } catch (e) { setError(e instanceof Error ? e.message : "Send outreach failed"); }
    finally { setSendingOutreach(false); }
  }

  async function bulkGenerateOutreach() {
    const targets = candidates.filter(c => selectedIds.has(c.id));
    if (!targets.length) return;
    setError(null); setMessage(null);
    setBulkProgress({ label: "Generating outreach", completed: 0, total: targets.length });
    let ok = 0, fail = 0;
    for (let i = 0; i < targets.length; i++) {
      try {
        await generatePartnerOutreach(targets[i].id);
        ok++;
      } catch { fail++; }
      setBulkProgress({ label: "Generating outreach", completed: i + 1, total: targets.length });
    }
    setBulkProgress(null);
    await fetchCandidates();
    setMessage(`Bulk outreach: ${ok} generated, ${fail} failed.`);
  }

  async function bulkSendOutreach() {
    const targets = candidates.filter(c => selectedIds.has(c.id) && c.outreach_subject);
    if (!targets.length) { setError("No selected candidates have outreach drafts."); return; }
    setError(null); setMessage(null);
    setBulkProgress({ label: "Creating Gmail drafts", completed: 0, total: targets.length });
    let ok = 0, fail = 0;
    for (let i = 0; i < targets.length; i++) {
      try {
        await sendPartnerOutreach(targets[i].id);
        ok++;
      } catch { fail++; }
      setBulkProgress({ label: "Creating Gmail drafts", completed: i + 1, total: targets.length });
    }
    setBulkProgress(null);
    await fetchCandidates();
    setMessage(`Bulk send: ${ok} drafts created, ${fail} failed.`);
  }

  async function bulkDelete() {
    const targets = [...selectedIds];
    if (!targets.length) return;
    setError(null); setMessage(null);
    setBulkProgress({ label: "Deleting", completed: 0, total: targets.length });
    let ok = 0;
    for (let i = 0; i < targets.length; i++) {
      try {
        await deletePartnerCandidate(targets[i]);
        ok++;
      } catch { /* skip */ }
      setBulkProgress({ label: "Deleting", completed: i + 1, total: targets.length });
    }
    setBulkProgress(null);
    setSelectedIds(new Set());
    if (selectedCandidate && targets.includes(selectedCandidate.id)) setSelectedCandidate(null);
    await fetchCandidates();
    setMessage(`Deleted ${ok} candidate(s).`);
  }

  async function bulkStatusChange(newStatus: string) {
    const targets = [...selectedIds];
    if (!targets.length) return;
    setError(null);
    let ok = 0;
    for (const id of targets) {
      try { await updatePartnerCandidate(id, { status: newStatus }); ok++; } catch { /* skip */ }
    }
    await fetchCandidates();
    setMessage(`Updated ${ok} candidate(s) to "${newStatus.replace(/_/g, " ")}".`);
  }

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    candidates.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1; });
    return counts;
  }, [candidates]);

  const signals = selectedCandidate?.extracted_signals as Record<string, string | string[] | number | null> | null;
  const reasons = ((signals?.reasons || []) as unknown as string[]);

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Partnership Discovery</h1>
            <p className="page-subtitle">Find vendors, MSPs, and subcontracting partners using AI web search.</p>
          </div>
          <span className="stat-pill">Total: {total}</span>
        </header>
      </section>

      {/* Status overview */}
      {candidates.length > 0 && (
        <section className="stats-grid">
          <div className="metric-card">
            <div className="metric-label">Total</div>
            <div className="metric-value">{total}</div>
          </div>
          {Object.entries(statusCounts).map(([status, count]) => (
            <div className="metric-card" key={status}>
              <div className="metric-label">{status.replace(/_/g, " ")}</div>
              <div className="metric-value">{count}</div>
            </div>
          ))}
        </section>
      )}

      {/* Automated Search */}
      <section className="card">
        <h2 style={{ marginBottom: 10 }}>Find Partners</h2>
        <p className="muted" style={{ marginBottom: 12, fontSize: ".85rem" }}>
          Describe what kind of partner you&rsquo;re looking for. The system will search the web, crawl company websites, and AI-analyze each one for fit.
        </p>
        <div className="field" style={{ marginBottom: 10 }}>
          <textarea
            value={searchIntent}
            onChange={(e) => setSearchIntent(e.target.value)}
            rows={3}
            placeholder="e.g. National camera installation companies that subcontract to local technicians&#10;e.g. MSPs that need field service partners for network cabling&#10;e.g. Large security system vendors who farm out installation work"
          />
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <label style={{ fontSize: ".78rem", whiteSpace: "nowrap" }}>Max results</label>
            <input type="number" min={3} max={20} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))} style={{ width: 60, fontSize: ".84rem" }} />
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <label style={{ fontSize: ".78rem", whiteSpace: "nowrap" }}>Min fit %</label>
            <input type="number" min={0} max={100} value={Math.round(minFit * 100)} onChange={(e) => setMinFit(Number(e.target.value) / 100)} style={{ width: 60, fontSize: ".84rem" }} />
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={searching || !searchIntent.trim()}
            onClick={() => void handleSearch()}
          >
            {searching ? "Searching & Analyzing..." : "Search for Partners"}
          </button>
        </div>
        {searching && (
          <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
            <Spinner />
            <span className="muted" style={{ fontSize: ".85rem" }}>Searching the web, crawling websites, and running AI analysis on each company. This may take 1-2 minutes...</span>
          </div>
        )}
      </section>

      {/* Manual URL discover */}
      <div style={{ marginBottom: 4 }}>
        <button type="button" onClick={() => setShowManual(!showManual)} style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", fontSize: ".82rem", padding: 0 }}>
          {showManual ? "Hide manual URL analysis" : "Or analyze a specific website URL"}
        </button>
      </div>
      {showManual && (
        <section className="card">
          <div style={{ display: "flex", gap: 10 }}>
            <input
              style={{ flex: 1 }}
              value={discoveryQuery}
              onChange={(e) => setDiscoveryQuery(e.target.value)}
              placeholder="find IT vendors https://example.com"
              onKeyDown={(e) => { if (e.key === "Enter") void handleDiscover(); }}
            />
            <button type="button" className="btn-primary" disabled={discovering || !discoveryQuery.trim()} onClick={() => void handleDiscover()}>
              {discovering ? "Analyzing..." : "Analyze"}
            </button>
          </div>
        </section>
      )}

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      {/* Bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="bulk-action-bar">
          <div>
            <strong>{selectedIds.size} selected</strong>
            {bulkProgress && (
              <div className="muted" style={{ marginTop: 4, fontSize: ".82rem" }}>
                {bulkProgress.label}: {bulkProgress.completed}/{bulkProgress.total}
              </div>
            )}
          </div>
          <div className="inline-actions">
            <button type="button" className="btn-primary" disabled={isBulkRunning} onClick={() => void bulkGenerateOutreach()}>
              Bulk Generate Outreach
            </button>
            <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => void bulkSendOutreach()}>
              Bulk Send Drafts
            </button>
            <select
              disabled={isBulkRunning}
              onChange={(e) => { if (e.target.value) { void bulkStatusChange(e.target.value); e.target.value = ""; } }}
              defaultValue=""
              style={{ fontSize: ".82rem", padding: "6px 10px" }}
            >
              <option value="" disabled>Set Status...</option>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
            </select>
            <button type="button" className="btn-danger" disabled={isBulkRunning} onClick={() => void bulkDelete()}>
              Delete Selected
            </button>
            <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => setSelectedIds(new Set())}>
              Clear
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: selectedCandidate ? "1fr 1fr" : "1fr", gap: 16 }}>
        {/* Candidate list */}
        <section className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 18px 12px" }}>
            <h2>Candidates ({candidates.length})</h2>
            <button
              type="button"
              className="btn-secondary"
              style={{ fontSize: ".78rem", padding: "5px 10px" }}
              disabled={candidates.length === 0}
              onClick={toggleSelectAll}
            >
              {allSelected ? "Unselect All" : "Select All"}
            </button>
          </div>
          <div style={{ maxHeight: "calc(100vh - 500px)", overflowY: "auto", padding: "0 18px 18px" }}>
            {loading && <Spinner label="Loading candidates..." />}
            {!loading && candidates.length === 0 && (
              <p className="muted">No candidates yet. Run a search to get started.</p>
            )}
            {candidates.map((c) => (
              <div
                key={c.id}
                className={`subcard${selectedCandidate?.id === c.id ? " active-thread" : ""}`}
                style={{ marginBottom: 8, cursor: "pointer", padding: "10px 12px" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(c.id)}
                    onChange={() => toggleSelect(c.id)}
                    onClick={(e) => e.stopPropagation()}
                    style={{ width: 16, height: 16, flexShrink: 0 }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }} onClick={() => setSelectedCandidate(c)}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                      <strong style={{ fontSize: ".86rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.company_name}</strong>
                      <span className={`stage-pill ${statusBadge(c.status)}`} style={{ fontSize: ".68rem", flexShrink: 0, marginLeft: 8 }}>{c.status.replace(/_/g, " ")}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: ".78rem" }}>
                      <span className="muted">{c.partnership_type || "unclassified"}</span>
                      {c.fit_score !== null && (
                        <span style={{ fontWeight: 600, color: fitScoreColor(c.fit_score) }}>{(c.fit_score * 100).toFixed(0)}% fit</span>
                      )}
                    </div>
                    {c.outreach_status && (
                      <span className="muted" style={{ fontSize: ".68rem" }}>outreach: {c.outreach_status}</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Detail panel */}
        {selectedCandidate && (
          <section className="card" style={{ maxHeight: "calc(100vh - 500px)", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <h2 style={{ fontSize: "1.1rem" }}>{selectedCandidate.company_name}</h2>
              <div className="inline-actions">
                <select value={selectedCandidate.status} onChange={(e) => void handleStatusChange(selectedCandidate.id, e.target.value)} style={{ fontSize: ".82rem", padding: "4px 8px" }}>
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                </select>
                <button type="button" className="btn-danger" style={{ fontSize: ".78rem", padding: "4px 10px" }} onClick={() => void handleDelete(selectedCandidate.id)}>Delete</button>
              </div>
            </div>

            <div className="stack" style={{ gap: 10 }}>
              {selectedCandidate.website && (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Website</strong>
                  <div><a href={selectedCandidate.website} target="_blank" rel="noopener noreferrer" style={{ color: "var(--blue)", fontSize: ".88rem" }}>{selectedCandidate.website}</a></div>
                </div>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Partnership Type</strong>
                  <div style={{ fontWeight: 600 }}>{selectedCandidate.partnership_type || "—"}</div>
                </div>
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Fit Score</strong>
                  <div style={{ fontWeight: 700, fontSize: "1.2rem", color: fitScoreColor(selectedCandidate.fit_score) }}>
                    {selectedCandidate.fit_score !== null ? `${(selectedCandidate.fit_score * 100).toFixed(0)}%` : "—"}
                  </div>
                </div>
              </div>

              {signals?.company_summary && (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Company Summary</strong>
                  <div style={{ fontSize: ".86rem", lineHeight: 1.5 }}>{String(signals.company_summary)}</div>
                </div>
              )}

              {(signals?.search_description || signals?.search_relevance) ? (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Why This Match</strong>
                  <div style={{ fontSize: ".84rem", color: "var(--text-secondary)" }}>{String(signals?.search_relevance ?? signals?.search_description ?? "")}</div>
                </div>
              ) : null}

              {reasons.length > 0 && (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Fit Reasons</strong>
                  <ul style={{ margin: "6px 0 0 16px", fontSize: ".86rem", lineHeight: 1.6 }}>
                    {reasons.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}

              {selectedCandidate.recommended_outreach_angle && (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Recommended Outreach Angle</strong>
                  <div style={{ fontSize: ".86rem" }}>{selectedCandidate.recommended_outreach_angle}</div>
                </div>
              )}

              {selectedCandidate.contact_emails?.length ? (
                <div className="subcard">
                  <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Contact Emails</strong>
                  <div style={{ fontSize: ".86rem" }}>{selectedCandidate.contact_emails.join(", ")}</div>
                </div>
              ) : null}

              {/* Outreach section */}
              <div className="subcard">
                <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Partner Outreach</strong>
                {selectedCandidate.outreach_subject ? (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: ".82rem", fontWeight: 600, marginBottom: 4 }}>{selectedCandidate.outreach_subject}</div>
                    <div style={{ fontSize: ".82rem", whiteSpace: "pre-wrap", lineHeight: 1.5, background: "var(--bg)", padding: 10, borderRadius: "var(--radius-sm)", border: "1px solid var(--line)" }}>
                      {selectedCandidate.outreach_body}
                    </div>
                  </div>
                ) : (
                  <p className="muted" style={{ fontSize: ".82rem", marginTop: 4 }}>No outreach draft yet.</p>
                )}
                <div className="inline-actions" style={{ marginTop: 10, gap: 8 }}>
                  <button type="button" className="btn-secondary" disabled={generatingOutreach} onClick={() => void handleGenerateOutreach()}>
                    {generatingOutreach ? "Generating..." : selectedCandidate.outreach_subject ? "Regenerate" : "Generate Outreach"}
                  </button>
                  {selectedCandidate.outreach_subject && selectedCandidate.contact_emails?.length ? (
                    <button type="button" className="btn-primary" disabled={sendingOutreach} onClick={() => void handleSendOutreach()}>
                      {sendingOutreach ? "Creating..." : "Create Gmail Draft"}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
