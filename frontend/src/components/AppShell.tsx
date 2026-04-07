"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { IdentityBanner } from "@/src/components/IdentityBanner";
import { NavAuthLink } from "@/src/components/NavAuthLink";
import { hasIdentity, IDENTITY_UPDATED_EVENT } from "@/src/lib/identity";

const LOGIN_PATH = "/login";
const ONBOARDING_PATH = "/onboarding";

const NO_NAV_PATHS = [LOGIN_PATH, ONBOARDING_PATH];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const sync = () => setAuthenticated(hasIdentity());
    sync();
    window.addEventListener(IDENTITY_UPDATED_EVENT, sync);
    return () => window.removeEventListener(IDENTITY_UPDATED_EVENT, sync);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const onNoNavPath = NO_NAV_PATHS.includes(pathname);
    if (!onNoNavPath && !authenticated) {
      router.replace(LOGIN_PATH);
    }
  }, [mounted, pathname, authenticated, router]);

  const onNoNavPath = NO_NAV_PATHS.includes(pathname);

  if (!mounted) {
    return (
      <div className="app-shell-loading">
        <div className="app-shell-spinner" />
      </div>
    );
  }

  if (onNoNavPath) {
    return <>{children}</>;
  }

  if (!authenticated) {
    return (
      <div className="app-shell-loading">
        <div className="app-shell-spinner" />
      </div>
    );
  }

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <Link href="/" className="brand-wrap">
            <span className="brand">CRM Command</span>
            <span className="brand-sub">Lead pipeline control center</span>
          </Link>
          <div className="topbar-actions">
            <nav>
              <Link href="/" className="nav-link">
                Leads
              </Link>
              <Link href="/prospects" className="nav-link">
                Prospects
              </Link>
              <Link href="/leads/new" className="nav-link">
                New Lead
              </Link>
              <Link href="/onboarding" className="nav-link">
                Setup
              </Link>
              <Link href="/settings" className="nav-link">
                Settings
              </Link>
              <Link href="/automation" className="nav-link">
                Automation
              </Link>
              <NavAuthLink />
            </nav>
            <IdentityBanner />
          </div>
        </div>
      </header>
      <main className="container page">{children}</main>
    </>
  );
}
