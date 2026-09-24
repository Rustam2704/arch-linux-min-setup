#!/usr/bin/env python3
"""Diablo's 30 px menu font (ui_art/font30s.pcx + font30.bin) as a TrueType font.

Each glyph is a 32x31 cell in the sprite sheet, one per byte value (Latin-1);
font30.bin holds two header bytes and then the advance of every character. The
letter's body is the light pixels (the dark outline around it is dropped: the
panel colours the text itself), and the lit pixels become one outline (their union, no seams), so at
15 pt on the 144 dpi panel (a 30 px em) the font lands pixel for pixel as in the
game. Digits get tabular alternates under the `tnum` feature, the way the panel
asks for them: same advance, ink centred.

Output: desktop/share/fonts/Diablo.ttf (family "Diablo").
"""
import os
import sys

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib import builder as feabuilder

sys.path.insert(0, os.path.dirname(__file__))
import pcx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHEET = os.path.join(ROOT, "diablo-spawn/ui_art/font30s.pcx")
WIDTHS = os.path.join(ROOT, "diablo-spawn/ui_art/font30.bin")
OUT = os.path.join(os.path.dirname(ROOT), "desktop/share/fonts/Diablo.ttf")
CELL_W, CELL_H, CHARS = 32, 31, 256
PX = 30                      # pixels per em: 15 pt at 144 dpi renders 1:1
UPM = PX * 32                # units per em (32 units per pixel keeps everything integral)
U = UPM // PX
BASELINE = 26                # row under the letters' feet in the cell
BODY = 40                    # brightness above which a pixel belongs to the letter, not its dark edge (the sheet is a grey ramp, indexes 227-239)
SPACING = 1                  # px between letters, as DrawArtStr spaces them
CODES = [*range(32, 127), 176]   # the ASCII cells and the degree sign; the rest of the sheet is
                                 # not Latin-1 (Pango falls back to the UI font for those characters)


def contours(rows):
    """Closed outlines of the lit pixels as one union: every pixel contributes its four
    edges, edges shared by two lit pixels cancel, the rest are chained into loops.
    (Separate rectangles per row touched along shared edges, and at any size that
    is not a whole multiple of the pixel the antialiasing of the two abutting shapes
    left a light seam - the "horizontal lines" through the letters at 18 pt.)"""
    lit = {(x, y) for y, row in enumerate(rows) for x, on in enumerate(row) if on}
    edges = {}
    for x, y in lit:
        # directed edges, outline running clockwise in a y-down grid
        for a, b in (((x, y), (x + 1, y)), ((x + 1, y), (x + 1, y + 1)),
                     ((x + 1, y + 1), (x, y + 1)), ((x, y + 1), (x, y))):
            if (b, a) in edges:
                del edges[(b, a)]          # the neighbour's opposite edge: interior
            else:
                edges[(a, b)] = True
    nxt = {}
    for a, b in edges:
        nxt.setdefault(a, []).append(b)
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur = [start], start
        while True:
            outs = nxt[cur]
            b = outs.pop()
            if not outs:
                del nxt[cur]
            if b == start:
                break
            loop.append(b)
            cur = b
        loops.append(loop)
    return loops


def main():
    w, fh, frames, pal = pcx.frames(SHEET, CHARS)
    widths = open(WIDTHS, "rb").read()[2:]
    bg = max(set(frames[65]), key=frames[65].count)          # the sheet's transparent index
    glyphs, advances, names, cmap = {}, {}, [".notdef"], {}
    digits = {}
    for code in CODES:
        f = frames[code]
        rows = []
        for y in range(fh):
            row = []
            for x in range(w):
                idx = f[y * w + x]
                r, g, b = pal[idx]
                row.append(idx != bg and (r + g + b) / 3 >= BODY)
            rows.append(row)
        if not any(any(r) for r in rows) and code != 32:
            continue
        name = f"uni{code:04X}"
        pen = TTGlyphPen(None)
        for loop in contours(rows):
            pts = [(x * U, (BASELINE - y) * U) for x, y in loop]
            pen.moveTo(pts[0])
            for pt in pts[1:]:
                pen.lineTo(pt)
            pen.closePath()
        glyphs[name] = pen.glyph()
        adv = (widths[code] or (8 if code == 32 else 10)) + SPACING
        advances[name] = (adv * U, 0)
        names.append(name)
        cmap[code] = name
        if 48 <= code <= 57:
            ink = [x for row in rows for x, on in enumerate(row) if on]
            digits[name] = (code, min(ink), max(ink) + 1)
    # tabular digits: one advance (the widest ink, the zero's, plus a pixel each side),
    # ink centred - the game's advances leave the digits too far apart in a column
    tab = max(x1 - x0 for _, x0, x1 in digits.values()) + 2
    for name, (code, x0, x1) in digits.items():
        alt = name + ".tnum"
        shift = ((tab - (x1 - x0)) // 2 - x0) * U
        pen = TTGlyphPen(None)
        g = glyphs[name]
        coords = [(x + shift, y) for x, y in g.coordinates]
        for start, end in zip([0] + [e + 1 for e in g.endPtsOfContours[:-1]], g.endPtsOfContours):
            pen.moveTo(coords[start])
            for p in coords[start + 1:end + 1]:
                pen.lineTo(p)
            pen.closePath()
        glyphs[alt] = pen.glyph()
        advances[alt] = (tab * U, 0)
        names.append(alt)
    glyphs[".notdef"] = TTGlyphPen(None).glyph()
    advances[".notdef"] = (10 * U, 0)

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(advances)
    fb.setupHorizontalHeader(ascent=BASELINE * U, descent=-(CELL_H - BASELINE) * U)
    fb.setupOS2(sTypoAscender=BASELINE * U, sTypoDescender=-(CELL_H - BASELINE) * U,
                usWinAscent=BASELINE * U, usWinDescent=(CELL_H - BASELINE) * U)
    fb.setupNameTable({"familyName": "Diablo", "styleName": "Regular", "fullName": "Diablo",
                       "psName": "Diablo-Regular", "uniqueFontIdentifier": "Diablo 30px from ui_art/font30s.pcx",
                       "version": "Version 1.0"})
    fb.setupPost()
    fea = "feature tnum {\n" + "".join(f"  sub {n} by {n}.tnum;\n" for n in digits) + "} tnum;\n"
    feabuilder.addOpenTypeFeaturesFromString(fb.font, fea)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fb.save(OUT)
    print(f"{len(names)} glyphs -> {OUT}; tabular digit advance {tab} px")


if __name__ == "__main__":
    main()
