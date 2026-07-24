# SANAD the RefGuard — Critical Audit

*Scope: build, product outlook, correctness/integrity, performance, and security.
Written against the repository at the "v1.0 engine + desktop shell + scaffolds"
state. Deliberately critical — this is a readiness review, not a launch brochure.*

## Verdict up front

**SANAD is not a finished product yet.** What exists is genuinely strong and, in
one dimension, ahead of the entire market: a **well-tested Core engine** (114
passing tests) with a differentiating **citation-integrity engine (R1–R8)**, a
**working local desktop shell**, a frozen Core binary, and *scaffolds* for
packaging and a Word add-in.

What stands between it and "shippable product":

1. **No authentication on the local Core, with wide-open loopback CORS** — the
   single most important issue (see Security).
2. **The Word/LibreOffice connector is a dev scaffold**, not a deployable add-in
   (no hosted HTTPS origin, no sideload/store path, unverified in real Word).
3. **No signed installers** are produced — only build configuration.
4. **No live metadata resolution** (no DOI/Crossref lookup); import is
   parse-only, a real functional gap vs. competitors.
5. **The desktop app is a library manager + demo** today; its Documents and
   Integrity screens are empty until the connector exists.

Rated as an *engine and architecture*: excellent. Rated as a *product a stranger
could download and rely on*: pre-beta.

---

## 1. Build

| Area | State | Notes |
|---|---|---|
| Core tests | ✅ 114 passing | Fast (~18 s), deterministic, covers every rule + API path. |
| Core freeze | ✅ `sanad-core.exe` (35 MB) via PyInstaller | Worked on Python 3.14 — a real risk that paid off. |
| Electron shell | ✅ runs, spawns Core, cleans up | Verified end-to-end. |
| Installers | ⚠️ configured, not produced | electron-builder targets nsis/dmg/AppImage, but no artifact is built or **code-signed** — Windows SmartScreen and macOS Gatekeeper will warn, and PyInstaller one-file binaries frequently trip antivirus false-positives. |
| Cross-platform | ❌ | PyInstaller cannot cross-compile; each OS binary must be built on that OS. No CI matrix exists. |
| Dependency pinning | ⚠️ | `requirements.txt` uses `>=` (supply-chain drift); npm side has a lockfile. |
| Versioning | ⚠️ | Core reports `0.1.0-dev`; app `package.json` says `0.1.0`. Unify before release. |
| Reproducibility | ❌ | No CI, no lockfile for Python, no build attestation. |

**To finish:** a CI matrix (win/mac/linux) that freezes the Core and runs
electron-builder, plus code-signing certificates (Authenticode + Apple Developer
ID/notarization). Pin Python deps.

## 2. Product outlook (UX & scope)

- **The app cannot yet open or track a document by itself.** Documents and
  Integrity are empty states until the Word add-in feeds them — and that add-in
  is a scaffold. So today the desktop app is: a **library manager**, a **style-
  profile builder**, and a **demo** of the integrity engine. That is honest, but
  it is not the "write-and-check" loop the product promises.
- **Style profiles** can be created but not **edited, deleted, or applied to a
  document from the UI** (apply exists only in the API).
- **RTL/Urdu is a headline claim but under-delivered in the app.** The Core and
  rendering handle RTL; the shell only shows سند in the title bar — the UI
  itself is not RTL-capable, which an Urdu-first user would immediately notice.
- **Accessibility is partial:** modals don't trap focus, toasts aren't announced
  (`aria-live`), and keyboard navigation of lists/tables is limited.
- **No PDF management, no browser "save to library" capture, no cloud sync.** Two
  of these are deliberate (local-first, no cloud), but the absence of PDF
  handling and one-click web capture is a real adoption gap.
- **No onboarding** beyond a static "Getting started" panel; no empty-library
  guidance beyond a hint.

## 3. Integrity / correctness

**Strengths (real and rare):**
- The **Text Integrity Guarantee** is enforced *in code* by `document_model.py`
  and proven by a fuzz test — the Core cannot write outside a `sanad-*` control.
- The integrity engine is principled: exact-only dedup, R1–R7 deterministic
  rules, R8 semantic check, all unit-tested, all *honest* about their limits.

**Genuine limitations:**
- **The guarantee's weakest link is the client, not the Core.** The Word add-in
  writes citations via Office.js; that it "only ever writes a `sanad-cite`
  control" is enforced by a code comment and discipline, **not by an automated
  test**. The fuzz test covers the model, not the live add-in. This is the exact
  class of gap the guarantee exists to close.
- **No live metadata resolution.** `sanad_core` makes no network calls — great
  for privacy, but it means a bare DOI or a messy typed reference is *not*
  enriched/corrected against Crossref. Competitors do this automatically.
- **R6 duplicate detection** uses exact-token Jaccard — misses stem/plural
  variants ("service" vs "services"). Documented; a stemming/rapidfuzz upgrade is
  deferred.
- **R8 quality depends on an optional heavy dependency.** Without
  `sentence-transformers`, R8 falls back to a *lexical* proxy (word overlap, not
  meaning). It's calibrated (zero false alarms on the labelled set) but will miss
  paraphrased misattributions that share few words. The scan reports which
  backend ran — honest, but the default install is the weaker one.
- **CSL fidelity:** `citeproc-py` is less spec-faithful than `citeproc-js`;
  rendering artifacts are patched with regexes. Only ~5 styles are wired vs.
  thousands in the CSL ecosystem.

## 4. Performance

- **R8 re-embeds the entire library on every scan** (`_library_refs(conn)` →
  embed all) with no vector caching. Fine with the lexical model on a small
  library; with the real transformer on a 1,000+ ref library this is slow. A
  persistent embedding cache is the known v1.x fix.
- **The CSL `Formatter` re-parses the CSL XML on essentially every render** —
  expensive; it's why the fuzz test takes ~25 s. A cached compiled style would
  help.
- **Scans run synchronously** in the request; fine for one user, but a large
  document blocks the event loop briefly.
- **No pagination** on library search (fixed `limit`); a big library truncates.
- **Install footprint** ≈ Electron (~150 MB) + frozen Core (35 MB) ≈ 200 MB — on
  the heavy side for the feature set.

## 5. Security & vulnerabilities

**This is the section that most affects "finished".**

### 5.1 Unauthenticated local service + broad CORS (High)
The Core listens on `127.0.0.1:23890` with **no authentication of any kind**, and
CORS now allows **any** loopback origin on **any** port, plus `null`/`file://`:

```
allow_origin_regex = ^(https?://(localhost|127\.0\.0\.1)(:\d+)?|null|file://)$
```

Consequences:
- **Any local process** can read and modify the user's entire library, create
  citations, and delete style profiles — no credential required.
- **Any web page served from `localhost`/`127.0.0.1`** (common on a developer's
  machine) can do the same cross-origin, because CORS explicitly allows it.
- Cross-origin **JSON** POSTs from a normal website (`evil.com`) are blocked by
  the browser's preflight (the Core won't echo `evil.com`), which is the main
  thing saving it today — but this is a browser side-effect, not a control SANAD
  enforces. **DNS-rebinding** can defeat origin checks entirely, and there is **no
  `Host`-header validation** to stop it.

**Recommended fixes (do before any public release):**
1. A **per-session bearer token**: the Core mints it at startup, the shell passes
   it via preload, the add-in receives it at sideload; reject requests without it.
2. **Strict `Host` header check** (reject anything but `127.0.0.1:23890`) to kill
   DNS-rebinding.
3. **Narrow CORS** to the exact app/add-in origins, not "any loopback".

### 5.2 No request-size limits (Medium)
`/v1/library/import` accepts unbounded text → trivial memory exhaustion. Add a
cap and stream/Reject oversized payloads.

### 5.3 Connector transport (Medium)
The add-in fetches `http://127.0.0.1` from an `https://` task-pane origin — mixed
content that only works via the browser's "localhost is potentially trustworthy"
exception. Fragile across browsers/Office versions; a locally-trusted TLS cert or
a documented exception is needed.

### 5.4 Distribution integrity (Medium)
Unsigned binaries + PyInstaller one-file (AV false positives) undermine user trust
at install time and provide no tamper evidence.

### 5.5 What's already good
- **Parameterized SQL everywhere** — no injection surface found.
- **Electron hardening is correct:** `contextIsolation: true`,
  `nodeIntegration: false`, a restrictive **CSP** (`connect-src` limited to the
  Core), external links routed through `shell.openExternal`, no remote content.
- **No secrets, no telemetry, no network egress** from the Core — a genuinely
  private, local-first posture.

---

## 6. Market comparison

| | **SANAD** | Zotero | Mendeley | EndNote | JabRef |
|---|---|---|---|---|---|
| Price / licence | Free, AGPLv3 | Free, open | Free, proprietary | Paid | Free, open |
| Local-first / private | ✅ fully local | ⚠️ local + paid sync | ❌ cloud-centric | ⚠️ | ✅ |
| Word / LibreOffice | ⚠️ scaffold | ✅ mature | ✅ | ✅ | ⚠️ |
| **"Cited in the right place?" (context check)** | ✅ **unique (R8)** | ❌ | ❌ | ❌ | ❌ |
| Wrong-year / venue / duplicate checks | ✅ R1–R7 | partial | partial | partial | partial |
| University-handbook style profiles | ✅ | ❌ (raw CSL) | ❌ | limited | ❌ |
| "Never edits your prose" guarantee | ✅ code-enforced | ❌ | ❌ | ❌ (`_ENREF_` dead links) | ❌ |
| First-class RTL / Urdu | ◑ claimed, partial in app | limited | limited | limited | limited |
| CSL style breadth | ❌ ~5 | ✅ 10,000+ | ✅ | ✅ | ✅ |
| Metadata resolution (DOI→data) | ❌ | ✅ | ✅ | ✅ | ✅ |
| PDF library / reader | ❌ | ✅ | ✅ | ✅ | ⚠️ |
| Browser capture | ❌ | ✅ | ✅ | ⚠️ | ❌ |
| Cloud sync / collaboration | ❌ (by design) | ✅ | ✅ | ✅ | ❌ |
| Maturity / install base | ❌ new | ✅ huge | ✅ large | ✅ large | ✅ |

**The one-line positioning:** SANAD is the only tool that checks whether a
citation is *right* — correct source, correct place — and guarantees it never
touches your writing, entirely offline. It is *not* yet a replacement for
Zotero/Mendeley on the fundamentals (metadata resolution, PDFs, style breadth,
capture, sync, maturity). The realistic play is a **companion/verifier** that
sits alongside a mature manager, or a niche win for **thesis writers under strict
university handbooks and RTL/Urdu users** — provided the security and connector
gaps are closed.

---

## 7. Prioritized remediation

**Must-fix before public release**
1. Core **authentication** (session token) + **Host-header check** + **narrow
   CORS** (§5.1).
2. **Signed installers** on a CI matrix; unify version strings (§1).
3. A **deployable connector** (hosted HTTPS, sideload docs, verified in real
   Word) or an automated test that the add-in only writes `sanad-*` controls
   (§3, §5.3).

**Should-fix for a credible v1**
4. **Metadata resolution** (DOI/Crossref) in import (§3).
5. Request-size limits (§5.2).
6. Style-profile **edit/delete/apply** in the UI; more CSL styles (§2).
7. **Persistent embedding cache** and cached compiled CSL (§4).

**Nice-to-have**
8. Real **RTL app layout**, accessibility pass, onboarding (§2).
9. PDF handling / browser capture / optional sync (§6) — or a deliberate decision
   to stay lean and position as a verifier.

---

## 8. Fix log (post-audit)

Tracking the audit's findings as they are closed.

- **§5.1 Unauthenticated Core + broad CORS — FIXED.** The Core now requires a
  per-launch **bearer session token** on every `/v1` request (401 otherwise);
  the launcher generates it and hands it to both the Core and the renderer, and
  it is written to a `0600` token file for the add-in. Added a **Host-header
  allow-list** (TrustedHostMiddleware) to defeat DNS-rebinding, a **WebSocket
  token check**, and an **import size cap** (§5.2). The health probe no longer
  leaks the library path. Covered by tests: token-required, wrong-token,
  foreign-host-rejected, WS-requires-token, import-413. This was the top
  must-fix blocker.
