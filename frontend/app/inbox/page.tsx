"use client";

import { useCallback, useEffect, useState } from "react";

import { Spinner } from "@/src/components/Spinner";
import {
  approveReply,
  classifyThread,
  createInboxGmailDraft,
  getInboxThread,
  getInboxThreads,
  reclassifyMessage,
  rejectReply,
  sendInboxReply,
  suggestReply,
  syncInbox,
  updateThreadStatus,
} from "@/src/lib/api";
import type {
  EmailMessage,
  EmailThreadListItem,
  EmailThreadWithMessages,
} from "@/src/lib/types";

const CLASSIFICATION_OPTIONS = [
  "interested", "not_interested", "question", "objection",
  "pricing_request", "meeting_request", "referral", "unsubscribe", "unknown",
];

const FILTER_OPTIONS = [
  { value: "", label: "All" },
  { value: "interested", label: "Interested" },
  { value: "meeting_request", label: "Meeting Request" },
  { value: "pricing_request", label: "Pricing Request" },
  { value: "question", label: "Question" },
  { value: "not_interested", label: "Not Interested" },
  { value: "objection", label: "Objection" },
  { value: "referral", label: "Referral" },
];

function classificationColor(c: string | null): string {
  if (!c) return "";
  const map: Record<string, string> = {
    interested: "stage-done", meeting_request: "stage-done",
    question: "stage-active", pricing_request: "stage-active", referral: "stage-active",
    not_interested: "stage-pending", objection: "stage-pending", unsubscribe: "stage-pending",
  };
  return map[c] || "";
}

function nextActionLabel(a: string | null): string {
  if (!a) return "";
  const map: Record<string, string> = {
    schedule_meeting: "Schedule Meeting",
    provide_quote: "Provide Quote",
    follow_up: "Follow Up",
    follow_up_later: "Follow Up Later",
    create_job: "Create Job",
  };
  return map[a] || a.replace(/_/g, " ");
}

export default function InboxPage() {
  const [threads, setThreads] = useState<EmailThreadListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [filterClassification, setFilterClassification] = useState("");

  const [selectedThread, setSelectedThread] = useState<EmailThreadWithMessages | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);

  const [replySubject, setReplySubject] = useState("");
  const [replyBody, setReplyBody] = useState("");
  const [sending, setSending] = useState(false);
  const [classifying, setClassifying] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [draftingGmail, setDraftingGmail] = useState(false);

  const fetchThreads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getInboxThreads(100, 0);
      setThreads(data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load threads");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchThreads(); }, [fetchThreads]);

  const filteredThreads = filterClassification
    ? threads.filter((t) => t.classification === filterClassification)
    : threads;

  async function handleSync() {
    setSyncing(true); setError(null); setMessage(null);
    try {
      const r = await syncInbox(30);
      setMessage(`Synced ${r.threads_synced} threads, ${r.messages_synced} messages (${r.new_inbound} new inbound)`);
      await fetchThreads();
    } catch (e) { setError(e instanceof Error ? e.message : "Sync failed"); }
    finally { setSyncing(false); }
  }

  async function openThread(threadId: string) {
    setThreadLoading(true); setError(null);
    try {
      const data = await getInboxThread(threadId);
      setSelectedThread(data);
      const lastInbound = [...data.messages].reverse().find((m) => m.direction === "inbound");
      if (lastInbound?.suggested_response) {
        setReplySubject(lastInbound.suggested_response.subject || "");
        setReplyBody(lastInbound.suggested_response.reply_body || "");
      } else { setReplySubject(""); setReplyBody(""); }
    } catch (e) { setError(e instanceof Error ? e.message : "Failed to load thread"); }
    finally { setThreadLoading(false); }
  }

  async function handleClassify() {
    if (!selectedThread) return;
    setClassifying(true);
    try {
      const r = await classifyThread(selectedThread.id);
      setMessage(`Classified as: ${(r.classification as Record<string, string>).classification}`);
      await openThread(selectedThread.id); await fetchThreads();
    } catch (e) { setError(e instanceof Error ? e.message : "Classification failed"); }
    finally { setClassifying(false); }
  }

  async function handleSuggestReply() {
    if (!selectedThread) return;
    setSuggesting(true);
    try {
      const r = await suggestReply(selectedThread.id);
      setReplySubject(r.suggested_response.subject);
      setReplyBody(r.suggested_response.reply_body);
      setMessage("Response suggestion generated");
      await openThread(selectedThread.id);
    } catch (e) { setError(e instanceof Error ? e.message : "Suggestion failed"); }
    finally { setSuggesting(false); }
  }

  async function handleSendReply() {
    if (!selectedThread || !replyBody.trim()) return;
    setSending(true);
    try {
      await sendInboxReply(selectedThread.id, replySubject, replyBody);
      setMessage("Reply sent"); setReplySubject(""); setReplyBody("");
      await openThread(selectedThread.id); await fetchThreads();
    } catch (e) { setError(e instanceof Error ? e.message : "Send failed"); }
    finally { setSending(false); }
  }

  async function handleCreateGmailDraft() {
    if (!selectedThread) return;
    setDraftingGmail(true);
    try {
      await createInboxGmailDraft(selectedThread.id);
      setMessage("Gmail draft created");
      await openThread(selectedThread.id);
    } catch (e) { setError(e instanceof Error ? e.message : "Draft creation failed"); }
    finally { setDraftingGmail(false); }
  }

  async function handleApprove() {
    if (!selectedThread) return;
    try { await approveReply(selectedThread.id); setMessage("Reply approved"); await openThread(selectedThread.id); await fetchThreads(); }
    catch (e) { setError(e instanceof Error ? e.message : "Approve failed"); }
  }

  async function handleReject() {
    if (!selectedThread) return;
    try { await rejectReply(selectedThread.id); setMessage("Reply rejected"); await openThread(selectedThread.id); await fetchThreads(); }
    catch (e) { setError(e instanceof Error ? e.message : "Reject failed"); }
  }

  async function handleReclassify(messageId: string, classification: string) {
    try {
      await reclassifyMessage(messageId, classification);
      if (selectedThread) await openThread(selectedThread.id);
      await fetchThreads();
    } catch (e) { setError(e instanceof Error ? e.message : "Reclassify failed"); }
  }

  async function handleMarkDone() {
    if (!selectedThread) return;
    try { await updateThreadStatus(selectedThread.id, "done"); setSelectedThread(null); await fetchThreads(); }
    catch (e) { setError(e instanceof Error ? e.message : "Update failed"); }
  }

  const lastInbound = selectedThread?.messages
    ? [...selectedThread.messages].reverse().find((m) => m.direction === "inbound")
    : null;
  const hasSuggestion = !!lastInbound?.suggested_response;

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Inbox Command Center</h1>
            <p className="page-subtitle">Conversations, classification, AI replies, and review queue.</p>
          </div>
          <div className="inline-actions">
            <select value={filterClassification} onChange={(e) => setFilterClassification(e.target.value)} style={{ fontSize: ".82rem", padding: "6px 10px" }}>
              {FILTER_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>
            <button type="button" className="btn-primary" disabled={syncing} onClick={() => void handleSync()}>
              {syncing ? "Syncing..." : "Sync Gmail"}
            </button>
          </div>
        </header>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="inbox-grid">
        {/* LEFT — Thread list */}
        <section className="card inbox-panel-threads">
          <h2 style={{ marginBottom: 10, fontSize: ".95rem" }}>Conversations ({filteredThreads.length})</h2>
          {loading ? <Spinner label="Loading..." /> : null}
          {!loading && filteredThreads.length === 0 ? (
            <p className="muted" style={{ fontSize: ".84rem" }}>No threads. Click &ldquo;Sync Gmail&rdquo; to fetch.</p>
          ) : null}
          {filteredThreads.map((t) => (
            <div
              key={t.id}
              className={`subcard${selectedThread?.id === t.id ? " active-thread" : ""}`}
              style={{ marginBottom: 6, cursor: "pointer", padding: "10px 12px" }}
              onClick={() => void openThread(t.id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 3 }}>
                <strong style={{ fontSize: ".82rem" }}>
                  {t.latest_message?.sender?.replace(/<[^>]+>/, "").trim().slice(0, 35) || "Unknown"}
                </strong>
                {t.classification ? (
                  <span className={`stage-pill ${classificationColor(t.classification)}`} style={{ fontSize: ".68rem" }}>
                    {t.classification.replace(/_/g, " ")}
                  </span>
                ) : null}
              </div>
              <div className="muted" style={{ fontSize: ".78rem", marginBottom: 2 }}>
                {t.latest_message?.subject?.slice(0, 50) || "(no subject)"}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: ".72rem", color: "var(--text-faint)" }}>
                <span>{t.related_entity_name || ""}</span>
                <span>{t.last_message_at ? new Date(t.last_message_at).toLocaleDateString() : ""}</span>
              </div>
              {t.next_action ? (
                <div style={{ marginTop: 3 }}>
                  <span className="stage-pill stage-active" style={{ fontSize: ".65rem" }}>{nextActionLabel(t.next_action)}</span>
                </div>
              ) : null}
            </div>
          ))}
        </section>

        {/* CENTER — Messages */}
        <section className="card inbox-panel-messages">
          {!selectedThread ? (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-muted)" }}>
              Select a conversation to view messages
            </div>
          ) : threadLoading ? <Spinner label="Loading thread..." /> : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <h2 style={{ fontSize: ".95rem" }}>Messages</h2>
                <div className="inline-actions" style={{ gap: 6 }}>
                  <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "4px 10px" }} disabled={classifying} onClick={() => void handleClassify()}>
                    {classifying ? "..." : "Classify"}
                  </button>
                  <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "4px 10px" }} disabled={suggesting} onClick={() => void handleSuggestReply()}>
                    {suggesting ? "..." : "Suggest Reply"}
                  </button>
                  <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "4px 10px" }} onClick={() => void handleMarkDone()}>
                    Done
                  </button>
                </div>
              </div>
              <div className="stack" style={{ gap: 8, marginBottom: 14, overflowY: "auto", maxHeight: "calc(100vh - 400px)" }}>
                {selectedThread.messages.map((msg: EmailMessage) => (
                  <div key={msg.id} className="subcard" style={{ padding: "10px 12px", borderLeft: `3px solid ${msg.direction === "inbound" ? "var(--blue)" : "var(--green)"}` }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: ".8rem" }}>
                        {msg.direction === "inbound" ? msg.sender?.replace(/<[^>]+>/, "").trim().slice(0, 45) : "You"}
                      </span>
                      <span style={{ fontSize: ".72rem", color: "var(--text-faint)" }}>
                        {msg.received_at ? new Date(msg.received_at).toLocaleString() : ""}
                      </span>
                    </div>
                    {msg.subject ? <div style={{ fontSize: ".78rem", color: "var(--text-secondary)", marginBottom: 3 }}>{msg.subject}</div> : null}
                    <div style={{ fontSize: ".82rem", whiteSpace: "pre-wrap", lineHeight: 1.45 }}>
                      {msg.body?.slice(0, 1500) || "(empty)"}
                    </div>
                    {msg.classification ? (
                      <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 6 }}>
                        <span className={`stage-pill ${classificationColor(msg.classification)}`} style={{ fontSize: ".7rem" }}>
                          {msg.classification.replace(/_/g, " ")}
                        </span>
                        <select
                          style={{ fontSize: ".72rem", padding: "1px 4px" }}
                          value={msg.classification}
                          onChange={(e) => void handleReclassify(msg.id, e.target.value)}
                        >
                          {CLASSIFICATION_OPTIONS.map((opt) => (
                            <option key={opt} value={opt}>{opt.replace(/_/g, " ")}</option>
                          ))}
                        </select>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>

        {/* RIGHT — Actions panel */}
        <section className="card inbox-panel-actions">
          {!selectedThread ? (
            <div style={{ color: "var(--text-muted)", fontSize: ".84rem", textAlign: "center", paddingTop: 40 }}>
              Actions will appear here
            </div>
          ) : (
            <div className="stack" style={{ gap: 12 }}>
              {/* Thread meta */}
              <div className="subcard" style={{ padding: "10px 12px" }}>
                <strong style={{ fontSize: ".78rem", color: "var(--text-muted)" }}>Status</strong>
                <div style={{ fontSize: ".85rem", fontWeight: 600 }}>{selectedThread.status.replace(/_/g, " ")}</div>
                {selectedThread.next_action ? (
                  <>
                    <strong style={{ fontSize: ".78rem", color: "var(--text-muted)", marginTop: 6, display: "block" }}>Next Action</strong>
                    <div className="stage-pill stage-active" style={{ fontSize: ".75rem", display: "inline-block" }}>
                      {nextActionLabel(selectedThread.next_action)}
                    </div>
                  </>
                ) : null}
                {selectedThread.reply_review_status ? (
                  <>
                    <strong style={{ fontSize: ".78rem", color: "var(--text-muted)", marginTop: 6, display: "block" }}>Reply Status</strong>
                    <div style={{ fontSize: ".82rem" }}>{selectedThread.reply_review_status.replace(/_/g, " ")}</div>
                  </>
                ) : null}
              </div>

              {/* Suggested reply / compose */}
              <div className="subcard" style={{ padding: "10px 12px" }}>
                <h3 style={{ marginBottom: 8, fontSize: ".85rem" }}>
                  {hasSuggestion ? "Suggested Reply" : "Compose Reply"}
                </h3>
                <div className="field" style={{ marginBottom: 6 }}>
                  <label style={{ fontSize: ".75rem" }}>Subject</label>
                  <input value={replySubject} onChange={(e) => setReplySubject(e.target.value)} placeholder="Re: ..." style={{ fontSize: ".84rem" }} />
                </div>
                <div className="field" style={{ marginBottom: 8 }}>
                  <label style={{ fontSize: ".75rem" }}>Body</label>
                  <textarea
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                    rows={8}
                    style={{ width: "100%", resize: "vertical", padding: "8px 10px", borderRadius: "var(--radius-sm)", border: "1px solid var(--line)", fontSize: ".84rem", fontFamily: "inherit" }}
                    placeholder="Type or generate a reply..."
                  />
                </div>

                <div className="stack" style={{ gap: 6 }}>
                  {hasSuggestion ? (
                    <div className="inline-actions" style={{ gap: 6 }}>
                      <button type="button" className="btn-primary" style={{ fontSize: ".78rem", padding: "5px 10px" }} onClick={() => void handleApprove()}>
                        Approve
                      </button>
                      <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }} onClick={() => void handleReject()}>
                        Reject
                      </button>
                    </div>
                  ) : null}

                  <div className="inline-actions" style={{ gap: 6, flexWrap: "wrap" }}>
                    <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }} disabled={suggesting} onClick={() => void handleSuggestReply()}>
                      {suggesting ? "Generating..." : hasSuggestion ? "Regenerate" : "Generate Reply"}
                    </button>
                    <button type="button" className="btn-secondary" style={{ fontSize: ".78rem", padding: "5px 10px" }} disabled={draftingGmail || !hasSuggestion} onClick={() => void handleCreateGmailDraft()}>
                      {draftingGmail ? "Creating..." : "Gmail Draft"}
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ fontSize: ".78rem", padding: "5px 10px" }}
                      disabled={sending || !replyBody.trim()}
                      onClick={() => void handleSendReply()}
                    >
                      {sending ? "Sending..." : "Send Reply"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
