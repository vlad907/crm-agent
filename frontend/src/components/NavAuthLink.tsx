"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { clearIdentity, hasIdentity, IDENTITY_UPDATED_EVENT } from "@/src/lib/identity";

export function NavAuthLink() {
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const sync = () => setAuthenticated(hasIdentity());
    sync();
    window.addEventListener(IDENTITY_UPDATED_EVENT, sync);
    return () => window.removeEventListener(IDENTITY_UPDATED_EVENT, sync);
  }, []);

  if (authenticated) {
    return (
      <button
        type="button"
        className="nav-link nav-link-button"
        onClick={() => {
          clearIdentity();
          router.push("/login");
        }}
      >
        Log out
      </button>
    );
  }

  return (
    <Link href="/login" className="nav-link">
      Login
    </Link>
  );
}
