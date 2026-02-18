import Link from "next/link";
import { FormEvent } from "react";

interface LeadListFiltersProps {
  statusInput: string;
  searchInput: string;
  onStatusChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onApplyFilters: (event: FormEvent<HTMLFormElement>) => void;
}

export function LeadListFilters({
  statusInput,
  searchInput,
  onStatusChange,
  onSearchChange,
  onApplyFilters
}: LeadListFiltersProps) {
  return (
    <div className="card row" style={{ justifyContent: "space-between", alignItems: "end" }}>
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
  );
}
