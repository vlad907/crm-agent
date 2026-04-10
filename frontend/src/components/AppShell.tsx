"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { IdentityBanner } from "@/src/components/IdentityBanner";
import { hasIdentity, IDENTITY_UPDATED_EVENT, clearIdentity } from "@/src/lib/identity";

const LOGIN_PATH = "/login";
const ONBOARDING_PATH = "/onboarding";
const NO_NAV_PATHS = [LOGIN_PATH, ONBOARDING_PATH];

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  matchExact?: boolean;
}

const PIPELINE_NAV: NavItem[] = [
  {
    href: "/",
    label: "Leads",
    matchExact: true,
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/prospects",
    label: "Prospects",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
];

const OPS_NAV: NavItem[] = [
  {
    href: "/automation",
    label: "Automation",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
];

const CONFIG_NAV: NavItem[] = [
  {
    href: "/settings",
    label: "Settings",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/onboarding",
    label: "Setup Wizard",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
  },
];

function isActive(pathname: string, item: NavItem): boolean {
  if (item.matchExact) return pathname === item.href;
  return pathname.startsWith(item.href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    const sync = () => setAuthenticated(hasIdentity());
    sync();
    window.addEventListener(IDENTITY_UPDATED_EVENT, sync);
    return () => window.removeEventListener(IDENTITY_UPDATED_EVENT, sync);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!NO_NAV_PATHS.includes(pathname) && !authenticated) {
      router.replace(LOGIN_PATH);
    }
  }, [mounted, pathname, authenticated, router]);

  useEffect(() => { setSidebarOpen(false); }, [pathname]);

  if (!mounted) {
    return (
      <div className="app-shell-loading">
        <div className="app-shell-spinner" />
      </div>
    );
  }

  if (NO_NAV_PATHS.includes(pathname)) {
    return <>{children}</>;
  }

  if (!authenticated) {
    return (
      <div className="app-shell-loading">
        <div className="app-shell-spinner" />
      </div>
    );
  }

  function renderNavGroup(label: string, items: NavItem[]) {
    return (
      <div className="sidebar-group">
        <div className="sidebar-group-label">{label}</div>
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`sidebar-link${isActive(pathname, item) ? " active" : ""}`}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </div>
    );
  }

  return (
    <div className="app-layout">
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`sidebar${sidebarOpen ? " sidebar-open" : ""}`}>
        <div className="sidebar-top">
          <Link href="/" className="sidebar-brand">
            <span className="sidebar-brand-icon">
              <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </span>
            <div className="sidebar-brand-text">
              <span className="sidebar-brand-name">CRM Command</span>
              <span className="sidebar-brand-sub">Pipeline Control</span>
            </div>
          </Link>

          <Link href="/leads/new" className="sidebar-new-lead">
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Lead
          </Link>

          <nav className="sidebar-nav">
            {renderNavGroup("Pipeline", PIPELINE_NAV)}
            {renderNavGroup("Operations", OPS_NAV)}
            {renderNavGroup("Configure", CONFIG_NAV)}
          </nav>
        </div>

        <div className="sidebar-bottom">
          <IdentityBanner />
          <button
            type="button"
            className="sidebar-logout"
            onClick={() => {
              clearIdentity();
              router.push("/login");
            }}
          >
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Log out
          </button>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar-mobile">
          <button
            type="button"
            className="hamburger"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
          >
            <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="topbar-mobile-brand">CRM Command</span>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
