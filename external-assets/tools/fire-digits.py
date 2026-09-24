#!/usr/bin/env python3
"""Cut the burning DIABLO logo (ui_art/smlogo.pcx, 15 frames) into its six flames and
press each flame through the shapes of the digits 1-9 as the panel draws them.

Output, what sky-stars uses (desktop/share/sky-desktop/fire/, installed with the tree):
  flame{k}-digit{d}.png              15 frames stacked vertically: the flame around and above the digit,
                                     the digit itself cut out and filled black (the panel's own digit
                                     under it is black too, but repaints later than the fire moves)
  spin.png                           the menu's spinning pentagram (ui_art/focus.pcx, 8 frames) at SPIN px
  index.json                         frame size per sheet
Reference only (external-assets/fire-digits/):
  flames/flame{k}/frame{i:02d}.png   the k-th flame alone, letter removed (k = 1..6 = D i a b l O)
  preview.png                        frame 0 of every flame x digit, 4x, for a look

The digit shape is the panel's own: the workspace strip font (xfconf plugin-45) at the
panel's DPI, bold like the active number, tabular figures like the strip.
"""
import json
import os
import subprocess
import sys

import cairo
import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

sys.path.insert(0, os.path.dirname(__file__))
import pcx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "diablo-spawn/ui_art/smlogo.pcx")
SPIN_SRC = os.path.join(ROOT, "diablo-spawn/ui_art/focus.pcx")   # 30x30, 8 frames
SPIN = 21                           # pentagram size on the panel, about the digit's height
OUT = os.path.join(ROOT, "fire-digits")          # reference: flames per frame, preview
TREE = os.path.join(os.path.dirname(ROOT), "desktop/share/sky-desktop/fire")   # what sky-stars uses
FRAMES = 15
TRANSPARENT = 250
LETTER_TOP = 78                     # first row of the letters; the flames live above
BELOW = 3                           # px of sheet under the digit's foot
# the whole flame is kept: the sheet rises LETTER_TOP * scale over the digit's top (the
# numbers sit low in the panel to make room, see STRIP_SHIFT in deskd)
HUG = 16                            # digit width + this = the flame width at the digit (sets the scale)
AIR = 1.5                           # the cut-out is a little wider than the glyph
SIDE_FADE = 8                       # px of fade at each side of a sheet
LETTERS = [(17, 71), (98, 114), (142, 176), (202, 232), (260, 287), (313, 364)]
# each flame's full width, measured: where its fire really is, split from the
# neighbour at the column with the least fire, plus 6 px of overlap - nothing clipped
BANDS = [(0, 89), (77, 137), (125, 190), (184, 247), (240, 304), (300, 389)]


def panel_font():
    try:
        return subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-p", "/plugins/plugin-45/font"],
                              capture_output=True, text=True).stdout.strip() or "Inter 15"
    except OSError:
        return "Inter 15"


def dpi():
    try:
        out = subprocess.run(["xrdb", "-query"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if line.startswith("Xft.dpi"):
                return float(line.split()[1])
    except OSError:
        pass
    return 96.0


def digit_mask(label, font, res):
    """(A8 surface, width, height) of the digit's ink, drawn as the strip draws it."""
    probe = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
    ctx = PangoCairo.create_context(cairo.Context(probe))
    PangoCairo.context_set_resolution(ctx, res)
    layout = Pango.Layout.new(ctx)
    desc = Pango.FontDescription.from_string(font)
    desc.set_weight(Pango.Weight.BOLD)
    layout.set_font_description(desc)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_font_features_new("tnum=1"))
    layout.set_attributes(attrs)
    layout.set_text(label, -1)
    ink, _ = layout.get_pixel_extents()
    surf = cairo.ImageSurface(cairo.FORMAT_A8, ink.width, ink.height)
    c = cairo.Context(surf)
    c.move_to(-ink.x, -ink.y)
    PangoCairo.show_layout(c, layout)
    surf.flush()
    return surf, ink.width, ink.height


def frame_surface(px, w, h, pal, static, x0, x1):
    """ARGB surface of one flame band (x0..x1, full height) without the static letter."""
    bw = x1 - x0 + 1
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, bw, h)
    buf = surf.get_data()
    stride = surf.get_stride()
    for y in range(h):
        row = y * w
        for x in range(x0, x1 + 1):
            i = row + x
            idx = px[i]
            if idx == TRANSPARENT or static[i]:
                continue
            r, g, b = pal[idx]
            if not (r >= g >= b and r - b > 40):
                continue                      # grey, white, black: a letter's edge, not fire
            o = y * stride + (x - x0) * 4
            buf[o:o + 4] = bytes((b, g, r, 255))
    surf.mark_dirty()
    return surf


def main():
    w, fh, frames, pal = pcx.frames(SRC, FRAMES)
    static = bytearray(w * fh)
    for i in range(w * fh):
        v = frames[0][i]
        if v != TRANSPARENT and all(f[i] == v for f in frames[1:]):
            static[i] = 1
    font, res = panel_font(), dpi()
    masks = {d: digit_mask(str(d), font, res) for d in range(1, 10)}
    print(f"font {font!r} at {res:.0f} dpi; digit ink sizes:",
          {d: (m[1], m[2]) for d, m in masks.items()})
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TREE, exist_ok=True)
    index = {"font": font, "dpi": res, "frames": FRAMES, "sheets": {}}
    bands = []
    for k, (x0, x1) in enumerate(BANDS, 1):
        flame_dir = os.path.join(OUT, "flames", f"flame{k}")
        os.makedirs(flame_dir, exist_ok=True)
        surfaces = []
        for i, f in enumerate(frames):
            s = frame_surface(f, w, fh, pal, static, x0, x1)
            s.write_to_png(os.path.join(flame_dir, f"frame{i:02d}.png"))
            surfaces.append(s)
        bands.append((x0, x1, surfaces))
    # where each flame's foot is: the x centre of the fire in the 30 rows above the
    # letters, over all frames, relative to the band
    base_x = []
    for x0, x1, _ in bands:
        total = weight = 0
        for f in frames:
            for y in range(LETTER_TOP - 30, LETTER_TOP):
                row = y * w
                for x in range(x0, x1 + 1):
                    i = row + x
                    idx = f[i]
                    if idx == TRANSPARENT or static[i]:
                        continue
                    r, g, b = pal[idx]
                    if r >= g >= b and r - b > 40:
                        total += x - x0
                        weight += 1
        base_x.append(total / weight if weight else (x1 - x0) / 2)
    print("flame feet at", [round(x0 + b) for (x0, _, _), b in zip(bands, base_x)])
    preview_cells = []
    for k, (x0, x1, surfaces) in enumerate(bands, 1):
        bw = x1 - x0 + 1
        for d in range(1, 10):
            mask, dw, dh = masks[d]
            lx0, lx1 = LETTERS[k - 1]
            # scale: the letter's own neighbourhood (letter +-6 px) becomes digit + HUG
            # px wide - the proportions of the first test, which read well; the frame
            # itself spans the whole flame so no tongue is cut
            scale = min(0.85, (dw + HUG) / (lx1 - lx0 + 1 + 12))
            ABOVE = int(LETTER_TOP * scale + 0.5)
            W, H = int(bw * scale + 0.5), ABOVE + dh + BELOW
            # the digit sits under the foot of the flame, not under the letter's middle:
            # the tongues lean, and a number placed by the letter looked pushed aside
            hole_x = int(base_x[k - 1] * scale - dw / 2 + 0.5)
            # below the flame, in the letters' zone, the fire only hugs the digit: the
            # rest there is shaped like the letter, not like the number
            hug = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
            hc = cairo.Context(hug)
            hc.set_source_rgba(0, 0, 0, 1)
            hc.rectangle(0, 0, W, ABOVE)
            hc.fill()
            # the flame's foot dies out over a few rows; below that only the halo around
            # the digit survives (the letter's own golden outline lives there)
            fade = cairo.LinearGradient(0, ABOVE, 0, ABOVE + 7)
            fade.add_color_stop_rgba(0, 0, 0, 0, 1)
            fade.add_color_stop_rgba(1, 0, 0, 0, 0)
            hc.set_source(fade)
            hc.rectangle(0, ABOVE, W, 7)
            hc.fill()
            hc.translate(hole_x, ABOVE)
            for width, alpha in ((14, 0.3), (9, 0.6), (5, 1.0)):
                hc.set_source_rgba(0, 0, 0, alpha)
                for dx in range(-width // 2, width // 2 + 1, 2):
                    for dy in range(-width // 2, width // 2 + 1, 2):
                        if dx * dx + dy * dy <= (width / 2) ** 2:
                            hc.mask_surface(mask, dx, dy)
            hug.flush()
            edge = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
            ec = cairo.Context(edge)
            ec.set_source_rgba(0, 0, 0, 1)
            ec.paint()
            ec.set_operator(cairo.OPERATOR_SOURCE)
            fade = cairo.LinearGradient(0, H - 8, 0, H)
            fade.add_color_stop_rgba(0, 0, 0, 0, 1)
            fade.add_color_stop_rgba(1, 0, 0, 0, 0)
            ec.set_source(fade)
            ec.rectangle(0, H - 8, W, 8)
            ec.fill()
            # the sides fade over 8 px: the logo's last flame runs into the image's
            # right edge, and a 3 px fade still read as a cut at the sixth number
            for x0, x1 in ((0, SIDE_FADE), (W, W - SIDE_FADE)):
                fade = cairo.LinearGradient(x0, 0, x1, 0)
                fade.add_color_stop_rgba(0, 0, 0, 0, 0)
                fade.add_color_stop_rgba(1, 0, 0, 0, 1)
                ec.set_source(fade)
                ec.rectangle(min(x0, x1), 0, SIDE_FADE, H - 8)
                ec.fill()
            edge.flush()
            sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H * FRAMES)
            ctx = cairo.Context(sheet)
            for i, s in enumerate(surfaces):
                ctx.save()
                ctx.translate(0, i * H)
                ctx.rectangle(0, 0, W, H)
                ctx.clip()
                ctx.save()
                ctx.translate(0, ABOVE - LETTER_TOP * scale)
                ctx.scale(scale, scale)
                pat = cairo.SurfacePattern(s)
                pat.set_filter(cairo.FILTER_BILINEAR)
                ctx.set_source(pat)
                ctx.paint()
                ctx.restore()
                # soft edges at the bottom and sides instead of a hard cut (DEST_IN is
                # unbounded in cairo, so the fade is applied as one full-frame mask)
                ctx.set_operator(cairo.OPERATOR_DEST_IN)
                ctx.mask_surface(edge, 0, 0)
                ctx.mask_surface(hug, 0, 0)
                # the digit is a hole in the fire, and the hole is filled black: the
                # number under it is black too (deskd paints the active one so), but the
                # panel repaints tens of ms after the fire has moved - this way the digit
                # is black the moment the fire lands on it
                ctx.set_operator(cairo.OPERATOR_CLEAR)
                ctx.translate(hole_x, ABOVE)
                for dx, dy in ((-AIR, 0), (AIR, 0), (0, -AIR), (0, AIR), (0, 0)):
                    ctx.mask_surface(mask, dx, dy)
                ctx.set_operator(cairo.OPERATOR_OVER)
                ctx.set_source_rgb(0, 0, 0)
                ctx.mask_surface(mask, 0, 0)
                ctx.restore()
            name = f"flame{k}-digit{d}.png"
            sheet.write_to_png(os.path.join(TREE, name))
            index["sheets"][name] = {"flame": k, "digit": d, "width": W, "height": H, "above": ABOVE,
                                     "hole_x": hole_x, "digit_width": dw, "digit_height": dh}
            preview_cells.append((k, d, sheet, W, H))
    # preview: rows = flames, columns = digits, frame 0 at 4x
    cw, ch = max(c[3] for c in preview_cells) + 6, max(c[4] for c in preview_cells) + 6
    prev = cairo.ImageSurface(cairo.FORMAT_ARGB32, cw * 9 * 4, ch * 6 * 4)
    pc = cairo.Context(prev)
    pc.set_source_rgb(0, 0, 0)
    pc.paint()
    for k, d, sheet, dw, dh in preview_cells:
        pc.save()
        pc.translate((d - 1) * cw * 4 + 12, (k - 1) * ch * 4 + 12)
        pc.scale(4, 4)
        pc.rectangle(0, 0, dw, dh)
        pc.clip()
        pat = cairo.SurfacePattern(sheet)
        pat.set_filter(cairo.FILTER_NEAREST)
        pc.set_source(pat)
        pc.paint()
        pc.restore()
    prev.write_to_png(os.path.join(OUT, "preview.png"))
    # the spinning pentagram of the main menu, scaled to the digit
    sw, sfh, sframes, spal = pcx.frames(SPIN_SRC, 8)
    sheet = cairo.ImageSurface(cairo.FORMAT_ARGB32, SPIN, SPIN * 8)
    ctx = cairo.Context(sheet)
    for i, f in enumerate(sframes):
        src = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sfh)
        buf, stride = src.get_data(), src.get_stride()
        for y in range(sfh):
            for x in range(sw):
                idx = f[y * sw + x]
                if idx != TRANSPARENT:
                    r, g, b = spal[idx]
                    o = y * stride + x * 4
                    buf[o:o + 4] = bytes((b, g, r, 255))
        src.mark_dirty()
        ctx.save()
        ctx.translate(0, i * SPIN)
        ctx.scale(SPIN / sw, SPIN / sfh)
        pat = cairo.SurfacePattern(src)
        pat.set_filter(cairo.FILTER_BILINEAR)
        ctx.set_source(pat)
        ctx.paint()
        ctx.restore()
    sheet.write_to_png(os.path.join(TREE, "spin.png"))
    index["spin"] = {"size": SPIN, "frames": 8}
    with open(os.path.join(TREE, "index.json"), "w") as f:
        json.dump(index, f, indent=1)
    print(f"{len(bands)} flames in {OUT}; {len(preview_cells)} digit sheets, spin.png and index.json in {TREE}")


if __name__ == "__main__":
    main()
