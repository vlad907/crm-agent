import { Spinner } from "@/src/components/Spinner";

type ActionKey = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";
type StageState = "done" | "active" | "pending" | "error";

interface StageItem {
  label: string;
  state: StageState;
  description?: string;
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
  websiteUrl?: string | null;
}

function nextActionLabel(stageItems: StageItem[]): { label: string; description: string } | null {
  const active = stageItems.find(s => s.state === "active");
  if (!active) return null;
  const label = active.label;
  if (label === "NEW" || label === "INGESTED") return { label: "Ingest Website", description: "Crawl and extract website content" };
  if (label === "AGENT1") return { label: "Run Research Agent", description: "AI analyzes the company" };
  if (label === "AGENT2") return { label: "Generate Email Draft", description: "AI writes outreach email" };
  if (label === "AGENT3") return { label: "Verify & Approve", description: "AI reviews the draft" };
  return null;
}

function nextActionKey(stageItems: StageItem[]): ActionKey | null {
  const active = stageItems.find(s => s.state === "active");
  if (!active) return null;
  const label = active.label;
  if (label === "NEW" || label === "INGESTED") return "ingest";
  if (label === "AGENT1") return "agent1";
  if (label === "AGENT2") return "agent2";
  if (label === "AGENT3") return "agent3";
  return null;
}

const STAGE_DESCRIPTIONS: Record<string, string> = {
  NEW: "Lead created",
  INGESTED: "Website crawled",
  AGENT1: "Company research",
  AGENT2: "Email draft",
  AGENT3: "Quality check",
  APPROVED: "Ready to send",
  SENT: "Email sent",
  REPLIED: "Got reply",
  CONVERTED: "Deal closed",
  ARCHIVED: "Archived",
  "NEEDS REVIEW": "Manual review",
  "PENDING REVIEW": "Awaiting review",
};

export function PipelineActionsCard({
  isBusy,
  loadingByAction,
  onIngest,
  onAgent1,
  onAgent2,
  onAgent3,
  onRefresh,
  stageItems,
  controls,
  websiteUrl,
}: PipelineActionsCardProps) {
  const next = nextActionLabel(stageItems);
  const nextKey = nextActionKey(stageItems);
  const actionMap: Record<ActionKey, () => void> = { ingest: onIngest, agent1: onAgent1, agent2: onAgent2, agent3: onAgent3, refresh: onRefresh };
  const currentStage = stageItems.find(s => s.state === "active") ?? stageItems.filter(s => s.state === "done").pop();

  return (
    <section className="ld-pipeline-card">
      {/* Visual stepper */}
      <div className="ld-stepper">
        {stageItems.map((stage, i) => (
          <div key={stage.label} className={`ld-step ${stage.state}`}>
            <div className="ld-step-track">
              <div className={`ld-step-dot ${stage.state}`}>
                {stage.state === "done" && (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                )}
                {stage.state === "active" && <div className="ld-step-pulse" />}
              </div>
              {i < stageItems.length - 1 && (
                <div className={`ld-step-line ${stage.state === "done" ? "filled" : ""}`} />
              )}
            </div>
            <div className="ld-step-content">
              <span className={`ld-step-label ${stage.state}`}>{stage.label}</span>
              <span className="ld-step-desc">{STAGE_DESCRIPTIONS[stage.label] ?? ""}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Current status + primary action */}
      <div className="ld-pipeline-actions">
        <div className="ld-pipeline-status">
          {currentStage && (
            <>
              <span className="ld-pipeline-status-label">Current Stage</span>
              <span className="ld-pipeline-status-value">{currentStage.label}</span>
            </>
          )}
        </div>

        <div className="ld-pipeline-btns">
          {/* Primary: next step */}
          {next && nextKey && (
            <button
              className="ld-btn-next"
              disabled={isBusy || controls[nextKey].disabled}
              title={controls[nextKey].reason ?? next.description}
              onClick={actionMap[nextKey]}
            >
              {loadingByAction[nextKey] ? (
                <Spinner size="sm" label="Running..." />
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  {next.label}
                </>
              )}
            </button>
          )}

          {/* Secondary actions */}
          <div className="ld-secondary-actions">
            {controls.ingest && !controls.ingest.disabled && stageItems[1]?.state === "done" && (
              <button className="ld-btn-secondary" disabled={isBusy} title="Re-crawl the website" onClick={onIngest}>
                {loadingByAction.ingest ? <Spinner size="sm" /> : "Re-ingest"}
              </button>
            )}
            {controls.agent1 && !controls.agent1.disabled && stageItems[2]?.state === "done" && (
              <button className="ld-btn-secondary" disabled={isBusy} title="Re-run research agent" onClick={onAgent1}>
                {loadingByAction.agent1 ? <Spinner size="sm" /> : "Re-run Agent 1"}
              </button>
            )}
            {controls.agent2 && !controls.agent2.disabled && stageItems[3]?.state === "done" && (
              <button className="ld-btn-secondary" disabled={isBusy} title="Regenerate email draft" onClick={onAgent2}>
                {loadingByAction.agent2 ? <Spinner size="sm" /> : "Re-run Agent 2"}
              </button>
            )}
            {controls.agent3 && !controls.agent3.disabled && stageItems[4]?.state === "done" && (
              <button className="ld-btn-secondary" disabled={isBusy} title="Re-verify draft" onClick={onAgent3}>
                {loadingByAction.agent3 ? <Spinner size="sm" /> : "Re-run Agent 3"}
              </button>
            )}
            {controls.refresh && !controls.refresh.disabled && (
              <button className="ld-btn-secondary" disabled={isBusy} title="Refresh context data" onClick={onRefresh}>
                {loadingByAction.refresh ? <Spinner size="sm" /> : "Refresh Context"}
              </button>
            )}
            {websiteUrl && (
              <a href={websiteUrl} target="_blank" rel="noreferrer" className="ld-btn-secondary">Open Website</a>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
