"""The Text Integrity Guarantee, fuzzed (MVP_SPEC.md §6.8 — the hardening sprint).

The promise SANAD is built around is "it never touches your prose." This test
makes that a property under attack rather than a claim: it drives the *real* Core
outputs (rendered citations, bibliography) into a document through the one
sanctioned write path, while a fuzzer mutates the surrounding prose as
adversarially as it can — text that looks like a citation, EndNote debris, Urdu
RTL, unicode, emptied and very long paragraphs, inserted/deleted paragraphs — and
asserts after every single Core sync that not one byte of prose moved.
"""
import random

import pytest

from sanad_core import db, documents, importer
from sanad_core import style_profile as sp
from sanad_core.document_model import (
    ALLOWED_TAGS, ControlRegion, Document, ProseRegion, ProseWriteError,
    apply_core_write, prose_snapshot,
)

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
"""

# Prose a hostile document might contain — none of it should tempt Core into a
# single edit outside its own controls.
ADVERSARIAL = [
    "(Fisher, 2001)",                                  # looks exactly like a citation
    "See also _ENREF_12 and the field {CITATION}.",    # EndNote/field-code debris
    "یہ جانچ کے لیے لکھا گیا ایک اردو جملہ ہے۔",         # Urdu / RTL prose
    "Manuscripts — ink, vellum & thread…",              # em dash, ampersand, ellipsis
    "",                                                # an emptied paragraph
    "z" * 400,                                          # a very long paragraph
    "Mixed English اور اردو (Nguyen & Ortega, 2016) on one line.",
]


def _seed(conn):
    importer.import_ris_text(conn, SAMPLE_RIS)
    fisher = conn.execute("SELECT id FROM reference WHERE title LIKE 'The Art of Memory%'").fetchone()["id"]
    nguyen = conn.execute("SELECT id FROM reference WHERE title LIKE 'A framework for distributed%'").fetchone()["id"]
    return fisher, nguyen


def _build_document(conn):
    doc_id = "d1"
    c1, _ = documents.create_citation(conn, doc_id, [_seed_cache["fisher"]],
                                      "(Fisher, 2001)")
    c2, _ = documents.create_citation(conn, doc_id, [_seed_cache["nguyen"]],
                                      "(Nguyen & Ortega, 2016)")
    doc = Document(regions=[
        ProseRegion("Working memory underpins everyday recall."),
        ControlRegion("sanad-cite", c1),
        ProseRegion("Structured notes in particular aid long-term retention."),
        ControlRegion("sanad-cite", c2),
        ProseRegion("This chapter builds on that foundation."),
        ProseRegion("References"),
        ControlRegion("sanad-bibliography", "bib"),
    ])
    return doc_id, doc


# a tiny per-test cache so _build_document can reach the seeded ids
_seed_cache: dict = {}


def _core_sync(conn, doc_id, doc):
    """Exactly what the add-in would do after any change: re-render every
    sanad-cite control and the bibliography, and place each result through the
    guarded writer — never anywhere else. Returns whether any control changed."""
    changed = False
    for ctrl in doc.controls("sanad-cite"):
        rendered = documents.rerender_citation(conn, ctrl.control_id) or ""
        if rendered != ctrl.text:
            changed = True
        apply_core_write(doc, ctrl.control_id, rendered)
    for ctrl in doc.controls("sanad-bibliography"):
        text = "\n".join(documents.render_bibliography(conn, doc_id))
        if text != ctrl.text:
            changed = True
        apply_core_write(doc, ctrl.control_id, text)
    return changed


def _user_fuzz(doc, rng):
    """The USER editing their own document — only ever prose, never a control."""
    for r in doc.regions:
        if isinstance(r, ProseRegion) and rng.random() < 0.6:
            suffix = f" {rng.randint(0, 9999)}" if rng.random() < 0.5 else ""
            r.text = rng.choice(ADVERSARIAL) + suffix
    if rng.random() < 0.3:
        doc.regions.insert(rng.randint(0, len(doc.regions)), ProseRegion(rng.choice(ADVERSARIAL)))
    prose_idx = [i for i, r in enumerate(doc.regions) if isinstance(r, ProseRegion)]
    if len(prose_idx) > 1 and rng.random() < 0.2:
        del doc.regions[rng.choice(prose_idx)]


# --------------------------------------------------------------------------- #
# the fuzz: Core sync must never move a byte of prose
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("seed_val", range(5))
def test_core_sync_never_alters_prose(seed_val):
    rng = random.Random(seed_val)
    conn = db.connect()
    _seed_cache["fisher"], _seed_cache["nguyen"] = _seed(conn)
    doc_id, doc = _build_document(conn)

    ever_changed = _core_sync(conn, doc_id, doc)  # initial fill of the controls
    for i in range(20):
        _user_fuzz(doc, rng)
        before = prose_snapshot(doc)

        # midway, change the library/style so Core's *output* genuinely changes
        # (ampersand -> "and") — proving prose is safe even while controls churn
        if i == 12:
            pid = sp.save_profile(conn, sp.build_profile(
                {"name": "amp", "ampersand_in_text": False,
                 "ampersand_in_bibliography": False}))
            documents.set_document_profile(conn, doc_id, pid)

        ever_changed |= _core_sync(conn, doc_id, doc)
        assert prose_snapshot(doc) == before   # Core touched no prose this round

    assert ever_changed  # non-vacuous: Core really was writing into its controls


def test_prose_that_looks_like_a_citation_is_left_verbatim():
    conn = db.connect()
    _seed_cache["fisher"], _seed_cache["nguyen"] = _seed(conn)
    doc_id, doc = _build_document(conn)
    trap = "As many note (Fisher, 2001), memory matters deeply."
    doc.regions.insert(0, ProseRegion(trap))

    before = prose_snapshot(doc)
    _core_sync(conn, doc_id, doc)
    assert prose_snapshot(doc) == before
    assert doc.regions[0].text == trap  # not "helpfully" reformatted


# --------------------------------------------------------------------------- #
# the enforcement point itself refuses everything but allowed controls
# --------------------------------------------------------------------------- #

def test_writer_refuses_unknown_id_and_leaves_prose_intact():
    doc = Document([ProseRegion("keep me exactly"),
                    ControlRegion("sanad-cite", "c1", "(X, 2020)")])
    before = prose_snapshot(doc)
    with pytest.raises(ProseWriteError):
        apply_core_write(doc, "no-such-control", "malicious text")
    assert prose_snapshot(doc) == before


def test_writer_refuses_a_mistagged_control():
    doc = Document([ControlRegion("body-text", "c1", "original")])
    with pytest.raises(ProseWriteError):
        apply_core_write(doc, "c1", "should not land")
    assert doc.regions[0].text == "original"


def test_writer_updates_only_the_targeted_control():
    doc = Document([
        ProseRegion("p1"), ControlRegion("sanad-cite", "c1", "old"),
        ProseRegion("p2"), ControlRegion("sanad-bibliography", "bib", "oldbib"),
    ])
    apply_core_write(doc, "c1", "(New, 2021)")
    assert doc.control("c1").text == "(New, 2021)"
    assert doc.control("bib").text == "oldbib"          # sibling control untouched
    assert prose_snapshot(doc) == ("p1", "p2")           # prose untouched


def test_allowed_tags_are_exactly_the_spec_set():
    # guard against anyone quietly widening the write surface
    assert set(ALLOWED_TAGS) == {"sanad-cite", "sanad-bibliography", "sanad-style-region"}
