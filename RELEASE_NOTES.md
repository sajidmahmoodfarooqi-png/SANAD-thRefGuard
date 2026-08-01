# Release notes

## v0.2.1 — near-duplicate detection

Point fix on top of v0.2.0.

- **Catches "same paper, entered twice" duplicates.** Real reference lists often
  hold one full record (DOI + authors + metadata) *and* a bare re-entry of the
  same work (title + year only, no DOI). These differ enough that exact matching
  missed them. The duplicate detector now also pairs records by **normalised
  title + year**, keeping the most complete copy and repointing any citations to
  it — while still refusing to merge two records that carry **different DOIs**
  (a genuine erratum/version, left for you to review). The *Remove duplicates*
  button now appears for these.

## v0.2.0 — thesis formatting, the Word add-in, and integrity fixes

Builds on v0.1.0 with the two things that make SANAD usable end-to-end inside
Word, plus real correctness fixes. Everything still runs on your own machine —
no account, no cloud, no telemetry.

### New

- **Format your thesis to your handbook.** Read a university format manual
  locally, confirm the detected Style Profile, then reformat your `.docx` — body
  font/size/spacing, margins, and the reference-list hanging indent — under the
  **"never touches your prose" guarantee** (enforced in code: every word is
  fingerprinted before and after, and the whole pass runs with the network
  sealed off).
- **Word Styles gallery.** Style Profiles now carry heading styles — a font and
  size for **Title** and **Heading 1–3** — and an optional switch to **number
  headings automatically** in Word's standard scheme: Heading 1 → `1`,
  Heading 2 → `1.1`, Heading 3 → `1.1.1`. Numbers land on the document's real
  Word styles, so they renumber themselves; no number is ever typed into prose.
- **Word add-in (Office.js task pane).** Insert citations from your local
  library, rebuild the whole reference list, and run the integrity check — all
  **inside your document**, writing only inside its own tagged fields. The pane's
  UI is hosted on GitHub Pages; your document never leaves your machine (it talks
  only to the local Core on `127.0.0.1`). Sideload `connectors/word/manifest.prod.xml`.
- **Complete offline help guide**, packaged with the app — a printable manual
  opened from the Help screen's *Open the full guide* button, no network needed.

### Fixed

- **Duplicate detection across DOI formats.** The same work imported twice — one
  entry storing its DOI bare, the other as a `doi.org` URL (or `doi:`-prefixed,
  or a different case) — was compared verbatim and slipped past both import-time
  dedup and the duplicate detector, so the *Remove duplicates* button never
  appeared. DOIs are now canonicalised on import and in detection, so these
  collapse correctly — and a library imported before this fix is caught too.

### Install (Windows)

Run `SANAD Setup 0.2.0.exe`. The build is **unsigned**, so Windows SmartScreen
shows an "unknown publisher" notice — click **More info → Run anyway**. A
portable `win-unpacked` build is also produced if you prefer not to install.

### Known limitations

- **Unsigned** — SmartScreen/Gatekeeper warns on first run. Code signing is a
  later step.
- **macOS `.dmg` / Linux `.AppImage`** are configured but must be built on their
  own OS.
- The real semantic model (`sentence-transformers`) is optional; without it, R8
  uses a deterministic lexical proxy and says so.

---

## v0.1.0 — first packaged release

**SANAD the RefGuard** is a local-first, open-source citation companion for
Microsoft Word and LibreOffice. It stores your reference library, formats
citations against real CSL styles layered with your university's own rules, and
**checks the integrity of every citation in context** — the differentiator no
mainstream reference manager offers.

Everything runs on your own machine. No account, no cloud, no telemetry. The only
time it ever touches the internet is if you explicitly tick the optional DOI
lookup on an import.

### Highlights

- **Reference library** — import from RIS, BibTeX, or a plain typed list, **or a
  well-formatted Excel (`.xlsx`), CSV, or Word (`.docx`) list of papers** — no PDF
  ingestion required. Safe de-duplication that never silently merges two different
  works.
- **Context-integrity checking (rules R1–R8)** — flags year/venue mismatches,
  duplicate or near-identical sources, missing bibliography entries, and — the
  headline check, **R8** — a citation whose surrounding sentence is about
  something the cited source isn't. Every scan honestly reports whether the true
  semantic backend or the lexical fallback ran.
- **University Style Profiles** — capture "et al." thresholds, ampersand rules,
  hanging indent, and reference fonts on top of a real citation style, then apply,
  rename, or delete them.
- **The "never touches your prose" guarantee** — the editor connector can only
  ever write tagged citation/bibliography fields; a static guard test proves no
  prose-writing API is reachable.
- **Opt-in online metadata resolution** — off by default, per-import. When enabled,
  entries that carry a DOI are corrected against Crossref (DOI-only, so it can
  never fetch the *wrong* paper); anything without a DOI, or any failure, leaves
  your data exactly as supplied.
- **Private and secure by construction** — the local engine requires a per-launch
  bearer token on every request, restricts allowed hosts (anti-DNS-rebinding), and
  caps import size.
- **In-app help** and a full [User Guide](docs/USER_GUIDE.md).

### What's in this build

- Desktop app (Electron) with the Python engine frozen and bundled — **no Python
  installation needed** to run it.
- Windows installer (NSIS) and a portable build.
- 143 automated tests; CI across Linux/Windows/macOS × Python 3.12/3.13.

### Install (Windows)

Run `SANAD Setup 0.1.0.exe`. The build is **unsigned**, so Windows SmartScreen
will show an "unknown publisher" notice — click **More info → Run anyway**. A
portable `win-unpacked` build is also available if you prefer not to install.

### Known limitations

- **Unsigned** — SmartScreen/Gatekeeper will warn on first run. Code signing is a
  later step.
- **Word/LibreOffice add-in** is a scaffold, not yet general-release; the desktop
  app is the way to build and check your library today.
- **macOS `.dmg` and Linux `.AppImage`** are configured but must be built on their
  own OS (the CI matrix produces them).
- The real semantic model (`sentence-transformers`) is optional; without it, R8
  uses a deterministic lexical proxy and says so.

### License

GNU Affero General Public License v3.0 (AGPL-3.0).
