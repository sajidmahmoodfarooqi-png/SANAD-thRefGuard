# SANAD connectors

Thin word-processor clients of the local SANAD Core. They own no data and no
logic — they call the Core over `http://127.0.0.1:23890` and place its results.
This is the deliberate "add-in is a thin client" design from `MVP_SPEC.md §3`.

## `word/` — Microsoft Word add-in (Office.js)

A task pane that does the real citation work **inside your document**, writing
only inside its own tagged content controls — never your prose:

- **Insert** — search your local library, insert a citation at the cursor
  (wrapped in a `sanad-cite` content control).
- **Reference list** — rebuild the whole bibliography from the document's
  citations, in your Style Profile's formatting, inside the single
  `sanad-bibliography` control (created if absent, updated in place if present).
- **Integrity** — run SANAD's Tier-A + Tier-B checks over every citation.
- **Connect** — paste the Core's per-launch session token once.

The bundle (`taskpane.html/.css/.js`, `assets/`, `manifest.xml`) is fully
self-contained and has a real add-in `<Id>` GUID. It ships pointing at
`https://localhost:3000` so you can test locally now, then host it by swapping
that one URL.

### A. Test it locally (fastest — no hosting yet)

1. **Run the Core** — start the SANAD desktop app (or `python -m sanad_core.server`).
   Note its session token (desktop app Settings, or the `sanad.token` file next
   to your library).
2. **Serve the task pane over HTTPS** from `connectors/word/`:
   ```bash
   npx office-addin-dev-certs install     # one-time trusted localhost cert
   npx http-server -S -C "$(npx office-addin-dev-certs verify --json | jq -r .localhostCertPath)" \
     -K "$(...keyPath)" -p 3000 .          # or simply: npx office-addin-debugging start manifest.xml
   ```
   Easiest: `npx office-addin-debugging start manifest.xml` — it installs the
   cert, serves on :3000, and sideloads into Word for you.
3. **Sideload** (if not automated) — Word → *Insert → Add-ins → My Add-ins →
   Upload My Add-in* → pick `manifest.xml`.
4. In the pane: open **Connect**, paste the token, click Connect (status should
   go green). Then **Insert** a citation, build the **Reference list**, run
   **Integrity**.

### B. Host it (for real use / distribution)

The task pane is static files, so any HTTPS host works — your own domain
subfolder/subdomain, or GitHub Pages.

1. Upload the contents of `connectors/word/` (`taskpane.*`, `assets/`) to your
   HTTPS host, e.g. `https://sanad.YOURDOMAIN/`.
2. Produce a hosted manifest by swapping the one URL:
   ```bash
   sed 's#https://localhost:3000#https://sanad.YOURDOMAIN#g' \
       manifest.xml > manifest.prod.xml
   ```
3. Sideload `manifest.prod.xml` in Word (same Upload My Add-in step), or deploy
   it via your Microsoft 365 admin centre for an organisation.

**Privacy note:** only the task-pane *UI* is served from the host. Your document
never leaves your machine — the pane talks only to the local Core on
`127.0.0.1`, whose CORS + Host allow-list are scoped to loopback origins (see
`sanad_core/server.py`). No document content is ever sent to the web host.

### The write boundary (unchanged guarantee)

The add-in writes in exactly two places, both tagged content controls it owns:
`sanad-cite` (citations) and `sanad-bibliography` (the reference list). It never
reads or writes your prose. `tests/test_addin_guarantee.py` statically enforces
that no prose-writing Office API is reachable from `taskpane.js`.

## LibreOffice

Same Core, a second thin client — LibreOffice uses a different extension model
(Python/Basic UNO), but it speaks the same HTTP protocol and reuses the same
`sanad-cite` / `sanad-bibliography` conventions. Not built yet; it's a mechanical
second client once the Word one is proven, since the protocol is stable.
