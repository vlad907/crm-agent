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
import { Draft, Lead, LatestContext, WebsitePage } from "@/src/lib/types";

type ActionKey = "ingest" | "agent1" | "agent2" | "agent3" | "refresh";
type StageState = "done" | "active" | "pending";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function LeadDetailPage() {
  const params = useParams<{ id: string }>();
  const leadId = params.id;

  const [lead, setLead] = useState<Lead | null>(null);
  const [context, setContext] = useState<LatestContext | null>(null);
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
    refresh: false
  });

  const snapshotText = context?.snapshot?.raw_text ?? "";
  const isSnapshotLong = snapshotText.length > 800;
  const snapshotPreview = useMemo(() => {
    if (!snapshotText) {
      return "";
    }
    if (showFullSnapshot || !isSnapshotLong) {
      return snapshotText;
    }
    return `${snapshotText.slice(0, 800)}...`;
  }, [snapshotText, showFullSnapshot, isSnapshotLong]);

  async function loadLead(): Promise<void> {
    if (!leadId) {
      return;
    }

    setLeadLoading(true);
    try {
      const data = await getLead(leadId);
      setLead(data);
      setError(null);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLeadLoading(false);
    }
  }

  async function loadContext(): Promise<void> {
    if (!leadId) {
      return;
    }

    setContextLoading(true);
    setPagesLoading(true);
    try {
      const [ctx, drafts, pages] = await Promise.all([
        getLatestContext(leadId).catch((ctxError: unknown) => {
          if (ctxError instanceof ApiError && ctxError.status === 404) {
            return null;
          }
          throw ctxError;
        }),
        getLeadDrafts(leadId, 20, 0).catch((draftError: unknown) => {
          if (draftError instanceof ApiError && draftError.status === 404) {
            return [];
          }
          throw draftError;
        }),
        getLeadWebsitePages(leadId, 100, 0).catch((pagesError: unknown) => {
          if (pagesError instanceof ApiError && pagesError.status === 404) {
            return [];
          }
          throw pagesError;
        }),
      ]);

      setContext(ctx);
      setLatestDraft(drafts.length > 0 ? drafts[0] : null);
      setWebsitePages(pages);
      setError(null);
    } catch (ctxError) {
      setError(getErrorMessage(ctxError));
    } finally {
      setContextLoading(false);
      setPagesLoading(false);
    }
  }

  async function runAction(key: ActionKey, label: string, action: (id: string) => Promise<unknown>): Promise<void> {
    if (!leadId) {
      return;
    }

    setLoadingByAction((prev) => ({ ...prev, [key]: true }));
    setActionMessage(null);
    setError(null);
    try {
      await action(leadId);
      setActionMessage(`${label} completed.`);
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      await Promise.all([loadLead(), loadContext()]);
      setLoadingByAction((prev) => ({ ...prev, [key]: false }));
    }
  }

  useEffect(() => {
    if (!leadId) {
      return;
    }
    void loadLead();
    void loadContext();
  }, [leadId]);

  const isBusy = Object.values(loadingByAction).some(Boolean);
  const summary = lead ? resolveLeadPipeline(lead) : null;

  const stageItems: Array<{ label: string; state: StageState }> = [
    {
      label: "NEW",
      state: summary && (summary.has_snapshot || summary.has_agent1_output || summary.has_draft || summary.has_agent3_verdict) ? "done" : "active"
    },
    { label: "INGESTED", state: summary?.has_snapshot ? "done" : summary ? "active" : "pending" },
    { label: "AGENT1", state: summary?.has_agent1_output ? "done" : summary?.has_snapshot ? "active" : "pending" },
    { label: "AGENT2", state: summary?.has_draft ? "done" : summary?.has_agent1_output ? "active" : "pending" },
    { label: "AGENT3", state: summary?.has_agent3_verdict ? "done" : summary?.has_draft ? "active" : "pending" },
    {
      label:
        summary?.computed_stage === "sent"
          ? "SENT"
          : summary?.computed_stage === "replied"
            ? "REPLIED"
            : summary?.computed_stage === "converted"
              ? "CONVERTED"
              : summary?.computed_stage === "archived"
                ? "ARCHIVED"
                : summary?.computed_stage === "needs_review"
                  ? "NEEDS REVIEW"
                  : summary?.computed_stage === "approved"
                    ? "APPROVED"
                    : "PENDING REVIEW",
      state:
        summary &&
        ["approved", "needs_review", "sent", "replied", "converted", "archived"].includes(summary.computed_stage)
          ? "done"
          : summary?.has_agent3_verdict
            ? "active"
            : "pending"
    }
  ];

  const controls = {
    ingest: {
      disabled: !lead?.website_url,
      reason: !lead ? "Lead is loading." : !lead.website_url ? "Website URL is required before ingestion." : null
    },
    agent1: {
      disabled: !summary?.has_snapshot,
      reason: !lead
        ? "Lead is loading."
        : !summary?.has_snapshot
          ? "Run Ingest Website first."
          : null
    },
    agent2: {
      disabled: !summary?.has_agent1_output,
      reason: !lead
        ? "Lead is loading."
        : !summary?.has_agent1_output
          ? "Run Agent 1 first."
          : null
    },
    agent3: {
      disabled: !summary?.has_draft,
      reason: !lead
        ? "Lead is loading."
        : !summary?.has_draft
          ? "Run Agent 2 first."
          : null
    },
    refresh: {
      disabled: !summary?.has_snapshot,
      reason: !lead
        ? "Lead is loading."
        : !summary?.has_snapshot
          ? "No context to refresh until a website snapshot exists."
          : null
    }
  };

  return (
    <div className="stack lead-detail-page">
      <section className="hero-panel lead-detail-hero">
        <Link href="/" className="lead-detail-back">
          ← Back to Leads
        </Link>
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">
              {lead ? `${lead.name} · ${lead.company}` : "Lead Detail"}
            </h1>
            <p className="page-subtitle">
              {lead ? "Track pipeline steps and AI context" : "Loading..."}
            </p>
          </div>
          {lead && summary ? (
            <span className={`lead-detail-status ${summary.computed_stage}`}>
              {summary.computed_stage.replace(/_/g, " ")}
            </span>
          ) : null}
        </header>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {actionMessage ? <div className="success">{actionMessage}</div> : null}

      <LeadSummaryCard lead={lead} loading={leadLoading} />

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
      />

      <LatestContextCard
        context={context}
        latestDraft={latestDraft}
        loading={contextLoading}
        snapshotPreview={snapshotPreview}
        isSnapshotLong={isSnapshotLong}
        showFullSnapshot={showFullSnapshot}
        onToggleSnapshot={() => setShowFullSnapshot((prev) => !prev)}
      />

      <section className="card stack website-pages-card">
        <h2>Ingested Website Pages</h2>
        {pagesLoading ? (
          <div className="muted">Loading website pages...</div>
        ) : websitePages.length === 0 ? (
          <div className="muted">No website pages found. Run Ingest Website to populate this section.</div>
        ) : (
          <div className="website-pages-grid">
            {websitePages.map((page) => (
              <article key={page.id} className="website-page-card">
                <div className="website-page-header">
                  <span className="website-page-type">{page.page_type}</span>
                  <span className="website-page-date">{new Date(page.created_at).toLocaleDateString()}</span>
                </div>
                <a href={page.url} target="_blank" rel="noreferrer" className="website-page-url">
                  {page.url}
                </a>
                {(page.extracted_emails.length > 0 || page.extracted_phones.length > 0) && (
                  <div className="website-page-extracted">
                    {page.extracted_emails.length > 0 && (
                      <div className="website-page-field">
                        <span className="website-page-field-label">Emails</span>
                        <span>{page.extracted_emails.join(", ")}</span>
                      </div>
                    )}
                    {page.extracted_phones.length > 0 && (
                      <div className="website-page-field">
                        <span className="website-page-field-label">Phones</span>
                        <span>{page.extracted_phones.join(", ")}</span>
                      </div>
                    )}
                  </div>
                )}
                <details className="website-page-details">
                  <summary>View page text</summary>
                  <pre className="snapshot-text">{page.raw_text}</pre>
                </details>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
