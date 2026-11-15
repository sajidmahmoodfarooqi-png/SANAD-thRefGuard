"""Regression tests for the November 2026 diagnostic audit.

Each test pins one defect that was reproduced against the code before it was
fixed (see docs/AUDIT.md §9). They are grouped by what the user would have seen:
an action that failed outright, references lost or wrongly merged, an import
that silently dropped or mangled rows, bilingual (Urdu) handling, and the Word
add-in's text-integrity guarantee. All sample data is invented.
"""
import base64
import io
import re
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sanad_core import (db, documents, embedding, formatter, handbook, importer,
                        integrity, list_import, resolver, server)
from sanad_core import style_profile as sp

ONE_PAPER_RIS = "TY  - JOUR\nAU  - Alpha, B.\nTI  - Some paper title\nPY  - 2020\nER  -\n"
DOC = "doc-audit"


@pytest.fixture
def conn():
    return db.connect(":memory:")


@pytest.fixture
def client(tmp_path):
    app = server.create_app(tmp_path / "audit.db")
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {app.state.token}"})
    return c


def add(conn, title, year=2020, authors=None, doi=None, **extra):
    rid = importer.insert_reference(
        conn, {"item_type": "article-journal", "title": title, "year": year,
               "doi": doi, **extra}, authors or [])
    conn.commit()
    return rid


def _seed_one(client):
    client.post("/v1/library/import", json={"format": "ris", "text": ONE_PAPER_RIS})
    return client.get("/v1/library/search?q=paper").json()["results"][0]["id"]


# --------------------------------------------------------------------------- #
# 1. actions that failed outright (database link errors -> HTTP 500)
# --------------------------------------------------------------------------- #

def test_scan_reports_a_control_with_no_record_instead_of_failing(client):
    """An orphan control is exactly what R3 exists to report; saving that
    finding used to violate the flag->citation link and abort the scan."""
    rid = _seed_one(client)
    cid = client.post("/v1/citations",
                      json={"document_id": DOC, "reference_ids": [rid]}).json()["citation_id"]
    r = client.post(f"/v1/documents/{DOC}/scan",
                    json={"present_control_ids": [cid, "ghost-control"]})
    assert r.status_code == 200
    r3 = [f for f in r.json()["flags"] if f["rule_id"] == "R3_ORPHANED_CITATION"]
    assert [f["citation_id"] for f in r3] == ["ghost-control"]
    # and it survives a round trip through storage with the same identity
    stored = client.get(f"/v1/documents/{DOC}/flags").json()["flags"]
    assert any(f["citation_id"] == "ghost-control" for f in stored)


def test_dismissed_orphan_control_finding_stays_dismissed(client):
    r = client.post(f"/v1/documents/{DOC}/scan", json={"present_control_ids": ["ghost"]})
    flag = r.json()["flags"][0]
    client.put(f"/v1/flags/{flag['id']}", json={"status": "dismissed"})
    again = client.post(f"/v1/documents/{DOC}/scan", json={"present_control_ids": ["ghost"]})
    assert again.json()["open_count"] == 0


def test_scan_of_a_document_sanad_has_never_seen(client):
    r = client.post("/v1/documents/brand-new/scan", json={"listed_reference_ids": ["x"]})
    assert r.status_code == 200
    assert r.json()["flags"][0]["rule_id"] == "R5_LISTED_NOT_CITED"


def test_reference_list_rebuilds_after_a_flagged_citation_is_deleted_in_word(client):
    rid = _seed_one(client)
    client.post("/v1/citations", json={"document_id": DOC, "reference_ids": [rid],
                                       "raw_original_text": "(Alpha, 1999)"})
    assert client.post(f"/v1/documents/{DOC}/scan", json={}).json()["flag_count"] >= 1
    # the user deletes that citation in Word, then rebuilds the list
    r = client.post(f"/v1/documents/{DOC}/bibliography", json={"present_control_ids": []})
    assert r.status_code == 200 and r.json()["entries"] == []
    # its findings went with it
    assert client.get(f"/v1/documents/{DOC}/flags").json()["flags"] == []


def test_deleting_a_style_profile_a_document_uses(client):
    pid = client.post("/v1/style-profiles/build", json={"name": "In use"}).json()["id"]
    rid = _seed_one(client)
    client.post("/v1/citations", json={"document_id": DOC, "reference_ids": [rid]})
    client.post(f"/v1/style-profiles/{pid}/apply", json={"document_id": DOC})
    assert client.delete(f"/v1/style-profiles/{pid}").status_code == 200
    # the document falls back to the default style and still renders
    assert len(client.get(f"/v1/documents/{DOC}/bibliography").json()["entries"]) == 1


def test_unreadable_spreadsheet_is_a_clear_400_not_a_server_error(client):
    junk = base64.b64encode(b"this is not a zip archive").decode()
    for fmt in ("xlsx", "docx"):
        r = client.post("/v1/library/import", json={"format": fmt, "data_b64": junk})
        assert r.status_code == 400
        assert "could not be read" in r.json()["detail"]


def test_odd_values_from_a_client_cannot_break_an_import(client):
    """A year of 'n.d.', a missing item type and nameless authors used to raise
    database/type errors (HTTP 500); a missing title is now refused clearly."""
    ok = client.post("/v1/library/add-resolved", json={
        "fields": {"title": "Undated working paper", "year": "n.d.", "item_type": None,
                   "volume": 12},
        "authors": [{"family": None, "given": None}, {"family": " Khan ", "given": "A."}]})
    assert ok.status_code == 200 and ok.json()["added"] is True
    row = client.get("/v1/library?q=Undated").json()["results"][0]
    assert row["year"] is None and row["authors"] == "Khan"
    assert client.get("/v1/library/search?q=undated").status_code == 200   # sort used to need a number

    missing = client.post("/v1/library/add-resolved",
                          json={"fields": {"title": None, "year": 2020}, "authors": []})
    assert missing.status_code == 422


def test_year_is_always_stored_as_a_number_or_nothing(conn):
    assert importer.coerce_year("2020/05/01") == 2020
    assert importer.coerce_year(2019.0) == 2019
    assert importer.coerce_year("in press") is None
    assert importer.coerce_year(True) is None
    rid = add(conn, "A dated thing", year="2018")
    assert conn.execute("SELECT typeof(year) t FROM reference WHERE id=?",
                        (rid,)).fetchone()["t"] == "integer"


def test_junk_authorization_header_is_unauthorized_not_an_error():
    assert server._same_secret("Bearer éé", "Bearer abc") is False
    assert server._same_secret("Bearer abc", "Bearer abc") is True


def test_citation_to_sources_that_do_not_exist_is_refused(client):
    rid = _seed_one(client)
    assert client.post("/v1/citations", json={"document_id": DOC,
                                              "reference_ids": ["nope"]}).status_code == 404
    # one dead id inside a live group is still accepted (that is R4's finding)
    ok = client.post("/v1/citations", json={"document_id": DOC, "reference_ids": [rid, "nope"]})
    assert ok.status_code == 200 and ok.json()["rendered_text"]
    cid = ok.json()["citation_id"]
    assert client.put(f"/v1/citations/{cid}", json={"reference_ids": ["nope"]}).status_code == 404
    assert client.put(f"/v1/citations/{cid}", json={"reference_ids": []}).status_code == 404


def test_bad_style_profile_values_are_rejected_when_saved(client):
    """They used to be accepted and then break every citation and the whole
    reference list of any document the profile was applied to."""
    assert client.post("/v1/style-profiles/build",
                       json={"name": "P", "et_al_min": "abc"}).status_code == 422
    for bad in ({"csl_overrides": {"ampersand_in_text": ["x"]}},
                {"csl_overrides": {"et_al_use_first": "two"}},
                {"csl_overrides": {"et_al_min": 0}},
                {"csl_overrides": "nope"},
                {"paragraph_style": {"bibliography_hanging_indent_cm": "wide"}},
                {"paragraph_style": {"font_size_pt": -3}}):
        r = client.post("/v1/style-profiles", json={"name": "P", "based_on_csl": "apa", **bad})
        assert r.status_code == 422, bad
    # numbers typed as text in the guided form are still accepted
    ok = client.post("/v1/style-profiles/build", json={"name": "P", "font_size_pt": "11"})
    assert ok.status_code == 200
    assert ok.json()["profile"]["paragraph_style"]["font_size_pt"] == 11


def test_embedding_cache_survives_being_full():
    cache = embedding.CachingEmbedding(embedding.HashingEmbedding(dim=8), max_entries=5)
    first = cache.embed(["a", "b", "c", "d", "e"])
    # 'a' is cached AND needed, but storing five new texts evicts it mid-call
    out = cache.embed(["a", "f", "g", "h", "i", "j"])
    assert out[0] == first[0] and len(out) == 6
    # a single batch larger than the whole cache
    assert len(cache.embed([f"t{i}" for i in range(12)])) == 12


# --------------------------------------------------------------------------- #
# 2. references lost or wrongly merged
# --------------------------------------------------------------------------- #

def test_sparse_reimport_never_wipes_a_complete_record(conn):
    rid = add(conn, "Full paper", 2020, [{"family": "Khan", "given": "A."}],
              doi="10.1/x", abstract="An abstract", container_title="Journal of Things")
    # the same work again, as a bare spreadsheet row: title + DOI only
    again = importer.insert_reference(conn, {"title": "Full paper",
                                             "doi": "https://doi.org/10.1/X"}, [])
    conn.commit()
    assert again == rid
    row = conn.execute("SELECT * FROM reference WHERE id=?", (rid,)).fetchone()
    assert (row["abstract"], row["container_title"], row["year"]) == \
        ("An abstract", "Journal of Things", 2020)
    assert conn.execute("SELECT COUNT(*) c FROM reference_author WHERE reference_id=?",
                        (rid,)).fetchone()["c"] == 1
    # ...while a value the new row DOES supply still wins
    importer.insert_reference(conn, {"title": "Full paper (revised)", "doi": "10.1/x"}, [])
    assert conn.execute("SELECT title FROM reference WHERE id=?",
                        (rid,)).fetchone()["title"] == "Full paper (revised)"


def test_same_generic_title_by_different_authors_is_not_auto_removed(conn):
    add(conn, "Introduction", 2020, [{"family": "Khan", "given": "A."}], container_title="Journal A")
    add(conn, "Introduction", 2020, [{"family": "Smith", "given": "J."}], container_title="Journal B")
    assert documents.find_duplicate_groups(conn) == []
    assert documents.deduplicate_library(conn)["removed"] == 0
    # not lost: it is offered for a human decision instead
    assert documents.library_health(conn)["near_duplicate_count"] == 2


def test_same_title_same_author_different_volume_or_page_is_not_auto_removed(conn):
    who = [{"family": "Editor", "given": "E."}]
    add(conn, "Editorial", 2021, who, volume="12", pages="1-2")
    add(conn, "Editorial", 2021, who, volume="13", pages="1-2")
    add(conn, "Book review", 2021, who, volume="5", pages="10-11")
    add(conn, "Book review", 2021, who, volume="5", pages="40-41")
    assert documents.find_duplicate_groups(conn) == []


def test_bare_reentry_is_still_paired_with_its_full_record(conn):
    full = add(conn, "Mesoscale eddy detection", 2024, [{"family": "Khan", "given": "A."}],
               doi="10.5/eddy", volume="7", pages="1-9")
    add(conn, "Mesoscale Eddy Detection", 2024)          # title + year only
    groups = documents.find_duplicate_groups(conn)
    assert len(groups) == 1 and groups[0]["keep"] == full


def test_unresolvable_doi_is_removed_but_a_failed_lookup_is_not(conn):
    conn.execute("INSERT INTO reference (id,item_type,title) VALUES "
                 "('gone','article-journal','10.1234/doesnotexist'),"
                 "('busy','article-journal','10.1234/ratelimited')")
    conn.commit()

    def fetch(url):
        code = 404 if "doesnotexist" in url else 429
        raise urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(b""))

    r = documents.repair_or_remove_malformed(conn, fetch=fetch)
    assert (r["removed"], r["skipped"], r["repaired"]) == (1, 1, 0)
    left = [x["id"] for x in conn.execute("SELECT id FROM reference")]
    assert left == ["busy"]
    assert "429" in r["details"]["skipped"][0]["reason"]


def test_delete_document_leaves_the_library_alone(client):
    rid = _seed_one(client)
    client.post("/v1/citations", json={"document_id": DOC, "reference_ids": [rid],
                                       "raw_original_text": "(Alpha, 1999)"})
    client.post(f"/v1/documents/{DOC}/scan", json={})
    r = client.delete(f"/v1/documents/{DOC}")
    assert r.status_code == 200 and r.json()["citations"] == 1 and r.json()["flags"] >= 1
    assert client.get(f"/v1/documents/{DOC}/flags").json()["flags"] == []
    assert client.get("/v1/library").json()["total"] == 1
    assert client.delete(f"/v1/documents/{DOC}").json()["deleted"] == 0     # idempotent


def test_import_reports_the_ids_it_created(client):
    r = client.post("/v1/library/import", json={"format": "ris", "text": ONE_PAPER_RIS}).json()
    assert len(r["ids"]) == r["imported"] == 1
    assert client.get("/v1/library").json()["results"][0]["id"] == r["ids"][0]


def test_scan_ignores_citations_no_longer_in_the_document(conn):
    rid = add(conn, "Some paper", 2020, [{"family": "Khan", "given": "A."}])
    cid, _ = documents.create_citation(conn, DOC, [rid], "(Khan, 1999)")
    assert [f["rule_id"] for f in integrity.compute_flags(conn, DOC)] == ["R1_YEAR_MISMATCH"]
    assert [f["rule_id"] for f in integrity.compute_flags(
        conn, DOC, present_control_ids=[cid])] == ["R1_YEAR_MISMATCH"]
    # deleted in Word (its control is gone) -> nothing to report about it
    assert integrity.compute_flags(conn, DOC, present_control_ids=[]) == []


# --------------------------------------------------------------------------- #
# 3. imports that silently dropped or mangled rows
# --------------------------------------------------------------------------- #

def test_ris_with_byte_order_mark_and_alternative_tags():
    text = ("﻿TY  - JOUR\nA1  - Khan, Ali\nT1  - First paper\nJO  - Journal of Things\n"
            "Y1  - 2019///\nUR  - https://doi.org/10.5555/First.1\nER  - \n"
            "TY  - JOUR\nAU  - Shah, B.\nTI  - Second\nJF  - Other Journal\nPY  - 2020\n"
            "SP  - 7\nEP  - 7\nER  - \n")
    recs = [importer.ris_record_to_fields(r) for r in importer.parse_ris(text)]
    assert len(recs) == 2                                   # the BOM hid the first record
    (f1, a1), (f2, a2) = recs
    assert (f1["title"], f1["container_title"], f1["year"]) == ("First paper", "Journal of Things", 2019)
    assert a1 == [{"family": "Khan", "given": "Ali"}]
    assert f1["doi"] == "10.5555/first.1"
    assert (f2["container_title"], f2["pages"]) == ("Other Journal", "7")


def test_bibtex_housekeeping_entries_and_latex_conventions():
    text = ('@string{jgr = "J. Geophys. Res., A"}\n@preamble{"\\newcommand{\\x}{y}, z"}\n'
            "@article{k, title={Real}, author={Smith, J. AND Lee, K. and others}, "
            "pages={12--34}, year=2020}")
    entries = importer.parse_bibtex(text)
    assert [e["entry_type"] for e in entries] == ["article"]
    fields, authors = importer.bibtex_entry_to_fields(entries[0])
    assert fields["pages"] == "12-34"
    assert authors == [{"family": "Smith", "given": "J."}, {"family": "Lee", "given": "K."}]


def test_typed_list_accepts_other_numbering_and_plain_lists():
    refs = ["Khan, A. (2020). A paper. Journal.", "Shah, B. (2019). Another. J.",
            "Ali, C. (2018). Third. J."]
    for style in ("{n}. {r}", "{n}) {r}", "[{n}] {r}", "({n}) {r}"):
        text = "\n".join(style.format(n=i + 1, r=r) for i, r in enumerate(refs))
        assert importer.split_typed_list(text) == refs, style
    # nothing numbered at all -> one reference per line (heading dropped)
    assert importer.split_typed_list("References\n\n" + "\n".join(refs)) == refs
    # a numbered list still skips its un-numbered heading/notes, as before
    assert importer.split_typed_list("My reading list\n1. " + refs[0]) == [refs[0]]


def test_csv_saved_by_excel_imports():
    bom = list_import.parse_csv("﻿title,authors,year\nPaper one,Khan A,2020\n")
    semi = list_import.parse_csv("title;authors;year\nPaper one;Khan, A.;2020\n")
    tab = list_import.parse_csv("title\tauthors\tyear\nPaper one\tKhan, A.\t2020\n")
    for rows in (bom, semi, tab):
        assert len(rows) == 1 and rows[0][0]["title"] == "Paper one" and rows[0][0]["year"] == 2020
    assert semi[0][1] == [{"family": "Khan", "given": "A."}]
    # a comma inside a quoted title must not be mistaken for the separator
    quoted = list_import.parse_csv('title,year\n"Cities, rivers; and roads",2021\n')
    assert quoted[0][0]["title"] == "Cities, rivers; and roads"


@pytest.mark.parametrize("cell,expected", [
    ("Smith, J., Jones, K., & Lee, M.",
     [{"family": "Smith", "given": "J."}, {"family": "Jones", "given": "K."},
      {"family": "Lee", "given": "M."}]),
    ("van der Berg, J. P., Khan, A.",
     [{"family": "van der Berg", "given": "J. P."}, {"family": "Khan", "given": "A."}]),
    ("John Smith, Jane Doe, Ali Raza Khan",
     [{"family": "Smith", "given": "John"}, {"family": "Doe", "given": "Jane"},
      {"literal": "Ali Raza Khan"}]),
    ("Smith, John; Doe, Jane",                           # unchanged behaviour
     [{"family": "Smith", "given": "John"}, {"family": "Doe", "given": "Jane"}]),
    ("Khan, Ali",                                        # a lone 'Family, Given' stays one author
     [{"family": "Khan", "given": "Ali"}]),
    ("Ali Khan and Sara Ahmed et al.",
     [{"family": "Khan", "given": "Ali"}, {"family": "Ahmed", "given": "Sara"}]),
])
def test_author_cells_as_people_actually_type_them(cell, expected):
    assert list_import._split_authors(cell) == expected


def test_excel_whole_numbers_do_not_grow_a_decimal_point():
    fields, _ = list_import._row_to_fields({"title": "T", "volume": 12.0, "issue": 3.0,
                                            "year": 2020.0, "pages": "  "})
    assert (fields["volume"], fields["issue"], fields["year"]) == ("12", "3", 2020)
    assert "pages" not in fields


def test_handbook_reads_whole_numbers():
    form = handbook.detect_rules(
        "All margins must be 25 mm. Use a hanging indent of 12.7 mm.")["form"]
    assert (form["margin_cm"], form["hanging_indent_cm"]) == (2.5, 1.27)
    form = handbook.detect_rules("Margins of 1.5 inches on the left.")["form"]
    assert form["margin_cm"] == 3.81


def test_crossref_organisation_author_is_kept():
    _, authors = resolver.crossref_message_to_fields({
        "title": ["Annual report"], "author": [{"name": "Global Standards Consortium"},
                                               {"family": "Khan", "given": "A."}]})
    assert authors == [{"literal": "Global Standards Consortium"},
                       {"family": "Khan", "given": "A."}]


# --------------------------------------------------------------------------- #
# 4. the "and" / "&" setting, and bilingual (Urdu) handling
# --------------------------------------------------------------------------- #

TWO_AUTHORS = [{"id": "x", "type": "article-journal", "title": "A framework",
                "container-title": "Journal", "issued": {"date-parts": [[2016]]},
                "author": [{"family": "Nguyen", "given": "Linh"},
                           {"family": "Ortega", "given": "Pablo"}]}]


def test_builder_checkbox_and_in_text_but_ampersand_in_list():
    """Exactly what the desktop app's style builder sends when the box is
    ticked. It used to change nothing at all."""
    profile = sp.build_profile({"name": "P", "ampersand_in_text": False,
                                "ampersand_in_bibliography": True})
    fmt = formatter.Formatter(TWO_AUTHORS, profile)
    assert fmt.render_citation(["x"]) == "(Nguyen and Ortega, 2016)"
    assert "& Ortega" in fmt.render_bibliography()[0]


def test_ampersand_the_other_way_round_and_left_alone():
    bib_only = sp.build_profile({"name": "P", "ampersand_in_text": True,
                                 "ampersand_in_bibliography": False})
    fmt = formatter.Formatter(TWO_AUTHORS, bib_only)
    assert fmt.render_citation(["x"]) == "(Nguyen & Ortega, 2016)"
    assert "and Ortega" in fmt.render_bibliography()[0]
    # both True (the builder's default) leaves the style's own choice untouched
    untouched = sp.patch_csl_style("apa", {"ampersand_in_text": True,
                                           "ampersand_in_bibliography": True})
    import citeproc_styles
    original = Path(citeproc_styles.get_style_filepath("apa")).read_text(encoding="utf-8")
    patched = Path(untouched).read_text(encoding="utf-8")
    assert patched.count('and="symbol"') == original.count('and="symbol"') > 0
    assert patched.count('and="text"') == original.count('and="text"')


URDU_A = "اردو ادب کی تاریخ 2020"            # "History of Urdu literature 2020"
URDU_B = "پاکستان میں تعلیم 2020"            # "Education in Pakistan 2020"


def test_different_urdu_titles_are_not_duplicates(conn):
    """An ASCII-only filter reduced both titles to just "2020", so two different
    Urdu works looked identical and 'Remove duplicates' would delete one."""
    assert importer.normalize_title(URDU_A) != importer.normalize_title(URDU_B)
    assert importer.normalize_title(URDU_A) != "2020"
    add(conn, URDU_A, 2020)
    add(conn, URDU_B, 2020)
    assert documents.find_duplicate_groups(conn) == []
    assert documents.library_health(conn)["near_duplicate_count"] == 0


def test_the_same_urdu_title_twice_is_still_caught(conn):
    full = add(conn, URDU_A, 2020, [{"family": "خان", "given": "ا"}], doi="10.9/urdu")
    add(conn, URDU_A, 2020)
    groups = documents.find_duplicate_groups(conn)
    assert len(groups) == 1 and groups[0]["keep"] == full
    assert integrity._title_similarity(URDU_A, URDU_A) == 1.0
    assert integrity._title_similarity(URDU_A, URDU_B) < integrity.R6_TITLE_SIMILARITY_THRESHOLD


def test_title_normalisation_is_unchanged_for_english():
    assert importer.normalize_title("Mesoscale Eddy Detection From <scp>SST</scp> Maps!") == \
        "mesoscale eddy detection from sst maps"


def test_urdu_sentence_citing_a_matching_urdu_source_is_not_flagged(conn):
    rid = add(conn, "پاکستان میں شہری پانی کا انتظام", 2020, [{"family": "خان", "given": "ا"}])
    cid, _ = documents.create_citation(conn, DOC, [rid])
    flags = integrity.compute_flags(
        conn, DOC, contexts={cid: "پاکستان میں شہری پانی کا انتظام ایک اہم مسئلہ ہے"},
        embedder=embedding.HashingEmbedding())
    assert flags == []


def test_urdu_sentence_about_something_else_is_still_flagged(conn):
    rid = add(conn, "پاکستان میں شہری پانی کا انتظام", 2020, [{"family": "خان", "given": "ا"}])
    cid, _ = documents.create_citation(conn, DOC, [rid])
    flags = integrity.compute_flags(
        conn, DOC, contexts={cid: "مغل دور کی فن تعمیر اور باغات کی تاریخ"},
        embedder=embedding.HashingEmbedding())
    assert [f["rule_id"] for f in flags] == ["R8_CONTEXT_MISALIGNMENT"]


def test_word_overlap_check_gives_no_opinion_across_scripts(conn):
    """The lexical fallback compares shared words, so it cannot judge an Urdu
    sentence against an English source -- it must stay silent, not flag it."""
    rid = add(conn, "Urban water management in Pakistan", 2020, [{"family": "Khan", "given": "A."}])
    cid, _ = documents.create_citation(conn, DOC, [rid])
    flags = integrity.compute_flags(
        conn, DOC, contexts={cid: "پاکستان میں شہری پانی کا انتظام ایک اہم مسئلہ ہے"},
        embedder=embedding.HashingEmbedding())
    assert flags == []
    # ...and a sentence with no words at all is not judged either
    assert integrity.compute_flags(conn, DOC, contexts={cid: "— … —"},
                                   embedder=embedding.HashingEmbedding()) == []


# --------------------------------------------------------------------------- #
# 5. the Word add-in: never replace the author's highlighted text
# --------------------------------------------------------------------------- #

TASKPANE = (Path(__file__).resolve().parent.parent / "connectors" / "word"
            / "taskpane.js").read_text(encoding="utf-8")


def test_addin_never_wraps_the_live_selection():
    """insertContentControl() on the selection itself wraps whatever the author
    has highlighted; filling the control then REPLACES those words. Every
    control must be created on a collapsed range at the end of the selection."""
    assert not re.search(r"getSelection\s*\(\s*\)\s*\.\s*insertContentControl", TASKPANE)
    created = re.findall(r"[^;\n]*\.insertContentControl\s*\(", TASKPANE)
    assert created and all('getRange("End")' in line for line in created)


def test_addin_does_not_wipe_a_list_when_the_library_does_not_match():
    # the empty-list branch must check the document really has no citations left
    assert "present.length" in TASKPANE.split("if (!entries.length)")[1].split("try {")[0]
