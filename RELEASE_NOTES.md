# Release notes

## v0.2.10 — the seal is the icon now, and you can actually see it

- **The ornate SANAD seal is now the app icon** on your Desktop and Taskbar, and
  the identity mark inside the app (header and About) — the brand you know,
  everywhere. The seal's fine gold linework was invisible on light backgrounds
  and at small sizes, so it is now set into a solid dark medallion with a bold
  gold rim: it stays crisp and clearly visible on any background, right down to
  the small taskbar size.
- If your Desktop/Taskbar still shows the old icon straight after updating, that
  is Windows caching the previous icon — sign out and back in (or run
  `ie4uinit.exe -show`) and the seal appears.

## v0.2.9 — a visible app icon, author search that works, and an easier-to-find bibliography

- **The app icon is solid and legible again.** On the desktop and taskbar the
  icon had been showing the faint, ornate seal (thin gold lines on a mostly
  transparent background), which looked washed-out and colourless. The icon is
  now the intended compact mark — the bracketed jade check on a dark tile —
  which reads clearly at every size, including the small taskbar size. (The
  ornate seal stays where it belongs: the installer splash and the About screen.)
- **Searching by author name now works.** Typing an author's surname — with or
  without "et al." and a year, e.g. "Khan et al. 2025" or just "Ortega" — now
  finds the reference. Previously the whole query was matched as one exact piece
  of text, so anything but an exact title fragment found nothing. Search now
  matches each word on its own across the title, journal, author names and year.
- **The bibliography is easier to find.** The tab that builds your reference
  list is now labelled **Bibliography** (it was "Reference list"), and inserting
  a citation now reminds you it's there.

## v0.2.8 — the Word add-in connects to the Core again

- **Fixed: the Word add-in said "Core not running" (and then froze after you
  pasted the token) even though the Core was up.** The task pane is a web page
  served from GitHub Pages, so the browser inside Word labels its requests with
  that web origin. The Core only recognised requests coming from `localhost` /
  `127.0.0.1`, so the browser threw away even the Core's health reply — the
  add-in never saw it and assumed the Core was down. The Core now recognises the
  add-in's own address as a trusted caller, so the connection succeeds. Nothing
  about the privacy model changes: the Core still listens only on your own
  machine, still requires your session token on every request, and still refuses
  every other web page.
- **Fixed: the add-in appearing to hang right after connecting.** Modern
  browsers add an extra permission check ("Private Network Access") before a web
  page may talk to a service on your own machine; the Core now answers that check
  so the request completes instead of stalling.
- Advanced: the trusted add-in address can be overridden (e.g. for a fork hosted
  elsewhere) with the `SANAD_ADDIN_ORIGINS` environment variable.

## v0.2.7 — connect-to-Word is unmissable now, and import tells you about duplicates

- **"Connect to Microsoft Word" now on the Home screen**, not only in Settings —
  the token, a Copy button, and a link to the how-to are visible the moment you
  open the app, so there's no chance of not finding it.
- **Importing now tells you if it found duplicates.** Previously, duplicates
  and malformed entries only surfaced if you happened to open Library health
  yourself — a large messy import could silently sit there unreviewed. Now,
  right after any import, if the library has exact duplicates, possible
  duplicates, or malformed entries, a notice offers to take you straight to
  Library health to review them.

## v0.2.6 — build your library from a plain list of titles

- **"Build from titles"** (Library screen) — paste your reading list, numbered
  or one per line, and each title is searched on Crossref. **Every result is a
  candidate for you to review, never an automatic pick** — a title search can
  surface a similarly-named but different paper, so nothing is added to your
  library until you explicitly choose the right match (or skip it) for each
  title. The top-ranked candidate is pre-selected as a convenience, since your
  own already-verified reading list usually resolves cleanly — but you still
  confirm before anything is added.

## v0.2.5 — Library Health, boot-stats fix, and closing real gaps found by testing

A pass driven by a real, evidence-based audit of the actually-installed app (not
just re-running automated tests) — every item below traces to a concrete,
reproduced problem, not a guess.

### New

- **Library Health** — a new screen (sidebar → Quality → Library health) that
  surfaces the library's own data-quality issues directly in the app: missing
  DOIs, malformed import-artifact entries, exact duplicates, and **possible
  near-duplicates** (titles similar enough to likely be the same work — e.g. a
  spelling variant like "Modeling"/"modelling", or the same paper filed under
  two years — that exact matching alone misses). Nothing is ever removed
  automatically; every entry has its own Delete button. Validated against a
  real 446-reference library: found all known malformed entries and 40 genuine
  near-duplicate groups with no false positives spot-checked.

### Fixed

- **Home screen showed "—" for Sources/Style profiles until you visited those
  tabs.** The dashboard now populates on launch, before you click anything.
- **Word add-in "can't load the add-in" network error** — traced to
  `manifest.xml` and `manifest.prod.xml` being easy to confuse (both plausible
  names, one needs a local dev server). Restructured so the plainly-named
  `manifest.xml` always points at the real, hosted (GitHub Pages) task pane —
  no server needed. The dev-only manifest is now clearly named
  `manifest.dev.xml` and visually labeled "(dev)" in Word's Add-ins list.
- **Import now rejects malformed bare-DOI/number "references"** at the door —
  a record whose title is just a stray DOI fragment or number with no author
  (the root cause of junk entries reaching the library in the first place) is
  silently skipped rather than imported, on every import path (RIS, BibTeX,
  typed list, CSV/Excel/Word).

## v0.2.4 — connect Word in one step (and it stays connected)

**Local by design — your library and your writing never leave your computer.**
The Word add-in talks only to the engine on your own machine (`127.0.0.1`), so
your document and references are never sent online. Connecting it used to be a
developer chore; now it's one step, once.

- **Stable session token.** The token no longer changes on every restart — it's
  saved locally and reused. So the add-in, which you paste it into once, keeps
  working after a restart instead of needing a fresh paste every time.
- **"Connect to Microsoft Word" panel** in Settings — shows your token, a **Copy**
  button, clear paste-into-Word steps, and a **Regenerate** button to rotate it.
  The panel explains *why*: this token is what keeps everything offline.
- **The add-in remembers the token** across all your documents (not just the one),
  so it's genuinely a one-time paste.
- **In-app help: "Using the Word add-in"** — load it, connect once, and use
  Insert / Reference list / Integrity.

## v0.2.3 — sort your library + delete a single reference

Manual duplicate control, because the automatic detector only catches exact and
DOI matches — not spelling/case variants (e.g. "Modeling" vs "modelling",
"Characterisation" vs "Characterization") or citation text pasted into a title.

- **Sort the library** — click the **Title** column header to sort A–Z (click
  again for Z–A), or **Year**. Sorting by title puts near-identical entries right
  next to each other, so you can spot duplicates by eye.
- **Delete a single reference** — select a reference and click **Delete this
  reference** (with a confirm). Any citation pointing at it is unlinked; the
  count updates immediately.

Together these give you a reliable, manual way to clean the library that doesn't
depend on the automatic detector being perfect. (The automatic *Remove
duplicates* button still handles exact/DOI duplicates as before.)

## v0.2.2 — thesis formatting: numbering fix, binding margin, captions

All verified by rendering the formatted `.docx` to PDF (LibreOffice renders the
same OOXML Word does), not just by inspecting the file.

- **Heading numbering now actually works.** On a document created fresh in Word
  (no lists), numbering was silently skipped because the file had no "numbering
  part"; and where it did apply, a heading could appear to drift onto the end of
  the previous line. Fixed: the formatter now creates a numbering part when
  absent and uses Word's own canonical `Heading 1/2/3` multilevel scheme
  (`1` / `1.1` / `1.1.1`), each heading on its own line.
- **Binding (gutter) margin.** Set a larger margin on the binding edge (default
  left) for thesis binding — e.g. 1″ all round with 1.5″ on the left — while the
  other sides keep the page margin.
- **Caption style.** Set the font, size, and italic/regular of Word's Caption
  style (for figures and tables). Placement — below figures/graphs, above tables
  — is chosen when you insert the caption in Word; this styles how it looks.
- Reminder: heading numbering requires your headings to use Word's **Heading 1 /
  2 / 3** styles; if your document already has a Multilevel List applied, clear it
  (Home → Multilevel List → None) so it doesn't show through.

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
  only to the local Core on `127.0.0.1`). Sideload `connectors/word/manifest.xml`.
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
