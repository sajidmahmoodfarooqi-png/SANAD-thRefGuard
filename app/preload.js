"use strict";
// Minimal, safe bridge into the renderer. The renderer talks to the Core over
// plain HTTP itself; this exposes the Core's address (via argv) and the per-launch
// session token (fetched synchronously over IPC, never via argv, so the secret
// stays off the renderer process's command line) plus the platform. Nothing else
// crosses the boundary.
const { contextBridge, ipcRenderer } = require("electron");

function arg(prefix) {
  const a = process.argv.find((x) => x.startsWith(prefix));
  return a ? a.slice(prefix.length) : null;
}

function sessionToken() {
  try { return ipcRenderer.sendSync("sanad:token") || ""; } catch (_) { return ""; }
}

contextBridge.exposeInMainWorld("sanadShell", {
  coreUrl: arg("--sanad-core=") || "http://127.0.0.1:23890",
  token: sessionToken(),
  platform: process.platform,
  // open the complete offline guide in the system's default browser
  openGuide: () => ipcRenderer.invoke("sanad:open-guide"),
  // copy the session token to the clipboard (to paste into the Word add-in)
  copyToken: (t) => ipcRenderer.invoke("sanad:copy", t),
  // rotate the token and relaunch (the user re-pastes it into the add-in once)
  regenerateToken: () => ipcRenderer.invoke("sanad:regenerate-token"),
});
