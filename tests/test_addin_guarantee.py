"""The Text Integrity Guarantee, enforced on the *client*.

The Core side of the guarantee is proven by the document-model fuzz test. But the
Word add-in writes to the live document via Office.js, and there the promise
("only ever writes inside a sanad-* content control") was previously held by a
code comment alone — the audit's flagged weakest link.

These tests statically guard the add-in source: every document-write must target a
content control that is tagged sanad-*, and none of the prose-writing Office.js
APIs (writing to the body, the raw selection, a range, or a paragraph) may appear.
If a future edit adds a prose write, the suite fails loudly.
"""
import re
from pathlib import Path

TASKPANE = Path(__file__).resolve().parent.parent / "connectors" / "word" / "taskpane.js"
JS = TASKPANE.read_text(encoding="utf-8")

# Office.js methods that *write* text/markup into the document.
WRITE = r"(?:insertText|insertHtml|insertOoxml|insertParagraph|insertBreak|insertFileFromBase64|clear|delete)"


def test_sanctioned_wrapping_pattern_exists():
    # citations are placed by creating a content control and tagging it sanad-*.
    assert ".insertContentControl(" in JS
    assert re.search(r'\.tag\s*=\s*"sanad-(cite|bibliography)"', JS), \
        "add-in must tag its content controls sanad-cite / sanad-bibliography"


def test_no_prose_writing_apis_anywhere():
    forbidden = {
        "write to the document body": r"\bbody\b\s*\.\s*" + WRITE,
        "reach the body": r"getBody\s*\(",
        "write straight to the selection": r"getSelection\s*\(\s*\)\s*\.\s*" + WRITE,
        "write to a raw range": r"getRange\s*\([^)]*\)\s*\.\s*" + WRITE,
        "write via setSelectedData": r"setSelectedData(Async)?\s*\(",
        "write into a paragraph object": r"\bparagraph\w*\s*\.\s*" + WRITE,
        "write into a range object": r"\brange\w*\s*\.\s*" + WRITE,
    }
    for why, pat in forbidden.items():
        assert not re.search(pat, JS), f"add-in could {why}: pattern /{pat}/ found"


def test_every_write_targets_a_tagged_content_control():
    # variables created as content controls
    cc_vars = set(re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*[^;\n]*\.insertContentControl\s*\(", JS))
    assert cc_vars, "expected at least one content-control variable"
    # each such control must be tagged sanad-*
    for v in cc_vars:
        assert re.search(rf"\b{v}\s*\.\s*tag\s*=\s*\"sanad-", JS), \
            f"content control '{v}' is written to but never tagged sanad-*"
    # every write-method call's receiver must be one of those tagged controls
    for m in re.finditer(r"(\w+)\s*\.\s*" + WRITE + r"\s*\(", JS):
        receiver = m.group(1)
        assert receiver in cc_vars, \
            f"write '{receiver}.{m.group(0)}' targets a non-content-control receiver"
