"use strict";

const { app, BrowserWindow, shell } = require("electron");
const fs = require("fs");
const path = require("path");
const net = require("net");
const { spawn } = require("child_process");

const FRONTEND_PORT = process.env.PORT || "3000";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";
const START_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
/** Only wait this long for Next.js; backend runs in parallel and does not block the UI. */
const FRONTEND_WAIT_MS = Number(process.env.CRM_FRONTEND_WAIT_MS || 90000);
const POLL_MS = 100;

/** Next dev is started by concurrently; packaged build runs `.next/standalone/server.js` with `node`. */
const isDevShell = process.env.ELECTRON_DEV === "1";

function pathWithCommonNodeBinaries() {
  const base = process.env.PATH || "";
  if (process.platform === "win32") {
    const extra = [
      `${process.env.ProgramFiles || "C:\\Program Files"}\\nodejs`,
      process.env.LOCALAPPDATA ? `${process.env.LOCALAPPDATA}\\Programs\\nodejs` : ""
    ].filter(Boolean);
    return `${extra.join(";")};${base}`;
  }
  return `/opt/homebrew/bin:/usr/local/bin:${base}`;
}

let mainWindow = null;
let nextChild = null;
let backendChild = null;

function waitForPort(port, host, timeoutMs = FRONTEND_WAIT_MS, pollMs = POLL_MS) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const tryOnce = () => {
      const socket = net.createConnection({ port: Number(port), host });
      socket.once("connect", () => {
        socket.end();
        resolve();
      });
      socket.once("error", () => {
        socket.destroy();
        if (Date.now() > deadline) {
          reject(new Error(`Timed out waiting for ${host}:${port}`));
        } else {
          setTimeout(tryOnce, pollMs);
        }
      });
    };
    tryOnce();
  });
}

function portReachable(port, host) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port: Number(port), host });
    socket.once("connect", () => {
      socket.end();
      resolve(true);
    });
    socket.once("error", () => {
      socket.destroy();
      resolve(false);
    });
  });
}

function getBackendRoot() {
  const marker = path.join("app", "main.py");
  if (app.isPackaged) {
    const bundled = path.join(process.resourcesPath, "backend");
    if (fs.existsSync(path.join(bundled, marker))) {
      return bundled;
    }
    return null;
  }
  const dev = path.join(__dirname, "..", "..", "backend");
  if (fs.existsSync(path.join(dev, marker))) {
    return dev;
  }
  return null;
}

function startBackend(backendRoot) {
  const py = process.env.CRM_PYTHON || (process.platform === "win32" ? "python" : "python3");
  const args = [
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    String(BACKEND_PORT)
  ];
  backendChild = spawn(py, args, {
    cwd: backendRoot,
    env: { ...process.env, PYTHONUNBUFFERED: "1" },
    stdio: "inherit"
  });
  backendChild.on("error", (err) => {
    console.error("CRM: failed to start backend:", err);
  });
  backendChild.on("exit", (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error("CRM: backend process exited", code, signal);
    }
  });
}

/**
 * Start the API in the background. Does not block the window — the UI loads as soon as Next is ready.
 */
function kickOffBackend() {
  if (process.env.CRM_SKIP_BACKEND === "1") {
    console.log("CRM: CRM_SKIP_BACKEND=1, not starting backend");
    return;
  }
  void (async () => {
    if (await portReachable(BACKEND_PORT, "127.0.0.1")) {
      console.log("CRM: backend already listening on", BACKEND_PORT);
      return;
    }
    const root = getBackendRoot();
    if (!root) {
      console.warn(
        "CRM: backend directory not found; run the API separately (e.g. Docker) or set CRM_SKIP_BACKEND=1"
      );
      return;
    }
    console.log("CRM: starting backend from", root);
    startBackend(root);
    try {
      await waitForPort(BACKEND_PORT, "127.0.0.1", Number(process.env.CRM_BACKEND_WAIT_MS || 120000), POLL_MS);
      console.log("CRM: backend is ready");
    } catch (e) {
      console.error("CRM: backend did not become ready:", e.message || e);
    }
  })();
}

function startNextProductionServer() {
  const appRoot = app.getAppPath();
  const standaloneDir = path.join(appRoot, ".next", "standalone");
  const serverJs = path.join(standaloneDir, "server.js");
  const nodeBin = process.env.CRM_NODE || "node";
  const pathEnv = pathWithCommonNodeBinaries();

  if (fs.existsSync(serverJs)) {
    console.log("CRM: starting Next standalone from", standaloneDir);
    nextChild = spawn(nodeBin, ["server.js"], {
      cwd: standaloneDir,
      env: {
        ...process.env,
        NODE_ENV: "production",
        PORT: String(FRONTEND_PORT),
        HOSTNAME: "127.0.0.1",
        PATH: pathEnv
      },
      stdio: "inherit"
    });
  } else {
    console.warn("CRM: no .next/standalone/server.js — falling back to npm start (needs npm on PATH)");
    const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
    nextChild = spawn(
      npmCmd,
      ["run", "start", "--", "-H", "127.0.0.1", "-p", String(FRONTEND_PORT)],
      {
        cwd: appRoot,
        env: { ...process.env, PORT: String(FRONTEND_PORT), PATH: pathEnv },
        shell: process.platform === "win32",
        stdio: "inherit"
      }
    );
  }
  nextChild.on("error", (err) => {
    console.error("Failed to start Next.js:", err);
  });
}

async function ensureNextReady() {
  if (isDevShell) {
    await waitForPort(FRONTEND_PORT, "127.0.0.1", FRONTEND_WAIT_MS, POLL_MS);
    return;
  }
  startNextProductionServer();
  await waitForPort(FRONTEND_PORT, "127.0.0.1", FRONTEND_WAIT_MS, POLL_MS);
}

const LOADING_HTML = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>CRM Command</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f1419;color:#e6edf3}</style></head>
<body><p>Starting the app…</p></body></html>`;

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 600,
    title: "CRM Command",
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  return mainWindow;
}

async function loadAppOrError(err) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  if (err) {
    const msg = escapeHtml(err.message || err);
    await mainWindow.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(
        `<!DOCTYPE html><html><head><meta charset="utf-8"><title>CRM Command</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;padding:24px;max-width:560px;margin:40px auto;background:#0f1419;color:#e6edf3}</style></head>
<body><h1 style="font-size:18px">Could not start the app</h1><p style="line-height:1.5;color:#8b949e">${msg}</p>
<p style="color:#8b949e;font-size:13px">Tip: rebuild with <code style="color:#c9d1d9">npm run electron:build</code> (needs <code style="color:#c9d1d9">node</code> on PATH for the packaged app). Ensure Postgres is running and <code style="color:#c9d1d9">python3</code> is installed for the API. For development use <code style="color:#c9d1d9">npm run electron:dev</code>.</p></body></html>`
      )}`
    );
    return;
  }
  await mainWindow.loadURL(START_URL);
}

function shutdownBackend() {
  if (backendChild && !backendChild.killed) {
    try {
      backendChild.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    backendChild = null;
  }
}

function shutdownNext() {
  if (nextChild && !nextChild.killed) {
    try {
      nextChild.kill("SIGTERM");
    } catch {
      /* ignore */
    }
    nextChild = null;
  }
}

async function openMainWindow() {
  createWindow();
  await mainWindow.loadURL(
    `data:text/html;charset=utf-8,${encodeURIComponent(LOADING_HTML)}`
  );
  try {
    kickOffBackend();
    await ensureNextReady();
    await loadAppOrError(null);
  } catch (err) {
    console.error(err);
    await loadAppOrError(err);
  }
}

app.whenReady().then(async () => {
  const { session } = require("electron");
  await session.defaultSession.clearCache();
  await session.defaultSession.clearStorageData({ storages: ["cachestorage"] });
  void openMainWindow();
});

app.on("window-all-closed", () => {
  shutdownNext();
  shutdownBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void openMainWindow();
  }
});

app.on("before-quit", () => {
  shutdownNext();
  shutdownBackend();
});
