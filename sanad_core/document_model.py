"""The Text Integrity Guarantee, made executable (MVP_SPEC.md §1).

SANAD's central promise: it never touches your prose. In the real product that
promise is enforced in the Word add-in — "the add-in's write access is
code-restricted to content controls tagged sanad-cite / sanad-bibliography /
(opt-in) sanad-style-region. It has no code path that can write to any other
range in the document."

This module is the same restriction expressed in Python, so the guarantee is a
*testable* property rather than a claim in a docstring (see
tests/test_text_integrity.py, which fuzzes it). A document is an ordered list of
regions; a `ProseRegion` is the author's writing and carries no id and no tag, so
there is literally no handle by which Core code could address it. The one
sanctioned mutation, `apply_core_write`, can only ever resolve to a
`ControlRegion` whose tag is in `ALLOWED_TAGS` — everything else raises. There is
deliberately no other public function that mutates a Document.

The Office.js add-in mirrors this exact shape: render content in Core, hand back a
string, and let the guarded writer place it — only ever inside a tagged control.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The complete set of content-control tags Core is ever permitted to write into.
# sanad-style-region is opt-in (MVP_SPEC.md §1/§5); the first two are always on.
ALLOWED_TAGS = frozenset({"sanad-cite", "sanad-bibliography", "sanad-style-region"})


class ProseWriteError(Exception):
    """Raised when a write is aimed anywhere other than an allowed sanad-* control.
    Hitting this is the guarantee doing its job."""


@dataclass
class ProseRegion:
    """The author's own writing. No `control_id`, no `tag`: Core has no handle to
    address it, which is the whole point."""
    text: str


@dataclass
class ControlRegion:
    """A SANAD content control. Only `tag in ALLOWED_TAGS` is Core-writable; a
    control constructed with any other tag is still refused by the writer, so a
    mis-tag can never become a backdoor into the document body."""
    tag: str
    control_id: str
    text: str = ""


@dataclass
class Document:
    regions: list = field(default_factory=list)

    def control(self, control_id: str) -> ControlRegion | None:
        for r in self.regions:
            if isinstance(r, ControlRegion) and r.control_id == control_id:
                return r
        return None

    def controls(self, tag: str | None = None) -> list[ControlRegion]:
        return [r for r in self.regions
                if isinstance(r, ControlRegion) and (tag is None or r.tag == tag)]


def prose_snapshot(document: Document) -> tuple[str, ...]:
    """Every ProseRegion's text, in order — the thing that must be byte-identical
    before and after any Core operation."""
    return tuple(r.text for r in document.regions if isinstance(r, ProseRegion))


def apply_core_write(document: Document, control_id: str, new_text: str) -> None:
    """The ONE way Core-produced text (a rendered citation, a bibliography) may
    enter a document. It resolves `control_id` to a ControlRegion and rewrites
    only that region's text.

    It cannot touch prose: a ProseRegion has no `control_id`, so the lookup can
    never select one. A control whose tag is not in ALLOWED_TAGS, or an id that
    matches nothing, raises ProseWriteError rather than falling through to any
    other region.
    """
    for r in document.regions:
        if isinstance(r, ControlRegion) and r.control_id == control_id:
            if r.tag not in ALLOWED_TAGS:
                raise ProseWriteError(
                    f"refusing to write into a control tagged {r.tag!r}; "
                    f"Core may only write {sorted(ALLOWED_TAGS)}"
                )
            r.text = new_text
            return
    raise ProseWriteError(
        f"no sanad-* control with id {control_id!r}; Core may only write into "
        f"tagged controls, never into document prose"
    )
