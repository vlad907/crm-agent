"use client";

import { FormEvent, useEffect, useState } from "react";

import { API_BASE } from "@/src/lib/api";
import { getUserId, getWorkspaceId, setUserId, setWorkspaceId } from "@/src/lib/identity";

export default function SettingsPage() {
  const [workspaceId, setWorkspaceInput] = useState("");
  const [userId, setUserInput] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
  }, []);

  function onSave(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setWorkspaceId(workspaceId);
    setUserId(userId);
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setMessage("Identity saved.");
  }

  function onClear(): void {
    setWorkspaceId("");
    setUserId("");
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setMessage("Stored IDs cleared. Env values (if set) are now in effect.");
  }

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="page-subtitle">Dev-only identity headers. Later replaced by real auth.</p>
          </div>
        </header>
      </section>

      <section className="card stack">
        <div className="kv-grid">
          <div className="kv">
            <strong>API Base</strong>
            {API_BASE}
          </div>
          <div className="kv">
            <strong>Current Workspace ID</strong>
            {workspaceId || "(missing)"}
          </div>
          <div className="kv">
            <strong>Current User ID</strong>
            {userId || "(missing)"}
          </div>
        </div>

        <form className="stack" onSubmit={onSave}>
          <div className="row">
            <div className="field">
              <label htmlFor="workspace_id">Workspace ID</label>
              <input
                id="workspace_id"
                placeholder="workspace uuid"
                value={workspaceId}
                onChange={(event) => setWorkspaceInput(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="user_id">User ID</label>
              <input id="user_id" placeholder="user uuid" value={userId} onChange={(event) => setUserInput(event.target.value)} />
            </div>
          </div>

          {message ? <div className="success">{message}</div> : null}

          <div className="inline-actions">
            <button type="submit" className="btn-primary">
              Save
            </button>
            <button type="button" className="btn-secondary" onClick={onClear}>
              Clear
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
