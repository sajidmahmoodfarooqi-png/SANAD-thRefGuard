# Release notes

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
