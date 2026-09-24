"""Panel text measured the way genmon draws it, so labels can be padded to a fixed
width: readings that change ("offline" in place of two numbers, EN/RU/UA in a
proportional font) must not push their neighbours around.

Widths come from Pango with the plugin's own font (xfconf) at the screen's DPI
(xrdb), in Pango units (1024 per px); every string is measured once."""
import subprocess

from sky_theme import THEME

_cache = {}


def dpi():
    if "dpi" not in _cache:
        _cache["dpi"] = 96.0
        for line in subprocess.run(["xrdb", "-query"], capture_output=True, text=True).stdout.splitlines():
            if line.startswith("Xft.dpi:"):
                _cache["dpi"] = float(line.split()[1])
    return _cache["dpi"]


def panel_font(plugin_id):
    """The font xfconf gives a genmon plugin, or the theme's panel font."""
    key = ("font", plugin_id)
    if key not in _cache:
        out = subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-p", f"/plugins/plugin-{plugin_id}/font"],
                             capture_output=True, text=True).stdout.strip()
        _cache[key] = out or THEME["panel_font"]
    return _cache[key]


def width(markup, font):
    """Logical width of Pango markup in Pango units, in the given font at the screen DPI."""
    key = (markup, font)
    if key in _cache:
        return _cache[key]
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
    import cairo
    ctx = PangoCairo.create_context(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)))
    PangoCairo.context_set_resolution(ctx, dpi())
    layout = Pango.Layout.new(ctx)
    layout.set_font_description(Pango.FontDescription.from_string(font))
    layout.set_markup(markup, -1)
    _cache[key] = layout.get_size()[0]
    return _cache[key]


def pad_to(markup, target, font, align="right"):
    """`markup` padded with transparent zeroes to exactly `target` units: the text
    against the right edge, or centred. A tiny transparent zero (5 % size, about a
    pixel) carrying Pango letter spacing settles anything short of a whole zero;
    Pango only ever adds spacing, so the loop corrects upwards or drops a zero."""
    base = width(markup, font)
    if base >= target:
        return markup
    zero = width('<span font_features="tnum">0</span>', font)
    tiny = width('<span alpha="1" size="5%">0</span>', font)
    gap = target - base
    left = gap // 2 if align == "center" else 0
    parts = {"left": [0, 0], "right": [0, 0]}          # [whole zeroes, spacing units]
    for side, units in (("left", left), ("right", gap - left)):
        if units > 0:
            n = max(0, (units - tiny) // zero)
            parts[side] = [n, max(0, units - n * zero - tiny)]

    def filler(n, spacing):
        if n == 0 and spacing == 0:
            return ""
        return (f'<span alpha="1">{"0" * n}</span>'
                f'<span alpha="1" size="5%" letter_spacing="{spacing}">0</span>')

    def build():
        return (f'<span font_features="tnum">{filler(*parts["left"])}{markup}'
                f'{filler(*parts["right"])}</span>')
    out = build()
    side = "right" if gap - left > 0 else "left"
    for _ in range(8):
        off = target - width(out, font)
        if not off:
            break
        n, spacing = parts[side]
        spacing += off
        while spacing < 0 and n:                      # only positive spacing counts
            n, spacing = n - 1, spacing + zero
        parts[side] = [n, max(0, spacing)]
        out = build()
    return out
