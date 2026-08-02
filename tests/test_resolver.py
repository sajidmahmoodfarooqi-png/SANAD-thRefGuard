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


# --- search_by_title: candidates only, never auto-picks ---------------------- #

_SEARCH_RESPONSE = {
    "message": {
        "items": [
            {
                "DOI": "10.2000/aaa111",
                "type": "journal-article",
                "title": ["Sediment Transport Modelling in Coastal Estuaries"],
                "container-title": ["Journal of Verified Things"],
                "issued": {"date-parts": [[2019]]},
                "author": [{"family": "Alvarez", "given": "T."}],
            },
            {
                "DOI": "10.2000/bbb222",
                "type": "journal-article",
                "title": ["Sediment Transport in Coastal Estuaries: A Modelling Approach"],
                "container-title": ["Journal of Verified Things"],
                "issued": {"date-parts": [[2020]]},
                "author": [{"family": "Alvarez", "given": "T."}, {"family": "Kim", "given": "S."}],
            },
        ]
    }
}


def _fetch_search_ok(url, timeout=8.0):
    assert "query.bibliographic=" in url
    return _SEARCH_RESPONSE


def test_search_by_title_returns_ranked_candidates_never_picks_one():
    results = resolver.search_by_title("Sediment Transport Modelling Coastal Estuaries",
                                       fetch=_fetch_search_ok)
    assert len(results) == 2   # both candidates returned -- caller decides, not this function
    assert results[0]["fields"]["title"] == "Sediment Transport Modelling in Coastal Estuaries"
    assert results[0]["fields"]["doi"] == "10.2000/aaa111"
    assert results[1]["authors"][1]["family"] == "Kim"


def test_search_by_title_respects_rows_param_in_the_request():
    seen = {}
    def fetch(url, timeout=8.0):
        seen["url"] = url
        return _SEARCH_RESPONSE
    resolver.search_by_title("anything", fetch=fetch, rows=3)
    assert "rows=3" in seen["url"]


def test_search_by_title_empty_query_returns_nothing():
    assert resolver.search_by_title("", fetch=_fetch_search_ok) == []
    assert resolver.search_by_title("   ", fetch=_fetch_search_ok) == []


def test_search_by_title_degrades_gracefully_on_failure():
    assert resolver.search_by_title("x", fetch=_fetch_boom) == []


def test_search_by_title_handles_missing_items_key():
    assert resolver.search_by_title("x", fetch=lambda u, timeout=8.0: {"message": {}}) == []


def test_crossref_title_strips_html_entity_encoded_markup():
    # a real shape found via the live Crossref API: a title containing
    # HTML-entity-encoded tags (not raw <i> -- the literal text is "&lt;i&gt;")
    msg = {"title": ["Someone's &lt;i&gt;Big Idea&lt;/i&gt; Revisited"],
           "container-title": ["A &amp; B Journal"]}
    fields, _ = resolver.crossref_message_to_fields(msg)
    assert fields["title"] == "Someone's Big Idea Revisited"
    assert fields["container_title"] == "A & B Journal"


def test_crossref_title_strips_raw_tags_too():
    msg = {"title": ["Plain <i>Raw Tag</i> Title"]}
    fields, _ = resolver.crossref_message_to_fields(msg)
    assert fields["title"] == "Plain Raw Tag Title"
