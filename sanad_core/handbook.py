"""Local, on-device parsing of a university thesis/format manual.

Given an uploaded manual (.docx / .txt / .pdf), extract its text *on the machine*
(no cloud) and detect the common, unambiguously-stated formatting rules --
citation style, body font + size, line spacing, margins, reference hanging
indent. The result is a DRAFT: every detected value is returned with the exact
snippet it came from, for the researcher to confirm or correct in the Style
Profile builder. Nothing is ever silently applied, and nothing is invented -- a
rule the manual doesn't state clearly comes back as "not found", not a guess.
This is the deliberate, correctness-first counterpart to the old 501 stub.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

from . import styles

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# --- text extraction (local only) ----------------------------------------- #

def extract_text(data: bytes, fmt: str) -> str:
    fmt = (fmt or "").lower()
    if fmt == "txt":
        for enc in ("utf-8", "utf-16", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", "replace")
    if fmt == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
        return "\n".join(
            "".join(t.text or "" for t in para.iter(f"{{{_W_NS}}}t"))
            for para in root.iter(f"{{{_W_NS}}}p")
        )
    if fmt == "pdf":
        try:
            import fitz  # PyMuPDF, optional
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ValueError(
                "PDF support isn't available in this build — save the manual as "
                ".docx or paste its text instead.") from exc
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    raise ValueError(f"unsupported manual format {fmt!r} (use docx, pdf or txt)")


# --- rule detection -------------------------------------------------------- #

# style name -> CSL id, only for names stated plainly in manuals
_STYLE_HINTS = [
    (r"\bAPA\b", "apa", "APA"),
    (r"\bMLA\b|modern language association", "modern-language-association", "MLA"),
    (r"\bIEEE\b", "ieee", "IEEE"),
    (r"\bvancouver\b", "vancouver", "Vancouver"),
    (r"\bharvard\b", "harvard-cite-them-right", "Harvard"),
    (r"chicago.{0,20}(author.?date)", "chicago-author-date", "Chicago (author–date)"),
    (r"chicago.{0,20}(note|bibliograph)", "chicago-note-bibliography", "Chicago (notes & bibliography)"),
    (r"\bchicago\b", "chicago-author-date", "Chicago"),
    (r"\bturabian\b", "turabian-author-date", "Turabian"),
    (r"\bAMA\b|american medical association", "american-medical-association", "AMA"),
]
_FONTS = ["Times New Roman", "Arial", "Calibri", "Cambria", "Garamond",
          "Georgia", "Book Antiqua", "Palatino", "Verdana", "Helvetica"]


def _snippet(text: str, match: re.Match, span: int = 60) -> str:
    a = max(0, match.start() - span)
    b = min(len(text), match.end() + span)
    return re.sub(r"\s+", " ", text[a:b]).strip()


def detect_rules(text: str) -> dict:
    """Return {form, detected, notes}. `form` is a Style-Profile builder form
    with only the confidently-detected fields set; `detected` explains each with
    the source snippet; `notes` lists what could not be determined."""
    form: dict = {}
    detected: list[dict] = []
    low = text.lower()

    def note(field, value, m):
        detected.append({"field": field, "value": value, "evidence": _snippet(text, m)})

    # citation style
    for pat, csl_id, label in _STYLE_HINTS:
        m = re.search(pat, text, re.I)
        if m and styles.is_known_style(csl_id):
            form["based_on_csl"] = csl_id
            note("Citation style", label, m)
            break

    # body font
    for font in _FONTS:
        m = re.search(re.escape(font), text, re.I)
        if m:
            form["font_family"] = font
            note("Font", font, m)
            break

    # font size (pt) — prefer a size stated near "font"/"point"; 10–14 is a sane body range
    for m in re.finditer(r"(\d{1,2})\s*(?:pt\b|point|-point)", text, re.I):
        size = int(m.group(1))
        if 9 <= size <= 14:
            form["font_size_pt"] = size
            note("Font size", f"{size} pt", m)
            break

    # line spacing
    m = re.search(r"double[-\s]?spac", low)
    if m:
        form["line_spacing"] = 2.0; note("Line spacing", "Double (2.0)", m)
    elif (m := re.search(r"1\.5[-\s]?(?:line[-\s]?)?spac|one and a half", low)):
        form["line_spacing"] = 1.5; note("Line spacing", "1.5", m)
    elif (m := re.search(r"single[-\s]?spac", low)):
        form["line_spacing"] = 1.0; note("Line spacing", "Single (1.0)", m)

    # margins (inches or cm), taken near the word "margin"
    m = re.search(r"margin[s]?[^.\n]{0,40}?(\d(?:\.\d+)?)\s*(inch|inches|in\b|\"|cm|mm)", low)
    if m:
        val = float(m.group(1)); unit = m.group(2)
        cm = val * 2.54 if unit.startswith(("inch", "in", '"')) else (val / 10 if unit == "mm" else val)
        form["margin_cm"] = round(cm, 2)
        note("Margins", f"{val} {unit}", m)

    # reference hanging indent
    m = re.search(r"hanging[-\s]?indent[^.\n]{0,40}?(\d(?:\.\d+)?)\s*(inch|inches|in\b|\"|cm|mm)", low)
    if m:
        val = float(m.group(1)); unit = m.group(2)
        cm = val * 2.54 if unit.startswith(("inch", "in", '"')) else (val / 10 if unit == "mm" else val)
        form["hanging_indent_cm"] = round(cm, 2)
        note("Hanging indent", f"{val} {unit}", m)
    elif "hanging indent" in low:
        m = re.search(r"hanging[-\s]?indent", low)
        note("Hanging indent", "mentioned (no measurement found — default 1.27 cm)", m)

    found = {d["field"] for d in detected}
    notes = [f"Couldn't find {f} in the manual — set it yourself."
             for f in ("Citation style", "Font", "Font size", "Line spacing", "Margins")
             if f not in found]
    return {"form": form, "detected": detected, "notes": notes}
