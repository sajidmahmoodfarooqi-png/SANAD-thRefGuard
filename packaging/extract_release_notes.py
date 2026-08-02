"""Print the RELEASE_NOTES.md section for a given version, for the release body.

    python packaging/extract_release_notes.py 0.2.3

Extracts everything under the `## v0.2.3 ...` heading up to the next `## v`
heading. The leading heading line itself is dropped (the GitHub Release already
carries its own title). Falls back to a one-line pointer if the version isn't
found, so a release never fails just because notes are missing.
"""
import pathlib
import re
import sys

try:                                    # keep em-dashes etc. intact in the release body
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

version = (sys.argv[1] if len(sys.argv) > 1 else "").lstrip("v").strip()
notes_path = pathlib.Path(__file__).resolve().parent.parent / "RELEASE_NOTES.md"

body = ""
if version and notes_path.exists():
    text = notes_path.read_text(encoding="utf-8")
    m = re.search(rf"(?ms)^## v{re.escape(version)}\b.*?(?=^## v|\Z)", text)
    if m:
        # drop the '## vX — ...' heading line; keep the rest of the section
        body = re.sub(r"^## v\S+.*\n", "", m.group(0), count=1).strip()

print(body or f"SANAD the RefGuard v{version}. See RELEASE_NOTES.md for details.")
