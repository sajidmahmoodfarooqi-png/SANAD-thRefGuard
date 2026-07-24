"""CSL rendering via citeproc-py: citation and bibliography *content*.

Two responsibilities kept sharply separate, per MVP_SPEC.md §5:
  - This module renders citation/reference content (order, punctuation,
    italics, et al. threshold, ampersand) -- CSL's actual domain.
  - `paragraph_style` (hanging indent, spacing, font) is NOT rendered here;
    it is exposed as plain data for a Word/LibreOffice add-in to apply as
    real paragraph formatting, because it is not a CSL concept at all.
"""
from __future__ import annotations

import re

from citeproc import Citation, CitationItem, CitationStylesBibliography, CitationStylesStyle
from citeproc import formatter as cp_formatter
from citeproc.source.json import CiteProcJSON

from . import style_profile as sp_module

# --------------------------------------------------------------------------- #
# Known citeproc-py rendering artifacts, fixed here rather than trusted
# silently. Ground-truthed against real citeproc-py output (see the two-author
# bibliography test cases):
#   - a stray second period after an author's final initial ("A. E..")
#   - a missing ", " before the final author conjunction, for BOTH spellings:
#       "P.& Ortega"   (default APA ampersand)
#       "P.and Ortega" (when a Style Profile overrides "&" -> "and")
# citeproc-py is less spec-faithful than citeproc-js (what Zotero actually
# uses); if artifacts like this keep accumulating, migrating to a
# citeproc-js bridge is the real v1.x fix -- see MVP_SPEC.md §13.
# --------------------------------------------------------------------------- #
_DOUBLE_PERIOD = re.compile(r"\.\.(?=\s|$)")
# an author-initial period butted straight against the final conjunction,
# with the APA author-delimiter ", " dropped by citeproc-py
_MISSING_DELIM_BEFORE_CONJ = re.compile(r"([A-Za-z])\.(&|and\b)")


def _cleanup(text: str) -> str:
    text = _DOUBLE_PERIOD.sub(".", text)
    text = _MISSING_DELIM_BEFORE_CONJ.sub(r"\1., \2", text)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


class Formatter:
    """One Formatter per (library snapshot, Style Profile) pair. Cheap to
    build; construct a fresh one whenever the cited set or the profile
    changes, rather than trying to mutate one in place."""

    def __init__(self, csl_items: list[dict], profile: dict | None = None):
        self.profile = profile or sp_module.default_profile()
        style_path = sp_module.patch_csl_style(
            self.profile["based_on_csl"], self.profile.get("csl_overrides") or {}
        )
        self.style = CitationStylesStyle(style_path, validate=False)
        self.source = CiteProcJSON(csl_items)
        self.bibliography = CitationStylesBibliography(
            self.style, self.source, cp_formatter.plain
        )
        self._registered: dict[str, Citation] = {}

    def render_citation(self, reference_ids: list[str]) -> str:
        """One in-text citation, e.g. '(Fisher, 2001)', or a grouped
        '(A, 2003; B, 2006)' for a multi-reference citation."""
        key = ",".join(reference_ids)
        cite = self._registered.get(key)
        if cite is None:
            cite = Citation([CitationItem(rid) for rid in reference_ids])
            self.bibliography.register(cite)
            self._registered[key] = cite
        rendered = self.bibliography.cite(cite, lambda warning: None)
        return _cleanup(str(rendered))

    def render_bibliography(self) -> list[str]:
        """Every *registered* (i.e. actually cited) reference, sorted per
        the style, as plain-text entries for the `sanad-bibliography`
        content control."""
        self.bibliography.sort()
        return [_cleanup(str(entry)) for entry in self.bibliography.bibliography()]


def render_full_library(csl_items: list[dict], profile: dict | None = None) -> list[str]:
    """Convenience for validation/tooling: render every item in a library
    as a bibliography, regardless of whether anything cites it. A real
    document only ever uses Formatter.render_citation + render_bibliography
    for the subset it actually cites."""
    fmt = Formatter(csl_items, profile)
    for item in csl_items:
        fmt.render_citation([item["id"]])
    return fmt.render_bibliography()
