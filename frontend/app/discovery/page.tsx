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
  getPartnerCandidates,
  getProspects,
  getWorkspaceAiStrategy,
  runProspectSearch,
  searchPartners,
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

          {/* Header + inline toolbar */}
          <div className="list-toolbar">
            <div className="list-toolbar-left">
              <h2 style={{ margin: 0 }}>Prospects</h2>
              {selectedProspectIds.size > 0 && (
                <span className="toolbar-count">{selectedProspectIds.size} selected</span>
              )}
            </div>
            <div className="list-toolbar-right">
              {selectedProspectIds.size > 0 ? (
                <>
                  <button className="btn-primary" type="button" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    disabled={converting} onClick={() => void onConvertProspects()}>
                    {converting ? "Converting..." : "Add to CRM"}
                  </button>
                  <button className="btn-secondary" type="button" style={{ fontSize: ".78rem", padding: "5px 12px" }} onClick={onExportCsv}>Export CSV</button>
                  <button className="btn-danger" type="button" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    disabled={deletingProspects} onClick={() => void onDeleteProspects()}>
                    {deletingProspects ? "Deleting..." : "Delete"}
                  </button>
                  <button className="btn-ghost" type="button" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    onClick={() => setSelectedProspectIds(new Set())}>Clear</button>
                </>
              ) : (
                <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }}
                  disabled={prospects.length === 0} onClick={toggleAllProspects}>
                  {allProspectsSelected ? "Unselect All" : "Select All"}
                </button>
              )}
            </div>
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

          {/* Header + inline toolbar */}
          <div className="list-toolbar">
            <div className="list-toolbar-left">
              <h2 style={{ margin: 0 }}>Partner Candidates</h2>
              {selectedPartnerIds.size > 0 && (
                <span className="toolbar-count">{selectedPartnerIds.size} selected</span>
              )}
              {bulkProgress && <span className="muted" style={{ fontSize: ".78rem" }}>{bulkProgress.label}: {bulkProgress.done}/{bulkProgress.total}</span>}
            </div>
            <div className="list-toolbar-right">
              {selectedPartnerIds.size > 0 ? (
                <>
                  <button type="button" className="btn-primary" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    disabled={isBulkRunning || convertingPartners} onClick={() => void bulkConvertPartners()}>
                    {convertingPartners ? "Converting..." : "Convert to Leads"}
                  </button>
                  <select disabled={isBulkRunning} onChange={e => { if (e.target.value) { void bulkStatusChange(e.target.value); e.target.value = ""; } }} defaultValue=""
                    style={{ fontSize: ".78rem", padding: "5px 8px" }}>
                    <option value="" disabled>Status...</option>
                    {PARTNER_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                  </select>
                  <button type="button" className="btn-danger" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    disabled={isBulkRunning} onClick={() => void bulkDeletePartners()}>Delete</button>
                  <button type="button" className="btn-ghost" style={{ fontSize: ".78rem", padding: "5px 12px" }}
                    disabled={isBulkRunning} onClick={() => setSelectedPartnerIds(new Set())}>Clear</button>
                </>
              ) : (
                <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }}
                  disabled={candidates.length === 0} onClick={toggleAllPartners}>
                  {allPartnersSelected ? "Unselect All" : "Select All"}
                </button>
              )}
            </div>
          </div>

          {loadingPartners && <Spinner label="Loading partners..." />}
          {!loadingPartners && candidates.length === 0 && (
            <div className="empty-state">No partner candidates yet. Run a search above to discover partners.</div>
          )}

          {/* Card grid for partners */}
          {!loadingPartners && candidates.length > 0 && (
            <div className="prospect-grid">
              {candidates.map(c => {
                const sigs = c.extracted_signals as Record<string, string | string[] | number | null> | null;
                const isConverted = c.status === "converted";
                return (
                  <div key={c.id}
                    className={`prospect-card${selectedPartnerIds.has(c.id) ? " selected" : ""}${selectedCandidate?.id === c.id ? " selected" : ""}`}
                    onClick={() => setSelectedCandidate(c)}
                  >
                    <input type="checkbox" className="prospect-card-check"
                      checked={selectedPartnerIds.has(c.id)}
                      onChange={() => togglePartner(c.id)}
                      onClick={e => e.stopPropagation()} />

                    <div className="prospect-card-name">{c.company_name}</div>

                    <div className="prospect-card-meta">
                      {c.partnership_type && <span className="prospect-card-category">{c.partnership_type}</span>}
                      {c.fit_score != null && (
                        <span className={fitBadgeClass(c.fit_score)}>{(c.fit_score * 100).toFixed(0)}% fit</span>
                      )}
                      <span className={`stage-pill ${isConverted ? "stage-done" : c.status === "new" ? "stage-active" : c.status === "ignored" ? "stage-pending" : "stage-done"}`}
                        style={{ fontSize: ".66rem" }}>
                        {c.status.replace(/_/g, " ")}
                      </span>
                    </div>

                    {sigs?.company_summary && (
                      <div style={{ fontSize: ".8rem", color: "var(--text-secondary)", lineHeight: 1.4, marginBottom: 6,
                        display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const, overflow: "hidden" }}>
                        {String(sigs.company_summary)}
                      </div>
                    )}

                    <div className="prospect-card-footer">
                      <span>
                        {c.website ? (
                          <a href={c.website} target="_blank" rel="noreferrer" className="external-link" onClick={e => e.stopPropagation()}>
                            Website
                          </a>
                        ) : <span style={{ color: "var(--text-muted)" }}>No website</span>}
                        {c.contact_emails?.length ? (
                          <span style={{ marginLeft: 12, color: "var(--text-muted)" }}>{c.contact_emails[0]}</span>
                        ) : null}
                      </span>
                      {c.outreach_status && (
                        <span style={{ fontSize: ".68rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em",
                          color: c.outreach_status === "gmail_draft_created" ? "var(--green)" : "var(--blue)" }}>
                          {c.outreach_status.replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Slide-in detail panel */}
          {selectedCandidate && (
            <>
              <div className="slideout-backdrop" onClick={() => setSelectedCandidate(null)} />
              <aside className="slideout-panel">
                <div className="slideout-header">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h2 style={{ fontSize: "1.15rem", margin: 0 }}>{selectedCandidate.company_name}</h2>
                    {selectedCandidate.website && (
                      <a href={selectedCandidate.website} target="_blank" rel="noopener noreferrer" className="external-link" style={{ fontSize: ".84rem" }}>
                        {selectedCandidate.website}
                      </a>
                    )}
                  </div>
                  <button type="button" className="slideout-close" onClick={() => setSelectedCandidate(null)} aria-label="Close">&times;</button>
                </div>

                {/* Actions row */}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "0 24px", marginBottom: 16 }}>
                  <select value={selectedCandidate.status}
                    onChange={e => { void updatePartnerCandidate(selectedCandidate.id, { status: e.target.value }).then(u => { setSelectedCandidate(u); void fetchPartners(); }); }}
                    style={{ fontSize: ".82rem", padding: "6px 10px" }}>
                    {PARTNER_STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                  </select>
                  <button type="button" className="btn-primary" style={{ fontSize: ".8rem" }}
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
                  <button type="button" className="btn-danger" style={{ fontSize: ".8rem" }}
                    onClick={() => void handleDeletePartner(selectedCandidate.id)}>Delete</button>
                </div>

                {/* Scrollable content */}
                <div className="slideout-body">
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
                    <div className="subcard">
                      <strong className="slideout-label">Type</strong>
                      <div style={{ fontWeight: 600, marginTop: 4 }}>{selectedCandidate.partnership_type || "—"}</div>
                    </div>
                    <div className="subcard">
                      <strong className="slideout-label">Fit Score</strong>
                      <div style={{ marginTop: 4 }}>
                        {selectedCandidate.fit_score != null ? (
                          <span className={fitBadgeClass(selectedCandidate.fit_score)} style={{ fontSize: "1.1rem", padding: "4px 14px" }}>
                            {(selectedCandidate.fit_score * 100).toFixed(0)}%
                          </span>
                        ) : <span style={{ color: "var(--text-muted)" }}>—</span>}
                      </div>
                    </div>
                  </div>

                  {signals?.company_summary && (
                    <div className="subcard" style={{ marginBottom: 14 }}>
                      <strong className="slideout-label">Company Summary</strong>
                      <div style={{ fontSize: ".86rem", lineHeight: 1.55, marginTop: 4 }}>{String(signals.company_summary)}</div>
                    </div>
                  )}

                  {reasons.length > 0 && (
                    <div className="subcard" style={{ marginBottom: 14 }}>
                      <strong className="slideout-label">Fit Reasons</strong>
                      <ul style={{ margin: "6px 0 0 16px", fontSize: ".86rem", lineHeight: 1.6 }}>
                        {reasons.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    </div>
                  )}

                  {selectedCandidate.recommended_outreach_angle && (
                    <div className="subcard" style={{ marginBottom: 14 }}>
                      <strong className="slideout-label">Outreach Angle</strong>
                      <div style={{ fontSize: ".86rem", marginTop: 4 }}>{selectedCandidate.recommended_outreach_angle}</div>
                    </div>
                  )}

                  {selectedCandidate.contact_emails?.length ? (
                    <div className="subcard" style={{ marginBottom: 14 }}>
                      <strong className="slideout-label">Contacts</strong>
                      <div style={{ fontSize: ".86rem", marginTop: 4 }}>{selectedCandidate.contact_emails.join(", ")}</div>
                    </div>
                  ) : null}

                  {/* Convert CTA */}
                  {selectedCandidate.status !== "converted" && (
                    <div className="subcard" style={{ background: "var(--blue-soft)", borderColor: "var(--blue)", textAlign: "center", padding: "16px 14px" }}>
                      <p style={{ fontSize: ".86rem", color: "var(--text-secondary)", margin: "0 0 10px" }}>
                        Convert to a lead to generate outreach emails using the pipeline.
                      </p>
                      <button type="button" className="btn-primary" style={{ fontSize: ".85rem" }}
                        disabled={convertingPartners}
                        onClick={() => {
                          setConvertingPartners(true);
                          convertPartnersToLeads({ partner_ids: [selectedCandidate.id], require_website: true })
                            .then(r => { setMessage(`Converted ${r.converted_count} to lead — website research already applied.`); void fetchPartners(); setSelectedCandidate(null); })
                            .catch(e => setError(getErr(e)))
                            .finally(() => setConvertingPartners(false));
                        }}>
                        {convertingPartners ? "Converting..." : "Convert to Lead & Start Pipeline"}
                      </button>
                    </div>
                  )}
                  {selectedCandidate.status === "converted" && (
                    <div className="subcard" style={{ background: "var(--green-soft)", borderColor: "var(--green)", textAlign: "center", padding: "14px" }}>
                      <p style={{ fontSize: ".86rem", color: "var(--green)", fontWeight: 600, margin: 0 }}>
                        Converted to lead — manage outreach from the Leads page.
                      </p>
                    </div>
                  )}
                </div>
              </aside>
            </>
          )}
        </>
      )}
    </div>
  );
}
