"use strict";
// SANAD desktop shell — main process.
//
// Owns the app window and the lifecycle of the local SANAD Core service
// (Python, sanad_core.server) which it launches as a sidecar and shuts down on
// quit. The renderer talks to the Core over http://127.0.0.1:23890 directly; the
// main process only supervises it.

const { app, BrowserWindow, shell } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

const CORE_PORT = 23890;
const CORE_URL = `http://127.0.0.1:${CORE_PORT}`;
// dev layout: app/ sits next to sanad_core/ in the repo. Packaged layout: the
// Core is copied into resources/ (see package.json build.extraResources).
const DEV_ROOT = path.join(__dirname, "..");
const CORE_CWD = app.isPackaged ? process.resourcesPath : DEV_ROOT;

let coreProc = null;
let win = null;

function startCore() {
  const py = process.env.SANAD_PYTHON || (process.platform === "win32" ? "python" : "python3");
  coreProc = spawn(py, ["-m", "sanad_core.server"], {
    cwd: CORE_CWD,
    env: { ...process.env, PYTHONUTF8: "1" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  coreProc.stdout.on("data", (d) => process.stdout.write(`[core] ${d}`));
  coreProc.stderr.on("data", (d) => process.stdout.write(`[core] ${d}`));
  coreProc.on("error", (e) => console.error("[core] failed to launch:", e.message));
  coreProc.on("exit", (code) => console.log(`[core] exited with ${code}`));
}

async function waitForCore(timeoutMs = 25000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(`${CORE_URL}/v1/health`);
      if (r.ok && (await r.json()).status === "ok") return true;
    } catch (_) { /* not up yet */ }
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

function createWindow(coreReady) {
  win = new BrowserWindow({
    width: 1240,
    height: 820,
    minWidth: 940,
    minHeight: 620,
    backgroundColor: "#12151c",
    title: "SANAD",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.removeMenu();
  // open external links in the system browser, never in-app
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  const query = `?ready=${coreReady ? 1 : 0}`;
  win.loadFile(path.join(__dirname, "renderer", "index.html"), {
    search: query,
  });
}

app.whenReady().then(async () => {
  startCore();
  const ready = await waitForCore();
  createWindow(ready);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow(ready);
  });
});

function stopCore() {
  if (coreProc && !coreProc.killed) {
    coreProc.kill();
    coreProc = null;
  }
}

app.on("window-all-closed", () => app.quit());
app.on("before-quit", stopCore);
process.on("exit", stopCore);
