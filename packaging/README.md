# Packaging SANAD

SANAD ships as a desktop app (Electron) that bundles the Python Core as a frozen
standalone program, so an installed copy needs **no system Python**.

Two build steps, run on the **same OS** you're targeting (do a Windows build on
Windows, macOS on macOS, Linux on Linux):

## 1. Build the Core

```bash
pip install -r requirements.txt pyinstaller
python packaging/build_core.py
```

This produces the folder `packaging/dist/sanad-core/`:

```
packaging/dist/sanad-core/
  sanad-core[.exe]     the program
  _internal/           everything it needs: Python, FastAPI/uvicorn,
                       citeproc + the CSL styles, the schema
```

The two belong together — the program does not run without `_internal/` beside
it. Verify it standalone if you like:

```bash
SANAD_PORT=23896 ./packaging/dist/sanad-core/sanad-core   # then GET /v1/health on that port
```

**Why a folder and not a single file.** Until 0.2.13 the Core was one
self-unpacking file (PyInstaller `--onefile`). It unpacked its whole payload
(~140 MB) into a temporary folder on every launch, and the antivirus re-scanned
it each time — about 50 seconds before the Core answered on an ordinary Windows
laptop. As a folder (`--onedir`) it is unpacked once, by the installer, and
starts in a few seconds.

## 2. Build the installer

```bash
cd app
npm install
npm run dist          # electron-builder
```

`electron-builder` (configured in `app/package.json`) ships the Core folder
`packaging/dist/sanad-core/` as the app's `resources/core/`, applies the icons from
`assets/branding/`, and produces the platform installer:

| Platform | Output |
|---|---|
| Windows | NSIS `.exe` installer, icon `sanad-icon.ico` |
| macOS | `.dmg`, icon `sanad-icon.icns` |
| Linux | `AppImage`, icon `icon-512.png` |

At runtime `app/main.js` launches `resources/core/sanad-core[.exe]` (packaged;
its support files are in `resources/core/_internal/`) or
`python -m sanad_core.server` (dev), opens the window at once, connects when
`/v1/health` answers, and stores the library in the per-user data directory.

## Notes

- Verified building on **Python 3.14** with PyInstaller 6.21 — the frozen Core
  renders citations correctly, confirming the CSL data is bundled.
- `packaging/build/`, `packaging/dist/`, and generated `.spec` files are
  build artifacts and are gitignored.
- Cross-compiling is not supported by PyInstaller; use a CI matrix (one runner
  per OS) to produce all three installers.
