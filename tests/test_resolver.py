"""Resolver unit tests -- no real network. `fetch` is injected."""
from sanad_core import resolver

# A trimmed Crossref /works/{doi} response.
_MSG = {
    "message": {
        "DOI": "10.1000/xyz123",
        "type": "journal-article",
        "title": ["A Correct And Authoritative Title"],
        "container-title": ["Journal of Verified Things"],
        "issued": {"date-parts": [[2021, 6]]},
        "volume": "12",
        "issue": "3",
        "page": "45-67",
        "URL": "https://doi.org/10.1000/xyz123",
        "abstract": "<jats:p>Clean <jats:italic>me</jats:italic>.</jats:p>",
        "author": [
            {"family": "Rivera", "given": "Ana"},
            {"family": "Okoye", "given": "B."},
        ],
    }
}


def _fetch_ok(url, timeout=8.0):
    assert "10.1000/xyz123" in url
    return _MSG


def _fetch_boom(url, timeout=8.0):
    raise OSError("network down")


def test_message_mapping_covers_core_fields():
    fields, authors = resolver.crossref_message_to_fields(_MSG["message"])
    assert fields["title"] == "A Correct And Authoritative Title"
    assert fields["container_title"] == "Journal of Verified Things"
    assert fields["year"] == 2021
    assert fields["volume"] == "12" and fields["issue"] == "3" and fields["pages"] == "45-67"
    assert fields["item_type"] == "article-journal"
    assert fields["abstract"] == "Clean me."  # JATS stripped
    assert authors == [
        {"family": "Rivera", "given": "Ana"},
        {"family": "Okoye", "given": "B."},
    ]


def test_enrich_overwrites_from_crossref_when_doi_present():
    fields = {"doi": "10.1000/xyz123", "title": "wrong typed title", "year": 1999}
    out, authors = resolver.enrich(fields, [{"family": "Typo", "given": "X"}], fetch=_fetch_ok)
    assert out["title"] == "A Correct And Authoritative Title"
    assert out["year"] == 2021
    assert out["resolution_src"] == "crossref"
    assert out["confidence"] == 0.98
    assert authors[0]["family"] == "Rivera"


def test_enrich_is_noop_without_doi():
    fields = {"title": "keep me exactly"}
    out, authors = resolver.enrich(fields, [], fetch=_fetch_ok)
    assert out == fields
    assert out.get("resolution_src") != "crossref"


def test_enrich_degrades_gracefully_on_failure():
    fields = {"doi": "10.1000/xyz123", "title": "user value survives"}
    out, _ = resolver.enrich(fields, [], fetch=_fetch_boom)
    assert out["title"] == "user value survives"
    assert out.get("resolution_src") != "crossref"


def test_resolve_by_doi_returns_none_on_empty_message():
    assert resolver.resolve_by_doi("10.1/x", fetch=lambda u, timeout=8.0: {}) is None
