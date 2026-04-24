"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { LocationAutocompleteField } from "@/src/components/LocationAutocompleteField";
import { Spinner } from "@/src/components/Spinner";
import {
  ApiError,
  convertProspectsToLeads,
  deleteProspectsBulk,
  getProspects,
  getWorkspaceAiStrategy,
  runProspectSearch
} from "@/src/lib/api";
import { useDebouncedValue } from "@/src/lib/hooks";
import { Prospect, ProspectListResponse, ProspectSearchResponse } from "@/src/lib/types";

const PAGE_SIZE = 25;
const METERS_PER_MILE = 1609.344;
const MAX_RADIUS_METERS = 50000;

function milesToMeters(miles: number): number {
  return Math.round(miles * METERS_PER_MILE);
}
const DEFAULT_SEARCH_PRESETS: Array<{ label: string; value: string }> = [
  { label: "Restaurants", value: "restaurant" },
  { label: "Coffee Shops", value: "cafe,coffee_shop" },
  { label: "Dentists", value: "dentist" },
  { label: "Gyms", value: "gym" },
  { label: "Law Firms", value: "lawyer,law_firm" }
];

function strategyToPresets(
  targetCategories: string[] | undefined,
  idealCustomers: Array<{ category: string; display_name: string }> | undefined
): Array<{ label: string; value: string }> {
  if (!targetCategories?.length && !idealCustomers?.length) return DEFAULT_SEARCH_PRESETS;
  const byCat = new Map<string, string>();
  for (const ic of idealCustomers ?? []) {
    if (ic?.category && ic?.display_name) {
      byCat.set(ic.category, ic.display_name);
    }
  }
  return (targetCategories ?? Object.keys(Object.fromEntries(byCat))).map((cat) => ({
    label: byCat.get(cat) ?? cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    value: cat
  }));
}

type SortColumn = "company_name" | "rating" | "review_count" | "updated_at";
type SortDirection = "asc" | "desc";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function websiteStatus(url?: string | null): { cls: string; label: string } {
  if (!url || !url.trim()) {
    return { cls: "status-dot status-dot-yellow", label: "Missing website" };
  }
  if (!/^https?:\/\//i.test(url.trim())) {
    return { cls: "status-dot status-dot-red", label: "Potentially broken site URL" };
  }
  return { cls: "status-dot status-dot-green", label: "Website available" };
}

function toLocalDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export default function ProspectsPage() {
  const [prospectList, setProspectList] = useState<ProspectListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [searchResult, setSearchResult] = useState<ProspectSearchResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searchPresets, setSearchPresets] = useState<Array<{ label: string; value: string }>>(DEFAULT_SEARCH_PRESETS);

  const [offset, setOffset] = useState(0);
  const [statusInput, setStatusInput] = useState("");
  const [categoryFilterInput, setCategoryFilterInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearchInput = useDebouncedValue(searchInput, 400);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [searchFilter, setSearchFilter] = useState<string | undefined>(undefined);

  const [runCategories, setRunCategories] = useState("plumber,electrician");
  const [activePreset, setActivePreset] = useState("");
  const [runLocation, setRunLocation] = useState("Chico, CA");
  const [runRadiusMiles, setRunRadiusMiles] = useState("6");
  const [runMissingWebsiteOnly, setRunMissingWebsiteOnly] = useState(false);
  const [requireWebsiteForConversion, setRequireWebsiteForConversion] = useState(true);
  const [runningSearch, setRunningSearch] = useState(false);
  const [converting, setConverting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [sortColumn, setSortColumn] = useState<SortColumn>("updated_at");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  async function fetchRows(nextOffset: number, nextStatus?: string, nextCategory?: string, nextQuery?: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const result = await getProspects(PAGE_SIZE, nextOffset, nextStatus, nextCategory, nextQuery);
      setProspectList(result);
      setSelectedIds((prev) => new Set([...prev].filter((id) => result.items.some((item) => item.id === id))));
    } catch (fetchError) {
      setError(getErrorMessage(fetchError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void fetchRows(offset, statusFilter, categoryFilter, searchFilter);
  }, [offset, statusFilter, categoryFilter, searchFilter]);

  useEffect(() => {
    setSearchFilter(debouncedSearchInput.trim() || undefined);
    setOffset(0);
  }, [debouncedSearchInput]);

  useEffect(() => {
    getWorkspaceAiStrategy()
      .then((strategy) => {
        const gen = strategy.generated_strategy;
        const presets = strategyToPresets(
          gen?.target_categories,
          gen?.ideal_customers
        );
        setSearchPresets(presets);
      })
      .catch(() => {})
      .finally(() => {});
  }, []);

  function applyListFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setStatusFilter(statusInput.trim() || undefined);
    setCategoryFilter(categoryFilterInput.trim() || undefined);
    setOffset(0);
  }

  function applyPreset(preset: { label: string; value: string }): void {
    setActivePreset(preset.label);
    setRunCategories(preset.value);
  }

  async function onRunSearch(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const categories = runCategories
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    const miles = Number.parseFloat(runRadiusMiles);
    if (!categories.length) {
      setError("At least one category is required for search.");
      return;
    }
    if (!runLocation.trim()) {
      setError("Location is required.");
      return;
    }
    if (!Number.isFinite(miles) || miles <= 0) {
      setError("Radius must be a positive number (miles).");
      return;
    }
    const radiusMeters = milesToMeters(miles);
    if (radiusMeters < 1 || radiusMeters > MAX_RADIUS_METERS) {
      setError(`Radius must be between about ${(1 / METERS_PER_MILE).toFixed(2)} and ${(MAX_RADIUS_METERS / METERS_PER_MILE).toFixed(0)} miles (Google Places limit).`);
      return;
    }

    setRunningSearch(true);
    setError(null);
    setActionMessage(null);
    try {
      const result = await runProspectSearch({
        categories,
        location: runLocation.trim(),
        radius: radiusMeters,
        missing_website_only: runMissingWebsiteOnly,
        keyword: "business"
      });
      setSearchResult(result);
      setActionMessage(
        `Search fetched ${result.fetched_count} prospects. Imported ${result.import_result.imported_count}, skipped ${result.import_result.skipped_count}, errors ${result.import_result.error_count}.`
      );
      setOffset(0);
      await fetchRows(0, statusFilter, categoryFilter, searchFilter);
    } catch (searchError) {
      setError(getErrorMessage(searchError));
    } finally {
      setRunningSearch(false);
    }
  }

  function onSort(column: SortColumn): void {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection(column === "company_name" ? "asc" : "desc");
  }

  function toggleSelection(id: string, checked: boolean): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }

  function toggleSelectAllCurrentPage(checked: boolean, items: Prospect[]): void {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const item of items) {
        if (item.import_status === "imported") {
          continue;
        }
        if (checked) {
          next.add(item.id);
        } else {
          next.delete(item.id);
        }
      }
      return next;
    });
  }

  async function onConvertSelected(): Promise<void> {
    if (!selectedIds.size) {
      setError("Select at least one prospect first.");
      return;
    }

    setConverting(true);
    setError(null);
    setActionMessage(null);
    try {
      const payload = {
        prospect_ids: [...selectedIds],
        require_website: requireWebsiteForConversion
      };
      const result = await convertProspectsToLeads(payload);
      setActionMessage(
        `Converted ${result.converted_count} to leads. Skipped ${result.skipped_count}. Found ${result.found_count} of ${result.requested_count} requested.`
      );
      setSelectedIds(new Set());
      setOffset(0);
      await fetchRows(0, statusFilter, categoryFilter, searchFilter);
    } catch (convertError) {
      setError(getErrorMessage(convertError));
    } finally {
      setConverting(false);
    }
  }

  async function onDeleteSelected(): Promise<void> {
    if (!selectedIds.size) return;
    setDeleting(true);
    setError(null);
    setActionMessage(null);
    try {
      const result = await deleteProspectsBulk([...selectedIds]);
      setActionMessage(`Deleted ${result.deleted_count} prospect(s).`);
      setSelectedIds(new Set());
      await fetchRows(0, statusFilter, categoryFilter, searchFilter);
    } catch (deleteError) {
      setError(getErrorMessage(deleteError));
    } finally {
      setDeleting(false);
    }
  }

  function onExportCsv(): void {
    if (!selectedIds.size) {
      setError("Select prospects to export.");
      return;
    }

    const items = (prospectList?.items ?? []).filter((item) => selectedIds.has(item.id));
    const headers = [
      "company_name",
      "category",
      "rating",
      "review_count",
      "address",
      "phone",
      "website_url",
      "source",
      "import_status",
      "updated_at"
    ];
    const rows = items.map((item) =>
      [
        item.company_name,
        item.category ?? "",
        item.rating ?? "",
        item.review_count ?? "",
        item.address,
        item.phone ?? "",
        item.website_url ?? "",
        item.source,
        item.import_status,
        item.updated_at
      ]
        .map((value) => `"${String(value).replaceAll('"', '""')}"`)
        .join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "prospects-export.csv";
    link.click();
    URL.revokeObjectURL(url);
    setActionMessage(`Exported ${items.length} prospects to CSV.`);
  }

  const prospects = prospectList?.items ?? [];
  const sortedProspects = useMemo(() => {
    const cloned = [...prospects];
    cloned.sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;
      if (sortColumn === "company_name") {
        return dir * a.company_name.localeCompare(b.company_name);
      }
      if (sortColumn === "rating") {
        return dir * ((a.rating ?? -1) - (b.rating ?? -1));
      }
      if (sortColumn === "review_count") {
        return dir * ((a.review_count ?? -1) - (b.review_count ?? -1));
      }
      const aTime = new Date(a.updated_at).getTime();
      const bTime = new Date(b.updated_at).getTime();
      return dir * (aTime - bTime);
    });
    return cloned;
  }, [prospects, sortColumn, sortDirection]);

  const total = prospectList?.total ?? 0;
  const canGoPrev = offset > 0;
  const canGoNext = offset + PAGE_SIZE < total;
  const selectableCurrentIds = sortedProspects.filter((item) => item.import_status !== "imported").map((item) => item.id);
  const allCurrentSelected =
    selectableCurrentIds.length > 0 && selectableCurrentIds.every((id) => selectedIds.has(id));

  const statusCounts = useMemo(() => {
    return prospects.reduce(
      (acc, prospect) => {
        const status = (prospect.import_status || "new").toLowerCase();
        if (status === "imported") {
          acc.imported += 1;
        } else if (status === "skipped") {
          acc.skipped += 1;
        } else if (status === "selected") {
          acc.selected += 1;
        } else {
          acc.new += 1;
        }
        return acc;
      },
      { new: 0, selected: 0, imported: 0, skipped: 0 }
    );
  }, [prospects]);

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Prospect Discovery</h1>
            <p className="page-subtitle">
              Discover prospects, review quality, and selectively convert them into CRM leads.
            </p>
          </div>
          <span className="stat-pill">Selected: {selectedIds.size}</span>
        </header>
      </section>

      <section className="card surface-search stack">
        <h2>Run Discovery Search</h2>
        <div className="search-presets">
          {searchPresets.map((preset) => (
            <button
              key={preset.label}
              type="button"
              className={`preset-btn ${activePreset === preset.label ? "active" : ""}`}
              onClick={() => applyPreset(preset)}
              title={`Use ${preset.label} categories`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <form className="stack" onSubmit={onRunSearch}>
          <div className="row">
            <div className="field">
              <label htmlFor="search_categories">Categories (comma-separated)</label>
              <input
                id="search_categories"
                value={runCategories}
                onChange={(event) => setRunCategories(event.target.value)}
                placeholder="plumber,electrician,roofing_contractor"
              />
            </div>
            <LocationAutocompleteField
              id="search_location"
              label="Search location"
              value={runLocation}
              onChange={setRunLocation}
              placeholder="Start typing a city, ZIP, or address"
              hint={
                <>
                  Suggestions use Google Places. We geocode your choice for the search center. You can still paste{" "}
                  <code>lat,lng</code> without using the list.
                </>
              }
            />
            <div className="field field-narrow">
              <label htmlFor="search_radius">Radius (mi)</label>
              <input
                id="search_radius"
                type="number"
                min={1}
                max={31}
                step={1}
                value={runRadiusMiles}
                onChange={(event) => setRunRadiusMiles(event.target.value)}
              />
            </div>
          </div>
          <div className="inline-actions" style={{ alignItems: "center" }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={runMissingWebsiteOnly}
                onChange={(event) => setRunMissingWebsiteOnly(event.target.checked)}
                style={{ width: 18, height: 18 }}
              />
              Only missing website
            </label>
            <button className="btn-primary" type="submit" disabled={runningSearch}>
              {runningSearch ? "Running..." : "Run Search"}
            </button>
            {runningSearch ? <Spinner label="Searching Google Business..." /> : null}
          </div>
        </form>
        {searchResult ? (
          <div className="muted">
            Last search: fetched {searchResult.fetched_count}, imported {searchResult.import_result.imported_count}, skipped{" "}
            {searchResult.import_result.skipped_count}, errors {searchResult.import_result.error_count}.
          </div>
        ) : null}
      </section>

      <section className="stats-grid">
        <div className="metric-card">
          <div className="metric-label">Total Prospects</div>
          <div className="metric-value">{total}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">New (visible)</div>
          <div className="metric-value">{statusCounts.new}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Imported (visible)</div>
          <div className="metric-value">{statusCounts.imported}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Skipped (visible)</div>
          <div className="metric-value">{statusCounts.skipped}</div>
        </div>
      </section>

      <section className="card surface-table stack">
        <h2>Prospect List</h2>
        <form className="row" onSubmit={applyListFilters}>
          <div className="field">
            <label htmlFor="filter_status">Status</label>
            <input
              id="filter_status"
              placeholder="new/imported/skipped"
              value={statusInput}
              onChange={(event) => setStatusInput(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="filter_category">Category</label>
            <input
              id="filter_category"
              placeholder="plumber"
              value={categoryFilterInput}
              onChange={(event) => setCategoryFilterInput(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="filter_query">Company / Address (debounced)</label>
            <input
              id="filter_query"
              placeholder="search text"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>
          <div className="inline-actions" style={{ alignSelf: "flex-end" }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={requireWebsiteForConversion}
                onChange={(event) => setRequireWebsiteForConversion(event.target.checked)}
              />
              Require website for conversion
            </label>
            <button className="btn-secondary" type="submit" disabled={loading}>
              Apply Filters
            </button>
          </div>
        </form>

        {selectedIds.size > 0 ? (
          <div className="bulk-action-bar">
            <strong>{selectedIds.size} selected</strong>
            <div className="inline-actions">
              <button className="btn-primary" type="button" onClick={onConvertSelected} disabled={converting}>
                {converting ? "Converting..." : "Add Selected to CRM"}
              </button>
              <button className="btn-secondary" type="button" onClick={onExportCsv}>
                Export CSV
              </button>
              <button className="btn-danger" type="button" disabled={deleting} onClick={() => void onDeleteSelected()}>
                {deleting ? "Deleting..." : "Delete Selected"}
              </button>
            </div>
          </div>
        ) : null}

        {loading ? <Spinner label="Loading prospects..." /> : null}
        {error && error.includes("REQUEST_DENIED") ? (
          <div className="error">
            <strong>Google Places API not enabled.</strong> Go to{" "}
            <a href="https://console.cloud.google.com/apis/library?filter=category:maps" target="_blank" rel="noreferrer" style={{ color: "inherit", textDecoration: "underline" }}>
              Google Cloud Console &rarr; APIs &amp; Services &rarr; Library
            </a>{" "}
            and enable the <strong>Places API (New)</strong> for your project, then try again.
          </div>
        ) : error ? (
          <div className="error">{error}</div>
        ) : null}
        {actionMessage ? <div className="success">{actionMessage}</div> : null}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={allCurrentSelected}
                    onChange={(event) => toggleSelectAllCurrentPage(event.target.checked, sortedProspects)}
                    disabled={!selectableCurrentIds.length}
                  />
                </th>
                <th className="sortable-th" onClick={() => onSort("company_name")} title="Sort by company">
                  Company
                </th>
                <th>Category</th>
                <th className="sortable-th" onClick={() => onSort("rating")} title="Sort by rating">
                  Rating
                </th>
                <th className="sortable-th" onClick={() => onSort("review_count")} title="Sort by reviews">
                  Review Count
                </th>
                <th>Address</th>
                <th>Phone</th>
                <th>Website Status</th>
                <th>Website</th>
                <th>Source</th>
                <th>Status</th>
                <th className="sortable-th" onClick={() => onSort("updated_at")} title="Sort by last seen">
                  Last Seen
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={12} className="muted">
                    Loading prospects...
                  </td>
                </tr>
              ) : sortedProspects.length === 0 ? (
                <tr>
                  <td colSpan={12}>
                    <div className="empty-state">No prospects yet. Run a discovery search to find businesses.</div>
                  </td>
                </tr>
              ) : (
                sortedProspects.map((prospect) => {
                  const ws = websiteStatus(prospect.website_url);
                  return (
                    <tr key={prospect.id}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(prospect.id)}
                          onChange={(event) => toggleSelection(prospect.id, event.target.checked)}
                          disabled={prospect.import_status === "imported"}
                        />
                      </td>
                      <td>{prospect.company_name}</td>
                      <td>{prospect.category || "-"}</td>
                      <td>{prospect.rating != null ? prospect.rating.toFixed(1) : "-"}</td>
                      <td>{prospect.review_count ?? "-"}</td>
                      <td>{prospect.address}</td>
                      <td>{prospect.phone || "-"}</td>
                      <td>
                        <span className={ws.cls} title={ws.label} />
                      </td>
                      <td>
                        {prospect.website_url ? (
                          <a href={prospect.website_url} target="_blank" rel="noreferrer" className="external-link">
                            {prospect.website_url}
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>{prospect.source}</td>
                      <td>{prospect.import_status}</td>
                      <td>{toLocalDate(prospect.updated_at)}</td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="inline-actions">
          <button className="btn-secondary" onClick={() => setOffset((prev) => prev - PAGE_SIZE)} disabled={!canGoPrev || loading}>
            Prev
          </button>
          <button className="btn-secondary" onClick={() => setOffset((prev) => prev + PAGE_SIZE)} disabled={!canGoNext || loading}>
            Next
          </button>
          <span className="muted">
            Showing {sortedProspects.length} of {total}
          </span>
        </div>
      </section>
    </div>
  );
}
