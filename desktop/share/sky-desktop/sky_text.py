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
    against the right edge, or centred. The remainder short of a whole zero is Pango
    letter spacing on the *first* zero of a filler (a tiny 5 % zero, about a pixel,
    when there is no whole one), never on the last glyph: spacing after the last
    glyph of a line is dropped by Pango, so a filler that ended with it measured
    right alone and ten pixels wider once other text followed."""
    base = width(markup, font)
    if base >= target:
        return markup
    zero = width('<span font_features="tnum">0</span>', font)
    tiny = width('<span alpha="1" size="5%">0</span>', font)
    gap = target - base
    left = gap // 2 if align == "center" else 0
    parts = {}
    for side, units in (("left", left), ("right", gap - left)):
        if units <= 0:
            parts[side] = None
            continue
        n = max(0, (units - tiny) // zero)             # whole zeroes, one of them spaced
        parts[side] = [n, max(0, units - (n * zero + tiny if n else 2 * tiny))]

    def filler(part):
        if part is None:
            return ""
        n, spacing = part
        if n:
            return (f'<span alpha="1" letter_spacing="{spacing}">0</span><span alpha="1">{"0" * (n - 1)}</span>'
                    f'<span alpha="1" size="5%">0</span>')
        return f'<span alpha="1" size="5%" letter_spacing="{spacing}">0</span><span alpha="1" size="5%">0</span>'

    def build():
        return (f'<span font_features="tnum">{filler(parts["left"])}{markup}'
                f'{filler(parts["right"])}</span>')
    side = "right" if parts["right"] else "left"
    out = build()
    sentinel = '<span alpha="1">0</span>'              # measure as text that is followed by more text
    for _ in range(8):
        off = target - (width(out + sentinel, font) - width(sentinel, font))
        if not off:
            break
        n, spacing = parts[side]
        spacing += off
        while spacing < 0 and n:
            n, spacing = n - 1, spacing + zero
        parts[side] = [n, max(0, spacing)]
        out = build()
    return out
