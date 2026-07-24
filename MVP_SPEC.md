# SANAD the RefGuard — Phase-1 (v1.0) Technical Spec

Companion to `CONCEPT.md`. This document turns the vision into a buildable first sprint: data
model, the citation-marker design, the add-in ↔ core protocol, Tier-A rules as testable checks,
the Style Profile file format, and which existing script becomes which core module.

---

## 1. Design decision: how a citation is marked in the document

This is the single most consequential engineering choice, and it is grounded directly in
failures observed this project:

- **Mendeley Cite**: citations are live fields bound to a *cloud-synced* library. When sync
  stalled, the panel silently showed 3 of 346 references — and every citation already inserted
  kept working only because Word had already resolved it once; new insertion was simply dead.
- **EndNote**: leaves `_ENREF_` hyperlink citations whose target bookmarks do not travel with
  the document. Copy the file elsewhere (or hand it off, as happened here) and the citation is a
  dead link forwarding to nothing — silently, with no error.

Both failure modes share a root cause: **the visible citation text and its "live" backing state
can separate, and when they do, the citation becomes unreadable or non-functional with no
warning.**

**SANAD's rule: a citation must always be correct, readable plain text on its own, with the
live link as pure enhancement.**

**Mechanism — Word Content Controls, not field codes or hyperlink-bookmark pairs:**
- Each citation (or citation group) is wrapped in a Word **Rich Text Content Control**
  (`Word.ContentControl` via Office.js).
- `control.tag` = `"sanad-cite"`; `control.id` (or a custom XML property) = a **stable UUID**
  pointing to one or more `reference_id`s in the local library.
- The control's **visible text is always the fully-rendered citation** (e.g. `(Fisher, 2001)`)
  — never a field code, never a bare hyperlink with no visible fallback text.
- If SANAD Core is not running, the add-in is uninstalled, or the document is opened on a
  machine that has never had SANAD: **the text still reads correctly**, because it always was
  real text, not a placeholder. This is the graceful-degradation property Mendeley/EndNote
  lack.
- If SANAD Core *is* running: it can find every `sanad-cite` control by tag, re-resolve its
  UUID against the current library, and refresh its rendered text — this is what powers
  "reformat whole document to a new Style Profile."
- The **bibliography** is a single content control (`tag = "sanad-bibliography"`) whose content
  SANAD regenerates in place from every `sanad-cite` UUID currently present in the document, in
  document order (for numeric styles) or alphabetical order (for author-date styles) — this
  fully replaces "Create Bibliography," working offline, with no field codes involved.
- **Text Integrity Guarantee enforcement point:** the add-in's write access is code-restricted
  to content controls tagged `sanad-cite` / `sanad-bibliography` / (opt-in)
  `sanad-style-region`. It has no code path that can write to any other range in the document.

## 2. Data model (SQLite)

```sql
-- One row per distinct source in the user's library.
CREATE TABLE reference (
  id              TEXT PRIMARY KEY,        -- uuid
  item_type       TEXT NOT NULL,           -- article-journal | book | chapter | report | webpage | ...
  title           TEXT NOT NULL,
  container_title TEXT,                    -- journal / book title (for a chapter)
  year            INTEGER,
  year_suffix     TEXT,                    -- 'a' | 'b' | ... for disambiguation
  volume          TEXT,
  issue           TEXT,
  pages           TEXT,
  publisher       TEXT,
  doi             TEXT,
  isbn            TEXT,
  url             TEXT,
  abstract        TEXT,
  language        TEXT,                    -- ISO code; drives RTL rendering
  raw_source_text TEXT,                    -- original typed/imported reference string
  resolution_src  TEXT,                    -- embedded | crossref | openalex | manual | user_added
  confidence      REAL,                    -- 0..1, resolver confidence
  csl_json        TEXT,                    -- full CSL-JSON blob (source of truth for rendering)
  content_sig     TEXT,                    -- hash of normalized full content; exact (never fuzzy)
                                           -- import-time dedup key for records with no DOI. Fuzzy
                                           -- near-duplicate detection is Tier-A rule R6 (§4), a
                                           -- separate human-reviewed check, not a silent merge.
  created_at      TEXT, updated_at TEXT
);

CREATE TABLE author (
  id      TEXT PRIMARY KEY,
  family  TEXT, given TEXT, literal TEXT   -- literal for corporate authors, e.g. "Global Standards Consortium"
);

CREATE TABLE reference_author (
  reference_id TEXT REFERENCES reference(id),
  author_id    TEXT REFERENCES author(id),
  position     INTEGER,                    -- author order
  role         TEXT DEFAULT 'author',       -- author | editor | translator
  PRIMARY KEY (reference_id, author_id, role)
);

CREATE TABLE document (
  id            TEXT PRIMARY KEY,
  file_path     TEXT,
  direction     TEXT DEFAULT 'ltr',         -- ltr | rtl
  style_profile_id TEXT REFERENCES style_profile(id),
  last_synced_at TEXT
);

-- One row per sanad-cite content control instance in a document.
CREATE TABLE citation (
  id            TEXT PRIMARY KEY,           -- == the content control's stable UUID
  document_id   TEXT REFERENCES document(id),
  reference_ids TEXT NOT NULL,              -- JSON array; >1 for a grouped citation e.g. (A, 2003; B, 2006)
  rendered_text TEXT,                       -- last known-good rendered text (degradation fallback)
  raw_original_text TEXT,                   -- what the user had typed before conversion, if any
  created_at    TEXT, updated_at TEXT
);

CREATE TABLE style_profile (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,              -- "Metropolitan University Thesis Format 2026"
  university    TEXT,
  based_on_csl  TEXT NOT NULL,              -- e.g. "apa-7th" (a real CSL style id)
  csl_overrides TEXT,                       -- JSON: et_al thresholds, ampersand rules, date format...
  paragraph_style TEXT,                     -- JSON: hanging indent, spacing, font (Word ParagraphFormat)
  document_structure TEXT,                  -- JSON, opt-in: margins, heading numbering, TOC style
  source_handbook_file TEXT,                -- filename, if parsed from a handbook
  confirmed_by_user INTEGER DEFAULT 0,       -- bool: nothing applies until this is 1
  shared        INTEGER DEFAULT 0,           -- bool: published to the community library
  created_at    TEXT, updated_at TEXT
);

-- Every integrity finding, Tier A or B, for review in the Integrity Panel.
CREATE TABLE integrity_flag (
  id            TEXT PRIMARY KEY,
  document_id   TEXT REFERENCES document(id),  -- scan scope; reference-level flags (R6/R7)
                                               -- belong to a document but no single citation
  citation_id   TEXT REFERENCES citation(id),
  rule_id       TEXT NOT NULL,              -- see §4, e.g. "R1_YEAR_MISMATCH"
  tier          TEXT NOT NULL,              -- 'A' | 'B'
  severity      TEXT NOT NULL,              -- info | warning | error
  message       TEXT NOT NULL,
  suggestion    TEXT,                       -- JSON: proposed fix / alternative reference_id(s)
  status        TEXT DEFAULT 'open',        -- open | confirmed | dismissed
  created_at    TEXT
);

-- My-Library matcher (existing_papers_index.csv equivalent).
CREATE TABLE local_pdf (
  id                TEXT PRIMARY KEY,
  file_path         TEXT NOT NULL,
  extracted_doi     TEXT,
  extracted_title   TEXT,
  matched_reference_id TEXT REFERENCES reference(id),
  match_method      TEXT,                   -- doi | title | none
  match_confidence  REAL
);
```

**Why CSL-JSON as the reference's source of truth:** it is the citeproc-js/citeproc-py native
input format, so the resolver's output plugs directly into rendering with zero translation
layer, and it is itself an open, portable interchange format (import/export for free).

## 3. Add-in ↔ Core protocol

SANAD Core runs as a local HTTP+WebSocket service on `127.0.0.1:<port>` (configurable; default
`23890`), started on login, one instance per machine. The Word add-in (and any future
processor add-in) is a thin client that never touches the SQLite database directly.

| Method & path | Purpose |
|---|---|
| `GET  /v1/library/search?q=` | Search the local library (title/author/year) for the insert-citation UI |
| `POST /v1/citations` | Create a citation: `{reference_ids:[...], document_id}` → returns `{citation_id, rendered_text}` for the add-in to place in a new content control |
| `PUT  /v1/citations/{id}` | Re-resolve / re-render an existing citation (e.g. after a Style Profile change) |
| `GET  /v1/documents/{id}/bibliography` | Returns the fully rendered bibliography text for the `sanad-bibliography` control, built from every citation currently in the document |
| `POST /v1/documents/{id}/scan` | Run the Integrity Panel: Tier-A rules + Tier-B semantic check over every citation in the document → list of `integrity_flag` rows |
| `POST /v1/style-profiles` | Create/import a Style Profile (manual form submission, or a confirmed handbook-parse result) |
| `POST /v1/style-profiles/{id}/apply` | Set the active profile for a document; triggers a re-render of every citation + bibliography |
| `POST /v1/handbook/parse` | Upload a handbook file → candidate Style Profile deltas (never auto-applied; §4) |
| `WS   /v1/events` | Push channel: scan progress, library-changed, resolver-progress |

**Add-in responsibilities (kept deliberately thin):**
1. Detect/insert `sanad-cite` and `sanad-bibliography` content controls via Office.js.
2. Read the citing sentence's surrounding text (for Tier-B) and send it — never modify it.
3. Render the Integrity Panel from `integrity_flag` results; on user confirmation, call back to
   Core to update a citation's `reference_ids` and re-render.
4. Never write outside a `sanad-*` tagged control.

## 4. Tier-A integrity rules (precise, testable)

Each rule takes a citation + its resolved reference(s) + document context and returns zero or
more flags.

| Rule ID | Check | Trigger | Severity |
|---|---|---|---|
| `R1_YEAR_MISMATCH` | In-text year (parsed from `raw_original_text`) vs. `reference.year` | Not equal (after normalizing a/b/c suffixes) | warning |
| `R2_VENUE_TYPE_SANITY` | `reference.container_title` against a red-flag keyword list (`review`, `choice reviews`, `abstracting`, `book review`) when `item_type` suggests a monograph was intended | Match | error |
| `R3_ORPHANED_CITATION` | `sanad-cite` control's UUID has no row in `citation`, or `citation.reference_ids` resolves to nothing in `reference` | True | error |
| `R4_CITED_NOT_LISTED` | A `citation.reference_id` has no corresponding entry the bibliography renderer would include (e.g. excluded by a scoping bug) | True | error |
| `R5_LISTED_NOT_CITED` | A `reference` scoped to the document has zero `citation` rows referencing it | True | info |
| `R6_DUPLICATE_REFERENCE` | Normalized-title similarity (token-set) between two `reference` rows ≥ 0.85 with different `id`s | True | warning |
| `R7_AUTHOR_YEAR_AMBIGUITY` | Two+ `reference` rows share lead-author family name + year; in-text suffix (a/b) doesn't uniquely resolve | True | warning |

`R1`–`R7` generalize the classes of citation error seen in real theses (a wrong in-text year, a
book that resolved to a *review* venue, glued-cell duplicate references, `_ENREF_` orphans, and
cited-vs-listed mismatches).

**Tier-B (semantic)** sits on top as `R8_CONTEXT_MISALIGNMENT`: cosine similarity between an
embedding of the citing sentence and an embedding of the reference's title+abstract, flagged
below a tuned threshold, with the top-k nearest alternatives from the library attached as
`suggestion`.

## 5. Style Profile file format (`.sanadstyle.json`)

```json
{
  "id": "b6b6a1e2-...-uuid",
  "name": "Metropolitan University Thesis Format 2026",
  "university": "Metropolitan University",
  "version": "1.0",
  "based_on_csl": "apa-7th",
  "csl_overrides": {
    "et_al_min": 3,
    "et_al_use_first": 1,
    "ampersand_in_text": false,
    "ampersand_in_bibliography": true,
    "date_display": "year-only"
  },
  "paragraph_style": {
    "bibliography_hanging_indent_cm": 1.27,
    "bibliography_space_after_pt": 6,
    "font_family": "Times New Roman",
    "font_size_pt": 12,
    "line_spacing": 1.5
  },
  "document_structure": {
    "enabled": false,
    "margins_cm": { "top": 3.8, "bottom": 2.5, "left": 3.8, "right": 2.5 },
    "heading_numbering": "decimal",
    "toc_style": "default"
  },
  "provenance": {
    "source_handbook_file": null,
    "extracted_at": null,
    "confirmed_by_user": true,
    "shared": false
  }
}
```

Design notes:
- **`based_on_csl` + `csl_overrides`** handle *citation/reference-list content* (order,
  punctuation, `et al.` threshold, date format, italics) — this is CSL's actual domain.
- **`paragraph_style`** handles *physical layout of the reference list* (indent size, spacing,
  font) — this is **not** a CSL concept; it maps directly to Word `ParagraphFormat`/`Font` via
  Office.js, applied only inside the `sanad-bibliography` control.
- **`document_structure`** is opt-in and out of v1.0 scope by default (§6) — reserved for v1.x,
  and even then scoped only to structural containers (margins, heading *numbering*, TOC),
  never to heading *wording* or body prose.
- A `.sanadstyle.json` file is the unit shared in the community library (`CONCEPT.md` §4/§10).

## 6. v1.0 build order (concrete sprints)

1. **Core skeleton** — SQLite schema (§2), local HTTP server, CSL-JSON reference store.
2. **Library import** — port `resolve_bibliography.py` + `fix_authors.py` logic into the
   Metadata Resolver module; import RIS/BibTeX/CSV/XLSX into `reference`/`author`.
3. **CSL rendering** — integrate `citeproc-py` (or equivalent) against `based_on_csl` +
   `csl_overrides`; APA 7th as the first validated style.
4. **Word add-in, minimal** — insert citation (search → pick → content control), render
   bibliography control. This alone is "the reliable formatter that just works."
5. **Tier-A integrity engine** — implement `R1`–`R7` (§4); Integrity Panel UI in the add-in.
   *(engine: DONE — `sanad_core/integrity.py`, wired into `POST /scan` +
   `GET /flags` + `PUT /flags/{id}`, with scan events over `/v1/events`. The
   in-add-in Panel UI is the remaining client-side piece.)*
6. **Manual Style Profile form** — the guided UI for building a `.sanadstyle.json` by hand;
   `paragraph_style` application to the bibliography control.
   *(backend: DONE — `style_profile.build_profile()` +
   `POST /style-profiles/build`, list/get as `.sanadstyle.json`, and
   `paragraph_style_office()` folding hanging-indent/spacing/font into the
   `GET /documents/{id}/bibliography` payload as Office.js-ready points. The
   in-add-in guided form + the actual Office.js `ParagraphFormat` write are the
   remaining client-side piece.)*
7. **Tier-B semantic check** — local embedding model; `R8`; side-by-side suggestion UI,
   confirm-only.
   *(engine: DONE — `sanad_core/embedding.py` (pluggable: real sentence-transformers
   backend when installed, deterministic dependency-free lexical fallback otherwise)
   + `integrity.r8_context_misalignment`, run via `POST /scan` with per-citation
   `contexts`. The scan response reports `tier_b.ran` + `tier_b.backend` so a
   fallback result never masquerades as a true semantic one. The side-by-side
   suggestion UI is the remaining client-side piece; threshold calibration against a
   labelled misattribution set is the open tuning task.)*
8. **Hardening** — the Text Integrity Guarantee as an automated test: fuzz the document with
   edits everywhere *except* `sanad-*` controls and assert Core never touches those regions.
   *(DONE — `sanad_core/document_model.py` encodes the §1 write restriction as an
   executable boundary: prose regions carry no id/tag, and `apply_core_write` — the one
   sanctioned mutation — is structurally unable to resolve to anything but an allowed
   `sanad-*` control. `tests/test_text_integrity.py` drives real Core outputs through it
   while fuzzing prose adversarially, asserting prose is byte-identical before/after every
   sync, plus negative tests that the writer refuses unknown/mis-tagged targets.)*

## 7. Prototype script → core module map

The Core generalizes logic first worked out in a set of earlier standalone prototype scripts:

| Prototype script | Becomes |
|---|---|
| `resolve_bibliography.py` | Metadata Resolver module (Crossref/OpenAlex lookup, confidence scoring, CSL-JSON assembly) |
| `fix_authors.py` | Author-backfill step inside Library Import |
| `download_papers.py` | Full-Text Finder module (v1.x) |
| `match_existing_pdfs.py` | My-Library Matcher module (`local_pdf` table, v1.x) |
| `make_ch1_apa.py` | Prototype of both the CSL Formatter (in-text conversion table logic) *and* the citation-extraction regexes that seed the Tier-A `R1`/`R7` rules |

## 8. Out of scope for v1.0 (explicitly deferred)

- Automated handbook-document parsing (manual Style Profile form ships first; §4/§6.6).
- LibreOffice add-in (same Core, new thin client — mechanical once the protocol is stable).
- `document_structure` application (margins/TOC/heading numbering).
- Community Style Profile library hosting/discovery UI.
- Cloud sync of any kind.

---

*Next: the Word-add-in Office.js manifest + minimal insert-citation flow (§6.4), and the
citeproc-py integration test proving `.sanadstyle.json` overrides render correctly against a
real APA 7th baseline.*
