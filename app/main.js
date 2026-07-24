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
const crypto = require("crypto");

const CORE_PORT = 23890;
const CORE_URL = `http://127.0.0.1:${CORE_PORT}`;
// A per-launch session token. The Core requires it on every request; we hand the
// same value to the Core (env) and the renderer (preload). Nothing else can know
// it, so no other local process or web page can drive the user's library.
const TOKEN = crypto.randomBytes(24).toString("hex");
// dev layout: app/ sits next to sanad_core/ in the repo. Packaged layout: the
// frozen Core binary is shipped in resources/core/ (see package.json build).
const DEV_ROOT = path.join(__dirname, "..");

let coreProc = null;
let win = null;

function coreLaunch() {
  // packaged: the frozen Core binary shipped in resources/core/. dev: system Python.
  if (app.isPackaged) {
    const exe = process.platform === "win32" ? "sanad-core.exe" : "sanad-core";
    return { cmd: path.join(process.resourcesPath, "core", exe), args: [], cwd: process.resourcesPath };
  }
  const py = process.env.SANAD_PYTHON || (process.platform === "win32" ? "python" : "python3");
  return { cmd: py, args: ["-m", "sanad_core.server"], cwd: DEV_ROOT };
}

function startCore() {
  const { cmd, args, cwd } = coreLaunch();
  const env = { ...process.env, PYTHONUTF8: "1", SANAD_TOKEN: TOKEN };
  // packaged installs keep the library in the per-user data dir, not next to the app
  if (app.isPackaged) env.SANAD_DB = path.join(app.getPath("userData"), "library.db");
  coreProc = spawn(cmd, args, {
    cwd,
    env,
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
      additionalArguments: [`--sanad-core=${CORE_URL}`, `--sanad-token=${TOKEN}`],
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
