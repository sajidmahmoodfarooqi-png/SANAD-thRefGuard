/* Minimal HTTPS static server for local add-in testing.
 * Serves this folder on https://localhost:3000 using the trusted localhost
 * certificate from office-addin-dev-certs (installed automatically). Started by
 * `npm start` via office-addin-debugging. Not used in production hosting. */
"use strict";
const https = require("https");
const fs = require("fs");
const path = require("path");
const devCerts = require("office-addin-dev-certs");

const ROOT = __dirname;
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".png": "image/png", ".xml": "text/xml", ".json": "application/json", ".svg": "image/svg+xml" };

(async () => {
  const opts = await devCerts.getHttpsServerOptions(); // installs/returns {cert,key,ca}
  https.createServer(opts, (req, res) => {
    let p = decodeURIComponent((req.url || "/").split("?")[0]);
    if (p === "/") p = "/taskpane.html";
    const file = path.join(ROOT, p);
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      res.writeHead(404); return res.end("not found");
    }
    res.setHeader("Content-Type", TYPES[path.extname(file)] || "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  }).listen(3000, () => console.log("SANAD add-in served at https://localhost:3000"));
})().catch((e) => { console.error(e); process.exit(1); });
