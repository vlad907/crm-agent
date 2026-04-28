/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  /** Required for Electron: run `node server.js` from `.next/standalone` without `npm`. */
  output: "standalone",
  /**
   * Same-origin API in the browser/Electron: avoids CORS when the UI is on 127.0.0.1:3001+.
   * Server-side fetches should use NEXT_PUBLIC_API_BASE / CRM_API_URL (see src/lib/api.ts).
   */
  async rewrites() {
    const backend = (process.env.CRM_API_PROXY_TARGET || "http://127.0.0.1:8000").replace(/\/$/, "");
    // beforeFiles: must run before App Router, otherwise /api/v1/* is treated as a missing page (404 HTML).
    return {
      beforeFiles: [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }],
    };
  },
  /** Avoid stale HTML in the browser/Electron HTTP cache pointing at removed CSS chunks after rebuilds. */
  async headers() {
    const noStore = [{ key: "Cache-Control", value: "private, no-cache, no-store, must-revalidate" }];
    return [
      { source: "/", headers: noStore },
      { source: "/login", headers: noStore },
      { source: "/onboarding", headers: noStore },
    ];
  },
};

export default nextConfig;
