import Link from "next/link";
import { FormEvent } from "react";

interface LeadListFiltersProps {
  statusInput: string;
  searchInput: string;
  activeQuickFilter: string;
  onStatusChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onQuickFilterChange: (value: string) => void;
  onApplyFilters: (event: FormEvent<HTMLFormElement>) => void;
}

export function LeadListFilters({
  statusInput,
  searchInput,
  activeQuickFilter,
  onStatusChange,
  onSearchChange,
  onQuickFilterChange,
  onApplyFilters
}: LeadListFiltersProps) {
  return (
    <div className="card surface-search stack">
      <div className="quick-filter-row">
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "all" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("all")}
        >
          All
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "needs_ingestion" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("needs_ingestion")}
        >
          Needs Ingestion
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "needs_agent1" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("needs_agent1")}
        >
          Needs Agent 1
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "needs_agent2" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("needs_agent2")}
        >
          Needs Agent 2
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "needs_agent3" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("needs_agent3")}
        >
          Needs Agent 3
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "ready" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("ready")}
        >
          Ready
        </button>
        <button
          type="button"
          className={`quick-filter-btn ${activeQuickFilter === "hold" ? "active" : ""}`}
          onClick={() => onQuickFilterChange("hold")}
        >
          Hold
        </button>
      </div>

      <div className="row" style={{ justifyContent: "space-between", alignItems: "end" }}>
      <form onSubmit={onApplyFilters} className="row" style={{ flex: 1 }}>
        <div className="field" style={{ maxWidth: 190 }}>
          <label htmlFor="status">Status</label>
          <select id="status" value={statusInput} onChange={(event) => onStatusChange(event.target.value)}>
            <option value="">All statuses</option>
            <option value="new">new</option>
            <option value="draft">draft</option>
            <option value="send">send</option>
            <option value="hold">hold</option>
          </select>
        </div>
        <div className="field" style={{ minWidth: 270 }}>
          <label htmlFor="search">Company search</label>
          <input
            id="search"
            placeholder="Find by company name"
            value={searchInput}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <div className="field" style={{ minWidth: 130, flex: "0 0 auto" }}>
          <label>&nbsp;</label>
          <button type="submit" className="btn-secondary">
            Apply Filters
          </button>
        </div>
      </form>
      <Link href="/leads/new" className="btn-primary btn-link">
        New Lead
      </Link>
      </div>
    </div>
  );
}
