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

- **§3 List-based import (Excel / CSV / Word) — ADDED.** Beyond RIS/BibTeX, the
  Library now builds itself from a plain **Excel (.xlsx)**, **CSV**, or **Word
  (.docx)** list of papers — no PDF ingestion required. Binary files are carried
  base64-in-JSON (no new server dependency). Covered by `tests/test_list_import.py`.

- **§3/§7.4 Metadata resolution (DOI→Crossref) — ADDED, opt-in.** An optional,
  **off-by-default, per-import** online lookup enriches and corrects any entry
  that carries a **DOI** against Crossref (`sanad_core/resolver.py`). It is
  DOI-only (never a title guess, which could fetch the *wrong* paper), timeout-
  guarded, and degrades to the user's own data on any failure — preserving the
  local-first guarantee for everyone who leaves it off. Covered by
  `tests/test_resolver.py` (merge logic with an injected fetch, no network) and
  API `resolve`-flag tests. This narrows the Zotero/Mendeley gap in §7's table
  from "❌" to "opt-in".

- **Hygiene batch — FIXED.** (a) **Version strings unified** — Core and the
  desktop app now both report `0.1.0` (was `0.1.0-dev` vs `0.1.0`). (b) **Style
  Profile edit/delete** — added `PUT`/`DELETE /v1/style-profiles/{id}` plus
  Rename and Delete controls in the app, so a profile is no longer create-only;
  covered by module and API tests. (c) **Accessibility** — the modal is a real
  `role="dialog"` with a Tab focus-trap, focus moves in on open and is restored
  on close, toasts announce via `aria-live="polite"`, and a keyboard-only
  `:focus-visible` ring was added (verified headless with Playwright). (d)
  **Continuous integration** — `.github/workflows/ci.yml` runs the test suite on
  a Linux/Windows/macOS × Python 3.12/3.13 matrix and freezes + smoke-tests the
  Core binary on each OS. (e) **R8 embedding cache** — a persistent per-text
  vector cache (`embedding.CachingEmbedding`), built once per Core process and
  reused across scans, so re-scans only embed genuinely new sentences/sources
  rather than re-embedding the whole library pool every time (the dominant cost
  under the real semantic model). Bounded + FIFO-evicted; returns byte-identical
  vectors so determinism is preserved.

---

## 9. Diagnostic audit — November 2026 (v0.2.12 code)

A line-by-line pass over the Core (`sanad_core/`), the desktop shell (`app/`) and
the Word add-in (`connectors/word/`). Every item below was **reproduced against
the code before it was changed** and is pinned by a test in
`tests/test_audit_regressions.py` (43 tests; suite 218 → 261, all passing).

### 9.1 Actions that failed outright
| # | What the user saw | Cause | Fix |
|---|---|---|---|
| 1 | **Integrity check failed** whenever the document held a citation control SANAD had no record of — the exact case rule R3 exists to report. | The finding was saved with a link to a citation row that, by definition, does not exist; the database refused it. | Orphan-control findings are stored without the link; the control id travels in the suggestion and is returned as `citation_id` as before. |
| 2 | **"Update reference list" failed** after deleting, in Word, a citation that had an integrity finding. | The stale citation row could not be deleted while findings pointed at it. | Its findings are removed with it. |
| 3 | **Deleting a style profile failed** if any document used it. | Same class of link. | Documents using it fall back to the default style. |
| 4 | Integrity check failed on a document with no citations yet (e.g. a legacy list check). | No document row to attach findings to. | The row is created on first scan. |
| 5 | Import failed on one odd row — a year of "n.d.", a missing title/type, a nameless author. | Values were written to the database unchecked. | One cleaning step for every import path (`importer.clean_fields` / `clean_authors`); a title-less reference is refused with a clear message. |
| 6 | An old `.xls` / renamed / damaged file gave "500 Internal Server Error". | Parser exception not handled. | Clear 400: "save it again as .xlsx". |
| 7 | A junk style-profile value was accepted, then broke every citation in any document it was applied to. | Only one field was validated. | Profile values are validated when saved. |
| 8 | Semantic check could fail once its cache filled. | Cache evicted entries the same call still needed. | Each call is answered from its own results. |
| 9 | A junk `Authorization` header produced a server error instead of "unauthorized". | Text comparison rejects non-ASCII. | Compared as bytes. |

### 9.2 References lost or wrongly merged (the costliest class)
| # | Defect | Fix |
|---|---|---|
| 10 | **Two different Urdu works were treated as duplicates.** Title normalisation kept only a–z/0–9, so an Urdu title collapsed to its digits ("2020") and "Remove duplicates" would delete one of them. | Normalisation keeps letters and digits of every script. |
| 11 | **Different works sharing a generic title were auto-removed.** "Introduction", "Editorial", "Book review" in the same year were merged on title + year alone. | A group with different lead authors, volumes or first pages is no longer auto-merged; it is listed under Library health → Possible duplicates for a human decision. |
| 12 | **Re-importing a sparse row wiped a complete record.** A spreadsheet row with only title + DOI overwrote the stored authors, abstract, journal and year with blanks. | Blank incoming values keep what is on file; supplied values still win. |
| 13 | **An unresolvable DOI could never be cleaned up.** Crossref's "no such DOI" (404) was read as "no connection", so the entry was skipped forever. | 404 → removed (as documented); any other error → left alone. |
| 14 | **The demo check added three made-up sources to the user's real library**, and could cite the user's own references. | The sample run now removes exactly what it added and its sample document; the user's own copies are never touched. New `DELETE /v1/documents/{id}`; import returns the `ids` it created. |
| 15 | A citation to sources not in the library was created with empty text (an invisible citation in the document). | Refused with a clear message. |
| 16 | The integrity check reported problems "in" citations already deleted from the document. | Only citations actually present are checked. |

### 9.3 Imports that silently dropped or mangled rows
RIS: a byte-order mark hid the first record; `A1` authors and `JO`/`JF`/`J2`/`JA`/`BT`
titles were ignored; a DOI given only as a doi.org link was missed. BibTeX:
`@string`/`@preamble` were imported as references; "and others" became an author
called "others"; `12--34` pages kept the double dash. Typed lists: only `1.`
numbering was recognised (`1)`, `[1]`, `(1)` and un-numbered lists imported
nothing). CSV: Excel's "CSV UTF-8" (byte-order mark) and `;`- or tab-separated
files imported nothing; an author cell typed `Smith, J., Jones, K., & Lee, M.`
became one author; Excel whole numbers arrived as `12.0`. Handbook reader:
`25 mm` was read as `5 mm`. Crossref: organisation authors were dropped. Text
files saved as Windows-1252 or UTF-16 were read as UTF-8 (garbled names).

### 9.4 Style and bilingual handling
- **The builder's "use 'and' instead of '&' in text" checkbox did nothing** (it
  always arrived with "&" kept for the list, and a disagreement changed nothing).
  Each setting now applies to the names its own layout prints.
- **Every citation in Urdu text was flagged as off-topic** by the default
  (word-overlap) semantic check: it saw no words in non-Latin text. It now reads
  words of every script, and gives **no opinion** where it cannot judge (an Urdu
  sentence citing an English source) instead of a false alarm.
- R6 duplicate-title detection now works for non-Latin titles.

### 9.5 Desktop app and Word add-in
- **Text-integrity gap in the add-in:** inserting a citation or the list while
  text was highlighted wrapped *that text* in the control and replaced it. The
  control is now always created on an empty range at the end of the selection.
  Guarded by a static test. *(Not yet exercised in live Word — see 9.6.)*
- Add-in: a failed insert is reported instead of failing silently; the profile's
  line spacing is applied to the list; a list left over after every citation is
  removed is emptied — but never when the document still has citations the open
  library does not know (wrong library); that case is explained instead.
- App: errors show the Core's explanation, not "400 Bad Request"; deleting the
  last row of the last page no longer shows an empty table; a second launch
  focuses the existing window instead of riding on the first one's Core; on
  Windows the Core's whole process tree is stopped on exit and before
  "Regenerate token" restarts (a surviving Core kept the old token).

- **Start-up (found when the installer was built):** the installed Core takes
  about 50 seconds to answer on an ordinary laptop (measured three times, idle),
  but the app waited only 25 — with no window at all meanwhile — and then opened
  on "Core not reachable", with Home's numbers stuck at "—". The window now
  opens at once, says the engine is starting, checks every second, and fills in
  the screen the moment the engine answers. Checked in a real browser page with
  the engine off, then started. The 50 seconds itself was the one-file Core
  unpacking on every launch.
- **Start-up delay removed (follow-up to the item above):** the Core is now
  packaged as a folder (PyInstaller "onedir") instead of one self-unpacking
  file, so nothing is unpacked at launch. Measured on the same laptop, idle,
  three launches in a row of the packaged Core, from process start to
  `/v1/health` answering: **1.25 s, 1.07 s, 1.07 s** (before: 48.8 s, 49.9 s,
  50.0 s). Stopping it the way the app does leaves nothing listening on the
  port; the Core is now a single process rather than a launcher plus a child.
  The packaged Core was also exercised end to end (import from BibTeX, Excel
  and Word, a rendered citation and reference list, the style list — 8 checks,
  all passing). The Windows installer went from 215.9 MB to 194.9 MB; the
  installed Core is a folder of about 13,400 files (mostly citation styles), so
  installing takes a little longer than before. The first launch after a
  restart of the computer was not timed and may take a few seconds longer.
  CI now starts the frozen Core on Linux, Windows and macOS and waits for it to
  answer, instead of only checking that the file exists.

### 9.6 Not changed — owner decisions and residual risk
1. **Undo after a list rebuild.** If a citation is deleted in Word, the list is
   rebuilt, and the deletion is then undone, the restored control has no record
   and is reported by R3. This is the documented v0.2.12 behaviour (stale rows are
   pruned); making it non-destructive is a design choice, not a bug fix.
2. **"et al." threshold** is applied to both the in-text and reference-list
   layouts (documented scope). With APA it has no visible effect on the list.
3. **A "Save As" copy of a document** shares the original's document id, so the
   two files share citation records.
4. **Not verified here:** the Electron window and live Word were not opened in
   this pass. The JavaScript is syntax-checked and the app's sample-check flow was
   replayed against the Core end to end, but the add-in changes (selection
   handling, line spacing) need one manual pass in Word before release.
5. **Earlier demo runs** may have left three sample sources ("The Art of Memory",
   "Tides and the lunar cycle", "Consumer credit and interest rates") in an
   existing library; they are not removed automatically.
6. ~~**Slow engine start (~50 s).**~~ **Fixed** — moved to 9.5 ("Start-up delay
   removed"): the Core is now packaged as a folder and answers in about one
   second. Residual: the macOS and Linux desktop installers are not built by
   CI or by the release workflow (only the frozen Core is), so the folder
   layout inside a `.dmg` / `AppImage` has not been run.
