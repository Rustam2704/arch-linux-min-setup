"""The Alt+Tab switcher deskd shows while Alt is held: one row of window icons, the
selected one framed in the accent colour, its title underneath.

As in Windows and Plasma (KWin's tab box): the list is shown only after a short delay,
so a quick Alt+Tab switches without anything flashing up, and nothing is focused or
raised while the list is walked - the choice is taken when Alt is let go. deskd owns
the round (the order, the index, watching Alt); this file only draws.
"""
import cairo
from Xlib import X, Xatom, error

import gi
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo  # noqa: E402

from sky_theme import THEME, rgb as theme_rgb  # noqa: E402

ICON = 64          # px at 96 dpi; scaled with the screen's dpi
PAD = 14           # px at 96 dpi, around the row and between the cells
BG = theme_rgb("surface")
EDGE = theme_rgb("border")
ACCENT = theme_rgb("accent")
TEXT = theme_rgb("foreground")
MUTED = theme_rgb("muted")


def _rgba(c, a=1.0):
    return (c[0] / 255, c[1] / 255, c[2] / 255, a)


class Switcher:
    def __init__(self, xs, dpi):
        self.xs = xs
        self.k = dpi / 96.0
        self.win = None
        self.shown = False
        self.geom = None
        self.items = []            # [(xid, title, minimized)]
        self.index = 0
        self.icons = {}            # xid -> cairo surface (or None: the app has no icon)
        self.atom_icon = xs.d.intern_atom("_NET_WM_ICON")

    # ------------------------------------------------------------ icons
    def icon(self, xid):
        """The window's own icon (_NET_WM_ICON), the smallest one at least as big as a
        cell, premultiplied for cairo. Kept per window for the next round."""
        if xid in self.icons:
            return self.icons[xid]
        surface = None
        try:
            win = self.xs.d.create_resource_object("window", xid)
            prop = win.get_full_property(self.atom_icon, Xatom.CARDINAL)
            data = list(prop.value) if prop else []
            want, best, i = int(ICON * self.k), None, 0
            while i + 2 <= len(data):
                w, h = data[i], data[i + 1]
                if w <= 0 or h <= 0 or i + 2 + w * h > len(data):
                    break
                if best is None or (best[0] < want and w > best[0]) or (want <= w < best[0]):
                    best = (w, h, i + 2)
                i += 2 + w * h
            if best:
                w, h, start = best
                buf = bytearray(w * h * 4)
                for n, px in enumerate(data[start:start + w * h]):
                    a = (px >> 24) & 0xff
                    r, g, b = (px >> 16) & 0xff, (px >> 8) & 0xff, px & 0xff
                    if a < 255:
                        r, g, b = r * a // 255, g * a // 255, b * a // 255
                    buf[n * 4:n * 4 + 4] = bytes((b, g, r, a))        # ARGB32, little endian
                surface = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h, w * 4)
        except (error.XError, ValueError, MemoryError):
            surface = None
        self.icons[xid] = surface
        return surface

    def forget(self, xid):
        self.icons.pop(xid, None)

    # ------------------------------------------------------------ window
    def show(self, items, index, area):
        """items: [(xid, title, minimized)]; area: the screen rectangle to centre on."""
        self.items, self.index = items, index
        k = self.k
        cell, pad = int((ICON + 2 * PAD) * k), int(PAD * k)
        title_h = int(34 * k)
        per_row = max(1, min(len(items), int(area["width"] * 0.9 - 2 * pad) // cell))
        self.per_row = per_row
        w = per_row * cell + 2 * pad
        h = cell + title_h + 2 * pad
        x = area["x"] + (area["width"] - w) // 2
        y = area["y"] + (area["height"] - h) // 2
        if self.win is None:
            self.win = self.xs.window(self.xs.root, x, y, w, h, argb=True, override=True,
                                      events=X.ExposureMask)
            self.win.set_wm_class("deskd-switcher", "deskd")
        self.geom = (x, y, w, h)
        self.win.configure(x=x, y=y, width=w, height=h, stack_mode=X.Above)
        if not self.shown:
            self.win.map()
            self.shown = True
        self.draw()

    def select(self, index):
        self.index = index
        if self.shown:
            self.draw()

    def hide(self):
        if self.win is not None and self.shown:
            self.win.unmap()
        self.shown = False

    def draw(self):
        if not self.shown or not self.geom:
            return
        _, _, w, h = self.geom
        k = self.k
        cell, pad, icon = int((ICON + 2 * PAD) * k), int(PAD * k), int(ICON * k)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        c = cairo.Context(s)
        r = 12 * k
        self._rounded(c, 0.5, 0.5, w - 1, h - 1, r)
        c.set_source_rgba(*_rgba(BG, 0.97))
        c.fill_preserve()
        c.set_source_rgba(*_rgba(EDGE))
        c.set_line_width(1)
        c.stroke()
        n = len(self.items)
        first = 0
        if n > self.per_row:                       # more windows than fit: the row follows the choice
            first = min(max(0, self.index - self.per_row // 2), n - self.per_row)
        for slot, i in enumerate(range(first, min(n, first + self.per_row))):
            xid, _, minimized = self.items[i]
            cx = pad + slot * cell
            if i == self.index:
                self._rounded(c, cx + 2, pad + 2, cell - 4, cell - 4, 10 * k)
                c.set_source_rgba(*_rgba(ACCENT, 0.28))
                c.fill_preserve()
                c.set_source_rgba(*_rgba(ACCENT))
                c.set_line_width(max(2, round(2 * k)))
                c.stroke()
            surf = self.icon(xid)
            ix, iy = cx + (cell - icon) / 2, pad + (cell - icon) / 2
            if surf is not None:
                c.save()
                c.translate(ix, iy)
                c.scale(icon / surf.get_width(), icon / surf.get_height())
                c.set_source_surface(surf, 0, 0)
                c.get_source().set_filter(cairo.FILTER_GOOD)
                c.paint_with_alpha(0.45 if minimized else 1.0)
                c.restore()
            else:                                  # the app has no icon: a plain tile
                self._rounded(c, ix, iy, icon, icon, 10 * k)
                c.set_source_rgba(*_rgba(MUTED, 0.5 if minimized else 0.9))
                c.fill()
        if 0 <= self.index < n:
            _, title, minimized = self.items[self.index]
            layout = PangoCairo.create_layout(c)
            PangoCairo.context_set_resolution(layout.get_context(), 96.0 * k)
            layout.set_font_description(Pango.FontDescription.from_string(f'{THEME["font"]} 11'))
            layout.set_width(int((w - 2 * pad) * Pango.SCALE))
            layout.set_ellipsize(Pango.EllipsizeMode.END)
            layout.set_alignment(Pango.Alignment.CENTER)
            layout.set_text(title + ("  (minimized)" if minimized else ""), -1)
            _, th = layout.get_pixel_size()
            c.move_to(pad, pad + cell + (h - 2 * pad - cell - th) / 2)
            c.set_source_rgba(*_rgba(TEXT))
            PangoCairo.show_layout(c, layout)
        s.flush()
        self.xs.paint(self.win, s, 32)
        self.xs.flush()

    @staticmethod
    def _rounded(c, x, y, w, h, r):
        c.new_sub_path()
        c.arc(x + w - r, y + r, r, -1.5708, 0)
        c.arc(x + w - r, y + h - r, r, 0, 1.5708)
        c.arc(x + r, y + h - r, r, 1.5708, 3.1416)
        c.arc(x + r, y + r, r, 3.1416, 4.7124)
        c.close_path()
