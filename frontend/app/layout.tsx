import type { Metadata } from "next";
import Link from "next/link";

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
            <nav>
              <Link href="/" className="nav-link">
                Leads
              </Link>
              <Link href="/leads/new" className="nav-link">
                New Lead
              </Link>
            </nav>
          </div>
        </header>
        <main className="container page">{children}</main>
      </body>
    </html>
  );
}
