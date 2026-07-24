-- SANAD the RefGuard — core schema.
-- Single source of truth; mirrors MVP_SPEC.md §2 exactly. Any change here
-- must be mirrored back into that document.

PRAGMA foreign_keys = ON;

-- One row per distinct source in the user's library.
CREATE TABLE IF NOT EXISTS reference (
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
  content_sig     TEXT,                    -- hash of normalized full content; import-time dedup key
                                           -- for records with no DOI (exact, never fuzzy -- see
                                           -- MVP_SPEC.md R6 for the separate human-reviewed
                                           -- near-duplicate check)
  created_at      TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS author (
  id      TEXT PRIMARY KEY,
  family  TEXT, given TEXT, literal TEXT   -- literal for corporate authors, e.g. "Global Standards Consortium"
);

CREATE TABLE IF NOT EXISTS reference_author (
  reference_id TEXT REFERENCES reference(id),
  author_id    TEXT REFERENCES author(id),
  position     INTEGER,                    -- author order
  role         TEXT DEFAULT 'author',       -- author | editor | translator
  PRIMARY KEY (reference_id, author_id, role)
);

CREATE TABLE IF NOT EXISTS document (
  id            TEXT PRIMARY KEY,
  file_path     TEXT,
  direction     TEXT DEFAULT 'ltr',         -- ltr | rtl
  style_profile_id TEXT REFERENCES style_profile(id),
  last_synced_at TEXT
);

-- One row per sanad-cite content control instance in a document.
CREATE TABLE IF NOT EXISTS citation (
  id            TEXT PRIMARY KEY,           -- == the content control's stable UUID
  document_id   TEXT REFERENCES document(id),
  reference_ids TEXT NOT NULL,              -- JSON array; >1 for a grouped citation e.g. (A, 2003; B, 2006)
  rendered_text TEXT,                       -- last known-good rendered text (degradation fallback)
  raw_original_text TEXT,                   -- what the user had typed before conversion, if any
  created_at    TEXT, updated_at TEXT
);

CREATE TABLE IF NOT EXISTS style_profile (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,              -- "Metropolitan University Thesis Format 2026"
  university    TEXT,
  based_on_csl  TEXT NOT NULL,              -- e.g. "apa" (a real CSL style id)
  csl_overrides TEXT,                       -- JSON: et_al thresholds, ampersand rules, date format...
  paragraph_style TEXT,                     -- JSON: hanging indent, spacing, font (Word ParagraphFormat)
  document_structure TEXT,                  -- JSON, opt-in: margins, heading numbering, TOC style
  source_handbook_file TEXT,                -- filename, if parsed from a handbook
  confirmed_by_user INTEGER DEFAULT 0,       -- bool: nothing applies until this is 1
  shared        INTEGER DEFAULT 0,           -- bool: published to the community library
  created_at    TEXT, updated_at TEXT
);

-- Every integrity finding, Tier A or B, for review in the Integrity Panel.
CREATE TABLE IF NOT EXISTS integrity_flag (
  id            TEXT PRIMARY KEY,
  document_id   TEXT REFERENCES document(id),  -- scan scope; reference-level flags
                                               -- (R6/R7) belong to a document but no
                                               -- single citation, so citation_id may be NULL
  citation_id   TEXT REFERENCES citation(id),
  rule_id       TEXT NOT NULL,              -- see MVP_SPEC.md §4, e.g. "R1_YEAR_MISMATCH"
  tier          TEXT NOT NULL,              -- 'A' | 'B'
  severity      TEXT NOT NULL,              -- info | warning | error
  message       TEXT NOT NULL,
  suggestion    TEXT,                       -- JSON: proposed fix / alternative reference_id(s)
  status        TEXT DEFAULT 'open',        -- open | confirmed | dismissed
  created_at    TEXT
);

-- My-Library matcher (existing_papers_index.csv equivalent).
CREATE TABLE IF NOT EXISTS local_pdf (
  id                TEXT PRIMARY KEY,
  file_path         TEXT NOT NULL,
  extracted_doi     TEXT,
  extracted_title   TEXT,
  matched_reference_id TEXT REFERENCES reference(id),
  match_method      TEXT,                   -- doi | title | none
  match_confidence  REAL
);

CREATE INDEX IF NOT EXISTS idx_reference_doi ON reference(doi);
CREATE INDEX IF NOT EXISTS idx_reference_title ON reference(title);
CREATE INDEX IF NOT EXISTS idx_reference_content_sig ON reference(content_sig);
CREATE INDEX IF NOT EXISTS idx_citation_document ON citation(document_id);
CREATE INDEX IF NOT EXISTS idx_integrity_flag_citation ON integrity_flag(citation_id);
CREATE INDEX IF NOT EXISTS idx_integrity_flag_document ON integrity_flag(document_id);
