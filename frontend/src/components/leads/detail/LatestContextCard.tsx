"use client";

import { useState } from "react";
import { Draft, LatestContext, JsonObject } from "@/src/lib/types";

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

function extractAiSummary(agent1: JsonObject | null | undefined): {
  summary: string | null;
  industry: string | null;
  signals: string[];
  outreachAngle: string | null;
  riskFlags: string[];
} {
  if (!agent1) return { summary: null, industry: null, signals: [], outreachAngle: null, riskFlags: [] };

  const get = (key: string): string | null => {
    const v = agent1[key];
    return typeof v === "string" && v.trim() ? v.trim() : null;
  };
  const getArr = (key: string): string[] => {
    const v = agent1[key];
    if (Array.isArray(v)) return v.map(String).filter(Boolean);
    return [];
  };

  return {
    summary: get("company_summary") ?? get("summary") ?? get("business_overview"),
    industry: get("industry") ?? get("detected_industry"),
    signals: getArr("notable_signals").length ? getArr("notable_signals") : getArr("key_signals"),
    outreachAngle: get("recommended_outreach_angle") ?? get("outreach_angle") ?? get("recommended_angle"),
    riskFlags: getArr("risk_flags").length ? getArr("risk_flags") : getArr("concerns"),
  };
}

type ContextTab = "summary" | "snapshot" | "agent1" | "draft" | "agent3";

export function LatestContextCard({
  context,
  latestDraft,
  loading,
  snapshotPreview,
  isSnapshotLong,
  showFullSnapshot,
  onToggleSnapshot,
}: LatestContextCardProps) {
  const ai = extractAiSummary(context?.agent1_output);
  const hasSummary = !!(ai.summary || ai.industry || ai.signals.length || ai.outreachAngle);
  const defaultTab: ContextTab = hasSummary ? "summary" : "snapshot";
  const [activeTab, setActiveTab] = useState<ContextTab>(defaultTab);

  const tabs: Array<{ id: ContextTab; label: string; icon: string; hasContent: boolean }> = [
    { id: "summary", label: "AI Summary", icon: "sparkle", hasContent: hasSummary },
    { id: "snapshot", label: "Raw Snapshot", icon: "file", hasContent: !!context?.snapshot },
    { id: "agent1", label: "Agent 1", icon: "cpu", hasContent: !!context?.agent1_output },
    { id: "draft", label: "Draft", icon: "mail", hasContent: !!latestDraft },
    { id: "agent3", label: "Agent 3", icon: "shield", hasContent: !!context?.agent3_decision },
  ];

  return (
    <section className="ld-context-card">
      <div className="ld-context-header">
        <h2 className="ld-section-title">AI Context</h2>
        <div className="ld-context-tabs" role="tablist">
          {tabs.map(tab => (
            <button key={tab.id} role="tab" aria-selected={activeTab === tab.id}
              className={`ld-context-tab${activeTab === tab.id ? " active" : ""}${!tab.hasContent ? " empty" : ""}`}
              onClick={() => setActiveTab(tab.id)}>
              {tab.label}
              {tab.hasContent && <span className="ld-tab-dot" />}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="ld-context-body">
          <div className="ld-skeleton-line" style={{ width: "80%", height: 14 }} />
          <div className="ld-skeleton-line" style={{ width: "60%", height: 14, marginTop: 10 }} />
          <div className="ld-skeleton-line" style={{ width: "70%", height: 14, marginTop: 10 }} />
        </div>
      ) : (
        <div className="ld-context-body">
          {/* AI Summary tab */}
          {activeTab === "summary" && (
            hasSummary ? (
              <div className="ld-ai-summary">
                {ai.summary && (
                  <div className="ld-ai-block">
                    <h3 className="ld-ai-block-title">Company Overview</h3>
                    <p className="ld-ai-block-text">{ai.summary}</p>
                  </div>
                )}
                {ai.industry && (
                  <div className="ld-ai-block">
                    <h3 className="ld-ai-block-title">Detected Industry</h3>
                    <span className="ld-ai-chip">{ai.industry}</span>
                  </div>
                )}
                {ai.signals.length > 0 && (
                  <div className="ld-ai-block">
                    <h3 className="ld-ai-block-title">Notable Signals</h3>
                    <ul className="ld-ai-list">
                      {ai.signals.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
                {ai.outreachAngle && (
                  <div className="ld-ai-block ld-ai-highlight">
                    <h3 className="ld-ai-block-title">Recommended Outreach Angle</h3>
                    <p className="ld-ai-block-text">{ai.outreachAngle}</p>
                  </div>
                )}
                {ai.riskFlags.length > 0 && (
                  <div className="ld-ai-block ld-ai-warning">
                    <h3 className="ld-ai-block-title">Risk Flags</h3>
                    <ul className="ld-ai-list">
                      {ai.riskFlags.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="ld-empty">
                <p>No AI summary available yet.</p>
                <p className="muted">Run Agent 1 to generate a company research summary.</p>
              </div>
            )
          )}

          {/* Raw Snapshot */}
          {activeTab === "snapshot" && (
            context?.snapshot ? (
              <div>
                <pre className="ld-code-block">{snapshotPreview || "(empty)"}</pre>
                {isSnapshotLong && (
                  <button className="ld-btn-secondary" style={{ marginTop: 8 }} onClick={onToggleSnapshot}>
                    {showFullSnapshot ? "Show less" : "Show full snapshot"}
                  </button>
                )}
              </div>
            ) : (
              <div className="ld-empty">No snapshot yet. Run Ingest Website first.</div>
            )
          )}

          {/* Agent 1 raw output */}
          {activeTab === "agent1" && (
            context?.agent1_output ? (
              <pre className="ld-code-block">{prettyJson(context.agent1_output)}</pre>
            ) : (
              <div className="ld-empty">No Agent 1 output yet.</div>
            )
          )}

          {/* Draft */}
          {activeTab === "draft" && (
            latestDraft ? (
              <div className="ld-draft-preview">
                <div className="ld-draft-header">
                  <div className="ld-draft-field">
                    <span className="ld-draft-field-label">Subject</span>
                    <span className="ld-draft-field-value">{latestDraft.subject}</span>
                  </div>
                  <div className="ld-draft-field">
                    <span className="ld-draft-field-label">Decision</span>
                    <span className={`ld-decision-badge ${latestDraft.decision === "send" ? "ld-decision-send" : "ld-decision-hold"}`}>
                      {latestDraft.decision}
                    </span>
                  </div>
                </div>
                <pre className="ld-code-block ld-draft-body">{latestDraft.body}</pre>
              </div>
            ) : (
              <div className="ld-empty">No draft yet. Run Agent 2 to generate one.</div>
            )
          )}

          {/* Agent 3 verdict */}
          {activeTab === "agent3" && (
            context?.agent3_decision ? (
              <div className="ld-verdict">
                <div className="ld-verdict-header">
                  <span className={`ld-decision-badge ${context.agent3_decision === "send" ? "ld-decision-send" : "ld-decision-hold"}`} style={{ fontSize: ".9rem", padding: "6px 16px" }}>
                    {context.agent3_decision === "send" ? "Approved to Send" : "On Hold"}
                  </span>
                </div>
                {context.agent3_issues && context.agent3_issues.length > 0 && (
                  <div className="ld-ai-block ld-ai-warning" style={{ marginTop: 12 }}>
                    <h3 className="ld-ai-block-title">Issues Found</h3>
                    <ul className="ld-ai-list">
                      {context.agent3_issues.map((issue, i) => <li key={i}>{issue}</li>)}
                    </ul>
                  </div>
                )}
                {context.final_email && (
                  <div style={{ marginTop: 14 }}>
                    <div className="ld-draft-field" style={{ marginBottom: 8 }}>
                      <span className="ld-draft-field-label">Final Subject</span>
                      <span className="ld-draft-field-value">{context.final_email.subject}</span>
                    </div>
                    <pre className="ld-code-block ld-draft-body">{context.final_email.email_body}</pre>
                  </div>
                )}
                {!context.agent3_issues?.length && !context.final_email && (
                  <p className="muted" style={{ marginTop: 8 }}>No issues found. Draft is clean.</p>
                )}
              </div>
            ) : (
              <div className="ld-empty">No Agent 3 verdict yet.</div>
            )
          )}
        </div>
      )}
    </section>
  );
}
