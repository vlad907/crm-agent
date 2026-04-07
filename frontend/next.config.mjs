/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  /** Required for Electron: run `node server.js` from `.next/standalone` without `npm`. */
  output: "standalone"
};

export default nextConfig;
