"""Apply a Style Profile's formatting to a researcher's thesis .docx.

The user's actual document goes in; the same document comes back reformatted to
the university's rules — body font/size/line-spacing, page margins, heading fonts,
and a hanging indent on the reference list — with **not one word of prose
changed**. That last part is a hard guarantee, enforced two ways:

  * this module only ever writes *style and format* properties (Style.font,
    ParagraphFormat, Section margins). It never reads or assigns paragraph/run
    *text*. There is no code path here that could alter wording.
  * `text_fingerprint()` captures every paragraph + table cell string; the caller
    asserts it is byte-identical before and after, so a regression can't slip
    through silently.

The whole routine runs inside `offline.no_network()`, so the document can never
leave the machine while being processed (see offline.py for why that matters).
"""
from __future__ import annotations

import io

from . import offline


def text_fingerprint(data: bytes) -> list[str]:
    """Every run of user text in the document, in order — the thing that must
    NOT change. Used to prove prose was untouched."""
    from docx import Document

    doc = Document(io.BytesIO(data))
    out: list[str] = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                out.extend(p.text for p in cell.paragraphs)
    return out


def apply_profile_to_docx(data: bytes, profile: dict) -> dict:
    """Reformat the .docx to the profile. Returns {data (bytes), applied (list)}.
    Raises ValueError on a non-.docx or corrupt file. Never touches prose."""
    from docx import Document
    from docx.shared import Cm, Pt

    ps = profile.get("paragraph_style") or {}
    ds = profile.get("document_structure") or {}
    font = ps.get("font_family")
    size = ps.get("font_size_pt")
    spacing = ps.get("line_spacing")
    margin_cm = ds.get("margin_cm") if ds.get("enabled") else None
    indent_cm = ps.get("bibliography_hanging_indent_cm")
    applied: list[str] = []

    with offline.no_network():          # the document cannot leave the machine
        try:
            before = text_fingerprint(data)
            doc = Document(io.BytesIO(data))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("that doesn't look like a valid .docx file") from exc

        # body defaults live on the Normal style
        normal = doc.styles["Normal"]
        if font:
            normal.font.name = font
            applied.append(f"Body font → {font}")
        if size:
            normal.font.size = Pt(float(size))
            applied.append(f"Body size → {size} pt")
        if spacing:
            normal.paragraph_format.line_spacing = float(spacing)
            applied.append(f"Line spacing → {spacing}")

        # page margins on every section
        if margin_cm:
            for section in doc.sections:
                section.top_margin = section.bottom_margin = Cm(float(margin_cm))
                section.left_margin = section.right_margin = Cm(float(margin_cm))
            applied.append(f"Margins → {margin_cm} cm")

        # heading fonts follow the body font (a common manual requirement)
        if font:
            for name in ("Heading 1", "Heading 2", "Heading 3", "Title"):
                try:
                    doc.styles[name].font.name = font
                except KeyError:
                    pass

        # reference list hanging indent: apply to the built-in Bibliography style
        # if the document uses it (positive left indent + equal negative first line)
        if indent_cm is not None:
            try:
                bib = doc.styles["Bibliography"]
                bib.paragraph_format.left_indent = Cm(float(indent_cm))
                bib.paragraph_format.first_line_indent = Cm(-float(indent_cm))
                applied.append(f"Reference hanging indent → {indent_cm} cm")
            except KeyError:
                applied.append("Reference hanging indent: skipped (document has no "
                               "'Bibliography' style — apply that style to your reference list)")

        out = io.BytesIO()
        doc.save(out)
        after = text_fingerprint(out.getvalue())

    if before != after:  # the guarantee: prose is byte-identical
        raise RuntimeError("aborted: formatting would have altered document text "
                           "(this should be impossible — no text is written)")
    return {"data": out.getvalue(), "applied": applied}
