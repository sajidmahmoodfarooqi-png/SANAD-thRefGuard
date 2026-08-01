import xml.etree.ElementTree as ET

import pytest

from sanad_core import db, style_profile


def test_default_profile_validates_clean():
    profile = style_profile.default_profile()
    assert style_profile.validate_profile(profile) == []


def test_missing_name_is_rejected():
    profile = style_profile.default_profile()
    profile["name"] = ""
    errors = style_profile.validate_profile(profile)
    assert any("name" in e for e in errors)


def test_unknown_csl_style_is_rejected():
    profile = style_profile.default_profile()
    profile["based_on_csl"] = "not-a-real-style-xyz"
    errors = style_profile.validate_profile(profile)
    assert any("not-a-real-style-xyz" in e for e in errors)


def test_save_and_reload_profile_round_trips():
    conn = db.connect()
    profile = style_profile.default_profile("Metropolitan University Thesis Format 2026")
    profile["university"] = "Metropolitan University"
    profile["csl_overrides"] = {"et_al_min": 3, "et_al_use_first": 2}
    pid = style_profile.save_profile(conn, profile)

    reloaded = style_profile.get_profile(conn, pid)
    assert reloaded["name"] == "Metropolitan University Thesis Format 2026"
    assert reloaded["university"] == "Metropolitan University"
    assert reloaded["csl_overrides"] == {"et_al_min": 3, "et_al_use_first": 2}
    assert reloaded["provenance"]["confirmed_by_user"] is True


def test_delete_profile_removes_row():
    conn = db.connect()
    pid = style_profile.save_profile(conn, style_profile.default_profile("To Be Deleted"))
    assert style_profile.get_profile(conn, pid) is not None
    assert style_profile.delete_profile(conn, pid) is True
    assert style_profile.get_profile(conn, pid) is None
    # deleting again is a no-op, reported as False (not an error)
    assert style_profile.delete_profile(conn, pid) is False


def test_save_profile_with_existing_id_updates_in_place():
    conn = db.connect()
    profile = style_profile.default_profile("Original Name")
    pid = style_profile.save_profile(conn, profile)
    profile["id"] = pid
    profile["name"] = "Renamed In Place"
    pid2 = style_profile.save_profile(conn, profile)
    assert pid2 == pid
    assert style_profile.get_profile(conn, pid)["name"] == "Renamed In Place"
    assert len(style_profile.list_profiles(conn)) == 1  # no duplicate row


def test_invalid_profile_raises_on_save():
    conn = db.connect()
    profile = style_profile.default_profile()
    profile["based_on_csl"] = "nope"
    with pytest.raises(ValueError):
        style_profile.save_profile(conn, profile)


def test_patch_csl_style_applies_et_al_attributes():
    patched_path = style_profile.patch_csl_style("apa", {"et_al_min": 5, "et_al_use_first": 4})
    tree = ET.parse(patched_path)
    ns = {"c": style_profile.CSL_NS}
    citation_el = tree.getroot().find("c:citation", ns)
    bibliography_el = tree.getroot().find("c:bibliography", ns)
    assert citation_el.get("et-al-min") == "5"
    assert citation_el.get("et-al-use-first") == "4"
    assert bibliography_el.get("et-al-min") == "5"


def test_patch_csl_style_no_overrides_returns_base_path_unchanged():
    base = style_profile.patch_csl_style("apa", {})
    import citeproc_styles
    assert base == citeproc_styles.get_style_filepath("apa")


def test_patch_csl_style_ampersand_to_text():
    patched_path = style_profile.patch_csl_style("apa", {"ampersand_in_text": False})
    content = open(patched_path, encoding="utf-8").read()
    assert 'and="symbol"' not in content
    assert content.count('and="text"') > 0


# -- Sprint 6: guided builder + paragraph_style output ---------------------- #

def test_build_profile_from_empty_form_is_valid_default():
    p = style_profile.build_profile({})
    assert style_profile.validate_profile(p) == []
    assert p["based_on_csl"] == "apa"
    assert p["name"] == "Custom Style Profile"


def test_build_profile_maps_guided_answers():
    p = style_profile.build_profile({
        "name": "Metropolitan Thesis 2026", "university": "Metropolitan University",
        "et_al_min": 3, "ampersand_in_text": False,
        "font_family": "Times New Roman", "font_size_pt": 12,
        "hanging_indent_cm": 1.27, "line_spacing": 2.0,
    })
    assert p["university"] == "Metropolitan University"
    assert p["csl_overrides"]["et_al_min"] == 3
    assert p["csl_overrides"]["ampersand_in_text"] is False
    assert p["paragraph_style"]["bibliography_hanging_indent_cm"] == 1.27
    assert p["paragraph_style"]["line_spacing"] == 2.0


def test_paragraph_style_office_expresses_hanging_indent():
    office = style_profile.paragraph_style_office({
        "bibliography_hanging_indent_cm": 1.27,
        "bibliography_space_after_pt": 6,
        "font_family": "Times New Roman", "font_size_pt": 12, "line_spacing": 1.5,
    })
    assert office["leftIndentPt"] == 36.0          # 1.27 cm -> 36 pt
    assert office["firstLineIndentPt"] == -36.0     # negative first line = hanging
    assert office["spaceAfterPt"] == 6
    assert office["fontName"] == "Times New Roman"
    assert office["lineSpacing"] == 1.5
    assert office["lineSpacingRule"] == "multiple"


def test_paragraph_style_office_empty_is_empty():
    assert style_profile.paragraph_style_office({}) == {}
    assert style_profile.paragraph_style_office(None) == {}


def test_to_sanadstyle_json_has_full_field_set():
    p = style_profile.build_profile({"name": "X"})
    doc = style_profile.to_sanadstyle_json(p)
    assert set(doc) == {"id", "name", "university", "version", "based_on_csl",
                        "csl_overrides", "paragraph_style", "document_structure",
                        "provenance"}
    assert "extracted_at" in doc["provenance"]


def test_build_profile_maps_heading_styles_and_numbering():
    p = style_profile.build_profile({
        "name": "Thesis", "number_headings": True,
        "title_font": "Cambria", "title_size_pt": 26,
        "h1_font": "Cambria", "h1_size_pt": 16,
        "h2_size_pt": 14, "h3_size_pt": 12,
    })
    ds = p["document_structure"]
    assert ds["enabled"] is True
    h = ds["headings"]
    assert h["numbered"] is True
    assert h["title"] == {"font": "Cambria", "size_pt": 26.0}
    assert h["h1"] == {"font": "Cambria", "size_pt": 16.0}
    assert h["h2"] == {"size_pt": 14.0}       # size-only heading, no font
    assert h["h3"] == {"size_pt": 12.0}
    assert style_profile.validate_profile(p) == []


def test_build_profile_without_headings_omits_headings_key():
    p = style_profile.build_profile({"name": "Plain", "font_family": "Georgia"})
    assert "headings" not in (p.get("document_structure") or {})


def test_list_profiles_returns_saved_profiles():
    conn = db.connect()
    style_profile.save_profile(conn, style_profile.build_profile({"name": "Alpha"}))
    style_profile.save_profile(conn, style_profile.build_profile({"name": "Beta"}))
    names = [p["name"] for p in style_profile.list_profiles(conn)]
    assert names == ["Alpha", "Beta"]  # ordered by name
