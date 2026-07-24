"""Conversion between a `reference` row (+ authors) and CSL-JSON.

CSL-JSON is the reference's source of truth for rendering (MVP_SPEC.md §2) —
it is citeproc-py's native input format, so this module has no translation
layer to the formatter: build the dict here, hand it straight to citeproc.
"""
from __future__ import annotations

import json

# CSL item "type" values we actively use; anything outside this set is still
# passed through (citeproc is tolerant), but these are the ones the importer
# maps RIS/BibTeX entry types onto.
KNOWN_CSL_TYPES = {
    "article-journal", "book", "chapter", "report", "webpage", "thesis",
    "paper-conference", "manuscript", "review", "review-book",
}


def author_to_csl(author: dict) -> dict:
    """One author dict -> one CSL 'name variable' entry.

    `author` is {"family": ..., "given": ...} for a person, or
    {"literal": ...} for a corporate author (e.g. "Global Standards
    Consortium") -- CSL supports both natively.
    """
    if author.get("literal"):
        return {"literal": author["literal"]}
    out = {}
    if author.get("family"):
        out["family"] = author["family"]
    if author.get("given"):
        out["given"] = author["given"]
    return out


def build_csl_json(reference: dict, authors: list[dict] | None = None) -> dict:
    """Build a full CSL-JSON item from a `reference` row's fields.

    `reference` uses the same keys as the `reference` table (item_type,
    title, container_title, year, volume, issue, pages, publisher, doi,
    isbn, url, abstract, language). `authors` is an ordered list of author
    dicts as accepted by `author_to_csl`.
    """
    item: dict = {
        "id": reference["id"],
        "type": reference.get("item_type") or "article-journal",
        "title": reference.get("title") or "",
    }
    if reference.get("container_title"):
        item["container-title"] = reference["container_title"]
    if reference.get("volume"):
        item["volume"] = reference["volume"]
    if reference.get("issue"):
        item["issue"] = reference["issue"]
    if reference.get("pages"):
        item["page"] = reference["pages"]
    if reference.get("publisher"):
        item["publisher"] = reference["publisher"]
    if reference.get("doi"):
        item["DOI"] = reference["doi"]
    if reference.get("isbn"):
        item["ISBN"] = reference["isbn"]
    if reference.get("url"):
        item["URL"] = reference["url"]
    if reference.get("abstract"):
        item["abstract"] = reference["abstract"]
    if reference.get("language"):
        item["language"] = reference["language"]

    year = reference.get("year")
    if year:
        date_parts = [[int(year)]]
        item["issued"] = {"date-parts": date_parts}

    if authors:
        csl_authors = [author_to_csl(a) for a in authors]
        csl_authors = [a for a in csl_authors if a]
        if csl_authors:
            item["author"] = csl_authors

    return item


def csl_json_to_reference_fields(csl: dict) -> dict:
    """Reverse direction: a CSL-JSON item (e.g. fetched from Crossref) ->
    the flat fields the `reference` table expects. Authors are returned
    separately since they live in their own tables.
    """
    year = None
    issued = csl.get("issued") or {}
    date_parts = issued.get("date-parts") or []
    if date_parts and date_parts[0]:
        year = date_parts[0][0]

    fields = {
        "item_type": csl.get("type") or "article-journal",
        "title": csl.get("title") or "",
        "container_title": csl.get("container-title"),
        "year": year,
        "volume": csl.get("volume"),
        "issue": csl.get("issue"),
        "pages": csl.get("page"),
        "publisher": csl.get("publisher"),
        "doi": csl.get("DOI"),
        "isbn": csl.get("ISBN"),
        "url": csl.get("URL"),
        "abstract": csl.get("abstract"),
        "language": csl.get("language"),
    }

    authors = []
    for a in csl.get("author") or []:
        if a.get("literal"):
            authors.append({"literal": a["literal"]})
        else:
            authors.append({"family": a.get("family"), "given": a.get("given")})
    return {"fields": fields, "authors": authors}


def dumps(csl_item: dict) -> str:
    return json.dumps(csl_item, ensure_ascii=False)
