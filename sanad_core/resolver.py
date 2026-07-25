"""Opt-in metadata resolution against Crossref.

SANAD is local-first and makes no network calls by default. This module is the
single, explicit exception: when the user opts in (per import), a reference that
carries a DOI is looked up on Crossref and its authoritative metadata (title,
year, journal, authors, volume/issue/pages) is filled in and corrected. It is:

  * off by default (the caller must pass resolve=True),
  * DOI-only (no title guessing -- a title query can return the *wrong* paper,
    exactly the error SANAD exists to catch),
  * timeout-guarded and fully graceful: any failure leaves the reference as the
    user supplied it.

The HTTP fetch is injectable (`fetch=`) so the merge logic is unit-tested with no
network.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

CROSSREF = "https://api.crossref.org/works/"
# A polite User-Agent per Crossref etiquette. No personal data.
_UA = "SANAD-RefGuard (https://gpgcam.edu.pk; local citation tool)"

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


def crossref_message_to_fields(msg: dict) -> tuple[dict, list[dict]]:
    """Map a Crossref work `message` object to SANAD fields + authors."""
    fields: dict = {}
    if msg.get("title"):
        fields["title"] = msg["title"][0]
    ct = msg.get("container-title") or []
    if ct:
        fields["container_title"] = ct[0]
    dp = (msg.get("issued") or {}).get("date-parts") or []
    if dp and dp[0] and dp[0][0]:
        fields["year"] = int(dp[0][0])
    for src, dst in (("volume", "volume"), ("issue", "issue"), ("page", "pages"),
                     ("publisher", "publisher"), ("DOI", "doi"), ("URL", "url")):
        if msg.get(src):
            fields[dst] = str(msg[src])
    fields["item_type"] = _TYPE_MAP.get(msg.get("type", ""), "article-journal")
    if msg.get("abstract"):
        fields["abstract"] = _JATS_TAG.sub("", msg["abstract"]).strip()
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
