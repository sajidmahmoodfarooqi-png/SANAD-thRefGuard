# SANAD — branding & application icons

Icon assets for packaging the SANAD desktop application and its installers.

Two marks, each in its right role:

- **The compact mark** — a bracket pair `[ ]` embracing a jade check (a citation,
  verified in context) on an ink tile with a gold hairline. This is the
  **application / executable icon**, legible from 16 px up.
- **The seal** — the full ornate emblem (the RefGuard script arc, SANAD / سند,
  "CITATION INTEGRITY"). Use it large only: **installer splash and the About
  screen**, on a dark background.

## Files

| File | Use |
|---|---|
| `sanad-icon.ico` | Windows executable / installer icon (multi-resolution: 16–256 px). |
| `sanad-icon.icns` | macOS application icon. |
| `icon-16.png … icon-1024.png` | PNG set — Linux hicolor theme icons and general use. |
| `sanad-icon.svg` | Vector source for the app-icon tile (regenerate any size from this). |
| `sanad-seal-256.png`, `-512.png`, `-1024.png` | The ornate seal, transparent PNG, for splash / About (place on a dark ground). |

## Palette

- Ink `#171B24` · gold `#C9A44F` · manuscript paper `#EFE8D6` · jade `#41B898`

## Regenerating

The app-icon tile is pure vector (`sanad-icon.svg`) — render it at any size for
new targets. The seal uses the embedded calligraphic fonts **Noto Nastaliq Urdu**
and **Great Vibes** (both SIL OFL); it is provided here as rendered PNGs.
