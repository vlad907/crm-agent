import { Draft, LatestContext } from "@/src/lib/types";

interface LatestContextCardProps {
  context: LatestContext | null;
  latestDraft: Draft | null;
  loading: boolean;
  snapshotPreview: string;
  isSnapshotLong: boolean;
  showFullSnapshot: boolean;
  onToggleSnapshot: () => void;
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export function LatestContextCard({
  context,
  latestDraft,
  loading,
  snapshotPreview,
  isSnapshotLong,
  showFullSnapshot,
  onToggleSnapshot
}: LatestContextCardProps) {
  return (
    <section className="card stack">
      <h2>Latest Context</h2>
      {loading ? <div className="muted">Loading context...</div> : null}

      {context?.snapshot ? (
        <div className="subcard stack">
          <h3>Snapshot Text</h3>
          <pre className="snapshot-text">{snapshotPreview || "(empty)"}</pre>
          {isSnapshotLong ? (
            <button className="btn-secondary" onClick={onToggleSnapshot}>
              {showFullSnapshot ? "Show less" : "Show more"}
            </button>
          ) : null}
        </div>
      ) : (
        <div className="muted">No snapshot context yet.</div>
      )}

      <div className="context-grid">
        <div className="subcard stack">
          <h3>Agent 1 Output</h3>
          {context?.agent1_output ? <pre>{prettyJson(context.agent1_output)}</pre> : <div className="muted">No agent1_output.</div>}
        </div>

        <div className="subcard stack">
          <h3>Latest Draft</h3>
          {latestDraft ? (
            <>
              <div className="kv-grid">
                <div className="kv">
                  <strong>Subject</strong>
                  {latestDraft.subject}
                </div>
                <div className="kv">
                  <strong>Decision</strong>
                  {latestDraft.decision}
                </div>
              </div>
              <pre>{latestDraft.body}</pre>
            </>
          ) : (
            <div className="muted">No draft yet.</div>
          )}
        </div>
      </div>

      <div className="subcard stack">
        <h3>Agent 3 Verdict</h3>
        {context?.agent3_decision ? (
          <>
            <div className="kv-grid">
              <div className="kv">
                <strong>Decision</strong>
                {context.agent3_decision}
              </div>
              <div className="kv">
                <strong>Issues</strong>
                {context.agent3_issues && context.agent3_issues.length > 0 ? context.agent3_issues.join("; ") : "No issues"}
              </div>
            </div>
            {context.final_email ? (
              <>
                <div className="kv-grid">
                  <div className="kv">
                    <strong>Final Subject</strong>
                    {context.final_email.subject}
                  </div>
                </div>
                <pre>{context.final_email.email_body}</pre>
              </>
            ) : null}
          </>
        ) : (
          <div className="muted">No agent3 verdict yet.</div>
        )}
      </div>
    </section>
  );
}
