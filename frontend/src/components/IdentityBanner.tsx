"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { IDENTITY_UPDATED_EVENT, clearIdentity, getUserId, getWorkspaceId } from "@/src/lib/identity";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

function shortId(value: string): string {
  if (!value) {
    return "not set";
  }
  if (value.length <= 14) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function slugifyLabel(value: string): string {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || value;
}

export function IdentityBanner() {
  const router = useRouter();
  const [workspaceId, setWorkspace] = useState("");
  const [userId, setUser] = useState("");
  const [workspaceLabel, setWorkspaceLabel] = useState("");
  const [userLabel, setUserLabel] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onClickOutside(event: MouseEvent): void {
      if (!menuRef.current || menuRef.current.contains(event.target as Node)) {
        return;
      }
      setMenuOpen(false);
    }

    document.addEventListener("click", onClickOutside);
    return () => document.removeEventListener("click", onClickOutside);
  }, []);

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
          headers: {
            "X-Workspace-Id": workspaceId,
            "X-User-Id": userId
          },
          cache: "no-store"
        });
        if (!response.ok) {
          return;
        }
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

  const workspaceDisplay = useMemo(() => workspaceLabel || shortId(workspaceId), [workspaceLabel, workspaceId]);
  const userDisplay = useMemo(() => userLabel || shortId(userId), [userLabel, userId]);

  return (
    <div className="identity-menu" ref={menuRef}>
      <button
        className="identity-trigger"
        type="button"
        title="Workspace identity menu"
        onClick={() => setMenuOpen((prev) => !prev)}
      >
        <span className="identity-badge-dot" />
        <span className="identity-lines">
          <span>
            Workspace: <strong>{workspaceDisplay}</strong>
          </span>
          <span>
            User: <strong>{userDisplay}</strong>
          </span>
        </span>
      </button>
      {menuOpen ? (
        <div className="identity-dropdown">
          <Link href="/settings" className="identity-dropdown-item" onClick={() => setMenuOpen(false)}>
            Settings
          </Link>
          <button type="button" className="identity-dropdown-item" disabled title="Coming soon">
            Switch Workspace (future)
          </button>
          <button
            type="button"
            className="identity-dropdown-item"
            onClick={() => {
              setMenuOpen(false);
              clearIdentity();
              router.push("/login");
            }}
          >
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}
