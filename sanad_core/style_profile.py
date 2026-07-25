"""Style Profile: load/validate/apply a `.sanadstyle.json` (MVP_SPEC.md §5).

A profile separates three concerns that are easy to conflate:
  - csl_overrides    -> patches to the CSL style itself (et-al, ampersand)
  - paragraph_style  -> Word paragraph/font formatting of the bibliography
                        (not a CSL concept at all)
  - document_structure -> opt-in, out of scope for v1.0 (margins/TOC/etc.)
"""
from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import citeproc_styles

from . import db

CSL_NS = "http://purl.org/net/xbiblio/csl"
ET.register_namespace("", CSL_NS)


def default_profile(name: str = "APA 7th (default)") -> dict:
    return {
        "id": None,
        "name": name,
        "university": None,
        "version": "1.0",
        "based_on_csl": "apa",
        "csl_overrides": {},
        "paragraph_style": {
            "bibliography_hanging_indent_cm": 1.27,
            "bibliography_space_after_pt": 6,
            "font_family": "Times New Roman",
            "font_size_pt": 12,
            "line_spacing": 1.0,
        },
        "document_structure": {"enabled": False},
        "provenance": {
            "source_handbook_file": None,
            "extracted_at": None,
            "confirmed_by_user": True,
            "shared": False,
        },
    }


# 1 cm in typographic points (72 pt / inch, 2.54 cm / inch). Word/Office.js
# indentation and spacing are all in points, so paragraph_style's cm indent is
# converted here once rather than in the add-in.
CM_TO_PT = 72.0 / 2.54


def build_profile(form: dict) -> dict:
    """Assemble a full, valid `.sanadstyle.json` profile from the guided form's
    flat answers (MVP_SPEC.md §6.6). Everything the form doesn't set keeps the
    sane APA-7th default, so a near-empty form still yields a usable profile —
    the form is *guided*, not exhaustive.

    Recognized keys (all optional): name, university, based_on_csl, et_al_min,
    et_al_use_first, ampersand_in_text, ampersand_in_bibliography, font_family,
    font_size_pt, line_spacing, hanging_indent_cm, space_after_pt,
    document_structure.
    """
    p = default_profile(form.get("name") or "Custom Style Profile")
    if form.get("university"):
        p["university"] = form["university"]
    if form.get("based_on_csl"):
        p["based_on_csl"] = form["based_on_csl"]

    ov = p["csl_overrides"]
    for key in ("et_al_min", "et_al_use_first"):
        if form.get(key) is not None:
            ov[key] = int(form[key])
    for key in ("ampersand_in_text", "ampersand_in_bibliography"):
        if form.get(key) is not None:
            ov[key] = bool(form[key])

    ps = p["paragraph_style"]
    for fkey, pkey in (
        ("font_family", "font_family"),
        ("font_size_pt", "font_size_pt"),
        ("line_spacing", "line_spacing"),
        ("hanging_indent_cm", "bibliography_hanging_indent_cm"),
        ("space_after_pt", "bibliography_space_after_pt"),
    ):
        if form.get(fkey) is not None:
            ps[pkey] = form[fkey]

    if isinstance(form.get("document_structure"), dict):
        p["document_structure"] = form["document_structure"]
    return p


def paragraph_style_office(paragraph_style: dict | None) -> dict:
    """Translate a profile's `paragraph_style` into the exact fields + units an
    Office.js Word add-in applies to the `sanad-bibliography` content control
    (MVP_SPEC.md §5). This is where the Text Integrity Guarantee's *layout* half
    lives: paragraph_style is NOT a CSL concept — it maps to Word
    `ParagraphFormat`/`Font`, and only ever inside the bibliography control.

    Units: points throughout (Office.js indentation/spacing are in points). A
    hanging indent is expressed the Word way — a positive left indent with an
    equal *negative* first-line indent. `line_spacing` is passed through as a
    multiple with an explicit rule so the add-in doesn't have to guess whether
    it's points or a multiplier.
    """
    ps = paragraph_style or {}
    out: dict = {}
    if ps.get("font_family") is not None:
        out["fontName"] = ps["font_family"]
    if ps.get("font_size_pt") is not None:
        out["fontSizePt"] = ps["font_size_pt"]
    if ps.get("bibliography_space_after_pt") is not None:
        out["spaceAfterPt"] = ps["bibliography_space_after_pt"]
    if ps.get("line_spacing") is not None:
        out["lineSpacing"] = ps["line_spacing"]
        out["lineSpacingRule"] = "multiple"
    indent_cm = ps.get("bibliography_hanging_indent_cm")
    if indent_cm is not None:
        pt = round(float(indent_cm) * CM_TO_PT, 2)
        out["leftIndentPt"] = pt
        out["firstLineIndentPt"] = -pt   # negative first line = hanging indent
    return out


def to_sanadstyle_json(profile: dict) -> dict:
    """Canonical `.sanadstyle.json` export shape (MVP_SPEC.md §5) — the unit
    shared in the community library. Guarantees the full field set regardless of
    which keys the in-memory profile happened to carry."""
    prov = profile.get("provenance") or {}
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "university": profile.get("university"),
        "version": profile.get("version", "1.0"),
        "based_on_csl": profile.get("based_on_csl"),
        "csl_overrides": profile.get("csl_overrides") or {},
        "paragraph_style": profile.get("paragraph_style") or {},
        "document_structure": profile.get("document_structure") or {"enabled": False},
        "provenance": {
            "source_handbook_file": prov.get("source_handbook_file"),
            "extracted_at": prov.get("extracted_at"),
            "confirmed_by_user": prov.get("confirmed_by_user", True),
            "shared": prov.get("shared", False),
        },
    }


def list_profiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, university, based_on_csl FROM style_profile ORDER BY name"
    ).fetchall()
    return [dict(r) for r in rows]


def validate_profile(profile: dict) -> list[str]:
    """Return validation error strings; an empty list means the profile is
    safe to save and apply."""
    errors = []
    if not profile.get("name"):
        errors.append("name is required")
    if not profile.get("based_on_csl"):
        errors.append("based_on_csl is required")
    else:
        try:
            citeproc_styles.get_style_filepath(profile["based_on_csl"])
        except Exception:
            errors.append(f"based_on_csl {profile['based_on_csl']!r} is not a known CSL style")
    overrides = profile.get("csl_overrides") or {}
    if "et_al_min" in overrides and not isinstance(overrides["et_al_min"], int):
        errors.append("csl_overrides.et_al_min must be an integer")
    return errors


def load_profile_file(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_profile_file(profile: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def save_profile(conn: sqlite3.Connection, profile: dict) -> str:
    errors = validate_profile(profile)
    if errors:
        raise ValueError(f"invalid style profile: {'; '.join(errors)}")
    pid = profile.get("id") or db.new_id()
    now = db.now_iso()
    provenance = profile.get("provenance") or {}
    conn.execute(
        """INSERT INTO style_profile
           (id, name, university, based_on_csl, csl_overrides, paragraph_style,
            document_structure, source_handbook_file, confirmed_by_user, shared,
            created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name, university=excluded.university,
             based_on_csl=excluded.based_on_csl, csl_overrides=excluded.csl_overrides,
             paragraph_style=excluded.paragraph_style,
             document_structure=excluded.document_structure,
             confirmed_by_user=excluded.confirmed_by_user, shared=excluded.shared,
             updated_at=excluded.updated_at""",
        (
            pid, profile["name"], profile.get("university"), profile["based_on_csl"],
            json.dumps(profile.get("csl_overrides") or {}),
            json.dumps(profile.get("paragraph_style") or {}),
            json.dumps(profile.get("document_structure") or {}),
            provenance.get("source_handbook_file"),
            1 if provenance.get("confirmed_by_user", True) else 0,
            1 if provenance.get("shared") else 0,
            now, now,
        ),
    )
    conn.commit()
    return pid


def delete_profile(conn: sqlite3.Connection, profile_id: str) -> bool:
    """Delete a style profile. Returns True if a row was removed."""
    cur = conn.execute("DELETE FROM style_profile WHERE id = ?", (profile_id,))
    conn.commit()
    return cur.rowcount > 0


def get_profile(conn: sqlite3.Connection, profile_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM style_profile WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        return None
    return {
        "id": row["id"], "name": row["name"], "university": row["university"],
        "based_on_csl": row["based_on_csl"],
        "csl_overrides": json.loads(row["csl_overrides"] or "{}"),
        "paragraph_style": json.loads(row["paragraph_style"] or "{}"),
        "document_structure": json.loads(row["document_structure"] or "{}"),
        "provenance": {
            "source_handbook_file": row["source_handbook_file"],
            "confirmed_by_user": bool(row["confirmed_by_user"]),
            "shared": bool(row["shared"]),
        },
    }


# --------------------------------------------------------------------------- #
# CSL XML patching -- the *real* mechanism behind csl_overrides.
#
# Ground-truthed against citeproc-py-styles' apa.csl (not assumed): et-al
# thresholds are attributes on the top-level <citation> and <bibliography>
# elements; the "&" vs "and" choice is the `and="symbol"|"text"` attribute
# on every relevant <name> element.
# --------------------------------------------------------------------------- #

def patch_csl_style(base_style_id: str, overrides: dict) -> str:
    """Apply `overrides` to the named base CSL style; return a path to a
    patched copy of the CSL XML (citeproc-py loads styles from a file path).

    v1.0 scope, deliberately: et_al_min/et_al_use_first (targeted, exact),
    and a single global ampersand_in_text/ampersand_in_bibliography ->
    and="symbol"|"text" swap (applied uniformly across the style, since
    distinguishing citation-layout from bibliography-layout <name> elements
    requires macro-context tracing this project has not built yet -- see
    MVP_SPEC.md "Honest challenges"). Everything else in csl_overrides is
    accepted but not yet wired; this is the intended v1.x expansion point.
    """
    ov = overrides or {}
    return _patched_style_path(
        base_style_id,
        ov.get("et_al_min"), ov.get("et_al_use_first"),
        ov.get("ampersand_in_text"), ov.get("ampersand_in_bibliography"),
    )


@lru_cache(maxsize=64)
def _patched_style_path(base_style_id, et_al_min, et_al_use_first, amp_text, amp_bib):
    """Build (once, then cache) the patched CSL file for a given set of the
    overrides that actually affect rendering. Repeated renders under the same
    profile reuse the same file instead of re-writing it. Keyed only on the
    overrides that change output, so it stays hashable and correct."""
    base_path = citeproc_styles.get_style_filepath(base_style_id)
    overrides = {}
    if et_al_min is not None:
        overrides["et_al_min"] = et_al_min
    if et_al_use_first is not None:
        overrides["et_al_use_first"] = et_al_use_first
    if amp_text is not None:
        overrides["ampersand_in_text"] = amp_text
    if amp_bib is not None:
        overrides["ampersand_in_bibliography"] = amp_bib
    if not overrides:
        return base_path

    tree = ET.parse(base_path)
    root = tree.getroot()
    ns = {"c": CSL_NS}

    if "et_al_min" in overrides or "et_al_use_first" in overrides:
        for tag in ("citation", "bibliography"):
            el = root.find(f"c:{tag}", ns)
            if el is not None:
                if "et_al_min" in overrides:
                    el.set("et-al-min", str(overrides["et_al_min"]))
                if "et_al_use_first" in overrides:
                    el.set("et-al-use-first", str(overrides["et_al_use_first"]))

    want_text = overrides.get("ampersand_in_text") is False or \
                overrides.get("ampersand_in_bibliography") is False
    want_symbol = overrides.get("ampersand_in_text") is True or \
                  overrides.get("ampersand_in_bibliography") is True
    if want_text and not want_symbol:
        for name_el in root.iter(f"{{{CSL_NS}}}name"):
            if name_el.get("and") == "symbol":
                name_el.set("and", "text")

    import tempfile
    fd, tmp_path = tempfile.mkstemp(suffix=".csl", prefix="sanad_style_")
    tree.write(tmp_path, encoding="utf-8", xml_declaration=True)
    return tmp_path
