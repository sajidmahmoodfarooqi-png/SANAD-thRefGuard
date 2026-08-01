"use strict";
// Minimal, safe bridge into the renderer. The renderer talks to the Core over
// plain HTTP itself; this exposes the Core's address and the per-launch session
// token (both handed in by the main process via additionalArguments) plus the
// platform. Nothing else crosses the boundary.
const { contextBridge, ipcRenderer } = require("electron");

function arg(prefix) {
  const a = process.argv.find((x) => x.startsWith(prefix));
  return a ? a.slice(prefix.length) : null;
}

contextBridge.exposeInMainWorld("sanadShell", {
  coreUrl: arg("--sanad-core=") || "http://127.0.0.1:23890",
  token: arg("--sanad-token=") || "",
  platform: process.platform,
  // open the complete offline guide in the system's default browser
  openGuide: () => ipcRenderer.invoke("sanad:open-guide"),
});
