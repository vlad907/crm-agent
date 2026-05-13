"use client";

import { useEffect, useMemo, useState } from "react";

import { Spinner } from "@/src/components/Spinner";
import { getLatestContext } from "@/src/lib/api";
import { resolveLeadPipeline, stageLabel } from "@/src/lib/leadPipeline";
import { JsonObject, Lead, LatestContext } from "@/src/lib/types";

interface LeadSummaryPanelProps {
  /** Currently shown lead, or null when the panel is closed. */
  lead: Lead | null;
  /** Close handler — clicking the backdrop, the X, or pressing Esc all call this. */
  onClose: () => void;
  /** Open the full lead detail page. */
  onOpenDetail: (leadId: string) => void;
  /** Trigger the "Run next missing AI step" flow for this lead. */
  onRunAi: (leadId: string) => void;
  /** Re-run Agent 2 + Agent 3 for this lead (used for needs-review/approved). */
  onRerun: (leadId: string) => void;
  /** Re-ingest the lead's website. */
  onIngest: (leadId: string) => void;
  /** Whether a bulk operation is currently running (disables actions). */
  bulkRunning: boolean;
}

function pickFirstString(obj: JsonObject | null | undefined, keys: string[]): string | null {
  if (!obj) return null;
  for (const key of keys) {
    const value = obj[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value.trim();
    }
  }
  return null;
}

/**
 * Quick-look side panel that opens when a lead row is clicked.
 *
 * Shows the basic lead fields synchronously from the row data, then lazily
 * fetches `latestContext` to surface a one-paragraph research summary and the
 * AI verdict if those are available — saves the user from having to navigate
 * to the full detail page just to scan a few rows.
 */
export function LeadSummaryPanel({
  lead,
  onClose,
  onOpenDetail,
  onRunAi,
  onRerun,
  onIngest,
  bulkRunning,
}: LeadSummaryPanelProps) {
  const [context, setContext] = useState<LatestContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState<string | null>(null);

  // Lazy-load context only when a lead is selected
  useEffect(() => {
    if (!lead) {
      setContext(null);
      setContextError(null);
      return;
    }
    let cancelled = false;
    setContextLoading(true);
    setContextError(null);
    setContext(null);
    void (async () => {
      try {
        const result = await getLatestContext(lead.id);
        if (!cancelled) setContext(result);
      } catch (error) {
        if (!cancelled) {
          // Not an error worth showing — most leads don't have context yet.
          // We'll just silently render the basics.
          setContextError(error instanceof Error ? error.message : "Failed to load context.");
        }
      } finally {
        if (!cancelled) setContextLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lead?.id]);

  // Esc key closes the panel
  useEffect(() => {
    if (!lead) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lead, onClose]);

  const summary = useMemo(() => (lead ? resolveLeadPipeline(lead) : null), [lead]);

  if (!lead || !summary) return null;

  const stage = summary.computed_stage;
  const isLocalBiz = (lead.lead_type as string | undefined) !== "partnership";
  const businessOneLiner = pickFirstString(context?.agent1_output, [
    "core_positioning",
    "summary",
    "value_proposition",
    "company_summary",
    "what_they_do",
  ]);
  const industryGuess = pickFirstString(context?.agent1_output, ["industry"]);
  const verdictDecision = context?.agent3_decision || summary.final_decision || null;
  const verdictIssues = context?.agent3_issues ?? [];
  const finalEmail = context?.final_email;
  const ingestDisabled = bulkRunning || !lead.website_url;
  const isFinalized = ["approved", "sent", "replied", "converted", "archived"].includes(stage);

  return (
    <>
      <div className="lead-summary-backdrop" onClick={onClose} />
      <aside
        className="lead-summary-panel"
        role="dialog"
        aria-label={`Summary for ${lead.company}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="lead-summary-header">
          <div className="lead-summary-header-text">
            <span className="lead-summary-type-badge" style={{ background: isLocalBiz ? "var(--blue-soft)" : "var(--purple-soft)", color: isLocalBiz ? "var(--blue)" : "var(--purple)" }}>
              {isLocalBiz ? "Local Business" : "Partnership"}
            </span>
            <h2 className="lead-summary-title">{lead.company || "Unnamed lead"}</h2>
            <span className={`status-badge ${
              ["approved", "sent", "replied", "converted"].includes(stage)
                ? "status-send"
                : ["needs_review", "archived"].includes(stage)
                  ? "status-hold"
                  : ["drafting", "draft_ready"].includes(stage)
                    ? "status-draft"
                    : ["researching", "researched"].includes(stage)
                      ? "status-research"
                      : "status-new"
            }`}>{stageLabel(stage)}</span>
          </div>
          <button type="button" className="lead-summary-close" onClick={onClose} aria-label="Close panel">
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div className="lead-summary-body">
          {/* Basic info from the row */}
          <section className="lead-summary-section">
            <h3 className="lead-summary-section-title">Basics</h3>
            <dl className="lead-summary-dl">
              {lead.location ? (<><dt>Location</dt><dd>{lead.location}</dd></>) : null}
              {lead.industry || industryGuess ? (<><dt>Industry</dt><dd>{lead.industry || industryGuess}</dd></>) : null}
              {lead.website_url ? (
                <>
                  <dt>Website</dt>
                  <dd>
                    <a className="external-link" href={lead.website_url} target="_blank" rel="noreferrer">
                      {lead.website_url}
                    </a>
                  </dd>
                </>
              ) : null}
              {lead.email ? (<><dt>Email</dt><dd>{lead.email}</dd></>) : null}
              {lead.phone ? (<><dt>Phone</dt><dd>{lead.phone}</dd></>) : null}
              {lead.source ? (<><dt>Source</dt><dd>{lead.source}</dd></>) : null}
            </dl>
          </section>

          {/* Pipeline state */}
          <section className="lead-summary-section">
            <h3 className="lead-summary-section-title">Pipeline</h3>
            <div className="pipeline-mini">
              <span className={`pipeline-flag ${summary.has_snapshot ? "done" : ""}`}>Ingested</span>
              <span className={`pipeline-flag ${summary.has_agent1_output ? "done" : ""}`}>A1</span>
              <span className={`pipeline-flag ${summary.has_draft ? "done" : ""}`}>A2</span>
              <span className={`pipeline-flag ${summary.has_agent3_verdict ? "done" : ""}`}>A3</span>
              <span
                className={`pipeline-flag ${
                  verdictDecision === "send"
                    ? "done-send"
                    : verdictDecision === "hold"
                      ? "done-hold"
                      : ""
                }`}
              >
                {verdictDecision === "send" ? "Approved" : verdictDecision === "hold" ? "Review" : "Pending"}
              </span>
            </div>
          </section>

          {/* Lazy-loaded research/context */}
          {contextLoading ? (
            <section className="lead-summary-section">
              <Spinner size="sm" label="Loading research…" />
            </section>
          ) : null}

          {!contextLoading && businessOneLiner ? (
            <section className="lead-summary-section">
              <h3 className="lead-summary-section-title">What they do (Agent 1)</h3>
              <p className="lead-summary-paragraph">{businessOneLiner}</p>
            </section>
          ) : null}

          {!contextLoading && verdictIssues.length > 0 ? (
            <section className="lead-summary-section">
              <h3 className="lead-summary-section-title">Verifier issues (Agent 3)</h3>
              <ul className="lead-summary-list">
                {verdictIssues.slice(0, 5).map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </section>
          ) : null}

          {!contextLoading && finalEmail ? (
            <section className="lead-summary-section">
              <h3 className="lead-summary-section-title">Latest draft</h3>
              {finalEmail.subject ? (
                <p className="lead-summary-paragraph">
                  <strong>Subject:</strong> {finalEmail.subject}
                </p>
              ) : null}
              {finalEmail.email_body ? (
                <pre className="lead-summary-email-preview">{finalEmail.email_body.slice(0, 600)}{finalEmail.email_body.length > 600 ? "…" : ""}</pre>
              ) : null}
            </section>
          ) : null}

          {!contextLoading && contextError && !businessOneLiner ? (
            <section className="lead-summary-section">
              <p className="muted lead-summary-empty">No research output yet — run the AI pipeline to populate this.</p>
            </section>
          ) : null}
        </div>

        <footer className="lead-summary-footer">
          <button type="button" className="btn-primary" onClick={() => onOpenDetail(lead.id)}>
            Open full detail
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={ingestDisabled}
            title={lead.website_url ? "Re-ingest website" : "Website URL required"}
            onClick={() => onIngest(lead.id)}
          >
            Ingest
          </button>
          {isFinalized ? (
            <button type="button" className="btn-secondary" disabled={bulkRunning} onClick={() => onRerun(lead.id)}>
              Re-run drafts
            </button>
          ) : (
            <button type="button" className="btn-secondary" disabled={bulkRunning} onClick={() => onRunAi(lead.id)}>
              Run next AI step
            </button>
          )}
        </footer>
      </aside>
    </>
  );
}
