"""Unit tests for the Tier-A integrity engine (MVP_SPEC.md §4).

Each rule is exercised with a seeded library + citations through the same
storage path the live service uses (importer.insert_reference +
documents.create_citation), not hand-built dicts -- so a schema/rendering
mismatch surfaces here rather than in production. All sample data is invented.
"""
import pytest

from sanad_core import db, documents, embedding, integrity, importer

DOC = "doc-1"


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def add_ref(conn, title, *, year=None, year_suffix=None, item_type="article-journal",
            container_title=None, authors=None, doi=None, abstract=None):
    fields = {"title": title, "year": year, "year_suffix": year_suffix,
              "item_type": item_type, "container_title": container_title, "doi": doi,
              "abstract": abstract}
    a = [{"family": f} if isinstance(f, str) else f for f in (authors or [])]
    rid = importer.insert_reference(conn, fields, a)
    conn.commit()
    return rid


def cite(conn, reference_ids, raw=None, document_id=DOC):
    cid, _ = documents.create_citation(conn, document_id, reference_ids, raw)
    return cid


def rules_fired(flags):
    return {f["rule_id"] for f in flags}


# --- R1: year mismatch ----------------------------------------------------- #

def test_r1_flags_year_mismatch(conn):
    rid = add_ref(conn, "The Art of Memory", year=2001, authors=["Fisher"])
    cite(conn, [rid], raw="(Fisher, 1998)")
    flags = integrity.compute_flags(conn, DOC)
    r1 = [f for f in flags if f["rule_id"] == "R1_YEAR_MISMATCH"]
    assert len(r1) == 1
    assert r1[0]["severity"] == "warning"
    assert r1[0]["suggestion"]["reference_year"] == 2001


def test_r1_silent_when_year_matches(conn):
    rid = add_ref(conn, "The Art of Memory", year=2001, authors=["Fisher"])
    cite(conn, [rid], raw="(Fisher, 2001)")
    assert "R1_YEAR_MISMATCH" not in rules_fired(integrity.compute_flags(conn, DOC))


def test_r1_normalizes_letter_suffix(conn):
    rid = add_ref(conn, "Annual Review of Practice", year=2005,
                  year_suffix="a", authors=[{"literal": "Global Standards Consortium"}])
    cite(conn, [rid], raw="(Global Standards Consortium, 2005a)")
    assert "R1_YEAR_MISMATCH" not in rules_fired(integrity.compute_flags(conn, DOC))


# --- R2: venue/type sanity ------------------------------------------------- #

def test_r2_flags_review_venue(conn):
    rid = add_ref(conn, "A History of Clockmaking", item_type="book",
                  container_title="Choice Reviews Online", authors=["Webb"])
    cite(conn, [rid], raw="(Webb, 2010)")
    r2 = [f for f in integrity.compute_flags(conn, DOC) if f["rule_id"] == "R2_VENUE_TYPE_SANITY"]
    assert len(r2) == 1 and r2[0]["severity"] == "error"


def test_r2_flags_monograph_with_generic_review_venue(conn):
    rid = add_ref(conn, "Some monograph", item_type="book",
                  container_title="Contemporary Sociology: A Journal of Reviews",
                  authors=["Author"])
    cite(conn, [rid], raw="(Author, 2015)")
    assert "R2_VENUE_TYPE_SANITY" in rules_fired(integrity.compute_flags(conn, DOC))


def test_r2_silent_on_legitimate_review_journal(conn):
    # a real journal whose name contains "Review" must NOT be flagged
    rid = add_ref(conn, "Stellar spectra classification", item_type="article-journal",
                  container_title="Annual Review of Astronomy and Astrophysics",
                  authors=["Park"])
    cite(conn, [rid], raw="(Park, 2004)")
    assert "R2_VENUE_TYPE_SANITY" not in rules_fired(integrity.compute_flags(conn, DOC))


# --- R3 / R4: orphans and cited-not-listed --------------------------------- #

def test_r3_flags_all_unresolved_citation(conn):
    cite(conn, ["ghost-ref-id"], raw="(Nobody, 2000)")
    flags = integrity.compute_flags(conn, DOC)
    assert "R3_ORPHANED_CITATION" in rules_fired(flags)
    # a wholly-dead citation is R3's job, not R4's
    assert "R4_CITED_NOT_LISTED" not in rules_fired(flags)


def test_r3_flags_present_control_with_no_record(conn):
    rid = add_ref(conn, "Real work", year=2020, authors=["Real"])
    cite(conn, [rid], raw="(Real, 2020)")
    flags = integrity.compute_flags(conn, DOC, present_control_ids=["stray-control-uuid"])
    r3 = [f for f in flags if f["rule_id"] == "R3_ORPHANED_CITATION"]
    assert any(f["citation_id"] == "stray-control-uuid" for f in r3)


def test_r4_flags_one_dead_ref_in_a_live_group(conn):
    good = add_ref(conn, "Good work", year=2019, authors=["Good"])
    cite(conn, [good, "ghost-ref-id"], raw="(Good, 2019; Ghost, 2000)")
    flags = integrity.compute_flags(conn, DOC)
    assert "R4_CITED_NOT_LISTED" in rules_fired(flags)
    assert "R3_ORPHANED_CITATION" not in rules_fired(flags)  # the group still renders


# --- R5: listed but not cited ---------------------------------------------- #

def test_r5_only_with_listed_set(conn):
    cited = add_ref(conn, "Cited work", year=2018, authors=["Cited"])
    listed_only = add_ref(conn, "Never cited work", year=2017, authors=["Lonely"])
    cite(conn, [cited], raw="(Cited, 2018)")

    # no listed set -> SANAD's generated bibliography can't diverge -> nothing
    assert "R5_LISTED_NOT_CITED" not in rules_fired(integrity.compute_flags(conn, DOC))
    # with a legacy listed set -> the uncited one surfaces
    flags = integrity.compute_flags(conn, DOC,
                                    listed_reference_ids=[cited, listed_only])
    r5 = [f for f in flags if f["rule_id"] == "R5_LISTED_NOT_CITED"]
    assert len(r5) == 1 and r5[0]["suggestion"]["reference_id"] == listed_only
    assert r5[0]["severity"] == "info"


# --- R6: duplicate references ---------------------------------------------- #

def test_r6_flags_near_identical_titles(conn):
    a = add_ref(conn, "Global surface temperature records from 1900 to 2000",
                year=2013, authors=["Stone"])
    b = add_ref(conn, "Global surface temperature records from 1900 to 2000 revised",
                year=2014, authors=["Stone"])
    cite(conn, [a], raw="(Stone, 2013)")
    cite(conn, [b], raw="(Stone, 2014)")
    r6 = [f for f in integrity.compute_flags(conn, DOC) if f["rule_id"] == "R6_DUPLICATE_REFERENCE"]
    assert len(r6) == 1
    assert set(r6[0]["suggestion"]["reference_ids"]) == {a, b}


def test_r6_silent_on_distinct_titles(conn):
    a = add_ref(conn, "Principles of typography", year=2004, authors=["Rowe"])
    b = add_ref(conn, "A short history of the printing press", year=2016, authors=["Bell"])
    cite(conn, [a], raw="(Rowe, 2004)")
    cite(conn, [b], raw="(Bell, 2016)")
    assert "R6_DUPLICATE_REFERENCE" not in rules_fired(integrity.compute_flags(conn, DOC))


# --- R7: author-year ambiguity --------------------------------------------- #

def test_r7_flags_shared_author_year_without_suffix(conn):
    a = add_ref(conn, "First Park study on memory", year=2019, authors=["Park"])
    b = add_ref(conn, "Second Park study on recall", year=2019, authors=["Park"])
    cite(conn, [a], raw="(Park, 2019)")
    cite(conn, [b], raw="(Park, 2019)")
    r7 = [f for f in integrity.compute_flags(conn, DOC) if f["rule_id"] == "R7_AUTHOR_YEAR_AMBIGUITY"]
    assert len(r7) == 1
    assert set(r7[0]["suggestion"]["reference_ids"]) == {a, b}


def test_r7_silent_when_suffixes_disambiguate(conn):
    a = add_ref(conn, "First Park study on memory", year=2019, year_suffix="a", authors=["Park"])
    b = add_ref(conn, "Second Park study on recall", year=2019, year_suffix="b", authors=["Park"])
    cite(conn, [a], raw="(Park, 2019a)")
    cite(conn, [b], raw="(Park, 2019b)")
    assert "R7_AUTHOR_YEAR_AMBIGUITY" not in rules_fired(integrity.compute_flags(conn, DOC))


# --- R8: Tier-B semantic context misalignment ------------------------------ #

# an oceanography source and an unrelated finance source, each with an abstract
# so the embedding has real topic signal to compare against.
TIDE_TITLE = "Tides and the lunar cycle"
TIDE_ABSTRACT = ("Coastal water levels rise and fall with the moon's gravitational "
                 "pull across the lunar month along open shorelines.")
FINANCE_TITLE = "Consumer credit and interest rates"
FINANCE_ABSTRACT = ("Central bank interest rate decisions affect inflation and "
                    "lending in the commercial banking sector.")

# a sentence clearly about tides/the moon, not about finance
TIDE_SENTENCE = ("The rise and fall of coastal water levels follows the moon's "
                 "gravitational pull across the month.")


def test_r8_flags_off_topic_citation_and_suggests_better_source(conn):
    tide = add_ref(conn, TIDE_TITLE, year=2015, authors=["Marsh"], abstract=TIDE_ABSTRACT)
    finance = add_ref(conn, FINANCE_TITLE, year=2018, authors=["Frost"], abstract=FINANCE_ABSTRACT)
    # cite the FINANCE paper from a TIDE sentence -- the misattribution
    cid = cite(conn, [finance], raw="(Frost, 2018)")

    flags = integrity.compute_flags(conn, DOC, contexts={cid: TIDE_SENTENCE},
                                    embedder=embedding.HashingEmbedding())
    r8 = [f for f in flags if f["rule_id"] == "R8_CONTEXT_MISALIGNMENT"]
    assert len(r8) == 1
    assert r8[0]["tier"] == "B"
    alt_ids = [a["reference_id"] for a in r8[0]["suggestion"]["alternatives"]]
    assert tide in alt_ids           # the on-topic paper is offered as the fix


def test_r8_silent_when_citation_is_on_topic(conn):
    tide = add_ref(conn, TIDE_TITLE, year=2015, authors=["Marsh"], abstract=TIDE_ABSTRACT)
    add_ref(conn, FINANCE_TITLE, year=2018, authors=["Frost"], abstract=FINANCE_ABSTRACT)
    cid = cite(conn, [tide], raw="(Marsh, 2015)")

    flags = integrity.compute_flags(conn, DOC, contexts={cid: TIDE_SENTENCE},
                                    embedder=embedding.HashingEmbedding())
    assert "R8_CONTEXT_MISALIGNMENT" not in rules_fired(flags)


def test_r8_does_not_run_without_contexts_or_embedder(conn):
    finance = add_ref(conn, FINANCE_TITLE, year=2018, authors=["Frost"], abstract=FINANCE_ABSTRACT)
    cid = cite(conn, [finance], raw="(Frost, 2018)")
    # no embedder -> Tier-B is skipped entirely
    assert "R8_CONTEXT_MISALIGNMENT" not in rules_fired(
        integrity.compute_flags(conn, DOC, contexts={cid: TIDE_SENTENCE}))
    # no contexts -> a semantic check with nothing to read stays silent
    assert "R8_CONTEXT_MISALIGNMENT" not in rules_fired(
        integrity.compute_flags(conn, DOC, embedder=embedding.HashingEmbedding()))


def test_r8_persists_and_respects_dismissal(conn):
    finance = add_ref(conn, FINANCE_TITLE, year=2018, authors=["Frost"], abstract=FINANCE_ABSTRACT)
    add_ref(conn, TIDE_TITLE, year=2015, authors=["Marsh"], abstract=TIDE_ABSTRACT)
    cid = cite(conn, [finance], raw="(Frost, 2018)")
    emb = embedding.HashingEmbedding()

    flags = integrity.scan(conn, DOC, contexts={cid: TIDE_SENTENCE}, embedder=emb)
    r8 = next(f for f in flags if f["rule_id"] == "R8_CONTEXT_MISALIGNMENT")
    assert integrity.set_flag_status(conn, r8["id"], "dismissed") is True

    after = integrity.scan(conn, DOC, contexts={cid: TIDE_SENTENCE}, embedder=emb)
    r8s = [f for f in after if f["rule_id"] == "R8_CONTEXT_MISALIGNMENT"]
    assert len(r8s) == 1 and r8s[0]["status"] == "dismissed"


# --- persistence + dismissed-flag suppression ------------------------------ #

def test_scan_persists_and_lists_flags(conn):
    rid = add_ref(conn, "The Art of Memory", year=2001, authors=["Fisher"])
    cite(conn, [rid], raw="(Fisher, 1998)")
    flags = integrity.scan(conn, DOC)
    assert any(f["rule_id"] == "R1_YEAR_MISMATCH" and f["status"] == "open" for f in flags)
    # a persisted flag carries a real id + document scope
    assert all(f["id"] and f["document_id"] == DOC for f in flags)


def test_rescan_does_not_resurrect_a_dismissed_flag(conn):
    rid = add_ref(conn, "The Art of Memory", year=2001, authors=["Fisher"])
    cite(conn, [rid], raw="(Fisher, 1998)")
    flags = integrity.scan(conn, DOC)
    r1 = next(f for f in flags if f["rule_id"] == "R1_YEAR_MISMATCH")

    assert integrity.set_flag_status(conn, r1["id"], "dismissed") is True

    after = integrity.scan(conn, DOC)
    r1s = [f for f in after if f["rule_id"] == "R1_YEAR_MISMATCH"]
    assert len(r1s) == 1                      # not resurrected as a second open flag
    assert r1s[0]["status"] == "dismissed"
    assert not any(f["status"] == "open" for f in r1s)


def test_set_flag_status_unknown_id_is_false(conn):
    assert integrity.set_flag_status(conn, "no-such-flag", "confirmed") is False


def test_set_flag_status_rejects_bad_value(conn):
    with pytest.raises(ValueError):
        integrity.set_flag_status(conn, "x", "banana")


def test_clean_document_has_no_flags(conn):
    a = add_ref(conn, "Principles of typography", year=2004, authors=["Rowe"])
    b = add_ref(conn, "A short history of the printing press", year=2016, authors=["Bell"])
    cite(conn, [a], raw="(Rowe, 2004)")
    cite(conn, [b], raw="(Bell, 2016)")
    assert integrity.scan(conn, DOC) == []
