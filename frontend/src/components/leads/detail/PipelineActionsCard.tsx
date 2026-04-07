import { Spinner } from "@/src/components/Spinner";

type ActionKey = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";
type StageState = "done" | "active" | "pending";

interface StageItem {
  label: string;
  state: StageState;
}

interface ActionControl {
  disabled: boolean;
  reason?: string | null;
}

interface PipelineActionsCardProps {
  isBusy: boolean;
  loadingByAction: Record<ActionKey, boolean>;
  onIngest: () => void;
  onAgent1: () => void;
  onAgent2: () => void;
  onAgent3: () => void;
  onRefresh: () => void;
  stageItems: StageItem[];
  controls: Record<ActionKey, ActionControl>;
}

export function PipelineActionsCard({
  isBusy,
  loadingByAction,
  onIngest,
  onAgent1,
  onAgent2,
  onAgent3,
  onRefresh,
  stageItems,
  controls
}: PipelineActionsCardProps) {
  return (
    <section className="card stack pipeline-actions-card">
      <h2>Pipeline Actions</h2>
      <div className="pipeline-stepper">
        {stageItems.map((stage, i) => (
          <div key={stage.label} className="pipeline-stepper-item">
            <div className="pipeline-stepper-row">
              <div className={`pipeline-stepper-dot ${stage.state}`} aria-hidden />
              {i < stageItems.length - 1 ? (
                <div
                  className={`pipeline-stepper-line ${stage.state === "done" ? "filled" : ""}`}
                  aria-hidden
                />
              ) : null}
            </div>
            <span className={`pipeline-stepper-label stage-${stage.state}`}>{stage.label}</span>
          </div>
        ))}
      </div>
      <div className="inline-actions">
        <button className="btn-primary" disabled={isBusy || controls.ingest.disabled} title={controls.ingest.reason ?? ""} onClick={onIngest}>
          {loadingByAction.ingest ? <Spinner size="sm" label="Ingesting" /> : "Ingest Website"}
        </button>
        <button className="btn-primary" disabled={isBusy || controls.agent1.disabled} title={controls.agent1.reason ?? ""} onClick={onAgent1}>
          {loadingByAction.agent1 ? <Spinner size="sm" label="Running" /> : "Run Agent 1"}
        </button>
        <button className="btn-primary" disabled={isBusy || controls.agent2.disabled} title={controls.agent2.reason ?? ""} onClick={onAgent2}>
          {loadingByAction.agent2 ? <Spinner size="sm" label="Running" /> : "Run Agent 2"}
        </button>
        <button className="btn-primary" disabled={isBusy || controls.agent3.disabled} title={controls.agent3.reason ?? ""} onClick={onAgent3}>
          {loadingByAction.agent3 ? <Spinner size="sm" label="Running" /> : "Run Agent 3"}
        </button>
        <button className="btn-secondary" disabled={isBusy || controls.refresh.disabled} title={controls.refresh.reason ?? ""} onClick={onRefresh}>
          {loadingByAction.refresh ? <Spinner size="sm" label="Refreshing" /> : "Refresh Context"}
        </button>
      </div>
    </section>
  );
}
