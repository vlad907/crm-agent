type ActionKey = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";
type StageState = "done" | "active" | "pending";

interface PipelineActionsCardProps {
  isBusy: boolean;
  loadingByAction: Record<ActionKey, boolean>;
  onIngest: () => void;
  onAgent1: () => void;
  onAgent2: () => void;
  onAgent3: () => void;
  onRefresh: () => void;
  stageStates: StageState[];
}

export function PipelineActionsCard({
  isBusy,
  loadingByAction,
  onIngest,
  onAgent1,
  onAgent2,
  onAgent3,
  onRefresh,
  stageStates
}: PipelineActionsCardProps) {
  const stageLabels = ["Ingest", "Agent 1", "Agent 2", "Agent 3"];

  return (
    <section className="card stack">
      <h2>Pipeline Actions</h2>
      <p className="muted">Run each step in order and refresh to inspect context output.</p>
      <div className="stage-row">
        {stageLabels.map((label, index) => (
          <span key={label} className={`stage-pill stage-${stageStates[index]}`}>
            {label}
          </span>
        ))}
      </div>
      <div className="inline-actions">
        <button className="btn-primary" disabled={isBusy} onClick={onIngest}>
          {loadingByAction.ingest ? "Ingesting..." : "Ingest Website"}
        </button>
        <button className="btn-primary" disabled={isBusy} onClick={onAgent1}>
          {loadingByAction.agent1 ? "Running..." : "Run Agent 1"}
        </button>
        <button className="btn-primary" disabled={isBusy} onClick={onAgent2}>
          {loadingByAction.agent2 ? "Running..." : "Run Agent 2"}
        </button>
        <button className="btn-primary" disabled={isBusy} onClick={onAgent3}>
          {loadingByAction.agent3 ? "Running..." : "Run Agent 3"}
        </button>
        <button className="btn-secondary" disabled={isBusy} onClick={onRefresh}>
          {loadingByAction.refresh ? "Refreshing..." : "Refresh Context"}
        </button>
      </div>
    </section>
  );
}
