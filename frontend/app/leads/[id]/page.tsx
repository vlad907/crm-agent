"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { LatestContextCard } from "@/src/components/leads/detail/LatestContextCard";
import { LeadSummaryCard } from "@/src/components/leads/detail/LeadSummaryCard";
import { PipelineActionsCard } from "@/src/components/leads/detail/PipelineActionsCard";
import {
  ApiError,
  getLead,
  getLeadDrafts,
  getLeadWebsitePages,
  getLatestContext,
  ingestWebsite,
  runAgent1,
  runAgent2,
  runAgent3
} from "@/src/lib/api";
import { resolveLeadPipeline } from "@/src/lib/leadPipeline";
import { Draft, Lead, LatestContext as LatestContextType, PartnershipContext, WebsitePage } from "@/src/lib/types";

type ActionKey = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";
type StageState = "done" | "active" | "pending";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Unexpected error";
}

function timeAgo(date: string): string {
  const diff = Date.now() - new Date(date).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(date).toLocaleDateString();
}

function PartnershipContextPanel({ ctx }: { ctx: PartnershipContext }) {
  return (
    <div className="card" style={{ borderLeft: "4px solid var(--accent-purple, #7c3aed)" }}>
      <h3 className="ld-section-title" style={{ color: "var(--accent-purple, #7c3aed)", marginBottom: 12 }}>
        Partnership Context
      </h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px", marginBottom: 12 }}>
        {ctx.fit_score != null && (
          <div>
            <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--text-secondary)" }}>Fit Score</span>
            <div style={{ fontWeight: 700, fontSize: "1.1rem", color: ctx.fit_score >= 0.7 ? "var(--green)" : ctx.fit_score >= 0.4 ? "var(--amber)" : "var(--red)" }}>
              {Math.round(ctx.fit_score * 100)}%
            </div>
          </div>
        )}
        {ctx.partnership_type && (
          <div>
            <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--text-secondary)" }}>Partnership Type</span>
            <div style={{ fontWeight: 600, textTransform: "capitalize" }}>{ctx.partnership_type.replace(/_/g, " ")}</div>
          </div>
        )}
      </div>
      {ctx.company_summary && (
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--text-secondary)" }}>About Them</span>
          <p style={{ margin: "4px 0 0", fontSize: ".88rem" }}>{ctx.company_summary}</p>
        </div>
      )}
      {ctx.recommended_outreach_angle && (
        <div style={{ marginBottom: 10 }}>
          <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--text-secondary)" }}>Recommended Outreach Angle</span>
          <p style={{ margin: "4px 0 0", fontSize: ".88rem", fontStyle: "italic" }}>{ctx.recommended_outreach_angle}</p>
        </div>
      )}
      {Array.isArray(ctx.reasons) && ctx.reasons.length > 0 && (
        <div>
          <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--text-secondary)" }}>Fit Reasons</span>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: ".86rem" }}>
            {ctx.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;

  const [lead, setLead] = useState<Lead | null>(null);
  const [context, setContext] = useState<LatestContextType | null>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [latestDraft, setLatestDraft] = useState<Draft | null>(null);
  const [websitePages, setWebsitePages] = useState<WebsitePage[]>([]);

  const [leadLoading, setLeadLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
  const [pagesLoading, setPagesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const [showFullSnapshot, setShowFullSnapshot] = useState(false);
  const [loadingByAction, setLoadingByAction] = useState<Record<ActionKey, boolean>>({
    ingest: false,
    agent1: false,
    agent2: false,
    agent3: false,
    refresh: false,
  });

  const snapshotText = context?.snapshot?.raw_text ?? "";
  const isSnapshotLong = snapshotText.length > 800;
  const snapshotPreview = useMemo(() => {
    if (!snapshotText) return "";
    if (showFullSnapshot || !isSnapshotLong) return snapshotText;
    return `${snapshotText.slice(0, 800)}...`;
  }, [snapshotText, showFullSnapshot, isSnapshotLong]);

  async function loadLead(): Promise<void> {
    if (!leadId) return;
    setLeadLoading(true);
    try {
      const data = await getLead(leadId);
      setLead(data);
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setLeadLoading(false);
    }
  }

  async function loadContext(): Promise<void> {
    if (!leadId) return;
    setContextLoading(true);
    setPagesLoading(true);
    try {
      const [ctx, allDrafts, pages] = await Promise.all([
        getLatestContext(leadId).catch((e: unknown) => {
          if (e instanceof ApiError && e.status === 404) return null;
          throw e;
        }),
        getLeadDrafts(leadId, 20, 0).catch((e: unknown) => {
          if (e instanceof ApiError && e.status === 404) return [];
          throw e;
        }),
        getLeadWebsitePages(leadId, 100, 0).catch((e: unknown) => {
          if (e instanceof ApiError && e.status === 404) return [];
          throw e;
        }),
      ]);
      setContext(ctx);
      setDrafts(allDrafts);
      setLatestDraft(allDrafts.length > 0 ? allDrafts[0] : null);
      setWebsitePages(pages);
      setError(null);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setContextLoading(false);
      setPagesLoading(false);
    }
  }

  async function runAction(key: ActionKey, label: string, action: (id: string) => Promise<unknown>): Promise<void> {
    if (!leadId) return;
    setLoadingByAction(prev => ({ ...prev, [key]: true }));
    setActionMessage(null);
    setError(null);
    try {
      await action(leadId);
      setActionMessage(`${label} completed.`);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      await Promise.all([loadLead(), loadContext()]);
      setLoadingByAction(prev => ({ ...prev, [key]: false }));
    }
  }

  useEffect(() => {
    if (!leadId) return;
    void loadLead();
    void loadContext();
  }, [leadId]);

  const isBusy = Object.values(loadingByAction).some(Boolean);
  const summary = lead ? resolveLeadPipeline(lead) : null;

  const stageItems: Array<{ label: string; state: StageState }> = [
    {
      label: "NEW",
      state: summary && (summary.has_snapshot || summary.has_agent1_output || summary.has_draft || summary.has_agent3_verdict) ? "done" : "active",
    },
    { label: "INGESTED", state: summary?.has_snapshot ? "done" : summary ? "active" : "pending" },
    { label: "AGENT1", state: summary?.has_agent1_output ? "done" : summary?.has_snapshot ? "active" : "pending" },
    { label: "AGENT2", state: summary?.has_draft ? "done" : summary?.has_agent1_output ? "active" : "pending" },
    { label: "AGENT3", state: summary?.has_agent3_verdict ? "done" : summary?.has_draft ? "active" : "pending" },
    {
      label:
        summary?.computed_stage === "sent" ? "SENT"
          : summary?.computed_stage === "replied" ? "REPLIED"
          : summary?.computed_stage === "converted" ? "CONVERTED"
          : summary?.computed_stage === "archived" ? "ARCHIVED"
          : summary?.computed_stage === "needs_review" ? "NEEDS REVIEW"
          : summary?.computed_stage === "approved" ? "APPROVED"
          : "PENDING REVIEW",
      state:
        summary && ["approved", "needs_review", "sent", "replied", "converted", "archived"].includes(summary.computed_stage)
          ? "done"
          : summary?.has_agent3_verdict ? "active" : "pending",
    },
  ];

  const controls = {
    ingest: { disabled: !lead?.website_url, reason: !lead ? "Lead is loading." : !lead.website_url ? "Website URL required." : null },
    agent1: { disabled: !summary?.has_snapshot, reason: !lead ? "Lead is loading." : !summary?.has_snapshot ? "Run Ingest first." : null },
    agent2: { disabled: !summary?.has_agent1_output, reason: !lead ? "Lead is loading." : !summary?.has_agent1_output ? "Run Agent 1 first." : null },
    agent3: { disabled: !summary?.has_draft, reason: !lead ? "Lead is loading." : !summary?.has_draft ? "Run Agent 2 first." : null },
    refresh: { disabled: !summary?.has_snapshot, reason: !lead ? "Lead is loading." : !summary?.has_snapshot ? "No context yet." : null },
  };

  // Build activity timeline from available data
  const activityItems: Array<{ label: string; time: string; icon: "check" | "ai" | "mail" | "eye" | "clock" }> = [];
  if (lead?.created_at) activityItems.push({ label: "Lead created", time: lead.created_at, icon: "clock" });
  if (context?.snapshot?.fetched_at) activityItems.push({ label: "Website ingested", time: context.snapshot.fetched_at, icon: "check" });
  if (context?.agent1_output) activityItems.push({ label: "Agent 1 completed research", time: lead?.updated_at ?? "", icon: "ai" });
  if (latestDraft?.created_at) activityItems.push({ label: `Draft generated: "${latestDraft.subject}"`, time: latestDraft.created_at, icon: "mail" });
  if (context?.agent3_decision && latestDraft?.updated_at) {
    activityItems.push({
      label: `Agent 3: ${context.agent3_decision === "send" ? "Approved" : "Needs review"}`,
      time: latestDraft.updated_at,
      icon: context.agent3_decision === "send" ? "check" : "eye",
    });
  }
  if (latestDraft?.sent_at) activityItems.push({ label: "Email sent via Gmail", time: latestDraft.sent_at, icon: "mail" });
  activityItems.sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());

  return (
    <div className="ld-page">
      {/* Header */}
      <div className="ld-header">
        <Link href="/" className="ld-back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          Back to Leads
        </Link>
        {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
        {actionMessage && <div className="success" style={{ marginTop: 8 }}>{actionMessage}</div>}
      </div>

      {/* Main two-column layout */}
      <div className="ld-grid">
        {/* Left column: main content */}
        <div className="ld-main">
          <LeadSummaryCard
            lead={lead}
            loading={leadLoading}
            draftsCount={drafts.length}
            hasSnapshot={!!context?.snapshot}
          />

          {lead?.lead_type === "partnership" && lead.partnership_context && (
            <PartnershipContextPanel ctx={lead.partnership_context as PartnershipContext} />
          )}

          <PipelineActionsCard
            isBusy={isBusy}
            loadingByAction={loadingByAction}
            onIngest={() => void runAction("ingest", "Ingest Website", ingestWebsite)}
            onAgent1={() => void runAction("agent1", "Run Agent 1", runAgent1)}
            onAgent2={() => void runAction("agent2", "Run Agent 2", runAgent2)}
            onAgent3={() => void runAction("agent3", "Run Agent 3", runAgent3)}
            onRefresh={() => void runAction("refresh", "Refresh Context", async () => undefined)}
            stageItems={stageItems}
            controls={controls}
            websiteUrl={lead?.website_url}
          />

          <LatestContextCard
            context={context}
            latestDraft={latestDraft}
            loading={contextLoading}
            snapshotPreview={snapshotPreview}
            isSnapshotLong={isSnapshotLong}
            showFullSnapshot={showFullSnapshot}
            onToggleSnapshot={() => setShowFullSnapshot(prev => !prev)}
          />

          {/* Website pages (collapsible) */}
          {websitePages.length > 0 && (
            <details className="ld-pages-section">
              <summary className="ld-section-title" style={{ cursor: "pointer" }}>
                Ingested Pages ({websitePages.length})
              </summary>
              <div className="ld-pages-grid">
                {websitePages.map(page => (
                  <article key={page.id} className="ld-page-card">
                    <div className="ld-page-card-header">
                      <span className="ld-page-type">{page.page_type}</span>
                      <span className="ld-page-date">{new Date(page.created_at).toLocaleDateString()}</span>
                    </div>
                    <a href={page.url} target="_blank" rel="noreferrer" className="ld-page-url">{page.url}</a>
                    {(page.extracted_emails.length > 0 || page.extracted_phones.length > 0) && (
                      <div className="ld-page-extracted">
                        {page.extracted_emails.length > 0 && <span>Emails: {page.extracted_emails.join(", ")}</span>}
                        {page.extracted_phones.length > 0 && <span>Phones: {page.extracted_phones.join(", ")}</span>}
                      </div>
                    )}
                    <details>
                      <summary style={{ fontSize: ".82rem", fontWeight: 600, color: "var(--text-secondary)", cursor: "pointer" }}>View text</summary>
                      <pre className="ld-code-block" style={{ marginTop: 6, maxHeight: 200 }}>{page.raw_text}</pre>
                    </details>
                  </article>
                ))}
              </div>
            </details>
          )}
        </div>

        {/* Right column: activity timeline */}
        <aside className="ld-sidebar">
          <div className="ld-activity-card">
            <h3 className="ld-section-title">Activity</h3>
            {activityItems.length === 0 ? (
              <p className="muted" style={{ fontSize: ".84rem" }}>No activity yet.</p>
            ) : (
              <div className="ld-timeline">
                {activityItems.map((item, i) => (
                  <div key={i} className="ld-timeline-item">
                    <div className={`ld-timeline-icon ld-tl-${item.icon}`}>
                      {item.icon === "check" && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>}
                      {item.icon === "ai" && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2 L15 9 22 9 16.5 14 18.5 21 12 17 5.5 21 7.5 14 2 9 9 9Z"/></svg>}
                      {item.icon === "mail" && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>}
                      {item.icon === "eye" && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>}
                      {item.icon === "clock" && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>}
                    </div>
                    <div className="ld-timeline-content">
                      <span className="ld-timeline-label">{item.label}</span>
                      <span className="ld-timeline-time">{item.time ? timeAgo(item.time) : ""}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
