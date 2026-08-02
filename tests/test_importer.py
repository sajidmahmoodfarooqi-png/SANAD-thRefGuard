import json

from sanad_core import db, importer

# --------------------------------------------------------------------------- #
# Small, hand-built, invented inputs -- exercise specific parsing edge cases
# directly. None of this is real-world bibliography data.
# --------------------------------------------------------------------------- #

SAMPLE_RIS = """TY  - BOOK
AU  - Fisher, R. K.
TI  - The Art of Memory
PY  - 2001
PB  - Chandler Press
ER  -
TY  - JOUR
AU  - Nguyen, Linh
AU  - Ortega, Pablo M.
TI  - A framework for distributed caching
T2  - Journal of Systems Engineering
PY  - 2016
VL  - 262
SP  - 101
EP  - 111
DO  - 10.1234/jse.2016.014
ER  -
TY  - GEN
AU  - Global Standards Consortium
TI  - Annual Review of Practice
PY  - 2003
ER  -
"""

SAMPLE_BIBTEX = """
@book{Rowe_2013,
  title={Principles of Typography},
  author={Rowe, Thomas},
  year={2013},
  publisher={Chandler Press}
}

@article{Test_2020,
  title={A study of {NASA} data and its {uses}},
  author={Smith, John and Doe, Jane},
  journal={Journal of Testing},
  year={2020},
  volume={5},
  number={2},
  pages={10--20}
}
"""

TYPED_LIST = """1. Rowe, T. (2014). A short history of the printing press. Journal of Print Studies, 1(6), 193-207.
2. Bell, A., Carter, M. (2003). Notes on manuscript preservation. Archival Quarterly, 44(2), 219-231.
"""


def test_parse_person_name_family_comma_given():
    assert importer.parse_person_name("Fisher, R. K.") == {"family": "Fisher", "given": "R. K."}


def test_parse_person_name_given_family_no_comma():
    assert importer.parse_person_name("John Smith") == {"family": "Smith", "given": "John"}


def test_parse_person_name_corporate_heuristic():
    result = importer.parse_person_name("Global Standards Consortium")
    assert result == {"literal": "Global Standards Consortium"}


def test_parse_ris_produces_three_records():
    records = importer.parse_ris(SAMPLE_RIS)
    assert len(records) == 3


def test_ris_book_type_and_year():
    records = importer.parse_ris(SAMPLE_RIS)
    fields, authors = importer.ris_record_to_fields(records[0])
    assert fields["item_type"] == "book"
    assert fields["year"] == 2001
    assert authors == [{"family": "Fisher", "given": "R. K."}]


def test_ris_page_range_from_sp_ep():
    records = importer.parse_ris(SAMPLE_RIS)
    fields, _ = importer.ris_record_to_fields(records[1])
    assert fields["pages"] == "101-111"


def test_ris_gen_type_maps_to_safe_fallback():
    records = importer.parse_ris(SAMPLE_RIS)
    fields, _ = importer.ris_record_to_fields(records[2])
    assert fields["item_type"] == "article-journal"  # documented GEN fallback


def test_parse_bibtex_handles_nested_braces_in_title():
    entries = importer.parse_bibtex(SAMPLE_BIBTEX)
    test_entry = next(e for e in entries if e["key"] == "Test_2020")
    # inner protective braces {NASA}/{uses} must be stripped, not left dangling
    assert "{" not in test_entry["fields"]["title"]
    assert "NASA" in test_entry["fields"]["title"]


def test_parse_bibtex_two_entries():
    entries = importer.parse_bibtex(SAMPLE_BIBTEX)
    assert len(entries) == 2


def test_bibtex_entry_to_fields_authors_split_on_and():
    entries = importer.parse_bibtex(SAMPLE_BIBTEX)
    test_entry = next(e for e in entries if e["key"] == "Test_2020")
    fields, authors = importer.bibtex_entry_to_fields(test_entry)
    assert authors == [
        {"family": "Smith", "given": "John"},
        {"family": "Doe", "given": "Jane"},
    ]
    assert fields["container_title"] == "Journal of Testing"


def test_parse_typed_reference_recovers_author_and_year():
    fields, authors = importer.parse_typed_reference(
        "Bell, A., Carter, M. (2003). Notes on manuscript preservation. "
        "Archival Quarterly, 44(2), 219-231."
    )
    assert fields["year"] == 2003
    assert authors == [
        {"family": "Bell", "given": "A."},
        {"family": "Carter", "given": "M."},
    ]
    assert fields["confidence"] < 1.0  # never fully trusted, by design


def test_split_typed_list():
    refs = importer.split_typed_list(TYPED_LIST)
    assert len(refs) == 2
    assert refs[0].startswith("Rowe, T.")


def test_import_ris_text_end_to_end():
    conn = db.connect()
    ids = importer.import_ris_text(conn, SAMPLE_RIS)
    assert len(ids) == 3
    count = conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"]
    assert count == 3


def test_doi_dedup_on_reimport():
    conn = db.connect()
    importer.import_ris_text(conn, SAMPLE_RIS)
    importer.import_ris_text(conn, SAMPLE_RIS)  # import the same text again
    count = conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"]
    assert count == 3  # not 6 -- deduped via DOI (Nguyen) and content-sig fallback
    # the DOI-bearing record specifically must still be exactly one row
    doi_count = conn.execute(
        "SELECT COUNT(*) c FROM reference WHERE doi = ?",
        ("10.1234/jse.2016.014",),
    ).fetchone()["c"]
    assert doi_count == 1


def test_content_signature_merges_only_case_differences():
    """Two records identical apart from letter case ARE the same work and
    must collapse."""
    conn = db.connect()
    a = ("TY  - BOOK\nAU  - Global Standards Consortium\nTI  - Annual Standards Report 2012\n"
         "PY  - 2012\nER  -\n")
    b = ("TY  - BOOK\nAU  - Global Standards Consortium\nTI  - annual standards report 2012\n"
         "PY  - 2012\nER  -\n")
    importer.import_ris_text(conn, a + b)
    assert conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"] == 1


def test_content_signature_does_not_merge_different_works_sharing_a_title():
    """The generic-corporate-title failure case: two genuinely different reports
    from the same body in the same year, whose parsed title is the same generic
    string, must NOT be silently merged. They are disambiguated by year_suffix
    (a vs b) and container, so their content signatures differ. This is the exact
    false-merge SANAD exists to prevent; if this test ever fails, import-time
    dedup has become unsafe."""
    conn = db.connect()
    fields_a = {"item_type": "report", "title": "Annual standards report",
                "year": 2005, "year_suffix": "a",
                "container_title": "Annual Standards Report: Part One"}
    fields_b = {"item_type": "report", "title": "Annual standards report",
                "year": 2005, "year_suffix": "b",
                "container_title": "Annual Standards Report: Part Two"}
    corp = [{"literal": "Global Standards Consortium"}]
    importer.insert_reference(conn, fields_a, corp)
    importer.insert_reference(conn, fields_b, corp)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"] == 2


def test_csl_json_stored_is_valid_json_with_expected_shape():
    conn = db.connect()
    importer.import_ris_text(conn, SAMPLE_RIS)
    row = conn.execute(
        "SELECT csl_json FROM reference WHERE title LIKE '%Art of Memory%'"
    ).fetchone()
    item = json.loads(row["csl_json"])
    assert item["type"] == "book"
    assert item["issued"]["date-parts"] == [[2001]]
    assert item["author"] == [{"family": "Fisher", "given": "R. K."}]


# --- DOI normalisation + duplicate detection across DOI forms --------------- #

def test_normalize_doi_strips_prefixes_and_lowercases():
    n = importer.normalize_doi
    canon = "10.1016/j.landusepol.2020.104493"
    assert n("10.1016/j.landusepol.2020.104493") == canon
    assert n("https://doi.org/10.1016/J.LANDUSEPOL.2020.104493") == canon
    assert n("http://dx.doi.org/10.1016/j.landusepol.2020.104493") == canon
    assert n("doi: 10.1016/J.Landusepol.2020.104493") == canon
    assert n("  10.1016/j.landusepol.2020.104493.  ".strip() + ".") == canon  # trailing dot
    assert n("") is None and n(None) is None


def test_doi_normalised_at_import_so_url_form_dedupes_in_place():
    conn = db.connect()
    # same DOI, one bare and one as a doi.org URL in a different case
    importer.insert_reference(conn, {"title": "Same work", "year": 2020,
                                     "doi": "10.1/abc"}, [{"family": "A"}])
    importer.insert_reference(conn, {"title": "Same work (other pages)", "year": 2020,
                                     "doi": "https://doi.org/10.1/ABC"}, [{"family": "A"}])
    conn.commit()
    # collapsed to one row, stored DOI is the canonical bare lowercase form
    rows = conn.execute("SELECT doi FROM reference").fetchall()
    assert len(rows) == 1
    assert rows[0]["doi"] == "10.1/abc"


def test_detection_catches_preexisting_rawdoi_duplicates():
    from sanad_core import documents
    conn = db.connect()
    # simulate rows created by the OLD importer: same DOI, three raw forms
    for i, doi in enumerate(("10.5/x", "https://doi.org/10.5/X", "doi:10.5/x")):
        conn.execute("INSERT INTO reference (id,item_type,title,doi,content_sig,"
                     "created_at,updated_at,csl_json) VALUES (?,?,?,?,?,?,?,?)",
                     (f"r{i}", "article-journal", "Work", doi, f"sig{i}",
                      f"2020-01-0{i+1}", f"2020-01-0{i+1}", "{}"))
    conn.commit()
    groups = documents.find_duplicate_groups(conn)
    assert sum(len(g["remove"]) for g in groups) == 2      # 3 copies -> 2 removable
    documents.deduplicate_library(conn)
    kept = conn.execute("SELECT doi FROM reference").fetchall()
    assert len(kept) == 1
    assert kept[0]["doi"] == "10.5/x"                       # keeper canonicalised


# --- near-duplicate detection: same title + year, DOI on one copy only ------ #

def _raw_ref(conn, rid, title, year, doi, sig, created, authors=0):
    conn.execute("INSERT INTO reference (id,item_type,title,year,doi,content_sig,"
                 "created_at,updated_at,csl_json) VALUES (?,?,?,?,?,?,?,?,?)",
                 (rid, "article-journal", title, year, doi, sig, created, created, "{}"))
    for i in range(authors):
        aid = f"{rid}-a{i}"
        conn.execute("INSERT INTO author (id,family,given) VALUES (?,?,?)", (aid, f"Fam{i}", "X"))
        conn.execute("INSERT INTO reference_author (reference_id,author_id,position) "
                     "VALUES (?,?,?)", (rid, aid, i))
    conn.commit()


def test_near_duplicate_same_title_year_is_detected_keeping_richest():
    from sanad_core import documents
    conn = db.connect()
    # full record (DOI + 3 authors) vs a bare re-entry (no DOI, no authors),
    # titles differ only by case/markup -> must pair, keeping the full one
    _raw_ref(conn, "full", "Mesoscale Eddy Detection From <scp>SST</scp> Maps", 2024,
             "10.1109/x", "sigA", "2024-01-02", authors=3)
    _raw_ref(conn, "bare", "Mesoscale eddy detection from sst maps", 2024,
             None, "sigB", "2024-01-01", authors=0)
    groups = documents.find_duplicate_groups(conn)
    assert sum(len(g["remove"]) for g in groups) == 1
    g = groups[0]
    assert g["keep"] == "full" and g["remove"] == ["bare"]   # richer copy kept


def test_conflicting_dois_same_title_year_are_left_alone():
    from sanad_core import documents
    conn = db.connect()
    # same title+year but two DIFFERENT DOIs -> genuinely distinct (e.g. erratum)
    _raw_ref(conn, "a", "A shared exact title", 2024, "10.1/aaa", "s1", "2024-01-01")
    _raw_ref(conn, "b", "A shared exact title", 2024, "10.2/bbb", "s2", "2024-01-02")
    assert documents.find_duplicate_groups(conn) == []       # not merged


def test_same_title_different_year_is_not_a_duplicate():
    from sanad_core import documents
    conn = db.connect()
    _raw_ref(conn, "y1", "Annual survey of the field", 2023, None, "s1", "2024-01-01")
    _raw_ref(conn, "y2", "Annual survey of the field", 2024, None, "s2", "2024-01-02")
    assert documents.find_duplicate_groups(conn) == []       # different years -> distinct


# --- malformed bare-DOI/number title guard (real cases from a user's library) - #

def test_bare_doi_or_number_titles_with_no_author_are_rejected():
    conn = db.connect()
    bad_titles = [
        ".1109/JSTARS.2024.3402823",
        ".1007/s11277-018-6024-7",
        "/10.3390/su14052810",
        "0078",
        "512149",
    ]
    for t in bad_titles:
        rid = importer.insert_reference(conn, {"title": t, "year": 2024}, [])
        assert rid is None, f"expected {t!r} to be rejected"
    conn.commit()
    assert conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"] == 0


def test_legitimate_short_or_numeric_looking_titles_are_not_rejected():
    conn = db.connect()
    # a real title never has these shapes rejected: has a space, or has an author
    rid1 = importer.insert_reference(conn, {"title": "COVID-19 response", "year": 2020}, [])
    rid2 = importer.insert_reference(conn, {"title": "0078", "year": 2019},
                                     [{"family": "Smith"}])   # numeric title, but has an author
    conn.commit()
    assert rid1 is not None and rid2 is not None
    assert conn.execute("SELECT COUNT(*) c FROM reference").fetchone()["c"] == 2


def test_ris_import_skips_malformed_records_without_failing_the_whole_import():
    conn = db.connect()
    ris = """TY  - JOUR
TI  - .1109/JSTARS.2024.3402823
PY  - 2024
ER  -

TY  - JOUR
TI  - A genuine paper title with real content
AU  - Real, Author
PY  - 2023
ER  -
"""
    ids = importer.import_ris_text(conn, ris)
    assert len(ids) == 1   # the malformed record was skipped, not the whole import
    row = conn.execute("SELECT title FROM reference").fetchone()
    assert row["title"] == "A genuine paper title with real content"
