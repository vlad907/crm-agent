import type { Metadata } from "next";
import { DM_Sans, Instrument_Sans } from "next/font/google";

import { AppShell } from "@/src/components/AppShell";

import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-instrument",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CRM Command",
  description: "Lead pipeline control center"
};

/** Inline fallback so Electron / failed CSS still shows a visible shell (not a blank white window). */
const CRITICAL_FALLBACK_CSS = `
html,body{min-height:100%;margin:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#f1f5f9;color:#0f172a}
.app-shell-loading{min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f1f5f9}
.app-shell-spinner{width:32px;height:32px;border:3px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:crmSpin .75s linear infinite}
@keyframes crmSpin{to{transform:rotate(360deg)}}
.login-page-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;background:linear-gradient(160deg,#0f172a,#1e293b)}
.login-card{background:#fff;border-radius:16px;padding:28px 32px;max-width:420px;width:100%;box-shadow:0 24px 48px rgba(0,0,0,.35)}
.login-brand,.login-brand-text{color:#0f172a;text-decoration:none;font-weight:700;font-size:1.25rem}
.login-mode-tabs{display:flex;gap:6px;margin:18px 0}
.login-mode-tab{flex:1;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc;cursor:pointer;font-weight:600}
.login-mode-tab.active{background:#3b82f6;color:#fff;border-color:#3b82f6}
.stack{display:flex;flex-direction:column;gap:12px}
.field label{display:block;font-size:.8rem;font-weight:600;margin-bottom:4px}
.field input{width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font-size:1rem;box-sizing:border-box}
.btn-primary{padding:10px 18px;background:#3b82f6;color:#fff;border:none;border-radius:8px;font-weight:600;cursor:pointer}
.inline-actions{margin-top:8px}
.error{color:#b91c1c;background:#fef2f2;padding:10px;border-radius:8px;font-size:.88rem}
.success{color:#047857;background:#ecfdf5;padding:10px;border-radius:8px;font-size:.88rem}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${dmSans.variable} ${instrumentSans.variable}`}>
      <head>
        <style dangerouslySetInnerHTML={{ __html: CRITICAL_FALLBACK_CSS }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
