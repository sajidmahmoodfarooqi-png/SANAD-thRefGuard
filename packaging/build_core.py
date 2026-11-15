"""Build the standalone SANAD Core with PyInstaller.

Cross-platform: run this on each target OS (Windows/macOS/Linux) to produce the
folder `packaging/dist/sanad-core/` -- the program `sanad-core[.exe]` plus its
support files in `_internal/` -- then run the desktop packager (app/: `npm run
dist`) on the same OS, which ships that folder as the app's resources/core/.

    python packaging/build_core.py

Notes:
  * Run from the repo root with the project's dependencies installed
    (`pip install -r requirements.txt` plus `pyinstaller`).
  * The frozen Core embeds the CSL styles (citeproc-py-styles) and the schema,
    so the shipped app needs no system Python at all.
  * It is a FOLDER (PyInstaller "onedir"), not a single file. A one-file program
    unpacks its whole payload (~140 MB) into a temporary folder on every launch,
    and the antivirus re-scans it each time: about 50 seconds before the Core
    answered on an ordinary Windows laptop. A folder is unpacked once, by the
    installer, so the Core starts in a few seconds. The program does not run on
    its own without the `_internal/` folder beside it.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "packaging" / "dist"
SEP = os.pathsep  # ';' on Windows, ':' elsewhere -- PyInstaller --add-data separator


def remove_stale_onefile() -> None:
    """Delete a one-file Core left behind by an older build.

    Before the folder layout this script wrote `dist/sanad-core[.exe]` as a
    single file. On Linux/macOS that file has the very name the new folder
    needs, so PyInstaller cannot create the folder until it is gone; on Windows
    it would just sit next to the folder and invite shipping the wrong thing.
    """
    for name in ("sanad-core", "sanad-core.exe"):
        stale = DIST / name
        if stale.is_file():
            stale.unlink()
            print("removed stale one-file build:", stale)


def main() -> int:
    remove_stale_onefile()
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--name", "sanad-core",
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "packaging" / "build"),
        "--specpath", str(ROOT / "packaging"),
        "--collect-all", "citeproc",
        "--collect-all", "citeproc_styles",
        "--collect-all", "openpyxl",  # lazily imported in list_import.parse_xlsx
        "--collect-all", "docx",      # python-docx: manual reading + thesis formatting
        "--collect-all", "fitz",      # PyMuPDF: PDF thesis-manual text extraction
        "--collect-submodules", "uvicorn",
        "--collect-submodules", "sanad_core",
        "--hidden-import", "websockets",
        "--hidden-import", "anyio",
        "--add-data", f"{ROOT / 'sanad_core' / 'schema.sql'}{SEP}sanad_core",
        "--noconfirm",
        str(ROOT / "packaging" / "core_entry.py"),
    ]
    print("running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
