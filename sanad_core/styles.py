"""Searchable catalog over the bundled CSL styles.

citeproc-py-styles ships the full CSL repository (~10,800 styles). This exposes
a fast search so the Style Profile builder can offer any of them, not a hardcoded
handful -- and so handbook parsing can resolve a style *named* in a manual
("APA 7th", "Vancouver") to a real CSL id.

Search is by style id substring plus a small alias table for the styles people
name by an abbreviation the id doesn't contain (MLA, AMA, ...). Titles are parsed
only for the handful of results actually returned, so a query never has to read
thousands of files.
"""
from __future__ import annotations

import functools
import glob
import os
from xml.etree import ElementTree as ET

import citeproc_styles

CSL_NS = "http://purl.org/net/xbiblio/csl"

# common styles keyed by the abbreviation users type but the CSL id lacks
POPULAR: list[tuple[str, str]] = [
    ("apa", "APA 7th"),
    ("modern-language-association", "MLA 9th"),
    ("chicago-author-date", "Chicago (author–date)"),
    ("chicago-note-bibliography", "Chicago (notes & bibliography)"),
    ("harvard-cite-them-right", "Harvard (Cite Them Right)"),
    ("ieee", "IEEE"),
    ("vancouver", "Vancouver"),
    ("american-medical-association", "AMA"),
    ("nature", "Nature"),
    ("elsevier-harvard", "Elsevier (Harvard)"),
    ("turabian-author-date", "Turabian (author–date)"),
    ("council-of-science-editors-author-date", "CSE (author–date)"),
]
_ALIASES = {"mla": "modern-language-association", "ama": "american-medical-association",
            "cse": "council-of-science-editors-author-date"}


@functools.lru_cache(maxsize=1)
def _styles_root() -> str:
    return os.path.dirname(citeproc_styles.get_style_filepath("apa"))


@functools.lru_cache(maxsize=1)
def _all_ids() -> tuple[str, ...]:
    root = _styles_root()
    return tuple(sorted(
        os.path.basename(p)[:-4]
        for p in glob.glob(os.path.join(root, "**", "*.csl"), recursive=True)
    ))


def style_title(style_id: str) -> str:
    """The human-readable <title> from a CSL file (falls back to the id)."""
    try:
        path = citeproc_styles.get_style_filepath(style_id)
        for _event, el in ET.iterparse(path):
            if el.tag == f"{{{CSL_NS}}}title":
                return (el.text or style_id).strip()
    except Exception:
        pass
    return style_id


def is_known_style(style_id: str) -> bool:
    try:
        citeproc_styles.get_style_filepath(style_id)
        return True
    except Exception:
        return False


def search_styles(q: str = "", limit: int = 40) -> list[dict]:
    q = (q or "").strip().lower()
    ids = _all_ids()
    idset = set(ids)
    if not q:
        chosen = [pid for pid, _ in POPULAR if pid in idset]
    else:
        chosen: list[str] = []
        if q in _ALIASES and _ALIASES[q] in idset:
            chosen.append(_ALIASES[q])
        # popular whose id or friendly label matches
        for pid, label in POPULAR:
            if pid in idset and pid not in chosen and (q in pid or q in label.lower()):
                chosen.append(pid)
        # long tail: id substring
        for i in ids:
            if len(chosen) >= limit:
                break
            if q in i and i not in chosen:
                chosen.append(i)
    return [{"id": i, "title": style_title(i)} for i in chosen[:limit]]
