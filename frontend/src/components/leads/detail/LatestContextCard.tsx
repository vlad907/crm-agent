"use client";

import { useState } from "react";
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

type ContextTab = "snapshot" | "agent1" | "draft" | "agent3";

export function LatestContextCard({
  context,
  latestDraft,
  loading,
  snapshotPreview,
  isSnapshotLong,
  showFullSnapshot,
  onToggleSnapshot
}: LatestContextCardProps) {
  const [activeTab, setActiveTab] = useState<ContextTab>("snapshot");

  const tabs: Array<{ id: ContextTab; label: string; hasContent: boolean }> = [
    { id: "snapshot", label: "Snapshot", hasContent: !!context?.snapshot },
    { id: "agent1", label: "Agent 1", hasContent: !!context?.agent1_output },
    { id: "draft", label: "Draft", hasContent: !!latestDraft },
    { id: "agent3", label: "Agent 3", hasContent: !!context?.agent3_decision }
  ];

  return (
    <section className="card stack context-card">
      <div className="context-card-header">
        <h2>Latest Context</h2>
        <div className="context-tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`context-tab ${activeTab === tab.id ? "active" : ""} ${tab.hasContent ? "" : "empty"}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {!tab.hasContent && <span className="context-tab-hint">—</span>}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="muted" style={{ padding: 24 }}>Loading context...</div>
      ) : (
        <div className="context-tab-panel">
          {activeTab === "snapshot" && (
            <div className="context-card-section">
              {context?.snapshot ? (
                <>
                  <pre className="snapshot-text">{snapshotPreview || "(empty)"}</pre>
                  {isSnapshotLong ? (
                    <button className="btn-secondary" onClick={onToggleSnapshot}>
                      {showFullSnapshot ? "Show less" : "Show more"}
                    </button>
                  ) : null}
                </>
              ) : (
                <div className="muted">No snapshot context yet. Run Ingest Website first.</div>
              )}
            </div>
          )}

          {activeTab === "agent1" && (
            <div className="context-card-section">
              <h3>Agent 1 Output</h3>
              {context?.agent1_output ? (
                <pre>{prettyJson(context.agent1_output)}</pre>
              ) : (
                <div className="muted">No agent1_output.</div>
              )}
            </div>
          )}

          {activeTab === "draft" && (
            <div className="context-card-section">
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
          )}

          {activeTab === "agent3" && (
            <div className="context-card-section">
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
                      {context.agent3_issues && context.agent3_issues.length > 0
                        ? context.agent3_issues.join("; ")
                        : "No issues"}
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
          )}
        </div>
      )}
    </section>
  );
}
