import json

from sanad_core import db, formatter, importer, style_profile

# An invented library exercising the citation shapes that matter: a 1-author
# book, a 2-author DOI article, and a 7-author paper (for the et al. threshold).
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
TY  - JOUR
AU  - Reed, Sarah
AU  - Shaw, Thomas
AU  - Patel, Rina
AU  - Osei, Kwame
AU  - Lindqvist, Mika
AU  - Ibarra, Jose
AU  - Tanaka, Hiro
TI  - A survey of distributed ledger systems
PY  - 2020
ER  -
"""


def _load_library():
    conn = db.connect()
    importer.import_ris_text(conn, SAMPLE_RIS)
    return [json.loads(r["csl_json"]) for r in conn.execute("SELECT csl_json FROM reference").fetchall()]


def _find(items, needle):
    return next(i for i in items if needle in i["title"])


def test_single_author_in_text_citation():
    items = _load_library()
    fisher = _find(items, "Art of Memory")
    fmt = formatter.Formatter(items, style_profile.default_profile())
    assert fmt.render_citation([fisher["id"]]) == "(Fisher, 2001)"


def test_two_author_bibliography_has_no_double_period_and_correct_ampersand():
    items = _load_library()
    nguyen = _find(items, "distributed caching")
    fmt = formatter.Formatter(items, style_profile.default_profile())
    fmt.render_citation([nguyen["id"]])
    entry = fmt.render_bibliography()[0]
    assert ".." not in entry
    assert "L., & Ortega" in entry  # comma before "&" -- the exact bug found and fixed


def test_two_author_in_text_has_no_comma_before_ampersand():
    """APA in-text form for 2 authors is 'A & B, year' -- no comma before
    the ampersand (that rule is correct as-is; only the bibliography form
    needed the cleanup fix)."""
    items = _load_library()
    nguyen = _find(items, "distributed caching")
    fmt = formatter.Formatter(items, style_profile.default_profile())
    assert fmt.render_citation([nguyen["id"]]) == "(Nguyen & Ortega, 2016)"


def test_default_et_al_threshold_on_seven_author_paper():
    items = _load_library()
    reed = _find(items, "distributed ledger")
    fmt = formatter.Formatter(items, style_profile.default_profile())
    assert fmt.render_citation([reed["id"]]) == "(Reed et al., 2020)"


def test_et_al_use_first_override_changes_rendering():
    items = _load_library()
    reed = _find(items, "distributed ledger")
    profile = style_profile.default_profile()
    profile["csl_overrides"] = {"et_al_min": 3, "et_al_use_first": 2}
    fmt = formatter.Formatter(items, profile)
    rendered = fmt.render_citation([reed["id"]])
    assert rendered == "(Reed, Shaw, et al., 2020)"


def test_ampersand_override_produces_and_not_symbol():
    items = _load_library()
    nguyen = _find(items, "distributed caching")
    profile = style_profile.default_profile()
    profile["csl_overrides"] = {"ampersand_in_text": False, "ampersand_in_bibliography": False}
    fmt = formatter.Formatter(items, profile)
    rendered = fmt.render_citation([nguyen["id"]])
    assert "&" not in rendered
    assert "and" in rendered


def test_grouped_citation_sorts_and_separates_with_semicolon():
    items = _load_library()
    fisher = _find(items, "Art of Memory")
    reed = _find(items, "distributed ledger")
    fmt = formatter.Formatter(items, style_profile.default_profile())
    rendered = fmt.render_citation([fisher["id"], reed["id"]])
    assert rendered == "(Fisher, 2001; Reed et al., 2020)"  # alphabetical: Fisher before Reed


def test_render_full_library_has_no_stray_double_periods():
    """A broad regression net over the whole library -- not just the cases known
    in advance, in case another author-name shape hits the same citeproc-py
    artifact."""
    items = _load_library()
    entries = formatter.render_full_library(items, style_profile.default_profile())
    assert len(entries) == len(items)
    offenders = [e for e in entries if ".." in e]
    assert offenders == [], f"double-period artifact survived cleanup in: {offenders[:3]}"
