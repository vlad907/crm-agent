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
  getLatestContext,
  ingestWebsite,
  runAgent1,
  runAgent2,
  runAgent3
} from "@/src/lib/api";
import { Draft, Lead, LatestContext } from "@/src/lib/types";

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

  const [leadLoading, setLeadLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(true);
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
    try {
      const [ctx, drafts] = await Promise.all([
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
        })
      ]);

      setContext(ctx);
      setLatestDraft(drafts.length > 0 ? drafts[0] : null);
      setError(null);
    } catch (ctxError) {
      setError(getErrorMessage(ctxError));
    } finally {
      setContextLoading(false);
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
      await loadContext();
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
  const stageStates: StageState[] = [
    context?.snapshot ? "done" : "active",
    context?.agent1_output ? "done" : context?.snapshot ? "active" : "pending",
    latestDraft ? "done" : context?.agent1_output ? "active" : "pending",
    context?.agent3_decision ? "done" : latestDraft ? "active" : "pending"
  ];

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Lead Detail</h1>
            <p className="page-subtitle">Track pipeline steps and inspect AI context artifacts for this lead.</p>
          </div>
          <Link href="/" className="btn-secondary btn-link">
            Back
          </Link>
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
        onRefresh={() => void runAction("refresh", "Refresh Context", async () => loadContext())}
        stageStates={stageStates}
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
    </div>
  );
}
