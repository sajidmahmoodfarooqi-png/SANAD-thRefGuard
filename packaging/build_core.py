"""Build the standalone SANAD Core binary with PyInstaller.

Cross-platform: run this on each target OS (Windows/macOS/Linux) to produce
`packaging/dist/sanad-core[.exe]`, then run the desktop packager (app/: `npm run
dist`) on the same OS, which ships this binary into the app's resources/core/.

    python packaging/build_core.py

Notes:
  * Run from the repo root with the project's dependencies installed
    (`pip install -r requirements.txt` plus `pyinstaller`).
  * The frozen binary embeds the CSL styles (citeproc-py-styles) and the schema,
    so the shipped app needs no system Python at all.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEP = os.pathsep  # ';' on Windows, ':' elsewhere -- PyInstaller --add-data separator


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--name", "sanad-core",
        "--distpath", str(ROOT / "packaging" / "dist"),
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
