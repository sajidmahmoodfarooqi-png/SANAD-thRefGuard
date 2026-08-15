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

def _rows_to_refs(conn: sqlite3.Connection, rows) -> list[dict]:
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


def _pick_keeper(members: list, author_count: dict) -> object:
    """Choose which copy of a duplicate group to keep: the *richest* record --
    one with a DOI beats one without, then more authors wins, and an earlier
    import breaks any remaining tie. This matters for near-duplicates, where one
    copy is a full record (DOI + authors) and the other a bare re-entry: we keep
    the full one. ``members`` must already be ordered earliest-first, so a strict
    ``>`` comparison naturally keeps the earliest on a tie."""
    from .importer import normalize_doi
    best, best_key = None, None
    for m in members:
        key = (1 if normalize_doi(m["doi"]) else 0, author_count.get(m["id"], 0))
        if best is None or key > best_key:
            best, best_key = m, key
    return best


def find_duplicate_groups(conn: sqlite3.Connection) -> list[dict]:
    """Groups of references that are duplicates of one another. Two passes:

    1. **Exact** -- same DOI (normalised: bare vs doi.org URL vs "doi:"-prefixed,
       any case) or, failing a DOI, the same full-content signature. This is what
       re-importing the same library twice produces.
    2. **Near-duplicate** -- the same normalised title *and* year, for records not
       already grouped above. This catches the common case of one paper entered
       twice: a full record (DOI + authors + metadata) and a bare re-entry (title
       + year only). A group spanning two *different* DOIs is skipped -- that
       signals genuinely distinct works (e.g. an erratum), left for human review.

    Each group names the canonical keeper (the richest copy) plus the extras."""
    from .importer import normalize_doi, normalize_title
    rows = conn.execute(
        """SELECT id, title, year, doi, content_sig, created_at
             FROM reference ORDER BY created_at, id"""
    ).fetchall()
    author_count = {
        r["reference_id"]: r["c"] for r in conn.execute(
            "SELECT reference_id, COUNT(*) c FROM reference_author GROUP BY reference_id")
    }
    assigned: set = set()
    out: list = []

    # pass 1 -- exact: normalised DOI, else full-content signature
    exact: dict[str, list] = {}
    for r in rows:
        doi = normalize_doi(r["doi"])
        key = f"doi:{doi}" if doi else (f"sig:{r['content_sig']}" if r["content_sig"] else None)
        if key is None:
            continue
        exact.setdefault(key, []).append(r)
    for members in exact.values():
        if len(members) > 1:
            keep = _pick_keeper(members, author_count)
            out.append({"keep": keep["id"], "title": keep["title"],
                        "remove": [m["id"] for m in members if m["id"] != keep["id"]]})
            assigned.update(m["id"] for m in members)

    # pass 2 -- near-duplicate: same normalised title + year, not already grouped
    near: dict[tuple, list] = {}
    for r in rows:
        if r["id"] in assigned:
            continue
        nt = normalize_title(r["title"])
        if not nt or r["year"] is None:
            continue  # need a real title and a year to pair confidently
        near.setdefault((nt, r["year"]), []).append(r)
    for members in near.values():
        if len(members) < 2:
            continue
        dois = {normalize_doi(m["doi"]) for m in members}
        dois.discard(None)
        if len(dois) > 1:
            continue  # conflicting DOIs -> genuinely different works; leave for review
        keep = _pick_keeper(members, author_count)
        out.append({"keep": keep["id"], "title": keep["title"],
                    "remove": [m["id"] for m in members if m["id"] != keep["id"]]})
        assigned.update(m["id"] for m in members)
    return out


def library_health(conn: sqlite3.Connection) -> dict:
    """A self-diagnosing snapshot of the library's data quality, surfaced
    directly in the app so a lone user can see and act on hygiene issues
    without ever touching the database. Four independent checks:

      - missing_doi: references with no DOI on file. Purely informational --
        DOI lookup is opt-in per reference (privacy), so this does not mean
        anything failed.
      - malformed: references whose title is a bare DOI/URL fragment or number
        with no author -- import artifacts, not real references. importer.py
        now rejects these at import time (looks_like_malformed_bare_reference),
        but that guard only protects future imports; this is a RETROACTIVE scan
        so anything that got in before the guard existed is still found and can
        be removed here.
      - exact_duplicate_count: the same count find_duplicate_groups() already
        resolves via the "Remove duplicates" button (same DOI, or same
        normalized title + same year).
      - near_duplicate_groups: references similar enough in title to likely be
        the same work but not already resolved above -- catches spelling/case
        variants (e.g. "Modeling"/"modelling") that exact normalization alone
        would miss, not just a year difference. A conflicting DOI on either
        side rules the pair out (a genuinely different work, e.g. an erratum).
        Similarity threshold (0.88, difflib.SequenceMatcher on normalized
        titles) was tuned by hand against a real 449-reference library: it
        found the real near-duplicates present (including the exact
        "Modeling"/"modelling" case above) without flagging genuinely
        different papers. Pairs sharing a member are merged into one cluster.
        Never auto-merged -- listed for manual review via the Library screen's
        own sort+delete tool only."""
    from difflib import SequenceMatcher

    from .importer import (looks_like_malformed_bare_reference, normalize_doi,
                           normalize_title)

    rows = conn.execute("SELECT id, title, year, doi FROM reference").fetchall()
    total = len(rows)
    missing_doi = sum(1 for r in rows if not (r["doi"] or "").strip())

    author_count = {
        r["reference_id"]: r["c"] for r in conn.execute(
            "SELECT reference_id, COUNT(*) c FROM reference_author GROUP BY reference_id")
    }
    malformed = [
        {"id": r["id"], "title": r["title"], "year": r["year"]}
        for r in rows
        if looks_like_malformed_bare_reference(
            r["title"], [{}] * author_count.get(r["id"], 0))
    ]

    exact_groups = find_duplicate_groups(conn)
    exact_ids = {rid for g in exact_groups for rid in ([g["keep"]] + g["remove"])}
    exact_duplicate_count = sum(len(g["remove"]) for g in exact_groups)

    by_id = {r["id"]: r for r in rows}
    candidates = [r for r in rows if r["id"] not in exact_ids and normalize_title(r["title"])]
    NEAR_DUP_THRESHOLD = 0.88
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]   # path compression
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # Precompute each candidate's normalized title once (not per-pair -- an
    # all-pairs pass already means O(n^2) comparisons, no need to also redo the
    # normalization work itself that many times).
    normed = [normalize_title(r["title"]) for r in candidates]
    dois = [normalize_doi(r["doi"]) for r in candidates]
    sm = SequenceMatcher()   # reused across every pair; set_seqs() is cheap,
                              # avoids constructing a new matcher per comparison

    clustered_ids: set[str] = set()
    for i in range(len(candidates)):
        na = normed[i]
        for j in range(i + 1, len(candidates)):
            nb = normed[j]
            if na == nb:
                ratio = 1.0
            else:
                sm.set_seqs(na, nb)
                # quick_ratio()/real_quick_ratio() are cheap UPPER BOUNDS on the
                # real ratio() -- skip the expensive full comparison unless one
                # says there's still a chance of reaching the threshold. This
                # cannot miss a real match (both are proven upper bounds), and
                # cuts an all-pairs pass over a few hundred references from
                # tens of seconds to a fraction of a second in practice, since
                # almost every pair in a real library is obviously dissimilar.
                if sm.real_quick_ratio() < NEAR_DUP_THRESHOLD or sm.quick_ratio() < NEAR_DUP_THRESHOLD:
                    continue
                ratio = sm.ratio()
            if ratio < NEAR_DUP_THRESHOLD:
                continue
            a, b = candidates[i], candidates[j]
            doi_a, doi_b = dois[i], dois[j]
            if doi_a and doi_b and doi_a != doi_b:
                continue  # different DOIs -> genuinely distinct, not a near-dup
            union(a["id"], b["id"])
            clustered_ids.update((a["id"], b["id"]))

    clusters: dict[str, list[str]] = {}
    for rid in clustered_ids:
        clusters.setdefault(find(rid), []).append(rid)
    near_groups = [
        {"title": by_id[ids[0]]["title"],
         "members": [{"id": rid, "title": by_id[rid]["title"], "year": by_id[rid]["year"],
                     "doi": by_id[rid]["doi"]} for rid in sorted(ids)]}
        for ids in clusters.values()
    ]

    return {
        "total": total,
        "missing_doi": missing_doi,
        "exact_duplicate_count": exact_duplicate_count,
        "malformed": malformed,
        "near_duplicate_groups": near_groups,
        "near_duplicate_count": sum(len(g["members"]) for g in near_groups),
    }


def deduplicate_library(conn: sqlite3.Connection) -> dict:
    """Remove exact-duplicate references, keeping one canonical copy of each and
    repointing any citations / source-map matches at the keeper first, so no
    document is left referencing a deleted row. Returns what was done."""
    dupes = find_duplicate_groups(conn)
    remap: dict[str, str] = {}
    for g in dupes:
        for rid in g["remove"]:
            remap[rid] = g["keep"]
    if not remap:
        return {"removed": 0, "groups": 0, "library_size": count_library(conn)}

    # 1) repoint grouped citations (reference_ids is a JSON array)
    for cid, raw in conn.execute("SELECT id, reference_ids FROM citation").fetchall():
        try:
            ids = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            continue
        new_ids, seen, changed = [], set(), False
        for rid in ids:
            mapped = remap.get(rid, rid)
            if mapped != rid:
                changed = True
            if mapped not in seen:      # collapse if both original and keeper were cited
                seen.add(mapped); new_ids.append(mapped)
        if changed:
            conn.execute("UPDATE citation SET reference_ids = ? WHERE id = ?",
                         (json.dumps(new_ids), cid))

    # 2) repoint local-PDF matches (table is optional -- guard on its presence)
    has_local_pdf = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_pdf'").fetchone()
    if has_local_pdf:
        for removed, keep in remap.items():
            conn.execute(
                "UPDATE local_pdf SET matched_reference_id = ? WHERE matched_reference_id = ?",
                (keep, removed))

    # 3) delete the extra copies (author links first)
    removed_ids = list(remap)
    conn.executemany("DELETE FROM reference_author WHERE reference_id = ?",
                     [(r,) for r in removed_ids])
    conn.executemany("DELETE FROM reference WHERE id = ?", [(r,) for r in removed_ids])

    # 4) canonicalise the DOI on each kept row, so a library imported before
    # DOIs were normalised at store time doesn't keep re-accumulating the same
    # duplicate on every future import (the keeper now matches new imports too)
    from .importer import normalize_doi
    for g in dupes:
        row = conn.execute("SELECT doi FROM reference WHERE id = ?", (g["keep"],)).fetchone()
        if row is not None:
            canon = normalize_doi(row["doi"])
            if canon and canon != row["doi"]:
                conn.execute("UPDATE reference SET doi = ? WHERE id = ?", (canon, g["keep"]))
    conn.commit()
    return {"removed": len(removed_ids), "groups": len(dupes),
            "library_size": count_library(conn)}


def count_library(conn: sqlite3.Connection, q: str = "") -> int:
    """Total references matching q (whole library when q is empty)."""
    like = f"%{q.strip()}%"
    row = conn.execute(
        """SELECT COUNT(DISTINCT r.id) AS n
             FROM reference r
             LEFT JOIN reference_author ra ON ra.reference_id = r.id
             LEFT JOIN author a ON a.id = ra.author_id
            WHERE r.title LIKE ? OR a.family LIKE ? OR a.literal LIKE ?
                  OR CAST(r.year AS TEXT) LIKE ?""",
        (like, like, like, like),
    ).fetchone()
    return int(row["n"]) if row else 0


# sort options for the Library view. Whitelisted (never interpolate user input
# into SQL) -- title A-Z is what makes duplicates sit next to each other.
_LIBRARY_SORTS = {
    "title": "r.title COLLATE NOCASE ASC, r.year DESC",
    "title_desc": "r.title COLLATE NOCASE DESC, r.year DESC",
    "year": "r.year DESC, r.title COLLATE NOCASE ASC",
    "year_asc": "r.year ASC, r.title COLLATE NOCASE ASC",
}


def list_library(conn: sqlite3.Connection, q: str = "", limit: int = 200,
                 offset: int = 0, sort: str = "year") -> list[dict]:
    """Browse the whole library (or filtered by q), one page at a time. Unlike
    search_library (typeahead, small fixed cap) this is the paginated backing for
    the Library view, so a library of any size is fully reachable. `sort` selects
    the ordering (title A-Z, year, ...) so duplicates can be clustered by title."""
    like = f"%{q.strip()}%"
    order = _LIBRARY_SORTS.get(sort, _LIBRARY_SORTS["year"])
    rows = conn.execute(
        f"""SELECT DISTINCT r.id, r.title, r.year, r.doi, r.item_type
             FROM reference r
             LEFT JOIN reference_author ra ON ra.reference_id = r.id
             LEFT JOIN author a ON a.id = ra.author_id
            WHERE r.title LIKE ? OR a.family LIKE ? OR a.literal LIKE ?
                  OR CAST(r.year AS TEXT) LIKE ?
            ORDER BY {order}
            LIMIT ? OFFSET ?""",
        (like, like, like, like, max(1, min(limit, 1000)), max(0, offset)),
    ).fetchall()
    return _rows_to_refs(conn, rows)


def delete_reference(conn: sqlite3.Connection, ref_id: str) -> dict:
    """Delete a single reference (for manual de-duplication). Removes its author
    links and drops it from any grouped citation's reference list so nothing is
    left pointing at a deleted row. Returns {deleted: 0|1, library_size}."""
    exists = conn.execute("SELECT 1 FROM reference WHERE id = ?", (ref_id,)).fetchone()
    if not exists:
        return {"deleted": 0, "library_size": count_library(conn)}
    for cid, raw in conn.execute("SELECT id, reference_ids FROM citation").fetchall():
        try:
            ids = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            continue
        if ref_id in ids:
            conn.execute("UPDATE citation SET reference_ids = ? WHERE id = ?",
                         (json.dumps([x for x in ids if x != ref_id]), cid))
    conn.execute("DELETE FROM reference_author WHERE reference_id = ?", (ref_id,))
    conn.execute("DELETE FROM reference WHERE id = ?", (ref_id,))
    conn.commit()
    return {"deleted": 1, "library_size": count_library(conn)}


# words that are citation punctuation, not something stored in the library, so
# a query like "Khan et al. 2025" searches for "khan" + "2025", not the literal
# string "khan et al. 2025" (which matches no title or author field).
_SEARCH_NOISE = {"et", "al", "and", "&", "the", "a", "an"}


def _search_tokens(q: str) -> list[str]:
    toks = []
    for raw in (q or "").split():
        t = raw.strip(".,;:()[]{}&'\"").replace("%", "").replace("_", "")
        if t and t.lower() not in _SEARCH_NOISE:
            toks.append(t)
    return toks


def search_library(conn: sqlite3.Connection, q: str, limit: int = 20) -> list[dict]:
    # Match on every meaningful word independently (AND), across title, journal,
    # author name (family/given/literal) and year -- so "Khan 2025", "urban Khan",
    # or "Khan et al." all find the right reference, not just an exact substring.
    tokens = _search_tokens(q)
    if not tokens:
        return []

    clauses, params = [], []
    for t in tokens:
        like = f"%{t}%"
        clauses.append(
            "(r.title LIKE ? OR r.container_title LIKE ? OR CAST(r.year AS TEXT) LIKE ?"
            " OR r.id IN (SELECT ra.reference_id FROM reference_author ra"
            "             JOIN author a ON a.id = ra.author_id"
            "            WHERE a.family LIKE ? OR a.given LIKE ? OR a.literal LIKE ?))"
        )
        params += [like, like, like, like, like, like]

    params.append(limit)
    rows = conn.execute(
        f"""SELECT r.id, r.title, r.year, r.doi, r.item_type
              FROM reference r
             WHERE {' AND '.join(clauses)}
             ORDER BY r.year DESC, r.title
             LIMIT ?""",
        params,
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
