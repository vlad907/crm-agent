interface LeadListPaginationProps {
  canGoPrev: boolean;
  canGoNext: boolean;
  total: number;
  loading: boolean;
  onPrev: () => void;
  onNext: () => void;
}

export function LeadListPagination({
  canGoPrev,
  canGoNext,
  total,
  loading,
  onPrev,
  onNext
}: LeadListPaginationProps) {
  return (
    <div className="inline-actions" style={{ marginTop: 12, justifyContent: "space-between", alignItems: "center" }}>
      <div className="inline-actions">
        <button className="btn-secondary" disabled={!canGoPrev || loading} onClick={onPrev}>
          Prev
        </button>
        <button className="btn-secondary" disabled={!canGoNext || loading} onClick={onNext}>
          Next
        </button>
      </div>
      <span className="stat-pill">Total Leads: {total}</span>
    </div>
  );
}
