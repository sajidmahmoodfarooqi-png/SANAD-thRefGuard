# SANAD — branding & application icons

Icon assets for packaging the SANAD desktop application and its installers.

Two marks, each in its right role:

- **The seal medallion** — the full ornate emblem (the RefGuard script arc,
  SANAD / سند, "CITATION INTEGRITY") composited on a solid ink disc with a bold
  gold rim, so it stays visible on any background and down to 16 px. Per the
  owner's decision (2026-08-16) this is the **application / OS icon** (Desktop &
  Taskbar) **and** the in-app header / About identity — the seal *is* the brand.
  Build it with `make_medallion.py` from `sanad-seal-1024.png`; source of
  truth is `sanad-medallion-1024.png`. Do **not** revert the app/OS icon to the
  compact mark — the bare transparent seal (`sanad-seal-*.png`) is nearly
  invisible on light UI and small sizes, which is the exact bug this replaced.
- **The compact mark** — a bracket pair `[ ]` embracing a jade check on an ink
  tile with a gold hairline (`icon-16…1024.png`, `sanad-icon.svg`). Retained for
  the **Word task-pane header** (inline SVG) and general small-glyph use, not the
  OS icon.

## Files

| File | Use |
|---|---|
| `sanad-icon.ico` | Windows executable / installer icon — the **seal medallion** (16–256 px). |
| `sanad-icon.icns` | macOS application icon — the seal medallion. |
| `sanad-medallion-1024.png` | Rendered seal medallion (ink disc + gold rim). Source for the icons above and the in-app header seal (`app/renderer/assets/sanad-seal.png`). |
| `icon-16.png … icon-1024.png` | Compact-mark PNG set — Linux hicolor theme icons and general small-glyph use. |
| `sanad-icon.svg` | Vector source for the compact-mark tile (regenerate any size from this). |
| `sanad-seal-256.png`, `-512.png`, `-1024.png` | The bare ornate seal, transparent PNG (input to the medallion; use only on a dark ground). |

## Palette

- Ink `#171B24` · gold `#C9A44F` · manuscript paper `#EFE8D6` · jade `#41B898`

## Regenerating

The app-icon tile is pure vector (`sanad-icon.svg`) — render it at any size for
new targets. The seal uses the embedded calligraphic fonts **Noto Nastaliq Urdu**
and **Great Vibes** (both SIL OFL); it is provided here as rendered PNGs.
