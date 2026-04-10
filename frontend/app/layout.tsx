import type { Metadata } from "next";

import { AppShell } from "@/src/components/AppShell";

import "./globals.css";

export const metadata: Metadata = {
  title: "CRM Command",
  description: "Lead pipeline control center"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
