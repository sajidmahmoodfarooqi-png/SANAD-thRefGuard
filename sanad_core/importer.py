"""Library import: RIS, BibTeX, and hand-typed reference lists -> the
`reference`/`author`/`reference_author` tables.

Handles the structured formats (RIS/BibTeX) plus the messier case of a plain
numbered reference list with no structured fields at all -- author + year are
recovered heuristically and the record is marked low-confidence.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3

from . import csl_json, db

# --------------------------------------------------------------------------- #
# Person-name heuristics (shared across RIS/BibTeX/typed-list parsing)
# --------------------------------------------------------------------------- #

def parse_person_name(name: str) -> dict:
    """'Family, Given' (RIS/BibTeX convention) or 'Given Family' -> a
    {"family", "given"} dict, or {"literal": ...} for a likely corporate
    author. Heuristic -- BibTeX/RIS export doesn't disambiguate this either,
    it's the same limitation reference managers all live with."""
    name = name.strip().strip("{}").strip()
    if not name:
        return {}
    if "," in name:
        family, given = name.split(",", 1)
        return {"family": family.strip(), "given": given.strip()}
    parts = name.split()
    if len(parts) <= 2 or any(p.endswith(".") for p in parts):
        # "John Smith" or "R. L. Rowe" -- treat as a personal name
        if len(parts) == 1:
            return {"literal": name}
        return {"family": parts[-1], "given": " ".join(parts[:-1])}
    # 3+ bare words, no comma, no initials -- likely a corporate author
    # e.g. "Global Standards Consortium"
    return {"literal": name}


# --------------------------------------------------------------------------- #
# RIS
# --------------------------------------------------------------------------- #

RIS_TYPE_MAP = {
    "JOUR": "article-journal", "BOOK": "book", "CHAP": "chapter",
    "RPRT": "report", "THES": "thesis", "CONF": "paper-conference",
    "CPAPER": "paper-conference", "ELEC": "webpage", "WEB": "webpage",
    "GEN": "article-journal",          # safe fallback for untyped records
    "MGZN": "article-magazine", "NEWS": "article-newspaper",
}

_RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")


def parse_ris(text: str) -> list[dict]:
    """Text -> a list of raw RIS record dicts, tag -> list-of-values."""
    records: list[dict] = []
    current: dict | None = None
    last_tag: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue
        m = _RIS_LINE.match(line)
        if not m:
            # a wrapped continuation of the previous field
            if current is not None and last_tag and current.get(last_tag):
                current[last_tag][-1] += " " + line.strip()
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "TY":
            current = {"TY": [value]}
            records.append(current)
            last_tag = None
        elif tag == "ER":
            last_tag = None
        else:
            if current is None:
                continue
            current.setdefault(tag, []).append(value)
            last_tag = tag
    return records


def ris_record_to_fields(rec: dict) -> tuple[dict, list[dict]]:
    ty = (rec.get("TY") or [""])[0]
    item_type = RIS_TYPE_MAP.get(ty.upper(), "article-journal")
    title = (rec.get("TI") or rec.get("T1") or [""])[0]
    container = (rec.get("T2") or [None])[0]

    year = None
    py = (rec.get("PY") or rec.get("Y1") or [None])[0]
    if py:
        m = re.match(r"(\d{4})", py)
        if m:
            year = int(m.group(1))

    sp = (rec.get("SP") or [None])[0]
    ep = (rec.get("EP") or [None])[0]
    pages = f"{sp}-{ep}" if sp and ep else sp

    sn = rec.get("SN") or [None]

    fields = {
        "item_type": item_type,
        "title": title,
        "container_title": container,
        "year": year,
        "volume": (rec.get("VL") or [None])[0],
        "issue": (rec.get("IS") or [None])[0],
        "pages": pages,
        "publisher": (rec.get("PB") or [None])[0],
        "doi": (rec.get("DO") or [None])[0],
        "isbn": sn[0],
        "url": (rec.get("UR") or [None])[0],
        "abstract": (rec.get("AB") or [None])[0],
        "language": (rec.get("LA") or [None])[0],
        "resolution_src": "import_ris",
    }
    authors = [parse_person_name(a) for a in rec.get("AU") or []]
    authors = [a for a in authors if a]
    return fields, authors


# --------------------------------------------------------------------------- #
# BibTeX -- a small brace/quote-aware scanner (regex alone breaks on nested
# braces inside a title, e.g. "{NASA} data").
# --------------------------------------------------------------------------- #

BIBTEX_TYPE_MAP = {
    "article": "article-journal", "book": "book", "inbook": "chapter",
    "incollection": "chapter", "techreport": "report",
    "phdthesis": "thesis", "mastersthesis": "thesis",
    "inproceedings": "paper-conference", "conference": "paper-conference",
    "online": "webpage", "electronic": "webpage", "misc": "article-journal",
}

_STRIP_BRACES = re.compile(r"\{([^{}]*)\}")


def _find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces in BibTeX entry")


def _parse_bibtex_fields(body: str) -> dict:
    fields: dict[str, str] = {}
    i, n = 0, len(body)
    while i < n:
        while i < n and body[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        m = re.match(r"[A-Za-z_][\w:-]*", body[i:])
        if not m:
            break
        name = m.group(0).lower()
        i += len(name)
        while i < n and body[i] in " \t\r\n":
            i += 1
        if i < n and body[i] == "=":
            i += 1
        while i < n and body[i] in " \t\r\n":
            i += 1
        if i >= n:
            break
        if body[i] == "{":
            close = _find_matching_brace(body, i)
            value = body[i + 1:close]
            i = close + 1
        elif body[i] == '"':
            j = i + 1
            while j < n and body[j] != '"':
                j += 2 if body[j] == "\\" else 1
            value = body[i + 1:j]
            i = j + 1
        else:
            j, depth = i, 0
            while j < n and not (body[j] == "," and depth == 0):
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                j += 1
            value = body[i:j]
            i = j
        # collapse simple one-level case-protection braces, e.g. "{NASA}" -> "NASA"
        value = _STRIP_BRACES.sub(r"\1", value)
        fields[name] = re.sub(r"\s+", " ", value).strip()
    return fields


def parse_bibtex(text: str) -> list[dict]:
    """Text -> [{"key", "entry_type", "fields": {...}}, ...]."""
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{", text):
        entry_type = m.group(1).lower()
        if entry_type == "comment":
            continue
        open_pos = m.end() - 1
        try:
            close_pos = _find_matching_brace(text, open_pos)
        except ValueError:
            continue
        body = text[open_pos + 1:close_pos]
        comma_idx = body.find(",")
        if comma_idx == -1:
            continue
        key = body[:comma_idx].strip()
        fields = _parse_bibtex_fields(body[comma_idx + 1:])
        entries.append({"key": key, "entry_type": entry_type, "fields": fields})
    return entries


def bibtex_entry_to_fields(entry: dict) -> tuple[dict, list[dict]]:
    f = entry["fields"]
    item_type = BIBTEX_TYPE_MAP.get(entry["entry_type"], "article-journal")
    container = f.get("journal") or f.get("booktitle")
    year = None
    if f.get("year"):
        m = re.match(r"(\d{4})", f["year"])
        if m:
            year = int(m.group(1))

    fields = {
        "item_type": item_type,
        "title": f.get("title", ""),
        "container_title": container,
        "year": year,
        "volume": f.get("volume"),
        "issue": f.get("number"),
        "pages": f.get("pages"),
        "publisher": f.get("publisher"),
        "doi": f.get("doi"),
        "isbn": f.get("isbn"),
        "url": f.get("url"),
        "abstract": f.get("abstract"),
        "resolution_src": "import_bibtex",
    }
    authors = []
    if f.get("author"):
        for seg in f["author"].split(" and "):
            a = parse_person_name(seg)
            if a:
                authors.append(a)
    return fields, authors


# --------------------------------------------------------------------------- #
# Hand-typed reference list (no structured fields at all) -- a plain numbered
# list of APA-style reference strings, one per line.
# --------------------------------------------------------------------------- #

_APA_AUTHOR_RE = re.compile(r"([A-ZÀ-Ý][^,()]*?),\s*((?:[A-Z]\.\s*){1,5})")
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})([a-z])?\b")
_LEADNUM = re.compile(r"^\s*\d+\.\s*")


def parse_typed_reference(raw: str) -> tuple[dict, list[dict]]:
    """Best-effort parse of one hand-typed reference line. Always
    low-confidence -- a human should confirm before this is trusted for
    anything beyond a starting point."""
    raw = raw.strip()
    ym = _YEAR_RE.search(raw)
    year = year_suffix = None
    if ym:
        year = int(ym.group(1))
        year_suffix = ym.group(2)

    seg = raw[:ym.start()] if ym else raw
    authors = []
    for surname, initials in _APA_AUTHOR_RE.findall(seg):
        surname = surname.strip(" .,&")
        initials = " ".join(initials.split())
        if surname and len(surname) > 1:
            authors.append({"family": surname, "given": initials})

    title = raw
    m = re.search(r"\((?:19|20)\d{2}[a-z]?\)\.?\s*(.+?)\.\s", raw)
    if m:
        title = m.group(1).strip()

    fields = {
        "item_type": "article-journal",   # unknown -- best default guess
        "title": title,
        "container_title": None,
        "year": year,
        "year_suffix": year_suffix,
        "raw_source_text": raw,
        "resolution_src": "manual_typed",
        "confidence": 0.4 if (authors and year) else 0.2,
    }
    return fields, authors


def split_typed_list(text: str) -> list[str]:
    """A Markdown/plain numbered list ('1. Ref text...') -> raw reference
    strings, one per line."""
    out = []
    for line in text.splitlines():
        if _LEADNUM.match(line):
            out.append(_LEADNUM.sub("", line).strip())
    return out


# --------------------------------------------------------------------------- #
# Insertion (shared by every import path)
# --------------------------------------------------------------------------- #

def find_or_create_author(conn: sqlite3.Connection, author: dict) -> str | None:
    if not author:
        return None
    if author.get("literal"):
        row = conn.execute(
            "SELECT id FROM author WHERE literal = ?", (author["literal"],)
        ).fetchone()
        if row:
            return row["id"]
        aid = db.new_id()
        conn.execute("INSERT INTO author (id, literal) VALUES (?, ?)", (aid, author["literal"]))
        return aid
    family, given = author.get("family"), author.get("given")
    row = conn.execute(
        "SELECT id FROM author WHERE family = ? AND IFNULL(given,'') = IFNULL(?, '')",
        (family, given),
    ).fetchone()
    if row:
        return row["id"]
    aid = db.new_id()
    conn.execute(
        "INSERT INTO author (id, family, given) VALUES (?, ?, ?)", (aid, family, given)
    )
    return aid


def find_by_doi(conn: sqlite3.Connection, doi: str | None) -> str | None:
    if not doi:
        return None
    row = conn.execute(
        "SELECT id FROM reference WHERE doi = ? COLLATE NOCASE", (doi,)
    ).fetchone()
    return row["id"] if row else None


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


# Strip the many equivalent ways a DOI is written so the same DOI always
# compares equal: bare, "doi:"-prefixed, or a doi.org/dx.doi.org URL, any case.
# DOIs are case-insensitive by spec and contain no whitespace, so we can safely
# lower-case and remove spaces. Without this, one .ris entry storing a DOI as a
# URL and another storing it bare read as two different works and never dedupe.
_DOI_PREFIX = re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/|(?:dx\.)?doi\.org/)", re.I)


def normalize_doi(doi: object) -> str | None:
    if not doi:
        return None
    s = re.sub(r"\s+", "", str(doi).strip())     # DOIs never contain spaces
    s = _DOI_PREFIX.sub("", s).rstrip(".").lower()
    return s or None


def normalize_title(title: object) -> str:
    """A title reduced to its bare word content -- lower-cased, markup tags
    (e.g. ``<scp>MODIS</scp>``) removed, punctuation dropped, whitespace
    collapsed. Two records for the same paper that differ only in casing,
    stray commas, or publisher markup normalise to the same string, which lets
    the duplicate detector pair a full record (with a DOI + authors) against a
    bare re-entry of the same work (title + year only)."""
    t = re.sub(r"<[^>]+>", " ", str(title or "").lower())
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def content_signature(fields: dict, authors: list[dict]) -> str:
    """A hash of the record's *full* normalized content -- the import-time
    dedup key for references with no DOI.

    Deliberately EXACT, never fuzzy: two records collapse only if every
    identity-bearing field matches (title, year, year_suffix, container,
    volume, pages, and the ordered author surnames). This is what re-importing
    the same library twice hits, so it dedupes; but two genuinely different
    works -- e.g. a body that publishes two same-titled annual reports in one
    year, distinguished only by subtitle/part -- differ in year_suffix (and
    container) and so are NOT merged. Catching near-duplicates that differ only
    cosmetically (a mistaken
    a/b suffix, one entry in APA vs Springer style) is the job of Tier-A rule
    R6 (MVP_SPEC.md §4): a separate, human-reviewed integrity check, never a
    silent import-time merge."""
    author_key = "|".join(
        _norm(a.get("family") or a.get("literal") or "") for a in (authors or [])
    )
    parts = [
        _norm(fields.get("title")),
        str(fields.get("year") or ""),
        _norm(fields.get("year_suffix")),
        _norm(fields.get("container_title")),
        _norm(fields.get("volume")),
        _norm(fields.get("pages")),
        author_key,
    ]
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def find_by_content_signature(conn: sqlite3.Connection, sig: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM reference WHERE content_sig = ?", (sig,)
    ).fetchone()
    return row["id"] if row else None


def insert_reference(conn: sqlite3.Connection, fields: dict, authors: list[dict]) -> str:
    """Insert one reference + its authors. Dedupes on DOI first, then on an
    exact full-content signature for references with no DOI at all -- so
    re-importing the same library twice updates in place rather than
    duplicating, while never silently merging two genuinely distinct works."""
    # canonicalise the DOI once, up front, so it is stored, matched, and written
    # into the CSL JSON in one consistent form regardless of how the source wrote it
    fields = {**fields, "doi": normalize_doi(fields.get("doi"))}
    sig = content_signature(fields, authors)
    existing_id = find_by_doi(conn, fields.get("doi")) or \
        find_by_content_signature(conn, sig)
    ref_id = existing_id or db.new_id()
    now = db.now_iso()

    csl = csl_json.build_csl_json({**fields, "id": ref_id}, authors)

    if existing_id:
        conn.execute(
            """UPDATE reference SET item_type=?, title=?, container_title=?, year=?,
               year_suffix=?, volume=?, issue=?, pages=?, publisher=?, doi=?, isbn=?,
               url=?, abstract=?, language=?, raw_source_text=?, resolution_src=?,
               confidence=?, csl_json=?, content_sig=?, updated_at=? WHERE id=?""",
            (
                fields.get("item_type", "article-journal"), fields.get("title", ""),
                fields.get("container_title"), fields.get("year"), fields.get("year_suffix"),
                fields.get("volume"), fields.get("issue"), fields.get("pages"),
                fields.get("publisher"), fields.get("doi"), fields.get("isbn"),
                fields.get("url"), fields.get("abstract"), fields.get("language"),
                fields.get("raw_source_text"), fields.get("resolution_src"),
                fields.get("confidence"), csl_json.dumps(csl), sig, now, ref_id,
            ),
        )
        conn.execute("DELETE FROM reference_author WHERE reference_id = ?", (ref_id,))
    else:
        conn.execute(
            """INSERT INTO reference
               (id, item_type, title, container_title, year, year_suffix, volume, issue,
                pages, publisher, doi, isbn, url, abstract, language, raw_source_text,
                resolution_src, confidence, csl_json, content_sig, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_id, fields.get("item_type", "article-journal"), fields.get("title", ""),
                fields.get("container_title"), fields.get("year"), fields.get("year_suffix"),
                fields.get("volume"), fields.get("issue"), fields.get("pages"),
                fields.get("publisher"), fields.get("doi"), fields.get("isbn"),
                fields.get("url"), fields.get("abstract"), fields.get("language"),
                fields.get("raw_source_text"), fields.get("resolution_src"),
                fields.get("confidence"), csl_json.dumps(csl), sig, now, now,
            ),
        )

    for pos, author in enumerate(authors):
        author_id = find_or_create_author(conn, author)
        if author_id:
            conn.execute(
                "INSERT OR IGNORE INTO reference_author (reference_id, author_id, position, role) "
                "VALUES (?, ?, ?, 'author')",
                (ref_id, author_id, pos),
            )
    return ref_id


def import_ris_text(conn: sqlite3.Connection, text: str) -> list[str]:
    ids = []
    for rec in parse_ris(text):
        fields, authors = ris_record_to_fields(rec)
        ids.append(insert_reference(conn, fields, authors))
    conn.commit()
    return ids


def import_bibtex_text(conn: sqlite3.Connection, text: str) -> list[str]:
    ids = []
    for entry in parse_bibtex(text):
        fields, authors = bibtex_entry_to_fields(entry)
        ids.append(insert_reference(conn, fields, authors))
    conn.commit()
    return ids


def import_typed_list_text(conn: sqlite3.Connection, text: str) -> list[str]:
    ids = []
    for raw in split_typed_list(text):
        fields, authors = parse_typed_reference(raw)
        ids.append(insert_reference(conn, fields, authors))
    conn.commit()
    return ids
