#!/usr/bin/env python3
"""Regenerate the SANAD "seal medallion" brand mark and every icon derived from it.

The bare seal (``sanad-seal-*.png``) is thin gold linework on a transparent
background, so it is nearly invisible on light UI and at small sizes. This script
composites it onto a solid ink disc with a bold gold rim -- the medallion -- which
stays legible on any background down to 16 px, and writes:

  * ``sanad-medallion-1024.png``            -- the source of truth
  * ``sanad-icon.ico``                       -- Windows Desktop / Taskbar icon
  * ``sanad-icon.icns``                      -- macOS application icon
  * ``../../app/renderer/assets/sanad-seal.png`` -- the in-app header / About seal

Run from anywhere:  python assets/branding/make_medallion.py
"""
import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw

BR = Path(__file__).resolve().parent
APP_SEAL = BR.parents[1] / "app" / "renderer" / "assets" / "sanad-seal.png"

INK = (23, 27, 36, 255)   # #171B24
GOLD = (201, 164, 79, 255)  # #C9A44F
SS = 4                     # supersample for clean circle edges
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def medallion(size=1024, margin_frac=0.02, rim_frac=0.035):
    big = size * SS
    canvas = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    m = int(big * margin_frac)
    ImageDraw.Draw(canvas).ellipse([m, m, big - m, big - m], fill=INK)
    seal = Image.open(BR / "sanad-seal-1024.png").convert("RGBA").resize((big, big), Image.LANCZOS)
    canvas.alpha_composite(seal)
    # clip everything to the disc, then stroke a bold gold rim on top
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse([m, m, big - m, big - m], fill=255)
    canvas.putalpha(Image.composite(canvas.split()[3], Image.new("L", (big, big), 0), mask))
    rw = int(big * rim_frac)
    ImageDraw.Draw(canvas).ellipse(
        [m + rw // 2, m + rw // 2, big - m - rw // 2, big - m - rw // 2],
        outline=GOLD, width=rw)
    return canvas.resize((size, size), Image.LANCZOS)


def write_ico(med, path):
    frames = []
    for s in ICO_SIZES:
        buf = io.BytesIO()
        med.resize((s, s), Image.LANCZOS).save(buf, format="PNG")
        frames.append((s, buf.getvalue()))
    out = bytearray(struct.pack("<HHH", 0, 1, len(frames)))
    off = 6 + 16 * len(frames)
    for s, data in frames:
        b = 0 if s == 256 else s
        out += struct.pack("<BBBBHHII", b, b, 0, 0, 1, 32, len(data), off)
        off += len(data)
    for _, data in frames:
        out += data
    Path(path).write_bytes(out)


def main():
    med = medallion(1024)
    med.save(BR / "sanad-medallion-1024.png")
    write_ico(med, BR / "sanad-icon.ico")
    med.resize((256, 256), Image.LANCZOS).save(APP_SEAL)
    try:
        med.resize((1024, 1024), Image.LANCZOS).save(BR / "sanad-icon.icns", format="ICNS")
    except Exception as e:  # pragma: no cover - platform-dependent
        print("icns skipped:", e)
    print("regenerated medallion, .ico, .icns, and in-app header seal")


if __name__ == "__main__":
    main()
