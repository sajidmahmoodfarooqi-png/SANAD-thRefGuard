"""Document + citation service layer.

Everything the HTTP API (`server.py`) does, minus the HTTP -- so the real
logic is unit-testable without spinning up a server. Operates on a sqlite3
connection plus the existing formatter / style_profile modules.

Text Integrity Guarantee (CONCEPT.md §2): nothing in this module reads or
writes document *prose*. It only ever creates/renders citation records,
reference-list output, and Style-Profile associations -- there is no code
path here that could touch an author's writing.
"""
from __future__ import annotations

import json
import sqlite3

from . import db, formatter
from . import style_profile as sp


# --------------------------------------------------------------------------- #
# internal helpers
# --------------------------------------------------------------------------- #

def _profile_for_document(conn: sqlite3.Connection, document_id: str) -> dict:
    row = conn.execute(
        "SELECT style_profile_id FROM document WHERE id = ?", (document_id,)
    ).fetchone()
    if row and row["style_profile_id"]:
        prof = sp.get_profile(conn, row["style_profile_id"])
        if prof:
            return prof
    return sp.default_profile()


def _csl_items_for_refs(conn: sqlite3.Connection, reference_ids: list[str]) -> list[dict]:
    items = []
    for rid in reference_ids:
        r = conn.execute("SELECT csl_json FROM reference WHERE id = ?", (rid,)).fetchone()
        if r and r["csl_json"]:
            items.append(json.loads(r["csl_json"]))
    return items


# --------------------------------------------------------------------------- #
# documents
# --------------------------------------------------------------------------- #

def ensure_document(conn: sqlite3.Connection, document_id: str, file_path: str | None = None) -> str:
    row = conn.execute("SELECT id FROM document WHERE id = ?", (document_id,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO document (id, file_path) VALUES (?, ?)", (document_id, file_path)
        )
        conn.commit()
    return document_id


def set_document_profile(conn: sqlite3.Connection, document_id: str, profile_id: str) -> int:
    """Point a document at a Style Profile and re-render every citation in it.
    Returns the number of citations re-rendered."""
    ensure_document(conn, document_id)
    conn.execute(
        "UPDATE document SET style_profile_id = ? WHERE id = ?", (profile_id, document_id)
    )
    conn.commit()
    rows = conn.execute(
        "SELECT id FROM citation WHERE document_id = ?", (document_id,)
    ).fetchall()
    for row in rows:
        rerender_citation(conn, row["id"])
    return len(rows)


# --------------------------------------------------------------------------- #
# library search (for the insert-citation UI)
# --------------------------------------------------------------------------- #

def search_library(conn: sqlite3.Connection, q: str, limit: int = 20) -> list[dict]:
    like = f"%{q.strip()}%"
    rows = conn.execute(
        """SELECT DISTINCT r.id, r.title, r.year, r.doi, r.item_type
             FROM reference r
             LEFT JOIN reference_author ra ON ra.reference_id = r.id
             LEFT JOIN author a ON a.id = ra.author_id
            WHERE r.title LIKE ? OR a.family LIKE ? OR a.literal LIKE ?
                  OR CAST(r.year AS TEXT) LIKE ?
            ORDER BY r.year DESC, r.title
            LIMIT ?""",
        (like, like, like, like, limit),
    ).fetchall()

    out = []
    for r in rows:
        authors = conn.execute(
            """SELECT a.family, a.given, a.literal FROM reference_author ra
                 JOIN author a ON a.id = ra.author_id
                WHERE ra.reference_id = ? ORDER BY ra.position""",
            (r["id"],),
        ).fetchall()
        author_str = ", ".join(a["literal"] or a["family"] or "" for a in authors)
        out.append({
            "id": r["id"], "title": r["title"], "year": r["year"],
            "doi": r["doi"], "item_type": r["item_type"], "authors": author_str,
        })
    return out


# --------------------------------------------------------------------------- #
# citations
# --------------------------------------------------------------------------- #

def render_citation_text(conn: sqlite3.Connection, document_id: str,
                         reference_ids: list[str]) -> str:
    """Render one in-text citation (e.g. '(Fisher, 2001)' or a grouped
    '(A, 2003; B, 2006)') under the document's active Style Profile."""
    profile = _profile_for_document(conn, document_id)
    items = _csl_items_for_refs(conn, reference_ids)
    if not items:
        return ""
    fmt = formatter.Formatter(items, profile)
    return fmt.render_citation([it["id"] for it in items])


def create_citation(conn: sqlite3.Connection, document_id: str, reference_ids: list[str],
                    raw_original_text: str | None = None) -> tuple[str, str]:
    ensure_document(conn, document_id)
    cid = db.new_id()
    now = db.now_iso()
    rendered = render_citation_text(conn, document_id, reference_ids)
    conn.execute(
        """INSERT INTO citation
           (id, document_id, reference_ids, rendered_text, raw_original_text,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (cid, document_id, json.dumps(reference_ids), rendered, raw_original_text, now, now),
    )
    conn.commit()
    return cid, rendered


def get_citation(conn: sqlite3.Connection, citation_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM citation WHERE id = ?", (citation_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"], "document_id": row["document_id"],
        "reference_ids": json.loads(row["reference_ids"]),
        "rendered_text": row["rendered_text"],
        "raw_original_text": row["raw_original_text"],
    }


def rerender_citation(conn: sqlite3.Connection, citation_id: str,
                     reference_ids: list[str] | None = None) -> str | None:
    """Re-render an existing citation (e.g. after a Style Profile change, or
    after the user confirms a corrected source in the Integrity Panel).
    Optionally swap the referenced works via `reference_ids`."""
    row = conn.execute(
        "SELECT document_id, reference_ids FROM citation WHERE id = ?", (citation_id,)
    ).fetchone()
    if not row:
        return None
    if reference_ids is None:
        reference_ids = json.loads(row["reference_ids"])
    rendered = render_citation_text(conn, row["document_id"], reference_ids)
    conn.execute(
        "UPDATE citation SET reference_ids = ?, rendered_text = ?, updated_at = ? WHERE id = ?",
        (json.dumps(reference_ids), rendered, db.now_iso(), citation_id),
    )
    conn.commit()
    return rendered


# --------------------------------------------------------------------------- #
# bibliography
# --------------------------------------------------------------------------- #

def render_bibliography(conn: sqlite3.Connection, document_id: str) -> list[str]:
    """Rebuild the whole reference list from every citation currently in the
    document, ordered per the style -- this is what fills the
    `sanad-bibliography` content control, replacing 'Create Bibliography'."""
    profile = _profile_for_document(conn, document_id)
    cites = conn.execute(
        "SELECT reference_ids FROM citation WHERE document_id = ?", (document_id,)
    ).fetchall()

    groups, all_ids, seen = [], [], set()
    for c in cites:
        rids = json.loads(c["reference_ids"])
        groups.append(rids)
        for rid in rids:
            if rid not in seen:
                seen.add(rid)
                all_ids.append(rid)

    items = _csl_items_for_refs(conn, all_ids)
    if not items:
        return []
    fmt = formatter.Formatter(items, profile)
    valid = {it["id"] for it in items}
    for rids in groups:
        present = [rid for rid in rids if rid in valid]
        if present:
            fmt.render_citation(present)
    return fmt.render_bibliography()


def bibliography_payload(conn: sqlite3.Connection, document_id: str) -> dict:
    """The full response for the `sanad-bibliography` control: the rendered
    entries *and* the Office-ready paragraph formatting to apply to them, both
    derived from the document's active Style Profile. Content and layout arrive
    together so the add-in never has to make a second call to format what it
    just rebuilt."""
    profile = _profile_for_document(conn, document_id)
    return {
        "entries": render_bibliography(conn, document_id),
        "paragraph_style": sp.paragraph_style_office(profile.get("paragraph_style")),
    }
