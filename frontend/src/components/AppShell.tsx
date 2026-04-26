"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

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
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/discovery",
    label: "Discovery",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
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
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    href: "/inbox",
    label: "Inbox",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
];

const CONFIG_NAV: NavItem[] = [
  {
    href: "/settings",
    label: "Settings",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.573-1.066z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    href: "/onboarding",
    label: "Setup Wizard",
    icon: (
      <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
      </svg>
    ),
  },
];

type Theme = "light" | "dark";

function getStoredTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem("crm-theme");
  if (stored === "dark" || stored === "light") return stored;
  return null;
}

function getSystemTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("crm-theme", theme);
}

function resolvePageTitle(pathname: string): string {
  if (pathname === "/") return "Leads";
  if (pathname === "/discovery") return "Discovery";
  if (pathname === "/prospects") return "Discovery";
  if (pathname === "/partnerships") return "Discovery";
  if (pathname === "/automation") return "Automation";
  if (pathname === "/inbox") return "Inbox";
  if (pathname === "/settings") return "Settings";
  if (pathname === "/onboarding") return "Setup";
  if (pathname === "/leads/new") return "New Lead";
  if (pathname.startsWith("/leads/")) return "Lead Detail";
  return "Dashboard";
}

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
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    setMounted(true);
    const initial = getStoredTheme() ?? getSystemTheme();
    setTheme(initial);
    applyTheme(initial);
  }, []);

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

  const toggleTheme = useCallback(() => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    applyTheme(next);
  }, [theme]);

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
            title={item.label}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            <span className="sidebar-link-label">{item.label}</span>
          </Link>
        ))}
      </div>
    );
  }

  const sidebarClass = `sidebar${sidebarOpen ? " sidebar-open" : ""}${sidebarPinned ? " pinned" : ""}`;

  return (
    <div className={`app-layout${sidebarPinned ? " sidebar-is-pinned" : ""}`}>
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={sidebarClass}>
        <div className="sidebar-top">
          <div className="sidebar-header">
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
            <button
              className="sidebar-pin-btn"
              onClick={() => setSidebarPinned((prev) => !prev)}
              title={sidebarPinned ? "Collapse sidebar" : "Pin sidebar open"}
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                {sidebarPinned ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                )}
              </svg>
            </button>
          </div>

          <Link href="/leads/new" className="sidebar-new-lead" title="New Lead">
            <span className="sidebar-new-lead-icon" aria-hidden="true">+</span>
            <span className="sidebar-link-label">New Lead</span>
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
            title="Log out"
          >
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            <span className="sidebar-link-label">Log out</span>
          </button>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="hamburger"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open menu"
            >
              <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <h1 className="topbar-title">{resolvePageTitle(pathname)}</h1>
          </div>
          <div className="topbar-right">
            <button
              type="button"
              className="theme-toggle"
              onClick={toggleTheme}
              title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
              aria-label="Toggle theme"
            >
              {theme === "light" ? (
                <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
              ) : (
                <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
              )}
            </button>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
