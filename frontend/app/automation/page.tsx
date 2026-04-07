"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  approveDraft,
  createGmailDraft,
  getAutomationSettings,
  getDraftReviewQueue,
  getDraftReviewQueueSummary,
  getGmailConnectUrl,
  getGmailStatus,
  patchAutomationSettings,
  rejectDraft,
  sendDraft
} from "@/src/lib/api";
import { DraftReviewQueueItem, DraftReviewQueueSummary, GmailStatusResponse, WorkspaceAutomationSettings } from "@/src/lib/types";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function AutomationPage() {
  const [automationSettings, setAutomationSettings] = useState<WorkspaceAutomationSettings | null>(null);
  const [gmailStatus, setGmailStatus] = useState<GmailStatusResponse | null>(null);
  const [reviewQueueSummary, setReviewQueueSummary] = useState<DraftReviewQueueSummary | null>(null);
  const [reviewQueue, setReviewQueue] = useState<DraftReviewQueueItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshingQueue, setRefreshingQueue] = useState(false);
  const [actionState, setActionState] = useState<Record<string, string | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [gmailConnectError, setGmailConnectError] = useState<string | null>(null);
  const [connectingGmail, setConnectingGmail] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthStatus = params.get("gmail_oauth");
    const oauthMessage = params.get("message");
    if (!oauthStatus) {
      return;
    }
    if (oauthStatus === "success") {
      setMessage(oauthMessage || "Gmail connected.");
      setError(null);
      return;
    }
    if (oauthStatus === "error") {
      setError(oauthMessage || "Gmail OAuth failed.");
      setMessage(null);
    }
  }, []);

  async function loadAll(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [settings, statusPayload, summary, queue] = await Promise.all([
        getAutomationSettings(),
        getGmailStatus(),
        getDraftReviewQueueSummary(),
        getDraftReviewQueue(50, 0, true)
      ]);
      setAutomationSettings(settings);
      setGmailStatus(statusPayload);
      setReviewQueueSummary(summary);
      setReviewQueue(queue);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function refreshQueueData(): Promise<void> {
    setRefreshingQueue(true);
    try {
      const [summary, queue, statusPayload] = await Promise.all([
        getDraftReviewQueueSummary(),
        getDraftReviewQueue(50, 0, true),
        getGmailStatus()
      ]);
      setReviewQueueSummary(summary);
      setReviewQueue(queue);
      setGmailStatus(statusPayload);
    } catch (refreshError) {
      setError(getErrorMessage(refreshError));
    } finally {
      setRefreshingQueue(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function onSaveAutomationSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!automationSettings) {
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await patchAutomationSettings({
        automation_mode: automationSettings.automation_mode,
        require_manual_review_before_send: automationSettings.require_manual_review_before_send,
        auto_create_gmail_draft: automationSettings.auto_create_gmail_draft,
        auto_send_approved_emails: automationSettings.auto_send_approved_emails,
        pause_pipeline: automationSettings.pause_pipeline
      });
      setAutomationSettings(updated);
      setMessage("Automation settings saved.");
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSaving(false);
    }
  }

  async function onConnectGmail(): Promise<void> {
    setError(null);
    setMessage(null);
    setGmailConnectError(null);
    setConnectingGmail(true);
    try {
      const payload = await getGmailConnectUrl();
      const raw = payload?.connect_url;
      const url = typeof raw === "string" ? raw.trim() : "";
      if (!url || !/^https?:\/\//i.test(url)) {
        setGmailConnectError(
          "Backend did not return a valid Gmail URL. Add Google OAuth Client ID and secret under Settings → Integrations, or set GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET on the server and restart."
        );
        setConnectingGmail(false);
        return;
      }
      window.location.href = url;
    } catch (connectError) {
      const msg = getErrorMessage(connectError);
      setGmailConnectError(msg);
      setError(msg);
      setConnectingGmail(false);
    }
  }

  async function onPauseResume(nextPaused: boolean): Promise<void> {
    if (!automationSettings) {
      return;
    }
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await patchAutomationSettings({
        pause_pipeline: nextPaused
      });
      setAutomationSettings(updated);
      setMessage(nextPaused ? "Automation paused." : "Automation resumed.");
    } catch (pauseError) {
      setError(getErrorMessage(pauseError));
    } finally {
      setSaving(false);
    }
  }

  async function runReviewAction(draftId: string, action: "approve" | "reject" | "create_draft" | "send"): Promise<void> {
    setActionState((prev) => ({ ...prev, [draftId]: action }));
    setError(null);
    setMessage(null);
    try {
      if (action === "approve") {
        await approveDraft(draftId);
        setMessage("Draft approved.");
      } else if (action === "reject") {
        await rejectDraft(draftId);
        setMessage("Draft rejected.");
      } else if (action === "create_draft") {
        await createGmailDraft(draftId);
        setMessage("Gmail draft created.");
      } else {
        await sendDraft(draftId);
        setMessage("Draft sent.");
      }
      await refreshQueueData();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
    } finally {
      setActionState((prev) => ({ ...prev, [draftId]: null }));
    }
  }

  const activeQueueItems = useMemo(
    () => reviewQueue.filter((item) => item.review_status === "pending_review" || item.review_status === "approved"),
    [reviewQueue]
  );

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Automation Center</h1>
            <p className="page-subtitle">Manage pipeline automation, Gmail connection, and review queue operations.</p>
          </div>
        </header>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      {loading ? <section className="card"><div className="muted">Loading automation controls...</div></section> : null}

      {!loading && automationSettings ? (
        <section className="card stack">
          <h2>Automation Controls</h2>
          <form className="stack" onSubmit={onSaveAutomationSettings}>
            <div className="row">
              <div className="field">
                <label htmlFor="automation_mode">Automation Mode</label>
                <select
                  id="automation_mode"
                  value={automationSettings.automation_mode}
                  onChange={(event) =>
                    setAutomationSettings((prev) =>
                      prev
                        ? {
                            ...prev,
                            automation_mode: event.target.value as "manual" | "semi_auto" | "auto_draft" | "auto_send"
                          }
                        : prev
                    )
                  }
                >
                  <option value="manual">manual</option>
                  <option value="semi_auto">semi_auto</option>
                  <option value="auto_draft">auto_draft</option>
                  <option value="auto_send">auto_send</option>
                </select>
              </div>
            </div>

            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={automationSettings.require_manual_review_before_send}
                onChange={(event) =>
                  setAutomationSettings((prev) =>
                    prev ? { ...prev, require_manual_review_before_send: event.target.checked } : prev
                  )
                }
              />
              Require manual review before send
            </label>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={automationSettings.auto_create_gmail_draft}
                onChange={(event) =>
                  setAutomationSettings((prev) => (prev ? { ...prev, auto_create_gmail_draft: event.target.checked } : prev))
                }
              />
              Auto-create Gmail drafts
            </label>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={automationSettings.auto_send_approved_emails}
                onChange={(event) =>
                  setAutomationSettings((prev) => (prev ? { ...prev, auto_send_approved_emails: event.target.checked } : prev))
                }
              />
              Auto-send approved emails
            </label>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={automationSettings.pause_pipeline}
                onChange={(event) =>
                  setAutomationSettings((prev) => (prev ? { ...prev, pause_pipeline: event.target.checked } : prev))
                }
              />
              Pause pipeline
            </label>

            <div className="inline-actions">
              <button type="submit" className="btn-secondary" disabled={saving}>
                {saving ? "Saving..." : "Save Automation Settings"}
              </button>
              <button type="button" className="btn-secondary" disabled={saving || automationSettings.pause_pipeline} onClick={() => void onPauseResume(true)}>
                Pause Automation
              </button>
              <button type="button" className="btn-secondary" disabled={saving || !automationSettings.pause_pipeline} onClick={() => void onPauseResume(false)}>
                Resume Automation
              </button>
              <button type="button" className="btn-secondary" disabled={refreshingQueue} onClick={() => void refreshQueueData()}>
                {refreshingQueue ? "Refreshing..." : "Refresh Queue"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <section className="card stack">
        <h2>Gmail Integration</h2>
        <div className="kv-grid">
          <div className="kv">
            <strong>Status</strong>
            {gmailStatus?.connected ? "Connected" : "Disconnected"}
          </div>
          <div className="kv">
            <strong>Connected Email</strong>
            {gmailStatus?.connected_email || "-"}
          </div>
          <div className="kv">
            <strong>Integration State</strong>
            {gmailStatus?.integration_status || "-"}
          </div>
        </div>
        {gmailStatus?.last_error ? <div className="error">{gmailStatus.last_error}</div> : null}
        {gmailConnectError ? <div className="error">{gmailConnectError}</div> : null}
        <div className="inline-actions">
          <button
            type="button"
            className="btn-primary"
            disabled={connectingGmail}
            onClick={() => void onConnectGmail()}
          >
            {connectingGmail ? "Opening Google…" : gmailStatus?.connected ? "Reconnect Gmail" : "Connect Gmail"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 8, fontSize: "0.85rem" }}>
          Save Google OAuth Client ID and secret under{" "}
          <a href="/settings">Settings → Integrations</a>
          {" "}(or configure env vars on the server). If connect fails, check the message above or the network request to{" "}
          <code>/api/v1/integrations/gmail/connect-url</code>.
        </p>
      </section>

      <section className="card stack">
        <h2>Review Queue Summary</h2>
        <div className="kv-grid">
          <div className="kv">
            <strong>Needs Review</strong>
            {reviewQueueSummary?.needs_review ?? 0}
          </div>
          <div className="kv">
            <strong>Approved</strong>
            {reviewQueueSummary?.approved ?? 0}
          </div>
          <div className="kv">
            <strong>Queued To Send</strong>
            {reviewQueueSummary?.queued_to_send ?? 0}
          </div>
          <div className="kv">
            <strong>Sent</strong>
            {reviewQueueSummary?.sent ?? 0}
          </div>
        </div>
      </section>

      <section className="card stack">
        <h2>Review Queue</h2>
        {activeQueueItems.length === 0 ? (
          <div className="empty-state">No drafts currently need action.</div>
        ) : (
          <div className="stack">
            {activeQueueItems.map((item) => {
              const draftAction = actionState[item.draft_id] ?? null;
              const finalSubject = item.final_email?.subject || item.subject;
              const finalBody = item.final_email?.email_body || item.body;
              const canSend = Boolean(gmailStatus?.connected && item.lead_email);
              return (
                <article key={item.draft_id} className="subcard stack">
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div className="stack" style={{ gap: 4 }}>
                      <strong>{item.lead_company}</strong>
                      <div className="muted">Lead: {item.lead_id}</div>
                      <div className="muted">Email: {item.lead_email || "-"}</div>
                      <div className="muted">Decision: {item.decision} | Review: {item.review_status}</div>
                    </div>
                    <div className="muted">{new Date(item.updated_at).toLocaleString()}</div>
                  </div>
                  <div className="field">
                    <label>Subject</label>
                    <div>{finalSubject}</div>
                  </div>
                  <div className="field">
                    <label>Body</label>
                    <pre style={{ maxHeight: 220 }}>{finalBody}</pre>
                  </div>
                  <div className="field">
                    <label>Agent 3 Issues</label>
                    <div className="muted">{item.issues.length ? item.issues.join("; ") : "No explicit issues."}</div>
                  </div>
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={Boolean(draftAction) || item.review_status === "approved"}
                      onClick={() => void runReviewAction(item.draft_id, "approve")}
                    >
                      {draftAction === "approve" ? "Approving..." : "Approve"}
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={Boolean(draftAction)}
                      onClick={() => void runReviewAction(item.draft_id, "reject")}
                    >
                      {draftAction === "reject" ? "Rejecting..." : "Reject"}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={Boolean(draftAction)}
                      onClick={() => void runReviewAction(item.draft_id, "create_draft")}
                    >
                      {draftAction === "create_draft" ? "Creating..." : "Create Gmail Draft"}
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={Boolean(draftAction) || !canSend}
                      title={canSend ? "Send with Gmail" : "Connect Gmail and ensure lead email exists"}
                      onClick={() => void runReviewAction(item.draft_id, "send")}
                    >
                      {draftAction === "send" ? "Sending..." : "Send"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
