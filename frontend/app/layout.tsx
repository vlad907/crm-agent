import type { Metadata } from "next";
import Link from "next/link";

import { IdentityBanner } from "@/src/components/IdentityBanner";

import "./globals.css";

export const metadata: Metadata = {
  title: "CRM Frontend",
  description: "CRM MVP UI"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
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
                <Link href="/settings" className="nav-link">
                  Settings
                </Link>
                <Link href="/automation" className="nav-link">
                  Automation
                </Link>
                <Link href="/login" className="nav-link">
                  Login
                </Link>
              </nav>
              <IdentityBanner />
            </div>
          </div>
        </header>
        <main className="container page">
          {children}
        </main>
      </body>
    </html>
  );
}
