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


def pad_to(markup, target, font, align="right", after=None, before=""):
    """`markup` padded with transparent zeroes to exactly `target` units: the text
    against the right edge, or centred. `after` is the markup that will follow it
    on the panel (None: measured as followed by a plain glyph; "": at a line end),
    `before` what precedes it - run boundaries (a size change, a fallback font)
    round differently, so the cell is measured between exactly its neighbours.

    Only the *left* filler is exact: its remainder is Pango letter spacing on its
    first glyph, which is always followed by text, and a loop corrects it against
    a measurement taken in context. The right filler (centring) is unspaced glyphs -
    whole zeroes and tiny 5 % ones - because spacing after the last glyph of a
    line is dropped by Pango."""
    base = width(markup, font)
    if base >= target:
        return markup
    zero = width('<span font_features="tnum">0</span>', font)
    tiny = width('<span alpha="1" size="5%">0</span>', font)
    gap = target - base
    right_units = gap // 2 if align == "center" else 0
    n_r, rest = divmod(right_units, zero)
    m_r = round(rest / tiny)

    def right_filler():
        if not right_units:
            return ""
        return (f'<span alpha="1">{"0" * n_r}</span>' if n_r else "") + \
               (f'<span alpha="1" size="5%">{"0" * m_r}</span>' if m_r else "")

    def left_budget():
        r = right_filler()
        return target - base - (width(f'<span font_features="tnum">{r}</span>', font) if r else 0)
    left = left_budget()
    if 0 < left < tiny and m_r:            # too little for even a tiny spaced zero: take one from the right
        m_r -= 1
        left = left_budget()
    n = max(0, (left - tiny) // zero)
    part = [n, max(0, left - (n * zero + tiny))] if left > 0 else None

    def left_filler():
        if part is None:
            return ""
        n, spacing = part
        if n:
            return (f'<span alpha="1" letter_spacing="{spacing}">0</span><span alpha="1">{"0" * (n - 1)}</span>'
                    f'<span alpha="1" size="5%">0</span>')
        return f'<span alpha="1" size="5%" letter_spacing="{spacing}">0</span>'

    def build():
        return f'<span font_features="tnum">{left_filler()}{markup}{right_filler()}</span>'
    out = build()
    tail = '<span alpha="1">0</span>' if after is None else after
    for _ in range(8):
        if part is None:
            break
        whole = width(before + out + tail, font)
        off = target - (whole - (width(before, font) if before else 0) - (width(tail, font) if tail else 0))
        if not off:
            break
        n, spacing = part
        spacing += off
        while spacing < 0 and n:
            n, spacing = n - 1, spacing + zero
        part = [n, max(0, spacing)]
        out = build()
    return out
