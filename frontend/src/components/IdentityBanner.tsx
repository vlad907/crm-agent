"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { IDENTITY_UPDATED_EVENT, getUserId, getWorkspaceId } from "@/src/lib/identity";

function shortId(value: string): string {
  if (!value) {
    return "not set";
  }
  if (value.length <= 14) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

export function IdentityBanner() {
  const [workspaceId, setWorkspace] = useState("");
  const [userId, setUser] = useState("");

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

  return (
    <div
      className="row"
      style={{
        marginBottom: 12,
        padding: "8px 12px",
        border: "1px solid #d8e2ef",
        borderRadius: 10,
        background: "#f8fbff",
        fontSize: "0.82rem",
        color: "#3c4f67",
        alignItems: "center"
      }}
    >
      <span>
        Workspace: <strong>{shortId(workspaceId)}</strong>
      </span>
      <span>
        User: <strong>{shortId(userId)}</strong>
      </span>
      <Link href="/settings" className="external-link" style={{ fontWeight: 600 }}>
        Settings
      </Link>
    </div>
  );
}
