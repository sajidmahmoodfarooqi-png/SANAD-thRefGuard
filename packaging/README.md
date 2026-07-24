# Packaging SANAD

SANAD ships as a desktop app (Electron) that bundles the Python Core as a frozen
standalone binary, so an installed copy needs **no system Python**.

Two build steps, run on the **same OS** you're targeting (do a Windows build on
Windows, macOS on macOS, Linux on Linux):

## 1. Build the Core binary

```bash
pip install -r requirements.txt pyinstaller
python packaging/build_core.py
```

This produces `packaging/dist/sanad-core[.exe]` — a self-contained service that
embeds Python, FastAPI/uvicorn, citeproc + the CSL styles, and the schema. Verify
it standalone if you like:

```bash
SANAD_PORT=23896 ./packaging/dist/sanad-core        # then GET /v1/health on that port
```

## 2. Build the installer

```bash
cd app
npm install
npm run dist          # electron-builder
```

`electron-builder` (configured in `app/package.json`) ships the Core binary from
`packaging/dist/` into the app's `resources/core/`, applies the icons from
`assets/branding/`, and produces the platform installer:

| Platform | Output |
|---|---|
| Windows | NSIS `.exe` installer, icon `sanad-icon.ico` |
| macOS | `.dmg`, icon `sanad-icon.icns` |
| Linux | `AppImage`, icon `icon-512.png` |

At runtime `app/main.js` launches `resources/core/sanad-core` (packaged) or
`python -m sanad_core.server` (dev), waits for `/v1/health`, and stores the
library in the per-user data directory.

## Notes

- Verified building on **Python 3.14** with PyInstaller 6.21 — the frozen Core
  renders citations correctly, confirming the CSL data is bundled.
- `packaging/build/`, `packaging/dist/`, and generated `.spec` files are
  build artifacts and are gitignored.
- Cross-compiling is not supported by PyInstaller; use a CI matrix (one runner
  per OS) to produce all three installers.
