"""Opt-in metadata resolution against Crossref.

SANAD is local-first and makes no network calls by default. This module is the
explicit exception, in two distinct, differently-gated forms:

  * `enrich`/`resolve_by_doi` -- a reference that already carries a DOI is
    looked up and its authoritative metadata is filled in automatically. Safe
    to apply without asking again per result, because a DOI is exact: there is
    no "which paper did you mean" ambiguity.
  * `search_by_title` -- given only a bare title (no DOI), searches Crossref
    and returns *candidates*, ranked, never a single accepted answer. A title
    query can return the wrong paper, which is exactly the error SANAD exists
    to catch -- so this never auto-selects. The caller (the UI) always shows
    the candidates and requires an explicit human pick before anything is
    added to the library.

Both are off unless the user explicitly invokes them, timeout-guarded, and
fully graceful: any failure returns nothing extra rather than raising. The HTTP
fetch is injectable (`fetch=`) so the merge logic is unit-tested with no
network.
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request

CROSSREF = "https://api.crossref.org/works/"
# A polite User-Agent per Crossref etiquette. No personal data.
_UA = "SANAD-RefGuard (https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard; local citation tool)"

_TYPE_MAP = {
    "journal-article": "article-journal",
    "book": "book",
    "book-chapter": "chapter",
    "monograph": "book",
    "proceedings-article": "paper-conference",
    "report": "report",
    "dissertation": "thesis",
    "reference-entry": "entry-encyclopedia",
    "posted-content": "article-journal",
    "dataset": "dataset",
}
_JATS_TAG = re.compile(r"<[^>]+>")


def _default_fetch(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https host)
        return json.loads(r.read().decode("utf-8"))


def _clean_crossref_text(value: str) -> str:
    """Crossref titles/container-titles/abstracts sometimes carry inline markup
    -- either raw JATS tags (<i>...</i>) or, in titles especially, HTML-entity-
    encoded ones (Kuhn's &lt;i&gt;The Structure...&lt;/i&gt; at 60). Decode
    entities first, THEN strip tags, so both forms end up as plain text -- a
    real case found while verifying the title-search feature against the live
    Crossref API, not a hypothetical."""
    return _JATS_TAG.sub("", html.unescape(value)).strip()


def crossref_message_to_fields(msg: dict) -> tuple[dict, list[dict]]:
    """Map a Crossref work `message` object to SANAD fields + authors."""
    fields: dict = {}
    if msg.get("title"):
        fields["title"] = _clean_crossref_text(msg["title"][0])
    ct = msg.get("container-title") or []
    if ct:
        fields["container_title"] = _clean_crossref_text(ct[0])
    dp = (msg.get("issued") or {}).get("date-parts") or []
    if dp and dp[0] and dp[0][0]:
        fields["year"] = int(dp[0][0])
    for src, dst in (("volume", "volume"), ("issue", "issue"), ("page", "pages"),
                     ("publisher", "publisher"), ("DOI", "doi"), ("URL", "url")):
        if msg.get(src):
            fields[dst] = str(msg[src])
    fields["item_type"] = _TYPE_MAP.get(msg.get("type", ""), "article-journal")
    if msg.get("abstract"):
        fields["abstract"] = _clean_crossref_text(msg["abstract"])
    authors = [
        {"family": a.get("family", "").strip(), "given": a.get("given", "").strip()}
        for a in (msg.get("author") or [])
        if a.get("family") or a.get("given")
    ]
    return fields, authors


def resolve_by_doi(doi: str, fetch=None) -> tuple[dict, list[dict]] | None:
    fetch = fetch or _default_fetch
    try:
        data = fetch(CROSSREF + urllib.parse.quote(doi.strip()))
        msg = data.get("message")
        return crossref_message_to_fields(msg) if msg else None
    except Exception:
        return None


CROSSREF_SEARCH = "https://api.crossref.org/works"


def search_by_title(title: str, fetch=None, rows: int = 5) -> list[dict]:
    """Search Crossref by a bare title (no DOI known yet) and return up to
    `rows` candidates, each `{"fields": {...}, "authors": [...]}` -- ranked by
    Crossref's own relevance score, most-likely-match first. Deliberately never
    picks one: a title query can return a similarly-named but different paper,
    so the caller must show these to the user and let them choose (or reject
    all of them) rather than anything here guessing on their behalf. Returns
    [] on any lookup failure -- never raises."""
    title = (title or "").strip()
    if not title:
        return []
    fetch = fetch or _default_fetch
    try:
        url = f"{CROSSREF_SEARCH}?query.bibliographic={urllib.parse.quote(title)}&rows={int(rows)}"
        data = fetch(url)
        items = ((data.get("message") or {}).get("items")) or []
    except Exception:
        return []
    out = []
    for item in items:
        fields, authors = crossref_message_to_fields(item)
        if fields.get("title"):
            out.append({"fields": fields, "authors": authors})
    return out


def enrich(fields: dict, authors: list[dict], fetch=None) -> tuple[dict, list[dict]]:
    """Enrich one parsed reference from Crossref by its DOI. Crossref's
    authoritative values win for the fields it provides (the user opted in to be
    corrected); the DOI-less case, or any lookup failure, returns the inputs
    unchanged. Never raises."""
    doi = (fields.get("doi") or "").strip()
    if not doi:
        return fields, authors
    resolved = resolve_by_doi(doi, fetch=fetch)
    if not resolved:
        return fields, authors
    cf, ca = resolved
    merged = dict(fields)
    for k, v in cf.items():
        if v not in (None, ""):
            merged[k] = v
    merged["resolution_src"] = "crossref"
    merged["confidence"] = 0.98
    return merged, (ca or authors)
