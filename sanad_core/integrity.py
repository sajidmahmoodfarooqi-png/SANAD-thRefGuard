"""Tier-A integrity engine (MVP_SPEC.md §4).

The differentiating feature of SANAD: after the formatter has made citations
*look* right, this checks whether they are *actually* right -- the class of
error a formatter cannot catch because it only ever manipulated punctuation.

Each rule R1-R7 generalizes a class of citation error seen in real theses (a
wrong in-text year, a book that resolved to a *review* venue, `_ENREF_` orphans,
glued-cell duplicate references, cited-vs-listed mismatches). Every rule is a
small pure function over a gathered document
context, returning zero or more flag dicts -- so each is unit-testable in
isolation, with no HTTP and no persistence in the way.

Text Integrity Guarantee (CONCEPT.md §2): nothing here reads or writes document
*prose*. Rules read `citation.raw_original_text` (a copy of what the user typed,
captured at conversion time) and library metadata only; they never touch the
living document. All a rule can do is *report*.

Tier-B (R8_CONTEXT_MISALIGNMENT, the semantic check) is a separate later sprint
(build order §6.7) and deliberately not implemented here.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import db, embedding

# --------------------------------------------------------------------------- #
# tunables (module-level so tests and Style Profiles can reason about them)
# --------------------------------------------------------------------------- #

# R6: normalized token-set (Jaccard) similarity at/above which two distinct
# references are treated as probable duplicates. Deliberately high -- this is a
# human-reviewed *warning*, never a silent merge (that is import-time content-sig
# dedup, importer.content_signature). Jaccard on exact tokens misses stem/plural
# variants ("service" vs "services"); a rapidfuzz/stemming upgrade is the v1.x
# improvement (MVP_SPEC.md §13), but exact-token overlap already catches the real
# cases seen here (byte-identical titles from glued spreadsheet cells).
R6_TITLE_SIMILARITY_THRESHOLD = 0.85

# R2: venue strings that almost always mean the metadata resolved to something
# *about* a work (a review, an indexing record) rather than the work itself.
_R2_VENUE_REDFLAGS = [
    re.compile(r"\bchoice reviews?\b", re.I),
    re.compile(r"\breviews online\b", re.I),
    re.compile(r"\bbook reviews?\b", re.I),
    re.compile(r"\babstracting\b", re.I),
]
_MONOGRAPH_TYPES = {"book", "chapter", "monograph"}
_GENERIC_REVIEW_RE = re.compile(r"\breviews?\b", re.I)

# R8 (Tier-B): cosine at/below which a citing sentence is treated as weakly
# related to the source it cites. Backend-specific because lexical-overlap cosine
# and true semantic cosine live on different scales; keyed by the provider family
# (embedding.*.name before any ':').
#   lexical-hash: calibrated (eval/r8_calibration.py) against a labelled set of
#     on-topic vs off-topic pairs -- on-topic similarities clustered 0.12-0.59,
#     off-topic near 0 (max ~0.13). 0.11 gives zero false alarms with the widest
#     safe margin below the on-topic floor; erring low is deliberate, since a
#     false alarm on a correctly-cited source is the costlier error for a
#     confirm-only check.
#   sentence-transformers: a conservative default, not yet calibrated (needs the
#     real semantic backend installed; see MVP_SPEC.md §4).
R8_THRESHOLDS = {"sentence-transformers": 0.35, "lexical-hash": 0.11}
R8_DEFAULT_THRESHOLD = 0.11
R8_SUGGESTION_TOPK = 3

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})[a-z]?\b")
_TITLE_TOKEN_RE = re.compile(r"[a-z0-9]+")
# a few function words that add noise but no identity to a title-overlap check
_TITLE_STOPWORDS = frozenset(
    {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "with", "from"}
)

TIER = "A"


# --------------------------------------------------------------------------- #
# small text helpers
# --------------------------------------------------------------------------- #

def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _years_in_text(raw: str | None) -> set[int]:
    """Every 4-digit year mentioned in a raw in-text citation string, with any
    trailing a/b/c disambiguation suffix stripped ('2005a' -> 2005)."""
    return {int(m.group(1)) for m in _YEAR_RE.finditer(raw or "")}


def _title_tokens(title: str | None) -> set[str]:
    return {t for t in _TITLE_TOKEN_RE.findall((title or "").lower())
            if t not in _TITLE_STOPWORDS}


def _title_similarity(a: str | None, b: str | None) -> float:
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _lead_family(ref: dict) -> str:
    authors = ref.get("authors") or []
    if not authors:
        return ""
    a = authors[0]
    return _norm(a.get("family") or a.get("literal") or "")


def _flag(rule_id: str, severity: str, message: str,
          citation_id: str | None = None, suggestion: dict | None = None,
          tier: str = TIER) -> dict:
    return {
        "rule_id": rule_id, "tier": tier, "severity": severity,
        "message": message, "citation_id": citation_id, "suggestion": suggestion,
    }


# --------------------------------------------------------------------------- #
# document context
# --------------------------------------------------------------------------- #

def _load_reference(conn: sqlite3.Connection, rid: str) -> dict | None:
    r = conn.execute(
        "SELECT id, item_type, title, container_title, year, year_suffix, doi, abstract "
        "FROM reference WHERE id = ?", (rid,),
    ).fetchone()
    if not r:
        return None
    authors = conn.execute(
        "SELECT a.family, a.given, a.literal FROM reference_author ra "
        "JOIN author a ON a.id = ra.author_id "
        "WHERE ra.reference_id = ? ORDER BY ra.position", (rid,),
    ).fetchall()
    d = dict(r)
    d["authors"] = [dict(a) for a in authors]
    return d


class _Context:
    """Everything the rules need, gathered once per scan."""

    def __init__(self, conn: sqlite3.Connection, document_id: str):
        self.document_id = document_id
        rows = conn.execute(
            "SELECT id, reference_ids, raw_original_text FROM citation "
            "WHERE document_id = ?", (document_id,),
        ).fetchall()

        self.citations: list[dict] = []
        self.refs: dict[str, dict] = {}          # resolved references, by id
        self.unresolved: set[str] = set()        # reference_ids that resolve to nothing
        self.cited_ids: list[str] = []           # ordered-unique across the document
        self.citing: dict[str, list[str]] = {}   # reference_id -> [citation_id, ...]

        seen: set[str] = set()
        for row in rows:
            try:
                rids = json.loads(row["reference_ids"]) or []
            except (TypeError, ValueError):
                rids = []
            self.citations.append({
                "id": row["id"], "reference_ids": rids,
                "raw_original_text": row["raw_original_text"],
            })
            for rid in rids:
                self.citing.setdefault(rid, []).append(row["id"])
                if rid not in seen:
                    seen.add(rid)
                    self.cited_ids.append(rid)
                    if rid not in self.refs and rid not in self.unresolved:
                        ref = _load_reference(conn, rid)
                        if ref is None:
                            self.unresolved.add(rid)
                        else:
                            self.refs[rid] = ref

    def resolved_refs_of(self, citation: dict) -> list[dict]:
        return [self.refs[rid] for rid in citation["reference_ids"] if rid in self.refs]


# --------------------------------------------------------------------------- #
# the rules (each independent, each returns a list of flag dicts)
# --------------------------------------------------------------------------- #

def r1_year_mismatch(ctx: _Context) -> list[dict]:
    """The in-text year the author typed disagrees with the resolved
    reference's year -- e.g. a source typed as (Author, 1998) that resolves to a
    2001 record. Only fires when the citation carries a parseable typed year."""
    out = []
    for c in ctx.citations:
        in_text = _years_in_text(c["raw_original_text"])
        if not in_text:
            continue
        for ref in ctx.resolved_refs_of(c):
            if ref["year"] is None:
                continue
            if ref["year"] not in in_text:
                shown = "/".join(str(y) for y in sorted(in_text))
                out.append(_flag(
                    "R1_YEAR_MISMATCH", "warning",
                    f"In-text year {shown} does not match the library year "
                    f"{ref['year']} for “{ref['title']}”.",
                    citation_id=c["id"],
                    suggestion={"reference_id": ref["id"],
                                "in_text_years": sorted(in_text),
                                "reference_year": ref["year"]},
                ))
    return out


def r2_venue_type_sanity(ctx: _Context) -> list[dict]:
    """The reference resolved to a *review of* / *index record for* the work
    rather than the work itself -- e.g. a book whose venue came back as 'Choice
    Reviews Online'. One flag per offending reference, not per citation of it."""
    out = []
    for rid, ref in ctx.refs.items():
        venue = ref.get("container_title") or ""
        redflag = any(rx.search(venue) for rx in _R2_VENUE_REDFLAGS)
        monograph_with_review_venue = (
            ref["item_type"] in _MONOGRAPH_TYPES
            and bool(venue.strip())
            and bool(_GENERIC_REVIEW_RE.search(venue))
        )
        if redflag or monograph_with_review_venue:
            out.append(_flag(
                "R2_VENUE_TYPE_SANITY", "error",
                f"“{ref['title']}” is recorded with venue "
                f"“{venue}”, which looks like a review/index record "
                f"rather than the source itself. Re-resolve this reference.",
                citation_id=(ctx.citing.get(rid) or [None])[0],
                suggestion={"reference_id": rid, "container_title": venue},
            ))
    return out


def r3_orphaned_citation(ctx: _Context, present_control_ids=None) -> list[dict]:
    """A citation marker with no usable backing: an empty reference list, all
    references dead, or a content control present in the document with no
    citation row at all (the `_ENREF_` dead-link class)."""
    out = []
    for c in ctx.citations:
        rids = c["reference_ids"]
        if not rids:
            out.append(_flag("R3_ORPHANED_CITATION", "error",
                             "Citation has no reference attached.",
                             citation_id=c["id"]))
        elif all(rid in ctx.unresolved for rid in rids):
            out.append(_flag(
                "R3_ORPHANED_CITATION", "error",
                "Citation points only to references that are missing from the "
                "library; it would render as an empty or broken marker.",
                citation_id=c["id"], suggestion={"reference_ids": rids}))

    if present_control_ids:
        known = {c["id"] for c in ctx.citations}
        for ctrl_id in present_control_ids:
            if ctrl_id not in known:
                out.append(_flag(
                    "R3_ORPHANED_CITATION", "error",
                    f"Citation control {ctrl_id} exists in the document but has "
                    f"no backing record in the library.",
                    citation_id=ctrl_id))
    return out


def r4_cited_not_listed(ctx: _Context) -> list[dict]:
    """A single reference inside an otherwise-live citation resolves to nothing,
    so the bibliography renderer silently drops it -- the source is cited in the
    text but will never appear in the reference list. Distinct from R3, which is
    the *whole* citation being dead."""
    out = []
    for c in ctx.citations:
        rids = c["reference_ids"]
        if not rids or all(rid in ctx.unresolved for rid in rids):
            continue  # that is R3's job, not R4's
        for rid in rids:
            if rid in ctx.unresolved:
                out.append(_flag(
                    "R4_CITED_NOT_LISTED", "error",
                    "One reference in this grouped citation is missing from the "
                    "library and would be dropped from the reference list.",
                    citation_id=c["id"], suggestion={"reference_id": rid}))
    return out


def r5_listed_not_cited(ctx: _Context, listed_reference_ids=None) -> list[dict]:
    """A reference the document claims to *list* (e.g. extracted from a
    pre-existing typed bibliography during migration) that no citation actually
    references. Only runs when the caller supplies the listed set -- SANAD's own
    generated bibliography is built *from* citations, so it can never diverge on
    its own; this reconciles against an external/legacy list."""
    if not listed_reference_ids:
        return []
    out = []
    cited = set(ctx.cited_ids)
    for rid in listed_reference_ids:
        if rid not in cited:
            ref = ctx.refs.get(rid)
            title = f" (“{ref['title']}”)" if ref else ""
            out.append(_flag(
                "R5_LISTED_NOT_CITED", "info",
                f"Reference{title} appears in the list but is never cited in "
                f"the text.",
                suggestion={"reference_id": rid}))
    return out


def r6_duplicate_reference(ctx: _Context) -> list[dict]:
    """Two distinct references in the document are near-identical in title -- the
    glued-cell / double-entry duplicate class. Human-reviewed warning, one flag
    per pair; the panel lets the user merge or keep both."""
    out = []
    ids = list(ctx.refs.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ctx.refs[ids[i]], ctx.refs[ids[j]]
            sim = _title_similarity(a["title"], b["title"])
            if sim >= R6_TITLE_SIMILARITY_THRESHOLD:
                out.append(_flag(
                    "R6_DUPLICATE_REFERENCE", "warning",
                    f"Two references look like duplicates (title similarity "
                    f"{sim:.0%}): “{a['title']}” and "
                    f"“{b['title']}”.",
                    suggestion={"reference_ids": [a["id"], b["id"]],
                                "similarity": round(sim, 3)}))
    return out


def r7_author_year_ambiguity(ctx: _Context) -> list[dict]:
    """Two+ references share lead-author surname + year, and their a/b/c suffixes
    do not fully separate them -- so an in-text '(Author, 2019)' is ambiguous.
    One flag per ambiguous (author, year) group."""
    out = []
    groups: dict[tuple, list[dict]] = {}
    for ref in ctx.refs.values():
        fam = _lead_family(ref)
        if not fam or ref["year"] is None:
            continue
        groups.setdefault((fam, ref["year"]), []).append(ref)

    for (fam, year), members in groups.items():
        if len(members) < 2:
            continue
        suffixes = [_norm(m.get("year_suffix")) for m in members]
        if len(set(suffixes)) == len(members):
            continue  # a/b/c fully disambiguate -- fine
        out.append(_flag(
            "R7_AUTHOR_YEAR_AMBIGUITY", "warning",
            f"{len(members)} references share “{fam.title()} ({year})” "
            f"without distinct a/b suffixes; in-text citations to them are "
            f"ambiguous.",
            suggestion={"reference_ids": [m["id"] for m in members],
                        "lead_author": fam, "year": year}))
    return out


# --------------------------------------------------------------------------- #
# Tier-B: semantic context check (R8)
# --------------------------------------------------------------------------- #

def _ref_text(ref: dict) -> str:
    """What a reference 'is about', for embedding: title + abstract when present."""
    return f"{ref.get('title') or ''}. {ref.get('abstract') or ''}".strip()


def r8_context_misalignment(ctx: _Context, contexts: dict | None, embedder,
                            library_refs: list[dict] | None = None) -> list[dict]:
    """The reference is real and correctly formatted, but the *sentence citing
    it* is about something else -- the wrongly-cited / out-of-context reference
    at the heart of SANAD's vision. Compares an embedding of the citing sentence
    against the cited source's title+abstract; if the closest cited source is
    only weakly related, flags it and offers the top-k better matches from the
    library. Confirm-only: it never rewrites anything, it asks.

    Only runs where the add-in actually supplied the citing sentence (`contexts`
    maps citation_id -> sentence). No sentence, no opinion -- a semantic check
    with nothing to read stays silent rather than guessing."""
    if not contexts or embedder is None:
        return []

    backend_family = embedder.name.split(":")[0]
    threshold = R8_THRESHOLDS.get(backend_family, R8_DEFAULT_THRESHOLD)

    # candidate pool for suggestions = the whole library (title+abstract). Embed
    # every distinct text ONCE per scan (batched); cross-scan persistent caching
    # of these vectors is the real-model optimization noted in MVP_SPEC.md §4.
    pool = {r["id"]: _ref_text(r) for r in (library_refs or []) if _ref_text(r)}
    titles = {r["id"]: r.get("title") for r in (library_refs or [])}
    # make sure cited refs are embeddable even if the library snapshot missed them
    for rid, ref in ctx.refs.items():
        if _ref_text(ref):
            pool.setdefault(rid, _ref_text(ref))
            titles.setdefault(rid, ref.get("title"))

    active = [(c, contexts.get(c["id"], "").strip()) for c in ctx.citations]
    active = [(c, s) for c, s in active if s]
    if not active or not pool:
        return []

    pool_ids = list(pool)
    texts = [pool[i] for i in pool_ids] + [s for _, s in active]
    vectors = embedder.embed(texts)
    ref_vec = {rid: vectors[i] for i, rid in enumerate(pool_ids)}
    sent_vec = {c["id"]: vectors[len(pool_ids) + k] for k, (c, _) in enumerate(active)}

    out = []
    for c, _sentence in active:
        cited = [rid for rid in c["reference_ids"] if rid in ref_vec]
        if not cited:
            continue
        sv = sent_vec[c["id"]]
        best_cited = max(embedding.cosine(sv, ref_vec[rid]) for rid in cited)
        if best_cited > threshold:
            continue  # the sentence is on-topic for what it cites -- fine

        cited_set = set(cited)
        ranked = sorted(
            ((rid, embedding.cosine(sv, ref_vec[rid]))
             for rid in ref_vec if rid not in cited_set),
            key=lambda kv: kv[1], reverse=True,
        )
        alternatives = [
            {"reference_id": rid, "title": titles.get(rid), "similarity": round(sim, 3)}
            for rid, sim in ranked[:R8_SUGGESTION_TOPK] if sim > best_cited
        ]

        cited_title = next((titles.get(rid) for rid in cited if titles.get(rid)),
                           "the cited source")
        extra = (f" {len(alternatives)} closer source(s) in your library may fit better."
                 if alternatives else " No closer match was found in your library.")
        out.append(_flag(
            "R8_CONTEXT_MISALIGNMENT", "warning",
            f"The citing sentence seems only weakly related to “{cited_title}” "
            f"(similarity {best_cited:.0%}).{extra} Please verify.",
            citation_id=c["id"], tier="B",
            suggestion={"best_cited_similarity": round(best_cited, 3),
                        "backend": embedder.name, "alternatives": alternatives},
        ))
    return out


# --------------------------------------------------------------------------- #
# orchestration + persistence
# --------------------------------------------------------------------------- #

def _library_refs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, title, abstract FROM reference").fetchall()
    return [dict(r) for r in rows]


def compute_flags(conn: sqlite3.Connection, document_id: str,
                  present_control_ids=None, listed_reference_ids=None,
                  contexts=None, embedder=None) -> list[dict]:
    """Run every rule and return flags in stable order (Tier-A R1-R7, then
    Tier-B R8 when an embedder + citing sentences are supplied). Pure: reads the
    library, writes nothing."""
    ctx = _Context(conn, document_id)
    flags: list[dict] = []
    flags += r1_year_mismatch(ctx)
    flags += r2_venue_type_sanity(ctx)
    flags += r3_orphaned_citation(ctx, present_control_ids)
    flags += r4_cited_not_listed(ctx)
    flags += r5_listed_not_cited(ctx, listed_reference_ids)
    flags += r6_duplicate_reference(ctx)
    flags += r7_author_year_ambiguity(ctx)
    if embedder is not None and contexts:
        flags += r8_context_misalignment(ctx, contexts, embedder, _library_refs(conn))
    return flags


def _row_to_flag(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "document_id": row["document_id"],
        "citation_id": row["citation_id"], "rule_id": row["rule_id"],
        "tier": row["tier"], "severity": row["severity"], "message": row["message"],
        "suggestion": json.loads(row["suggestion"]) if row["suggestion"] else None,
        "status": row["status"], "created_at": row["created_at"],
    }


def persist_flags(conn: sqlite3.Connection, document_id: str, flags: list[dict]) -> None:
    """Replace this document's *open* flags with a fresh scan, while respecting
    the user's prior decisions: a finding the user already `confirmed` or
    `dismissed` is not re-created as a new open flag on re-scan."""
    resolved = conn.execute(
        "SELECT rule_id, IFNULL(citation_id,'') cid, message FROM integrity_flag "
        "WHERE document_id = ? AND status IN ('confirmed','dismissed')",
        (document_id,),
    ).fetchall()
    suppressed = {(r["rule_id"], r["cid"], r["message"]) for r in resolved}

    conn.execute(
        "DELETE FROM integrity_flag WHERE document_id = ? AND status = 'open'",
        (document_id,),
    )
    now = db.now_iso()
    for f in flags:
        key = (f["rule_id"], f["citation_id"] or "", f["message"])
        if key in suppressed:
            continue
        conn.execute(
            "INSERT INTO integrity_flag "
            "(id, document_id, citation_id, rule_id, tier, severity, message, "
            " suggestion, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
            (db.new_id(), document_id, f["citation_id"], f["rule_id"], f["tier"],
             f["severity"], f["message"],
             json.dumps(f["suggestion"]) if f["suggestion"] is not None else None,
             now),
        )
    conn.commit()


def list_flags(conn: sqlite3.Connection, document_id: str) -> list[dict]:
    """Every stored flag for a document, open ones first (what the Integrity
    Panel renders)."""
    rows = conn.execute(
        "SELECT * FROM integrity_flag WHERE document_id = ? "
        "ORDER BY (status != 'open'), "
        "         CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, "
        "         rule_id",
        (document_id,),
    ).fetchall()
    return [_row_to_flag(r) for r in rows]


def scan(conn: sqlite3.Connection, document_id: str,
         present_control_ids=None, listed_reference_ids=None,
         contexts=None, embedder=None) -> list[dict]:
    """Compute, persist, and return this document's integrity flags -- the one
    call the `/v1/documents/{id}/scan` endpoint makes. Pass `contexts`
    (citation_id -> citing sentence) + `embedder` to include the Tier-B
    semantic check."""
    flags = compute_flags(conn, document_id, present_control_ids,
                          listed_reference_ids, contexts, embedder)
    persist_flags(conn, document_id, flags)
    return list_flags(conn, document_id)


def set_flag_status(conn: sqlite3.Connection, flag_id: str, status: str) -> bool:
    """Confirm/dismiss/reopen a flag from the Integrity Panel. Returns False if
    no such flag."""
    if status not in ("open", "confirmed", "dismissed"):
        raise ValueError(f"invalid flag status {status!r}")
    cur = conn.execute(
        "UPDATE integrity_flag SET status = ? WHERE id = ?", (status, flag_id)
    )
    conn.commit()
    return cur.rowcount > 0
