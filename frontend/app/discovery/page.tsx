"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { LocationAutocompleteField } from "@/src/components/LocationAutocompleteField";
import { Spinner } from "@/src/components/Spinner";
import {
  ApiError,
  convertPartnersToLeads,
  convertProspectsToLeads,
  deletePartnerCandidate,
  deleteProspectsBulk,
  discoverPartner,
  generatePartnerOutreach,
  getPartnerCandidates,
  getProspects,
  getWorkspaceAiStrategy,
  runProspectSearch,
  searchPartners,
  sendPartnerOutreach,
  updatePartnerCandidate,
} from "@/src/lib/api";
import { useDebouncedValue } from "@/src/lib/hooks";
import type {
  PartnerCandidate,
  Prospect,
  ProspectListResponse,
} from "@/src/lib/types";

type Tab = "local" | "partner";

const PAGE_SIZE = 25;
const METERS_PER_MILE = 1609.344;
const MAX_RADIUS_METERS = 50000;
function milesToMeters(miles: number) {
  return Math.round(miles * METERS_PER_MILE);
}

function getErr(e: unknown): string {
  return e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unexpected error";
}

function renderStars(rating: number | null) {
  if (rating == null) return null;
  const full = Math.round(rating);
  return (
    <span className="prospect-card-stars" title={`${rating.toFixed(1)} stars`}>
      {"★".repeat(full)}{"☆".repeat(5 - full)}
    </span>
  );
}

function fitBadgeClass(score: number): string {
  if (score >= 0.7) return "fit-badge fit-badge-high";
  if (score >= 0.4) return "fit-badge fit-badge-mid";
  return "fit-badge fit-badge-low";
}

const PARTNER_STATUS_OPTIONS = ["new", "reviewed", "contacted", "replied", "active_partner", "ignored", "converted"];

export default function DiscoveryPage() {
  const [activeTab, setActiveTab] = useState<Tab>("local");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // ─── Local Search state ───
  const [prospectList, setProspectList] = useState<ProspectListResponse | null>(null);
  const [loadingProspects, setLoadingProspects] = useState(true);
  const [selectedProspectIds, setSelectedProspectIds] = useState<Set<string>>(new Set());
  const [offset, setOffset] = useState(0);
  const [statusInput, setStatusInput] = useState("");
  const [categoryInput, setCategoryInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput, 400);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [searchFilter, setSearchFilter] = useState<string | undefined>();
  const [runCategories, setRunCategories] = useState("plumber,electrician");
  const [runLocation, setRunLocation] = useState("Chico, CA");
  const [runRadius, setRunRadius] = useState("6");
  const [runMissingOnly, setRunMissingOnly] = useState(false);
  const [requireWebsite, setRequireWebsite] = useState(true);
  const [runningSearch, setRunningSearch] = useState(false);
  const [converting, setConverting] = useState(false);
  const [deletingProspects, setDeletingProspects] = useState(false);
  const [presets, setPresets] = useState<Array<{ label: string; value: string }>>([]);
  const [activePreset, setActivePreset] = useState("");

  // ─── Partner Search state ───
  const [candidates, setCandidates] = useState<PartnerCandidate[]>([]);
  const [partnerTotal, setPartnerTotal] = useState(0);
  const [loadingPartners, setLoadingPartners] = useState(true);
  const [selectedPartnerIds, setSelectedPartnerIds] = useState<Set<string>>(new Set());
  const [searchIntent, setSearchIntent] = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [minFit, setMinFit] = useState(0.3);
  const [searchingPartners, setSearchingPartners] = useState(false);
  const [manualUrl, setManualUrl] = useState("");
  const [showManual, setShowManual] = useState(false);
  const [discoveringManual, setDiscoveringManual] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<PartnerCandidate | null>(null);
  const [generatingOutreach, setGeneratingOutreach] = useState(false);
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{ label: string; done: number; total: number } | null>(null);
  const [convertingPartners, setConvertingPartners] = useState(false);

  // ─── Fetch prospect rows ───
  const fetchProspects = useCallback(async (o: number, st?: string, cat?: string, q?: string) => {
    setLoadingProspects(true); setError(null);
    try {
      const r = await getProspects(PAGE_SIZE, o, st, cat, q);
      setProspectList(r);
    } catch (e) { setError(getErr(e)); }
    finally { setLoadingProspects(false); }
  }, []);

  useEffect(() => { void fetchProspects(offset, statusFilter, categoryFilter, searchFilter); }, [offset, statusFilter, categoryFilter, searchFilter, fetchProspects]);
  useEffect(() => { setSearchFilter(debouncedSearch.trim() || undefined); setOffset(0); }, [debouncedSearch]);
  useEffect(() => {
    getWorkspaceAiStrategy()
      .then((s) => {
        const gen = s.generated_strategy;
        if (gen?.target_categories?.length) {
          const byName = new Map<string, string>();
          for (const ic of gen.ideal_customers ?? []) if (ic?.category && ic?.display_name) byName.set(ic.category, ic.display_name);
          setPresets(gen.target_categories.map((cat: string) => ({ label: byName.get(cat) ?? cat.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()), value: cat })));
        }
      })
      .catch(() => {});
  }, []);

  // ─── Fetch partner candidates ───
  const fetchPartners = useCallback(async () => {
    setLoadingPartners(true); setError(null);
    try {
      const d = await getPartnerCandidates(100, 0);
      setCandidates(d.items); setPartnerTotal(d.total);
    } catch (e) { setError(getErr(e)); }
    finally { setLoadingPartners(false); }
  }, []);

  useEffect(() => { void fetchPartners(); }, [fetchPartners]);

  // ─── Prospect actions ───
  const prospects = prospectList?.items ?? [];
  const totalProspects = prospectList?.total ?? 0;
  const allProspectsSelected = prospects.length > 0 && prospects.every(p => selectedProspectIds.has(p.id));

  function toggleProspect(id: string) {
    setSelectedProspectIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }
  function toggleAllProspects() {
    if (allProspectsSelected) setSelectedProspectIds(new Set());
    else setSelectedProspectIds(new Set(prospects.map(p => p.id)));
  }

  function applyFilters(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setStatusFilter(statusInput.trim() || undefined);
    setCategoryFilter(categoryInput.trim() || undefined);
    setOffset(0);
  }

  async function onRunSearch(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const cats = runCategories.split(",").map(s => s.trim()).filter(Boolean);
    const miles = parseFloat(runRadius);
    if (!cats.length) { setError("Enter at least one category."); return; }
    if (!runLocation.trim()) { setError("Location is required."); return; }
    if (!Number.isFinite(miles) || miles <= 0) { setError("Radius must be a positive number."); return; }
    const meters = milesToMeters(miles);
    if (meters > MAX_RADIUS_METERS) { setError("Radius too large (max ~31 miles)."); return; }
    setRunningSearch(true); setError(null); setMessage(null);
    try {
      const r = await runProspectSearch({ categories: cats, location: runLocation.trim(), radius: meters, missing_website_only: runMissingOnly, keyword: "business" });
      setMessage(`Fetched ${r.fetched_count} prospects. Imported ${r.import_result.imported_count}, skipped ${r.import_result.skipped_count}.`);
      setOffset(0); await fetchProspects(0, statusFilter, categoryFilter, searchFilter);
    } catch (e) { setError(getErr(e)); }
    finally { setRunningSearch(false); }
  }

  async function onConvertProspects() {
    if (!selectedProspectIds.size) return;
    setConverting(true); setError(null); setMessage(null);
    try {
      const r = await convertProspectsToLeads({ prospect_ids: [...selectedProspectIds], require_website: requireWebsite });
      setMessage(`Converted ${r.converted_count} to leads. Skipped ${r.skipped_count}.`);
      setSelectedProspectIds(new Set());
      await fetchProspects(0, statusFilter, categoryFilter, searchFilter);
    } catch (e) { setError(getErr(e)); }
    finally { setConverting(false); }
  }

  async function onDeleteProspects() {
    if (!selectedProspectIds.size) return;
    setDeletingProspects(true); setError(null); setMessage(null);
    try {
      const r = await deleteProspectsBulk([...selectedProspectIds]);
      setMessage(`Deleted ${r.deleted_count} prospect(s).`);
      setSelectedProspectIds(new Set());
      await fetchProspects(0, statusFilter, categoryFilter, searchFilter);
    } catch (e) { setError(getErr(e)); }
    finally { setDeletingProspects(false); }
  }

  function onExportCsv() {
    const items = prospects.filter(p => selectedProspectIds.has(p.id));
    if (!items.length) return;
    const headers = ["company_name", "category", "rating", "review_count", "address", "phone", "website_url", "source", "import_status"];
    const rows = items.map(p =>
      [p.company_name, p.category ?? "", p.rating ?? "", p.review_count ?? "", p.address, p.phone ?? "", p.website_url ?? "", p.source, p.import_status]
        .map(v => `"${String(v).replaceAll('"', '""')}"`)
        .join(",")
    );
    const blob = new Blob([headers.join(",") + "\n" + rows.join("\n")], { type: "text/csv" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "prospects-export.csv"; link.click();
    setMessage(`Exported ${items.length} prospects.`);
  }

  // ─── Partner actions ───
  const allPartnersSelected = candidates.length > 0 && candidates.every(c => selectedPartnerIds.has(c.id));
  function togglePartner(id: string) {
    setSelectedPartnerIds(prev => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }
  function toggleAllPartners() {
    if (allPartnersSelected) setSelectedPartnerIds(new Set());
    else setSelectedPartnerIds(new Set(candidates.map(c => c.id)));
  }

  async function handlePartnerSearch() {
    if (!searchIntent.trim()) return;
    setSearchingPartners(true); setError(null); setMessage(null);
    try {
      const r = await searchPartners({ discovery_intent: searchIntent, max_results: maxResults, min_fit_score: minFit });
      setMessage(`Found ${r.progress.total_found}, analyzed ${r.progress.analyzed}, qualified ${r.progress.qualified}${r.progress.errors > 0 ? `, ${r.progress.errors} errors` : ""}`);
      await fetchPartners();
    } catch (e) { setError(getErr(e)); }
    finally { setSearchingPartners(false); }
  }

  async function handleManualDiscover() {
    if (!manualUrl.trim()) return;
    setDiscoveringManual(true); setError(null); setMessage(null);
    try {
      const r = await discoverPartner({ query: manualUrl });
      setMessage(`Discovered: ${r.company_name} (fit: ${((r.fit_score || 0) * 100).toFixed(0)}%)`);
      setManualUrl(""); await fetchPartners();
    } catch (e) { setError(getErr(e)); }
    finally { setDiscoveringManual(false); }
  }

  async function handleDeletePartner(id: string) {
    try {
      await deletePartnerCandidate(id);
      if (selectedCandidate?.id === id) setSelectedCandidate(null);
      setSelectedPartnerIds(prev => { const n = new Set(prev); n.delete(id); return n; });
      await fetchPartners();
    } catch (e) { setError(getErr(e)); }
  }

  async function handleGenerateOutreach() {
    if (!selectedCandidate) return;
    setGeneratingOutreach(true); setError(null);
    try {
      const u = await generatePartnerOutreach(selectedCandidate.id);
      setSelectedCandidate(u); setMessage("Outreach draft generated."); await fetchPartners();
    } catch (e) { setError(getErr(e)); }
    finally { setGeneratingOutreach(false); }
  }

  async function handleSendOutreach() {
    if (!selectedCandidate) return;
    setSendingOutreach(true); setError(null);
    try {
      const u = await sendPartnerOutreach(selectedCandidate.id);
      setSelectedCandidate(u); setMessage("Gmail draft created."); await fetchPartners();
    } catch (e) { setError(getErr(e)); }
    finally { setSendingOutreach(false); }
  }

  async function bulkGenerateOutreach() {
    const targets = candidates.filter(c => selectedPartnerIds.has(c.id));
    if (!targets.length) return;
    setError(null); setMessage(null);
    setBulkProgress({ label: "Generating outreach", done: 0, total: targets.length });
    let ok = 0;
    for (let i = 0; i < targets.length; i++) {
      try { await generatePartnerOutreach(targets[i].id); ok++; } catch { /* skip */ }
      setBulkProgress({ label: "Generating outreach", done: i + 1, total: targets.length });
    }
    setBulkProgress(null); await fetchPartners();
    setMessage(`Bulk outreach: ${ok}/${targets.length} generated.`);
  }

  async function bulkDeletePartners() {
    const ids = [...selectedPartnerIds];
    if (!ids.length) return;
    setBulkProgress({ label: "Deleting", done: 0, total: ids.length });
    let ok = 0;
    for (let i = 0; i < ids.length; i++) {
      try { await deletePartnerCandidate(ids[i]); ok++; } catch { /* skip */ }
      setBulkProgress({ label: "Deleting", done: i + 1, total: ids.length });
    }
    setBulkProgress(null); setSelectedPartnerIds(new Set());
    if (selectedCandidate && ids.includes(selectedCandidate.id)) setSelectedCandidate(null);
    await fetchPartners(); setMessage(`Deleted ${ok} partner(s).`);
  }

  async function bulkConvertPartners() {
    if (!selectedPartnerIds.size) return;
    setConvertingPartners(true); setError(null); setMessage(null);
    try {
      const r = await convertPartnersToLeads({ partner_ids: [...selectedPartnerIds], require_website: true });
      setMessage(`Converted ${r.converted_count} to leads. Skipped ${r.skipped_count}.`);
      setSelectedPartnerIds(new Set()); await fetchPartners();
    } catch (e) { setError(getErr(e)); }
    finally { setConvertingPartners(false); }
  }

  async function bulkStatusChange(newStatus: string) {
    const ids = [...selectedPartnerIds];
    let ok = 0;
    for (const id of ids) { try { await updatePartnerCandidate(id, { status: newStatus }); ok++; } catch { /* skip */ } }
    await fetchPartners(); setMessage(`Updated ${ok} to "${newStatus.replace(/_/g, " ")}".`);
  }

  const partnerStatusCounts = useMemo(() => {
    const c: Record<string, number> = {};
    candidates.forEach(p => { c[p.status] = (c[p.status] || 0) + 1; });
    return c;
  }, [candidates]);

  const signals = selectedCandidate?.extracted_signals as Record<string, string | string[] | number | null> | null;
  const reasons = ((signals?.reasons || []) as unknown as string[]);

  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < totalProspects;
  const isBulkRunning = bulkProgress !== null;

  const prospectStatusCounts = useMemo(() => {
    return prospects.reduce((a, p) => {
      const s = (p.import_status || "new").toLowerCase();
      if (s === "imported") a.imported++; else if (s === "skipped") a.skipped++; else a.new++;
      return a;
    }, { new: 0, imported: 0, skipped: 0 });
  }, [prospects]);

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Discovery</h1>
            <p className="page-subtitle">Find prospects and partners, then convert them into CRM leads for outreach.</p>
          </div>
        </header>
      </section>

      {/* Tab bar */}
      <div className="discovery-tabs">
        <button type="button" className={`discovery-tab${activeTab === "local" ? " active" : ""}`} onClick={() => setActiveTab("local")}>
          Local Search
        </button>
        <button type="button" className={`discovery-tab${activeTab === "partner" ? " active" : ""}`} onClick={() => setActiveTab("partner")}>
          Partner Search
        </button>
      </div>

      {error && (
        error.includes("REQUEST_DENIED") ? (
          <div className="error">
            <strong>Google Places API not enabled.</strong>{" "}
            <a href="https://console.cloud.google.com/apis/library?filter=category:maps" target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "underline" }}>
              Enable the Places API
            </a>{" "} in Google Cloud Console.
          </div>
        ) : <div className="error">{error}</div>
      )}
      {message && <div className="success">{message}</div>}

      {/* ═══════════ LOCAL SEARCH TAB ═══════════ */}
      {activeTab === "local" && (
        <>
          <section className="card">
            <h2 style={{ marginBottom: 10 }}>Run Discovery Search</h2>
            {presets.length > 0 && (
              <div className="search-presets" style={{ marginBottom: 10 }}>
                {presets.map(p => (
                  <button key={p.label} type="button" className={`preset-btn ${activePreset === p.label ? "active" : ""}`}
                    onClick={() => { setActivePreset(p.label); setRunCategories(p.value); }}>
                    {p.label}
                  </button>
                ))}
              </div>
            )}
            <form className="stack" onSubmit={onRunSearch}>
              <div className="row">
                <div className="field">
                  <label htmlFor="s_categories">Categories (comma-separated)</label>
                  <input id="s_categories" value={runCategories} onChange={e => setRunCategories(e.target.value)} placeholder="plumber,electrician" />
                </div>
                <LocationAutocompleteField id="s_loc" label="Location" value={runLocation} onChange={setRunLocation} placeholder="City, ZIP, or address" />
                <div className="field field-narrow">
                  <label htmlFor="s_radius">Radius (mi)</label>
                  <input id="s_radius" type="number" min={1} max={31} step={1} value={runRadius} onChange={e => setRunRadius(e.target.value)} />
                </div>
              </div>
              <div className="inline-actions" style={{ alignItems: "center" }}>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: ".82rem" }}>
                  <input type="checkbox" checked={runMissingOnly} onChange={e => setRunMissingOnly(e.target.checked)} style={{ width: 16, height: 16 }} />
                  Only missing website
                </label>
                <button className="btn-primary" type="submit" disabled={runningSearch}>
                  {runningSearch ? "Searching..." : "Run Search"}
                </button>
                {runningSearch && <Spinner label="Searching Google Business..." />}
              </div>
            </form>
          </section>

          {/* Stats */}
          <section className="stats-grid">
            <div className="metric-card"><div className="metric-label">Total Prospects</div><div className="metric-value">{totalProspects}</div></div>
            <div className="metric-card"><div className="metric-label">New</div><div className="metric-value">{prospectStatusCounts.new}</div></div>
            <div className="metric-card"><div className="metric-label">Imported</div><div className="metric-value">{prospectStatusCounts.imported}</div></div>
            <div className="metric-card"><div className="metric-label">Skipped</div><div className="metric-value">{prospectStatusCounts.skipped}</div></div>
          </section>

          {/* Filters */}
          <section className="card">
            <form className="row" onSubmit={applyFilters} style={{ alignItems: "flex-end" }}>
              <div className="field">
                <label>Status</label>
                <input placeholder="new/imported/skipped" value={statusInput} onChange={e => setStatusInput(e.target.value)} />
              </div>
              <div className="field">
                <label>Category</label>
                <input placeholder="plumber" value={categoryInput} onChange={e => setCategoryInput(e.target.value)} />
              </div>
              <div className="field">
                <label>Search</label>
                <input placeholder="Company or address" value={searchInput} onChange={e => setSearchInput(e.target.value)} />
              </div>
              <div className="inline-actions" style={{ alignSelf: "flex-end" }}>
                <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: ".82rem" }}>
                  <input type="checkbox" checked={requireWebsite} onChange={e => setRequireWebsite(e.target.checked)} />
                  Require website
                </label>
                <button className="btn-secondary" type="submit">Apply</button>
              </div>
            </form>
          </section>

          {/* Bulk bar */}
          {selectedProspectIds.size > 0 && (
            <div className="bulk-action-bar">
              <strong>{selectedProspectIds.size} selected</strong>
              <div className="inline-actions">
                <button className="btn-primary" type="button" disabled={converting} onClick={() => void onConvertProspects()}>
                  {converting ? "Converting..." : "Add to CRM"}
                </button>
                <button className="btn-secondary" type="button" onClick={onExportCsv}>Export CSV</button>
                <button className="btn-danger" type="button" disabled={deletingProspects} onClick={() => void onDeleteProspects()}>
                  {deletingProspects ? "Deleting..." : "Delete"}
                </button>
                <button className="btn-secondary" type="button" onClick={() => setSelectedProspectIds(new Set())}>Clear</button>
              </div>
            </div>
          )}

          {/* Card header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2>Prospects</h2>
            <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }}
              disabled={prospects.length === 0} onClick={toggleAllProspects}>
              {allProspectsSelected ? "Unselect All" : "Select All"}
            </button>
          </div>

          {loadingProspects && <Spinner label="Loading prospects..." />}

          {!loadingProspects && prospects.length === 0 ? (
            <div className="empty-state">No prospects found. Run a discovery search above.</div>
          ) : (
            <div className="prospect-grid">
              {prospects.map(p => {
                const isImported = p.import_status === "imported";
                return (
                  <div key={p.id}
                    className={`prospect-card${selectedProspectIds.has(p.id) ? " selected" : ""}`}
                    onClick={() => !isImported && toggleProspect(p.id)}
                  >
                    <input type="checkbox" className="prospect-card-check"
                      checked={selectedProspectIds.has(p.id)}
                      disabled={isImported}
                      onChange={() => toggleProspect(p.id)}
                      onClick={e => e.stopPropagation()} />
                    <div className="prospect-card-name">{p.company_name}</div>
                    <div className="prospect-card-meta">
                      {p.category && <span className="prospect-card-category">{p.category}</span>}
                      {renderStars(p.rating ?? null)}
                      {p.review_count != null && <span>{p.review_count} reviews</span>}
                    </div>
                    <div className="prospect-card-address">{p.address}</div>
                    <div className="prospect-card-footer">
                      <span>
                        {p.website_url ? (
                          <a href={p.website_url} target="_blank" rel="noreferrer" className="external-link"
                            onClick={e => e.stopPropagation()}>
                            Website
                          </a>
                        ) : <span style={{ color: "var(--amber)" }}>No website</span>}
                        {p.phone && <span style={{ marginLeft: 12 }}>{p.phone}</span>}
                      </span>
                      <span className={`prospect-card-import-status status-${p.import_status || "new"}`}>
                        {p.import_status || "new"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          <div className="inline-actions" style={{ marginTop: 8 }}>
            <button className="btn-secondary" disabled={!canPrev || loadingProspects} onClick={() => setOffset(o => o - PAGE_SIZE)}>Prev</button>
            <button className="btn-secondary" disabled={!canNext || loadingProspects} onClick={() => setOffset(o => o + PAGE_SIZE)}>Next</button>
            <span className="muted">Showing {prospects.length} of {totalProspects}</span>
          </div>
        </>
      )}

      {/* ═══════════ PARTNER SEARCH TAB ═══════════ */}
      {activeTab === "partner" && (
        <>
          {/* Status overview */}
          {candidates.length > 0 && (
            <section className="stats-grid">
              <div className="metric-card"><div className="metric-label">Total</div><div className="metric-value">{partnerTotal}</div></div>
              {Object.entries(partnerStatusCounts).map(([s, c]) => (
                <div className="metric-card" key={s}>
                  <div className="metric-label">{s.replace(/_/g, " ")}</div>
                  <div className="metric-value">{c}</div>
                </div>
              ))}
            </section>
          )}

          <section className="card">
            <h2 style={{ marginBottom: 10 }}>Find Partners</h2>
            <p className="muted" style={{ marginBottom: 12, fontSize: ".85rem" }}>
              Describe what kind of partner you&rsquo;re looking for. AI will search the web, crawl company websites, and score each for fit.
            </p>
            <div className="field" style={{ marginBottom: 10 }}>
              <textarea value={searchIntent} onChange={e => setSearchIntent(e.target.value)} rows={3}
                placeholder={"e.g. National camera installation companies that subcontract to local technicians\ne.g. MSPs that need field service partners for network cabling"} />
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <label style={{ fontSize: ".78rem", whiteSpace: "nowrap" }}>Max results</label>
                <input type="number" min={3} max={20} value={maxResults} onChange={e => setMaxResults(Number(e.target.value))} style={{ width: 60, fontSize: ".84rem" }} />
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <label style={{ fontSize: ".78rem", whiteSpace: "nowrap" }}>Min fit %</label>
                <input type="number" min={0} max={100} value={Math.round(minFit * 100)} onChange={e => setMinFit(Number(e.target.value) / 100)} style={{ width: 60, fontSize: ".84rem" }} />
              </div>
              <button type="button" className="btn-primary" disabled={searchingPartners || !searchIntent.trim()} onClick={() => void handlePartnerSearch()}>
                {searchingPartners ? "Searching..." : "Search for Partners"}
              </button>
            </div>
            {searchingPartners && (
              <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 10 }}>
                <Spinner />
                <span className="muted" style={{ fontSize: ".85rem" }}>Searching the web and analyzing companies. This may take 1-2 minutes...</span>
              </div>
            )}
          </section>

          <div style={{ marginBottom: 4 }}>
            <button type="button" onClick={() => setShowManual(!showManual)} style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", fontSize: ".82rem", padding: 0 }}>
              {showManual ? "Hide manual URL analysis" : "Or analyze a specific website URL"}
            </button>
          </div>
          {showManual && (
            <section className="card">
              <div style={{ display: "flex", gap: 10 }}>
                <input style={{ flex: 1 }} value={manualUrl} onChange={e => setManualUrl(e.target.value)} placeholder="find IT vendors https://example.com"
                  onKeyDown={e => { if (e.key === "Enter") void handleManualDiscover(); }} />
                <button type="button" className="btn-primary" disabled={discoveringManual || !manualUrl.trim()} onClick={() => void handleManualDiscover()}>
                  {discoveringManual ? "Analyzing..." : "Analyze"}
                </button>
              </div>
            </section>
          )}

          {/* Bulk bar */}
          {selectedPartnerIds.size > 0 && (
            <div className="bulk-action-bar">
              <div>
                <strong>{selectedPartnerIds.size} selected</strong>
                {bulkProgress && <div className="muted" style={{ marginTop: 4, fontSize: ".82rem" }}>{bulkProgress.label}: {bulkProgress.done}/{bulkProgress.total}</div>}
              </div>
              <div className="inline-actions">
                <button type="button" className="btn-primary btn-full-pipeline" disabled={isBulkRunning || convertingPartners} onClick={() => void bulkConvertPartners()}>
                  {convertingPartners ? "Converting..." : "Convert to Leads"}
                </button>
                <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => void bulkGenerateOutreach()}>Bulk Outreach</button>
                <select disabled={isBulkRunning} onChange={e => { if (e.target.value) { void bulkStatusChange(e.target.value); e.target.value = ""; } }} defaultValue="" style={{ fontSize: ".82rem", padding: "6px 10px" }}>
                  <option value="" disabled>Set Status...</option>
                  {PARTNER_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                </select>
                <button type="button" className="btn-danger" disabled={isBulkRunning} onClick={() => void bulkDeletePartners()}>Delete</button>
                <button type="button" className="btn-secondary" disabled={isBulkRunning} onClick={() => setSelectedPartnerIds(new Set())}>Clear</button>
              </div>
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: selectedCandidate ? "1fr 1fr" : "1fr", gap: 16 }}>
            {/* Candidate list */}
            <section className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 18px 12px" }}>
                <h2>Candidates ({candidates.length})</h2>
                <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }}
                  disabled={candidates.length === 0} onClick={toggleAllPartners}>
                  {allPartnersSelected ? "Unselect All" : "Select All"}
                </button>
              </div>
              <div style={{ maxHeight: "calc(100vh - 500px)", overflowY: "auto", padding: "0 18px 18px" }}>
                {loadingPartners && <Spinner label="Loading..." />}
                {!loadingPartners && candidates.length === 0 && <p className="muted">No candidates yet. Run a search above.</p>}
                {candidates.map(c => (
                  <div key={c.id} className={`subcard${selectedCandidate?.id === c.id ? " active-thread" : ""}`}
                    style={{ marginBottom: 8, cursor: "pointer", padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input type="checkbox" checked={selectedPartnerIds.has(c.id)} onChange={() => togglePartner(c.id)}
                        onClick={e => e.stopPropagation()} style={{ width: 16, height: 16, flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }} onClick={() => setSelectedCandidate(c)}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
                          <strong style={{ fontSize: ".86rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.company_name}</strong>
                          <span className={`stage-pill ${c.status === "converted" ? "stage-done" : c.status === "new" ? "stage-active" : "stage-done"}`}
                            style={{ fontSize: ".68rem", flexShrink: 0, marginLeft: 8 }}>
                            {c.status.replace(/_/g, " ")}
                          </span>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: ".78rem" }}>
                          <span className="muted">{c.partnership_type || "unclassified"}</span>
                          {c.fit_score != null && (
                            <span className={fitBadgeClass(c.fit_score)}>{(c.fit_score * 100).toFixed(0)}%</span>
                          )}
                        </div>
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
                    <select value={selectedCandidate.status}
                      onChange={e => { void updatePartnerCandidate(selectedCandidate.id, { status: e.target.value }).then(u => { setSelectedCandidate(u); void fetchPartners(); }); }}
                      style={{ fontSize: ".82rem", padding: "4px 8px" }}>
                      {PARTNER_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                    </select>
                    <button type="button" className="btn-primary btn-full-pipeline" style={{ fontSize: ".78rem", padding: "4px 10px" }}
                      disabled={selectedCandidate.status === "converted" || convertingPartners}
                      onClick={() => {
                        setConvertingPartners(true);
                        convertPartnersToLeads({ partner_ids: [selectedCandidate.id], require_website: true })
                          .then(r => { setMessage(`Converted ${r.converted_count} to lead.`); void fetchPartners(); setSelectedCandidate(null); })
                          .catch(e => setError(getErr(e)))
                          .finally(() => setConvertingPartners(false));
                      }}>
                      Convert to Lead
                    </button>
                    <button type="button" className="btn-danger" style={{ fontSize: ".78rem", padding: "4px 10px" }}
                      onClick={() => void handleDeletePartner(selectedCandidate.id)}>Delete</button>
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
                      <div style={{ fontWeight: 700, fontSize: "1.2rem" }}>
                        {selectedCandidate.fit_score != null ? (
                          <span className={fitBadgeClass(selectedCandidate.fit_score)} style={{ fontSize: "1rem" }}>
                            {(selectedCandidate.fit_score * 100).toFixed(0)}%
                          </span>
                        ) : "—"}
                      </div>
                    </div>
                  </div>
                  {signals?.company_summary && (
                    <div className="subcard">
                      <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Summary</strong>
                      <div style={{ fontSize: ".86rem", lineHeight: 1.5 }}>{String(signals.company_summary)}</div>
                    </div>
                  )}
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
                      <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Outreach Angle</strong>
                      <div style={{ fontSize: ".86rem" }}>{selectedCandidate.recommended_outreach_angle}</div>
                    </div>
                  )}
                  {selectedCandidate.contact_emails?.length ? (
                    <div className="subcard">
                      <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Contact Emails</strong>
                      <div style={{ fontSize: ".86rem" }}>{selectedCandidate.contact_emails.join(", ")}</div>
                    </div>
                  ) : null}

                  <div className="subcard">
                    <strong style={{ fontSize: ".72rem", color: "var(--text-muted)" }}>Outreach Draft</strong>
                    {selectedCandidate.outreach_subject ? (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ fontSize: ".82rem", fontWeight: 600, marginBottom: 4 }}>{selectedCandidate.outreach_subject}</div>
                        <div style={{ fontSize: ".82rem", whiteSpace: "pre-wrap", lineHeight: 1.5, background: "var(--bg)", padding: 10, borderRadius: "var(--radius-sm)", border: "1px solid var(--line)" }}>
                          {selectedCandidate.outreach_body}
                        </div>
                      </div>
                    ) : <p className="muted" style={{ fontSize: ".82rem", marginTop: 4 }}>No draft yet.</p>}
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
        </>
      )}
    </div>
  );
}
