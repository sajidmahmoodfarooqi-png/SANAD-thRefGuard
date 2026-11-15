"""Import a well-formatted reference LIST from CSV, Excel (.xlsx) or Word (.docx).

The need this serves: PDF ingestion is optional. Feed a tidy table of papers
(title / authors / year / journal / DOI / ...) as CSV or Excel, or a Word
reference list, and SANAD turns it into exactly the same library the RIS/BibTeX
path produces -- after which citation formatting and the integrity checks work
identically. No new heavy dependency: CSV and DOCX use the standard library,
Excel uses openpyxl.
"""
from __future__ import annotations

import csv
import io
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile

from . import importer

# --------------------------------------------------------------------------- #
# column-name aliases -> canonical reference field
# --------------------------------------------------------------------------- #
_COLUMN_ALIASES = {
    "title": "title", "ti": "title", "article title": "title", "paper title": "title",
    "author": "authors", "authors": "authors", "au": "authors", "creators": "authors",
    "author(s)": "authors", "author names": "authors",
    "year": "year", "date": "year", "py": "year", "publication year": "year", "pub year": "year",
    "journal": "container_title", "container": "container_title", "container title": "container_title",
    "publication": "container_title", "source": "container_title", "venue": "container_title",
    "journal title": "container_title", "booktitle": "container_title", "book title": "container_title",
    "doi": "doi",
    "type": "item_type", "item type": "item_type", "reference type": "item_type", "kind": "item_type",
    "volume": "volume", "vol": "volume", "vl": "volume",
    "issue": "issue", "number": "issue", "no": "issue", "no.": "issue",
    "pages": "pages", "page": "pages", "pp": "pages", "page range": "pages", "page numbers": "pages",
    "publisher": "publisher", "pb": "publisher",
    "url": "url", "link": "url",
    "abstract": "abstract", "ab": "abstract",
    "isbn": "isbn",
}

_TYPE_ALIASES = {
    "journal": "article-journal", "journal article": "article-journal", "article": "article-journal",
    "book": "book", "book section": "chapter", "chapter": "chapter", "book chapter": "chapter",
    "conference": "paper-conference", "conference paper": "paper-conference",
    "proceedings": "paper-conference",
    "report": "report", "technical report": "report", "thesis": "thesis", "dissertation": "thesis",
    "web": "webpage", "webpage": "webpage", "website": "webpage", "online": "webpage",
}

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
# one "Surname, I. N." pair inside a reference-list-style author run
_APA_PAIR = re.compile(r"([^\W\d_][^,;]*?),\s*((?:[^\W\d_]\.\s*-?\s*){1,5})(?=,|$)")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _canon_type(v: str):
    v = (v or "").strip().lower()
    if not v:
        return None
    return _TYPE_ALIASES.get(v, "article-journal")


def _split_authors(cell: str) -> list[dict]:
    """Split an author cell into individual names. Multiple authors should be
    separated by ';' (or 'and' / '&'); a lone 'Family, Given' is left as one
    author rather than being wrongly split on its comma."""
    cell = (cell or "").strip()
    # a trailing "et al." is not a person (and must not end up inside a surname)
    cell = re.sub(r"[,;]?\s*\bet\s+al\.?\s*$", "", cell, flags=re.IGNORECASE).strip()
    if not cell:
        return []
    # ';' is the unambiguous separator; otherwise split on the word "and" / "&"
    if ";" in cell:
        parts = cell.split(";")
    else:
        parts = re.split(r"\s+(?:and|&)\s+", cell, flags=re.IGNORECASE)
    authors: list[dict] = []
    for part in parts:
        part = part.strip().strip(",").strip()
        if not part or part.lower() in ("et al", "et al.", "others"):
            continue
        # An author cell typed the way a reference list prints it --
        # "Smith, J., Jones, K., & Lee, M." -- holds several "Surname, Initials"
        # pairs in one comma-separated run. Read as a single 'Family, Given' it
        # became one author called Smith whose given name was "J., Jones, K.,".
        pairs = _APA_PAIR.findall(part)
        if len(pairs) >= 2:
            authors.extend({"family": fam.strip(), "given": " ".join(ini.split())}
                           for fam, ini in pairs)
            continue
        # "John Smith, Jane Doe, Ali Khan": three or more comma-separated full
        # names (each of 2+ words). Two segments stay one author -- that shape is
        # indistinguishable from a single "Family names, Given names".
        segments = [seg.strip() for seg in part.split(",") if seg.strip()]
        if len(segments) >= 3 and all(len(seg.split()) >= 2 for seg in segments):
            authors.extend(importer.parse_person_name(seg) for seg in segments)
            continue
        authors.append(importer.parse_person_name(part))
    return [a for a in authors if a]


def _row_to_fields(row: dict) -> tuple[dict, list[dict]]:
    """One header->value row (headers already lower-cased) -> (fields, authors)."""
    fields: dict = {}
    authors_cell = ""
    for header, val in row.items():
        canon = _COLUMN_ALIASES.get(header)
        if not canon or val in (None, ""):
            continue
        if isinstance(val, float) and val.is_integer():
            val = int(val)      # Excel hands whole numbers back as 12.0 -> "12", not "12.0"
        val = str(val).strip()
        if not val:
            continue
        if canon == "authors":
            authors_cell = val
        elif canon == "year":
            m = _YEAR_RE.search(val)
            if m:
                fields["year"] = int(m.group(1))
        elif canon == "item_type":
            t = _canon_type(val)
            if t:
                fields["item_type"] = t
        else:
            fields[canon] = val
    fields.setdefault("item_type", "article-journal")
    fields["resolution_src"] = "list-import"
    fields["confidence"] = 0.85  # structured but user-supplied, not resolver-verified
    return fields, _split_authors(authors_cell)


# --------------------------------------------------------------------------- #
# parsers
# --------------------------------------------------------------------------- #

def _csv_delimiter(header_line: str) -> str:
    """The column separator this file actually uses. Excel writes ';' between
    columns wherever ',' is the decimal mark (most of Europe), and a table
    copied out of a spreadsheet is tab-separated; reading either as
    comma-separated finds no "title" column and imports nothing. Whichever of
    , ; tab splits the header row into the most columns wins (',' on a tie)."""
    best, best_count = ",", header_line.count(",")
    for cand in (";", "\t"):
        if header_line.count(cand) > best_count:
            best, best_count = cand, header_line.count(cand)
    return best


def parse_csv(text: str) -> list[tuple[dict, list[dict]]]:
    # Excel's "CSV UTF-8" starts with a byte-order mark, which would otherwise
    # glue itself to the first header ("﻿title") so it is never recognised.
    text = (text or "").lstrip("﻿")
    header_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    reader = csv.DictReader(io.StringIO(text), delimiter=_csv_delimiter(header_line))
    out = []
    for raw in reader:
        row = {(k or "").strip().lower(): v for k, v in raw.items() if k}
        fields, authors = _row_to_fields(row)
        if fields.get("title"):
            out.append((fields, authors))
    return out


def parse_xlsx(data: bytes) -> list[tuple[dict, list[dict]]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        ws = wb.active
        headers = None
        out = []
        for r in ws.iter_rows(values_only=True):
            if headers is None:
                headers = [str(c).strip().lower() if c is not None else "" for c in r]
                continue
            row = {headers[i]: v for i, v in enumerate(r)
                   if i < len(headers) and headers[i]}
            fields, authors = _row_to_fields(row)
            if fields.get("title"):
                out.append((fields, authors))
        return out
    finally:
        wb.close()


def parse_docx(data: bytes) -> list[tuple[dict, list[dict]]]:
    """A Word reference list: each non-empty paragraph is treated as one typed
    reference (author + year recovered heuristically, like a pasted list)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{_W}p"):
        line = "".join(t.text for t in p.iter(f"{_W}t") if t.text).strip()
        if not line or re.fullmatch(r"(references|bibliography|works cited)\.?\s*", line, re.I):
            continue
        line = re.sub(r"^\s*\d+[.)]\s*", "", line)  # drop list numbering
        fields, authors = importer.parse_typed_reference(line)
        if fields.get("title"):
            out.append((fields, authors))
    return out


# --------------------------------------------------------------------------- #
# import (insert into the library)
# --------------------------------------------------------------------------- #

def _import_rows(conn: sqlite3.Connection, rows: list[tuple[dict, list[dict]]]) -> list[str]:
    # None -> insert_reference rejected a malformed bare-DOI/number "reference"
    ids = [rid for fields, authors in rows
           if (rid := importer.insert_reference(conn, fields, authors)) is not None]
    conn.commit()
    return ids


def import_csv_text(conn: sqlite3.Connection, text: str) -> list[str]:
    return _import_rows(conn, parse_csv(text))


def import_xlsx_bytes(conn: sqlite3.Connection, data: bytes) -> list[str]:
    return _import_rows(conn, parse_xlsx(data))


def import_docx_bytes(conn: sqlite3.Connection, data: bytes) -> list[str]:
    return _import_rows(conn, parse_docx(data))
