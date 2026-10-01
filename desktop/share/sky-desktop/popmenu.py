"""One popup menu under the panel, shared by the sound and power menus: the window,
its style, the place under the pointer, the grab that closes it on a click outside,
Escape, and the one-instance toggle. A menu module only fills the grid it is given.
Hosted by osd-daemon, so it opens instantly and never twice."""
import os
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from sky_theme import css  # noqa: E402

PANEL, GAP = 66, 6

STYLE = css("""
.sky-menu { background-color: @COLOUR_BACKGROUND@; border: 1px solid @COLOUR_BORDER@; border-radius: 8px; }
.sky-menu * { font-family: @FONT@; color: @COLOUR_FOREGROUND@; }
.sky-menu .row-label { color: @COLOUR_MUTED@; font-size: 9pt; }
.sky-menu scale trough { min-height: 8px; background-color: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; }
.sky-menu scale highlight { background-color: @COLOUR_LIGHT@; border-color: @COLOUR_LIGHT@; }
.sky-menu scale slider { min-width: 22px; min-height: 22px; background-color: @COLOUR_FOREGROUND@; border: none; }
.sky-menu button { background: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; border-radius: 8px; padding: 6px 12px; box-shadow: none; }
.sky-menu button:hover { border-color: @COLOUR_LIGHT@; }
.sky-menu button:checked { background: @COLOUR_ACCENT@; color: @COLOUR_BACKGROUND@; }
.sky-menu button:checked * { color: @COLOUR_BACKGROUND@; }
.sky-menu switch { background-color: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; }
.sky-menu switch:checked { background-color: @COLOUR_ACCENT@; }
.sky-menu switch slider { background-color: @COLOUR_FOREGROUND@; }
""")
_styled = []


class PopMenu:
    def __init__(self, name, fill):
        """fill(grid, close) puts the menu's rows into the grid."""
        self.name, self.fill, self.win = name, fill, None

    def toggle(self):
        """Open the menu under the pointer, or close it if it is open."""
        if self.win is not None:
            self.close()
        else:
            self.win = self.build()

    def close(self, *_):
        win, self.win = self.win, None
        if win is not None:
            try:
                Gdk.Display.get_default().get_default_seat().ungrab()
            except Exception:                                   # noqa: BLE001
                pass
            win.destroy()
        return False

    def build(self):
        if not _styled:
            provider = Gtk.CssProvider()
            provider.load_from_data(STYLE.encode())
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                     Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            _styled.append(provider)
        win = Gtk.Window(type=Gtk.WindowType.POPUP)
        win.set_name(self.name)
        win.get_style_context().add_class("sky-menu")
        grid = Gtk.Grid(column_spacing=14, row_spacing=12, margin=16)
        win.add(grid)
        self.fill(grid, self.close)
        win.show_all()

        display = Gdk.Display.get_default()
        seat = display.get_default_seat()
        _, px, py = seat.get_pointer().get_position()
        monitor = display.get_monitor_at_point(px, py).get_geometry()
        width = win.get_preferred_width()[1]
        win.move(max(monitor.x, min(px - width // 2, monitor.x + monitor.width - width)), monitor.y + PANEL + GAP)

        tries = {"n": 0}

        def grab(*_):
            # the grab is what closes the menu on a click outside; when it fails (another
            # grab still active - the panel click that opened us, a menu closing) it is
            # retried, and if it never takes, the menu closes on its own after a while
            status = seat.grab(win.get_window(), Gdk.SeatCapabilities.ALL, True, None, None, None, None)
            if status == Gdk.GrabStatus.SUCCESS or self.win is not win:
                return False
            tries["n"] += 1
            if tries["n"] < 20:
                GLib.timeout_add(50, grab)
            else:
                GLib.timeout_add(8000, self.close)
            return False

        def pressed(_w, event):
            inside = 0 <= event.x < win.get_allocated_width() and 0 <= event.y < win.get_allocated_height()
            if not inside:
                self.close()
            return not inside

        win.connect("map-event", grab)
        win.connect("button-press-event", pressed)
        win.connect("key-press-event", lambda _w, e: self.close() if e.keyval == Gdk.KEY_Escape else None)
        return win
