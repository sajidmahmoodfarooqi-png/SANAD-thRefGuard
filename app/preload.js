"use strict";
// Minimal, safe bridge into the renderer. The renderer talks to the Core over
// plain HTTP itself; all this exposes is the Core's address and the platform.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("sanadShell", {
  coreUrl: "http://127.0.0.1:23890",
  platform: process.platform,
});
