"use strict";

/**
 * Next.js `output: "standalone"` requires static assets next to the server bundle.
 * @see https://nextjs.org/docs/app/api-reference/next-config-js/output
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const standalone = path.join(root, ".next", "standalone");
const serverJs = path.join(standalone, "server.js");

if (!fs.existsSync(serverJs)) {
  console.error("prepare-standalone: missing", serverJs, "(did next build run with output: standalone?)");
  process.exit(1);
}

const staticSrc = path.join(root, ".next", "static");
const staticDest = path.join(standalone, ".next", "static");
const publicSrc = path.join(root, "public");
const publicDest = path.join(standalone, "public");

if (fs.existsSync(staticSrc)) {
  fs.mkdirSync(path.dirname(staticDest), { recursive: true });
  fs.cpSync(staticSrc, staticDest, { recursive: true });
  console.log("prepare-standalone: copied .next/static");
} else {
  console.warn("prepare-standalone: no .next/static (ok for some builds)");
}

if (fs.existsSync(publicSrc)) {
  fs.cpSync(publicSrc, publicDest, { recursive: true });
  console.log("prepare-standalone: copied public");
}

console.log("prepare-standalone: done");
