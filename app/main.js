"use strict";
// SANAD desktop shell — main process.
//
// Owns the app window and the lifecycle of the local SANAD Core service
// (Python, sanad_core.server) which it launches as a sidecar and shuts down on
// quit. The renderer talks to the Core over http://127.0.0.1:23890 directly; the
// main process only supervises it.

const { app, BrowserWindow, shell, ipcMain, clipboard } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const CORE_PORT = 23890;
const CORE_URL = `http://127.0.0.1:${CORE_PORT}`;
// The Core requires this session token on every request; the same value is handed
// to the Core (env) and the renderer (preload). Nothing else can know it, so no
// other local process or web page can drive the user's library.
//
// It is PERSISTED (a 0600 file in the user's app-data folder) and reused across
// launches — so the Word add-in, which the user pastes it into once, keeps working
// after a restart instead of needing a fresh paste every time. "Regenerate token"
// writes a new one and relaunches. It is set in app.whenReady (needs userData).
let TOKEN = "";
function tokenFilePath() { return path.join(app.getPath("userData"), "session-token"); }
function loadOrCreateToken() {
  try {
    const t = fs.readFileSync(tokenFilePath(), "utf8").trim();
    if (/^[a-f0-9]{32,}$/i.test(t)) return t;
  } catch (_) { /* not created yet */ }
  const t = crypto.randomBytes(24).toString("hex");
  try { fs.writeFileSync(tokenFilePath(), t, { mode: 0o600 }); } catch (_) {}
  return t;
}
// dev layout: app/ sits next to sanad_core/ in the repo. Packaged layout: the
// frozen Core binary is shipped in resources/core/ (see package.json build).
const DEV_ROOT = path.join(__dirname, "..");

let coreProc = null;
let win = null;

// The complete offline guide ships as a real file (extraResources when packaged,
// docs/ in dev). Opening it via shell.openPath hands it to the OS default browser,
// so a user can read or print the full manual without any network access.
function guidePath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "SANAD-Guide.html")
    : path.join(DEV_ROOT, "docs", "SANAD-Guide.html");
}
ipcMain.handle("sanad:open-guide", async () => {
  const err = await shell.openPath(guidePath());   // "" on success
  return { ok: !err, error: err || null };
});

// hand the session token to the renderer synchronously at preload time, over IPC
// instead of argv — so the secret never appears in the renderer process's command
// line, where another local process could read it. TOKEN is set in whenReady,
// before any window (and thus any preload) exists, so it is always populated here.
ipcMain.on("sanad:token", (e) => { e.returnValue = TOKEN; });

// copy the session token to the clipboard, so the user can paste it into the
// Word add-in's Connect tab (the one manual step that keeps everything offline)
ipcMain.handle("sanad:copy", (_e, text) => { clipboard.writeText(String(text || "")); return true; });

// rotate the token: write a fresh one and relaunch so the Core comes up with it.
// The user re-pastes the new token into the add-in once.
ipcMain.handle("sanad:regenerate-token", () => {
  try { fs.writeFileSync(tokenFilePath(), crypto.randomBytes(24).toString("hex"), { mode: 0o600 }); } catch (_) {}
  app.relaunch();
  app.exit(0);
});

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
      sandbox: true,
      // Only the (non-secret) Core URL travels via argv. The session token is
      // delivered over IPC (sanad:token) so it never appears in the renderer
      // process's command line, where another local process could read it.
      additionalArguments: [`--sanad-core=${CORE_URL}`],
    },
  });
  win.removeMenu();
  // open external links in the system browser, never in-app — and only http(s),
  // so a crafted file:/other-scheme link can never be handed to the OS to open.
  win.webContents.setWindowOpenHandler(({ url }) => {
    try {
      const proto = new URL(url).protocol;
      if (proto === "http:" || proto === "https:") shell.openExternal(url);
    } catch (_) { /* malformed or unsafe URL: ignore */ }
    return { action: "deny" };
  });
  // never let a dropped file (or stray link) navigate away from the app shell
  win.webContents.on("will-navigate", (e, url) => {
    if (url !== win.webContents.getURL()) e.preventDefault();
  });
  const query = `?ready=${coreReady ? 1 : 0}`;
  win.loadFile(path.join(__dirname, "renderer", "index.html"), {
    search: query,
  });
}

app.whenReady().then(async () => {
  TOKEN = loadOrCreateToken();     // stable token (needs userData, so set here)
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
