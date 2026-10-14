"""Nerd Font outlines and four-segment panel icons for sysqd.

The font is opened once at daemon startup. SVGs then reuse its path; sampling
never imports fontTools or traces a glyph.
"""
import math

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from sky_theme import THEME

FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFontPropo-Regular.ttf"
HEIGHT = 44
# Physical pixels in the 44 px GtkImage. The ink boxes match the old glyphs;
# leading strips restore the old gaps after Genmon split the readings into
# separate plugins. Xfce's item bar itself adds no inter-plugin spacing.
# (leading strip, path width, painted height, trailing strip). The swap path is
# 23 units wide because edge antialiasing makes its visible ink 24 px wide.
GEOMETRY = {
    "cpu": (6, 36, 36, 5.5),
    "memory": (24, 38, 24, 5.5),
    "swap": (22, 23, 30, 5.5),
}
COLOURS = tuple(THEME[k] for k in ("light", "success", "warning", "danger"))


def outlines(font_path=FONT):
    """Map indicator to one SVG path and its bounds, extracted once."""
    font = TTFont(font_path)
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    result = {}
    for name in GEOMETRY:
        glyph = glyphs[cmap[ord(THEME["icons"][name])]]
        bounds = BoundsPen(glyphs)
        path = SVGPathPen(glyphs)
        glyph.draw(bounds)
        glyph.draw(path)
        result[name] = (path.getCommands(), bounds.bounds)
    font.close()
    return result


def level(pct):
    return max(1, min(4, math.ceil(max(0, pct) / 25)))


def svg(name, pct, glyphs):
    """Clip muted and lit bands to the glyph; every level has one canvas."""
    lead, width, height, tail = GEOMETRY[name]
    x, w, h = lead, width, height
    y = (HEIGHT - h) / 2
    canvas = lead + width + tail
    path, (xmin, ymin, xmax, ymax) = glyphs[name]
    sx, sy = w / (xmax - xmin), h / (ymax - ymin)
    # Font y grows upwards; SVG y grows downwards.
    transform = f"translate({x - xmin * sx:.3f} {y + ymax * sy:.3f}) scale({sx:.6f} {-sy:.6f})"
    count = level(pct)
    horizontal = name != "memory"
    bars = []
    for i, colour in enumerate(COLOURS):
        on = i < count
        fill = colour if on else THEME["muted"]
        if horizontal:
            band = h / 4
            top = y + h - (i + 1) * band
            # Black pinstripe between bands shows through the clipped shape.
            gap = 1.5 if i < 3 else 0
            bars.append(f'<rect x="{x:.3f}" y="{top + gap:.3f}" width="{w:.3f}" '
                        f'height="{band - gap:.3f}" fill="{fill}"/>')
        else:
            band = w / 4
            gap = 1.5 if i < 3 else 0
            bars.append(f'<rect x="{x + i * band:.3f}" y="{y:.3f}" '
                        f'width="{band - gap:.3f}" height="{h:.3f}" fill="{fill}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas:.3f}" height="{HEIGHT}" '
            f'viewBox="0 0 {canvas:.3f} {HEIGHT}">'
            f'<defs><clipPath id="glyph" clipPathUnits="userSpaceOnUse">'
            f'<path d="{path}" transform="{transform}"/></clipPath></defs>'
            f'<g clip-path="url(#glyph)">{"".join(bars)}</g></svg>')
