"use client";

import { useEffect, useMemo, useState } from "react";

import { IDENTITY_UPDATED_EVENT, getUserId, getWorkspaceId } from "@/src/lib/identity";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

function shortId(value: string): string {
  if (!value) return "not set";
  if (value.length <= 14) return value;
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

function slugifyLabel(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || value;
}

export function IdentityBanner() {
  const [workspaceId, setWorkspace] = useState("");
  const [userId, setUser] = useState("");
  const [workspaceLabel, setWorkspaceLabel] = useState("");
  const [userLabel, setUserLabel] = useState("");

  useEffect(() => {
    const sync = () => {
      setWorkspace(getWorkspaceId());
      setUser(getUserId());
    };
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener(IDENTITY_UPDATED_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(IDENTITY_UPDATED_EVENT, sync);
    };
  }, []);

  useEffect(() => {
    async function loadIdentity(): Promise<void> {
      if (!workspaceId || !userId) {
        setWorkspaceLabel("");
        setUserLabel("");
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/api/v1/me`, {
          headers: { "X-Workspace-Id": workspaceId, "X-User-Id": userId },
          cache: "no-store",
        });
        if (!response.ok) return;
        const payload = (await response.json()) as {
          workspace?: { name?: string };
          user?: { name?: string; email?: string };
        };
        setWorkspaceLabel(slugifyLabel(payload.workspace?.name ?? ""));
        const displayUser = (payload.user?.name || payload.user?.email || "").trim();
        setUserLabel(displayUser ? slugifyLabel(displayUser.split(/\s+/)[0]) : "");
      } catch {
        setWorkspaceLabel("");
        setUserLabel("");
      }
    }
    void loadIdentity();
  }, [workspaceId, userId]);

  const workspaceDisplay = useMemo(
    () => workspaceLabel || shortId(workspaceId),
    [workspaceLabel, workspaceId]
  );
  const userDisplay = useMemo(
    () => userLabel || shortId(userId),
    [userLabel, userId]
  );

  const initials = useMemo(() => {
    const name = userLabel || workspaceLabel || "";
    if (!name) return "?";
    return name.slice(0, 2).toUpperCase();
  }, [userLabel, workspaceLabel]);

  return (
    <div className="sidebar-identity">
      <div className="sidebar-identity-avatar">{initials}</div>
      <div className="sidebar-identity-info">
        <span className="sidebar-identity-user">{userDisplay}</span>
        <span className="sidebar-identity-workspace">{workspaceDisplay}</span>
      </div>
    </div>
  );
}
