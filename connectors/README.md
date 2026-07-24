# SANAD connectors

Thin word-processor clients of the local SANAD Core. They own no data and no
logic — they call the Core over `http://127.0.0.1:23890` and place its results.
This is the deliberate "add-in is a thin client" design from `MVP_SPEC.md §3`.

## `word/` — Microsoft Word add-in (Office.js)

Inserts citations as content controls tagged `sanad-cite` (the only place it ever
writes) and runs the integrity check in a task pane.

### Try it in development

1. **Run the Core** — start the SANAD desktop app, or:
   ```bash
   python -m sanad_core.server
   ```
2. **Serve the task pane over HTTPS** (Office add-ins require HTTPS; loopback is
   allowed). From `connectors/word/`:
   ```bash
   npx office-addin-dev-certs install        # one-time trusted localhost cert
   npx http-server -S -p 3000 .              # or any static HTTPS server on :3000
   ```
   Copy the branding PNGs the manifest references (`icon-32.png`, `icon-64.png`)
   from `assets/branding/` alongside the task pane, or update the manifest URLs.
3. **Sideload the manifest** — in Word: *Insert → Add-ins → My Add-ins → Upload
   My Add-in* → pick `word/manifest.xml`. (`npx office-addin-debugging start
   word/manifest.xml` automates this.)

Before sideloading, set a real GUID for `<Id>` in `manifest.xml`.

### How it talks to the Core

The task pane is served from `https://localhost:3000`; the Core is
`http://127.0.0.1:23890`. Word's WebView2 treats `127.0.0.1` as a trustworthy
loopback origin, and the Core's CORS is scoped to allow any `localhost` /
`127.0.0.1` origin (see `sanad_core/server.py`). No cloud, no external host.

## LibreOffice

Same Core, a second thin client — LibreOffice uses a different extension model
(Python/Basic UNO), but it speaks the same HTTP protocol and reuses the same
`sanad-cite` content-control convention. Not built yet; it's a mechanical second
client once the Word one is finished, since the protocol is stable.
