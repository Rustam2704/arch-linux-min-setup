#!/usr/bin/env python3
"""deskd — Windows-style window handling on top of i3.

What it adds (all event driven; idle cost is zero):
  * title bar buttons on every window: minimize / maximize / close as coloured
    circles on the right (yellow, green, red), drawn inside i3's own frame;
  * every window floats, as in Windows (i3 tiles nothing: ~/.config/i3/config);
    resize by dragging any edge or corner, with no modifier key;
  * drag a title bar with either button: the window follows the pointer (its frame
    is moved directly, i3 hears the result once), its edges stick to screen and
    window edges on the way; dropping it on the top edge maximizes it, on the
    left/right edge snaps it to that half of the screen, near a corner to that
    quarter, on a workspace number in the panel moves it there (blue preview while
    dragging); dragging a maximized or snapped window away gives it its previous
    size back;
  * Alt+Tab as in Windows: a switcher while Alt is held, the choice taken on release,
    minimized windows included; a second window of an app opens beside its sibling
    (cascade), never exactly on top of it;
  * maximize and snap keep the panel visible; restore puts the window back exactly
    where it was; app buttons (Telegram, ...) asking to minimize/maximize are obeyed;
    an app's own full screen is left alone; "keep above" windows stay on top; a
    window blocked by its modal dialog hands the click to the dialog;
  * Windows keys: Super+Up/Down/Left/Right walk max / half / quarter / restore;
  * every screen has its own workspaces 1..6 (7..9 while they exist); when a screen goes away its
    workspaces join the laptop screen, and move to the next screen plugged in;
  * the panel's workspace strip (rendered here, clickable).

Commands arrive as i3 `nop deskd ...` bindings (see ~/.config/i3/config) or from
`deskd-ctl`, which sends the same `nop` through i3.
"""
import json
import math
import os
import ctypes
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))   # i3ipc, sky_theme, xfpanel
import gi  # noqa: E402
from gi.repository import GLib  # noqa: E402
import cairo  # noqa: E402
from Xlib import X, Xatom, Xutil, display, error  # noqa: E402
from Xlib.ext import shape  # noqa: E402
from Xlib.protocol import event as xevent  # noqa: E402

import i3ipc  # noqa: E402
import xfpanel  # noqa: E402
import panels  # noqa: E402
import switcher  # noqa: E402
from i3ipc import walk, find  # noqa: E402
from sky_theme import THEME, rgb as theme_rgb

RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
STATE_FILE = os.path.join(RUN, "deskd-state.json")
WS_FILE = os.path.join(RUN, "deskd-workspaces.txt")          # primary screen


def ws_file(output):
    return os.path.join(RUN, f"deskd-workspaces-{output}.txt")

# --- look (keep in step with the client.* colours in ~/.config/i3/config) --------
TITLE_BG_FOCUSED = theme_rgb("surface")
TITLE_BG_OTHER = theme_rgb("background")
ACCENT = theme_rgb("accent")
ACCENT_LIGHT = theme_rgb("light")
BTN_COLOURS = [theme_rgb(name) for name in ("warning", "success", "danger")]
DANGER = theme_rgb("danger")             # drop targets on the workspace strip
MARK_ORANGE = (0xf4, 0x81, 0x1e)   # the orange stripe of the apple in the corner
PANEL_WS_COUNT = 6            # workspaces always shown per screen
MARK_FILE = os.path.join(RUN, "deskd-mark.json")   # where the active digit is, for sky-stars
# windows closed the moment they appear: (class, title). Sublime Text ignores
# "update_check": false for an unregistered copy and nags on every start.
DISMISS = {("Sublime_text", "Update - Sublime Text")}
# window classes kept out of the dock (_NET_WM_STATE_SKIP_TASKBAR, which docklike
# honours and i3 4.25 leaves alone): Telegram has its own panel indicator instead
NO_DOCK = {"TelegramDesktop"}
# apps whose main windows drop their title bar through a Motif hint; they get it back
TITLED_CLASSES = {"zoom"}
UNTITLED_TITLES = {"annotate_toolbar", "zoom_linux_float_video_window", "cpt_frame_xcb_window"}
TARGET_MARGIN = 40            # px the drop-target overlay extends past the workspace strip
# Zoom's screen-share border: while it is up the compositor is bypassed and every
# translucent overlay of ours would be a solid black box - so none is shown
SHARE_FRAME = "cpt_frame_xcb_window"
STAR_MARK = False             # the drawn pentagram over the digit; off while the game's spinning ones are tried
POPUP_OWNERS = ("net-menu", "power-menu", "panel-calendar")   # our pop-ups: no tooltip may cover them
MENU_HOSTS = ("osd-daemon",)      # daemons whose *menus* (window type POPUP_MENU) count as pop-ups too
BLOCK = 10                    # screen k owns workspaces k*10+1 .. k*10+9
HANDLE = 10                   # grab width around floating windows (px)
DRAG_START = 8                # px of movement before a right press becomes a drag
EDGE = 3                      # px from a screen edge that counts as "at the edge"
POLL_MS = 16
PANEL_FONT = THEME["panel_font"]
CURSOR_PNG = os.path.expanduser("~/.local/share/sky-desktop/cursor-diablo.png")   # the game's pointer, 1.5x
PASSTHROUGH_CLASSES = {"rustdesk"}   # remote desktops: keys go to the remote machine
DEBUG = bool(os.environ.get("DESKD_DEBUG"))

MARK_MAX = "_deskd_max"
MARK_SNAP = "_deskd_snap"     # + a kind: the window fills that half / quarter of the screen
SNAP_KINDS = ("left", "right", "tl", "tr", "bl", "br")
MARK_MIN = "_deskd_min"
MARK_CLICK = "_deskd_click"
DOUBLE_CLICK_S = 0.4          # two left clicks on a title bar within this = maximize/restore
DRAG_KEEP = 60                # px of a dragged window that must stay above the bottom of the screen
SNAP_ZONE = 15                # px: a dragged window's edge within this of a screen or window edge
                              # sticks to it (KWin's 10 px border and window snap zones, at 1.5x)
CORNER = 0.1                  # along a screen edge, this share of it at either end is a corner (quarter)
INNER_EDGE_S = 0.25           # an edge shared with another screen snaps only after the pointer rests
                              # there this long (KWin: crossing to the next screen must not snap)
ALT_TAB_SHOW_S = 0.09         # Alt held this long after Alt+Tab: the switcher appears (KWin's delay)
CASCADE = 40                  # px a new window of an app is offset from one sitting at the same spot
STRIP_PAD = "\u2007"           # figure space (29 px, ~80 % of an em) on both sides of each workspace number
STRIP_END = "\u2009\u200a"     # thin + hair space after the last number: with the tray's invisible
                              # 18 px next to it, 15 px from the sixth number's pentagram to the line
STRIP_TAIL = ""                # (a trailing spacer used to push the numbers left; the end pad does that now)
STRIP_SHIFT = 0                # px the numbers sit below the panel's centre (0: centred; the flame
                              # sheets rise past the top of the screen and that part is simply unseen)


def log(*a):
    print("deskd:", *a, flush=True)


def spawn(argv):
    """Fire and forget; GLib reaps the child (no zombies)."""
    try:
        GLib.spawn_async(argv, flags=GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.STDOUT_TO_DEV_NULL
                         | GLib.SpawnFlags.STDERR_TO_DEV_NULL)
    except GLib.Error as e:
        log("spawn failed:", argv[0], e)


def rgb(c, a=1.0):
    return (c[0] / 255, c[1] / 255, c[2] / 255, a)


# ================================================================== X helpers
class XServer:
    def __init__(self):
        self.d = display.Display()
        self.d.set_error_handler(lambda *a: None)          # windows vanish all the time
        self.screen = self.d.screen()
        self.root = self.screen.root
        self.atom = lambda name: self.d.intern_atom(name)
        self.argb = self._argb_visual()
        font = self.d.open_font("cursor")
        self.cursors = {}
        for name, glyph in (("h", 108), ("v", 116), ("tl", 134), ("tr", 136), ("bl", 12),
                            ("br", 14), ("t", 138), ("b", 16), ("l", 70), ("r", 96), ("hand", 60)):
            self.cursors[name] = font.create_glyph_cursor(font, glyph, glyph + 1,
                                                          (0, 0, 0), (65535, 65535, 65535))
        diablo = self.image_cursor(CURSOR_PNG, 0, 0)
        if diablo is not None:
            self.cursors["hand"] = diablo          # the game's gauntlet instead of X's hand
        self.gc_cache = {}

    def image_cursor(self, path, xhot, yhot):
        """An ARGB cursor from a PNG through libXcursor. Cursor ids are server-wide, so
        the one made on a ctypes connection serves python-xlib windows; that connection
        stays open, the cursor lives as long as it does."""
        try:
            surface = cairo.ImageSurface.create_from_png(path)
            w, h = surface.get_width(), surface.get_height()
            xc = ctypes.CDLL("libXcursor.so.1")
            x11 = ctypes.CDLL("libX11.so.6")
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XFlush.argtypes = [ctypes.c_void_p]

            class Image(ctypes.Structure):
                _fields_ = [("version", ctypes.c_uint32), ("size", ctypes.c_uint32), ("width", ctypes.c_uint32),
                            ("height", ctypes.c_uint32), ("xhot", ctypes.c_uint32), ("yhot", ctypes.c_uint32),
                            ("delay", ctypes.c_uint32), ("pixels", ctypes.POINTER(ctypes.c_uint32))]
            xc.XcursorImageCreate.restype = ctypes.POINTER(Image)
            xc.XcursorImageLoadCursor.restype = ctypes.c_ulong
            xc.XcursorImageLoadCursor.argtypes = [ctypes.c_void_p, ctypes.POINTER(Image)]
            self._cursor_dpy = x11.XOpenDisplay(None)
            if not self._cursor_dpy:
                return None
            img = xc.XcursorImageCreate(w, h)
            img.contents.xhot, img.contents.yhot = xhot, yhot
            surface.flush()
            data = bytes(surface.get_data())          # cairo ARGB32: premultiplied, native order - what Xcursor wants
            stride = surface.get_stride()
            base = ctypes.addressof(img.contents.pixels.contents)
            for y in range(h):
                ctypes.memmove(base + y * w * 4, data[y * stride:y * stride + w * 4], w * 4)
            cursor = xc.XcursorImageLoadCursor(self._cursor_dpy, img)
            x11.XFlush(self._cursor_dpy)
            return int(cursor) or None
        except Exception as e:                       # noqa: BLE001 - the X hand will do
            log("image cursor failed:", e)
            return None

    def _argb_visual(self):
        for depth in self.screen.allowed_depths:
            if depth.depth == 32:
                for v in depth.visuals:
                    if v.visual_class == X.TrueColor:
                        cmap = self.root.create_colormap(v.visual_id, X.AllocNone)
                        return v.visual_id, cmap
        return None

    def window(self, parent, x, y, w, h, argb=False, input_only=False, override=True,
               events=0, cursor=None, bg=None):
        kw = {"event_mask": events}
        if override:
            kw["override_redirect"] = True
        if cursor is not None:
            kw["cursor"] = cursor
        if input_only:
            return parent.create_window(x, y, max(1, w), max(1, h), 0, 0, X.InputOnly,
                                        X.CopyFromParent, **kw)
        if argb and self.argb:
            vid, cmap = self.argb
            return parent.create_window(x, y, max(1, w), max(1, h), 0, 32, X.InputOutput, vid,
                                        colormap=cmap, border_pixel=0,
                                        background_pixel=bg if bg is not None else 0, **kw)
        return parent.create_window(x, y, max(1, w), max(1, h), 0, X.CopyFromParent,
                                    X.InputOutput, X.CopyFromParent,
                                    background_pixel=bg if bg is not None else 0, **kw)

    def paint(self, win, surface, depth):
        """Put a cairo ARGB32 surface onto a window, in strips small enough for one request."""
        w, h = surface.get_width(), surface.get_height()
        data = memoryview(surface.get_data())     # sliced per strip; no whole-image copy
        stride = surface.get_stride()
        gc = self.gc_cache.get(win.id)
        if gc is None:
            gc = win.create_gc()
            self.gc_cache[win.id] = gc
        rows = max(1, 200000 // stride)
        for y in range(0, h, rows):
            n = min(rows, h - y)
            win.put_image(gc, 0, y, w, n, X.ZPixmap, depth, 0,
                          bytes(data[y * stride:(y + n) * stride]))

    def pointer(self):
        p = self.root.query_pointer()
        return p.root_x, p.root_y, p.mask

    def flush(self):
        self.d.flush()


def argb_pixel(c, alpha):
    """Premultiplied ARGB pixel for a 32-bit window background."""
    a = int(alpha * 255)
    return (a << 24) | (int(c[0] * alpha) << 16) | (int(c[1] * alpha) << 8) | int(c[2] * alpha)


# ================================================================== title bar buttons
class ButtonStrip:
    """Three coloured circles at the right end of one window's title bar.
    A child of i3's frame window, so it moves, hides and stacks with the window."""
    def __init__(self, xs, frame, depth):
        self.xs = xs
        self.frame = frame
        self.depth = 32 if depth == 32 else 24
        self.win = xs.window(frame, 0, 0, 1, 1, argb=(self.depth == 32), override=True,
                             events=X.ButtonPressMask | X.ButtonReleaseMask | X.EnterWindowMask
                             | X.LeaveWindowMask | X.PointerMotionMask | X.ExposureMask,
                             cursor=xs.cursors["hand"])
        self.geom = None
        self.focused = None
        self.hover = -1
        self.pressed = -1
        self.d = 12
        self.gap = 8
        self.pad = 8
        self.win.map()

    def layout(self, frame_w, deco_h, focused):
        d = max(14, round(deco_h * 0.63))          # 1.5x the first version
        gap = max(6, round(d * 0.45))
        pad = max(6, round(d * 0.5))
        w = 3 * d + 2 * gap + 2 * pad
        h = max(d + 2, deco_h - 4)
        geom = (max(0, frame_w - w - 3), max(1, (deco_h - h) // 2), w, h)
        changed = geom != self.geom or focused != self.focused or (d, gap, pad) != (self.d, self.gap, self.pad)
        self.d, self.gap, self.pad = d, gap, pad
        if geom != self.geom:
            self.win.configure(x=geom[0], y=geom[1], width=w, height=h, stack_mode=X.Above)
            self.geom = geom
        self.focused = focused
        if changed:
            self.draw()

    def index_at(self, x):
        if not self.geom:
            return -1
        for i in range(3):
            cx = self.pad + i * (self.d + self.gap)
            if cx - self.gap / 2 <= x <= cx + self.d + self.gap / 2:
                return i
        return -1

    def draw(self):
        if not self.geom:
            return
        _, _, w, h = self.geom
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        c = cairo.Context(s)
        c.set_source_rgba(*rgb(TITLE_BG_FOCUSED if self.focused else TITLE_BG_OTHER))
        c.paint()
        r = self.d / 2
        cy = h / 2
        for i, col in enumerate(BTN_COLOURS):
            cx = self.pad + i * (self.d + self.gap) + r
            alpha = 1.0 if self.focused or self.hover >= 0 else 0.55
            c.set_source_rgba(*rgb(col, alpha))
            c.arc(cx, cy, r, 0, 6.2832)
            c.fill()
            if self.hover >= 0:                 # symbols appear on hover, like macOS
                c.set_source_rgba(0, 0, 0, 0.55)
                c.set_line_width(max(1.4, self.d / 9))
                c.set_line_cap(cairo.LINE_CAP_ROUND)
                k = r * 0.45
                if i == 0:
                    c.move_to(cx - k, cy); c.line_to(cx + k, cy)
                elif i == 1:
                    c.move_to(cx - k, cy); c.line_to(cx + k, cy)
                    c.move_to(cx, cy - k); c.line_to(cx, cy + k)
                else:
                    c.move_to(cx - k, cy - k); c.line_to(cx + k, cy + k)
                    c.move_to(cx + k, cy - k); c.line_to(cx - k, cy + k)
                c.stroke()
            if self.pressed == i:
                c.set_source_rgba(0, 0, 0, 0.25)
                c.arc(cx, cy, r, 0, 6.2832)
                c.fill()
        s.flush()
        self.xs.paint(self.win, s, self.depth)

    def destroy(self):
        try:
            self.win.destroy()
        except Exception:
            pass
        self.xs.gc_cache.pop(self.win.id, None)


# ================================================================== monitors
class ActiveMark:
    """A thin inverted pentagram over the workspace number you are on, drawn in its
    own transparent window above the panel - a panel label cannot draw behind its
    own text, and this has to sit around the digit, not under it."""
    def __init__(self, xs):
        self.xs = xs
        self.win = xs.window(xs.root, 0, 0, 1, 1, argb=True, override=True,
                             events=X.ExposureMask)
        self.win.set_wm_class("deskd", "deskd")
        self.geom = None
        self.shown = False
        self.digit = self.font = None
        self.dpi = 96.0

    def place(self, x, y, w, h, digit=None, font=None, dpi=96.0):
        changed = (x, y, w, h) != self.geom or (digit, font) != (self.digit, self.font)
        self.digit, self.font, self.dpi = digit, font, dpi
        if changed:
            self.geom = (x, y, w, h)
            self.win.configure(x=x, y=y, width=max(1, w), height=max(1, h))
        if not self.shown:
            self.win.map()                       # drawing into an unmapped window is lost
            self.shown = True
            changed = True
        if changed:
            self.draw()

    def hide(self):
        if self.shown:
            self.win.unmap()
            for w in self.spins:
                w.unmap()
            self.shown = False

    def draw(self):
        if not self.geom:
            return
        _, _, w, h = self.geom
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w), max(1, h))
        ctx = cairo.Context(surface)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)
        # a point-down star is 1.809 radii tall and 1.902 wide, and reaches further
        # below its centre than above it: size it to the window and lift the centre
        # so the drawing itself comes out centred
        radius = min((h - 3) / 1.809, (w - 3) / 1.902)
        cx, cy = w / 2, h / 2 - radius * 0.0955
        # one point straight down: y grows downwards, so the first vertex is at 90 deg
        points = [(cx + radius * math.cos(math.radians(90 + i * 72)),
                   cy + radius * math.sin(math.radians(90 + i * 72))) for i in range(5)]
        ctx.move_to(*points[0])
        for index in (2, 4, 1, 3):
            ctx.line_to(*points[index])
        ctx.close_path()
        ctx.set_line_width(1.6)                  # as thin as the lines in the panel icons
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_source_rgba(*rgb(MARK_ORANGE))
        ctx.stroke()
        self.cut_out_digit(ctx, w, h)
        self.xs.paint(self.win, surface, 32)

    def cut_out_digit(self, ctx, w, h):
        """Rub the star out where the panel draws the number, so the star reads as
        being behind it. The window itself cannot go under the panel - the panel is
        opaque - so the hole does the same job."""
        if not self.digit or not self.font:
            return
        try:
            gi.require_version("Pango", "1.0")
            gi.require_version("PangoCairo", "1.0")
            from gi.repository import Pango, PangoCairo
            layout = PangoCairo.create_layout(ctx)
            PangoCairo.context_set_resolution(layout.get_context(), self.dpi)
            layout.set_font_description(Pango.FontDescription.from_string(self.font))
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_font_features_new("tnum=1"))
            layout.set_attributes(attrs)
            layout.set_text(self.digit, -1)
            ink, _ = layout.get_pixel_extents()
            ctx.save()
            ctx.translate(w / 2 - (ink.x + ink.width / 2), h / 2 - (ink.y + ink.height / 2))
            PangoCairo.layout_path(ctx, layout)
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            ctx.set_line_width(4)                    # a little air around the glyph
            ctx.stroke_preserve()
            ctx.fill()
            ctx.restore()
        except Exception as e:                       # noqa: BLE001 - the star just stays whole
            log("digit cut-out failed:", e)


class MarkFile:
    """Where the active workspace digit is, written for sky-stars, which animates the
    fire and the spinning pentagrams around it. The animation used to live here, but
    deskd stalls for a quarter of a second on every workspace switch (i3 tree, panel
    windows, Pango, title buttons) and froze it; sky-stars has a loop of its own."""
    def __init__(self, i3):
        self.i3 = i3
        self.state = None

    def show(self, label, centre_x, top_y):
        self.write({"shown": True, "label": label, "centre_x": round(centre_x, 1), "top_y": round(top_y, 1)})

    def hide(self):
        self.write({"shown": False})

    def write(self, state):
        if state == self.state:
            return
        self.state = state
        try:
            with open(MARK_FILE + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(MARK_FILE + ".tmp", MARK_FILE)
        except OSError as e:
            log("mark file failed:", e)
            return
        try:
            self.i3.tick("sky-stars mark")   # sky-stars reads the file on this, not on its next 60 ms poll
        except Exception as e:             # noqa: BLE001
            log("mark tick failed:", e)


class PanelDim:
    """The panel sits under a thin dark veil, with a hole where the pointer is. That
    is how the volume icon behaves on its own - quiet until you point at it - and
    the only way to give every plugin the same behaviour: their drawings belong to
    the panel, and nothing outside it can repaint them brighter.

    One window per panel, click-through (empty input shape), so the panel keeps
    every click and the hole simply follows the pointer."""
    SHADE = 0.38

    def __init__(self, xs, geom):
        self.xs = xs
        self.geom = geom
        x, y, w, h = geom
        self.win = xs.window(xs.root, x, y, w, h, argb=True, override=True,
                             events=X.ExposureMask)
        self.win.set_wm_class("deskd", "deskd")
        try:
            shape.rectangles(self.win, shape.SO.Set, shape.SK.Input, 0, 0, 0, [])
        except Exception as e:                       # noqa: BLE001 - only the click-through
            log("panel veil is not click-through:", e)
        self.hole = None
        self.shown = True
        self.win.map()
        self.draw()

    def matches(self, geom):
        return self.geom == geom

    def set_visible(self, visible):
        """A window covering the screen (a photo, a video, anything full-screen) must
        not have our veil or anything else of ours on top of it."""
        if visible == self.shown:
            return
        self.shown = visible
        if visible:
            self.win.map()
            self.draw()
        else:
            self.win.unmap()

    def set_hole(self, hole):
        if hole != self.hole:
            self.hole = hole
            self.draw()

    def raise_above(self):
        self.win.configure(stack_mode=X.Above)

    def draw(self):
        x0, y0, w, h = self.geom
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w), max(1, h))
        ctx = cairo.Context(surface)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, self.SHADE)
        ctx.paint()
        if self.hole:
            hx, hy, hw, hh = self.hole
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            radius, inset = 7, 2
            x, y = hx - x0 + inset, hy - y0 + inset
            right, bottom = x + hw - 2 * inset, y + hh - 2 * inset
            ctx.new_sub_path()
            ctx.arc(right - radius, y + radius, radius, -1.5708, 0)
            ctx.arc(right - radius, bottom - radius, radius, 0, 1.5708)
            ctx.arc(x + radius, bottom - radius, radius, 1.5708, 3.1416)
            ctx.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
            ctx.close_path()
            ctx.fill()
        self.xs.paint(self.win, surface, 32)


class Monitors:
    """Screens are remembered with autorandr.

    * the set of connected screens changed (plug / unplug): apply the saved layout
      for that set, or place new screens side by side when the set is new;
    * the same screens, but the layout changed (display settings): save it, so it
      comes back next time this set is connected. No Save button anywhere.
    """
    SETTLE_MS = 2500

    def __init__(self, xs):
        from Xlib.ext import randr
        self.xs = xs
        self.timer = None
        self.last_fp = None
        try:
            ext = xs.d.query_extension("RANDR")
            self.base = ext.first_event if ext.present else None
            xs.root.xrandr_select_input(randr.RRScreenChangeNotifyMask
                                     | randr.RROutputChangeNotifyMask | randr.RRCrtcChangeNotifyMask)
        except Exception as e:
            log("randr unavailable:", e)
            self.base = None
        self.last_fp = self.fingerprint()
        GLib.timeout_add(self.SETTLE_MS, self.save_if_new)

    def is_randr(self, e):
        return self.base is not None and self.base <= e.type <= self.base + 1

    @staticmethod
    def run(*args):
        if os.environ.get("DESKD_NO_PANELS"):      # a nested X server (tests): never touch autorandr
            return ""
        try:
            return subprocess.run(["autorandr", *args], capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.TimeoutExpired):
            return ""

    def fingerprint(self):
        return self.run("--fingerprint").strip()

    def changed(self):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(1200, self.settle)

    def settle(self):
        self.timer = None
        fp = self.fingerprint()
        if fp != self.last_fp:
            self.last_fp = fp
            log("screens changed, applying saved layout")
            self.run("--change", "--default", "horizontal")
            self.ensure_primary()
        else:
            GLib.timeout_add(self.SETTLE_MS, self.save_if_new)
        return False

    def ensure_primary(self):
        """The laptop screen stays primary, so the panel stays on it."""
        out = subprocess.run(["xrandr", "--query"], capture_output=True, text=True).stdout
        if " primary " in out:
            return
        for line in out.splitlines():
            name = line.split(" ")[0]
            if " connected" in line and name.startswith(("eDP", "LVDS")):
                subprocess.run(["xrandr", "--output", name, "--primary"])
                return

    def save_if_new(self):
        if self.fingerprint() != self.last_fp:
            return False                       # still settling after a plug event
        if self.run("--current").strip():
            return False                       # matches a saved profile already
        import hashlib
        fp = self.last_fp or ""
        outputs = [l.split()[0] for l in fp.splitlines() if l.strip()]
        name = "laptop" if len(outputs) == 1 else "screens-" + hashlib.sha1(fp.encode()).hexdigest()[:8]
        self.run("--save", name, "--force")
        log("saved screen layout as", name)
        return False


# ================================================================== main daemon
class Deskd:
    def __init__(self):
        self.xs = XServer()
        self.i3 = i3ipc.I3()
        self.tree = None
        self.strips = {}            # con_id -> ButtonStrip
        self.strip_by_win = {}      # strip window id -> con_id
        self.frames = {}            # client window id -> (frame window, depth)
        self.targets_hot = False    # which drop target is lit right now
        self._ws_snap = None        # workspaces, kept for half a second during a drag
        self._ws_snap_at = 0.0
        self.docks = None           # the panel's frames, for stacking
        self.docks_at = 0.0
        self.handles = []           # [(xwindow, info)]
        self.handle_by_win = {}
        self.resizing = None
        self.drag = None
        self.preview = None
        self.targets = None         # drop-target overlays (per strip) during a drag
        self.last_click = None      # (con, time, x, y) of the last left title bar click
        self._strips = None         # [(genmon plugin id, output)] of the workspace strips
        self.strip_geoms = {}       # plugin id -> screen rectangle
        self.click_layers = {}      # plugin id -> click window over the strip
        self.ws_mark = None         # the pentagram over the workspace in front of you
        self.busy_outputs = set()   # screens with a full-screen window: nothing of ours on top
        self.sharing = False        # Zoom's share frame is up: no overlays at all
        self.audio_geoms = {}           # plugin id -> where its sound-wheel layer sits
        self.passthrough_frame = None   # the remote desktop's frame while it is focused
        self.passthrough_client = None

        self.audio_layers = {}      # plugin id -> InputOnly window over panel-audio: wheel = volume, middle = mute
        self.veils = {}             # dock frame id -> the dimming veil over that panel
        self.panel_items = []       # (rectangle, plugin id) of everything on the panel
        self.panel_windows = set()  # panel windows we watch the pointer on
        self.reflow_pending = False
        self.click_by_win = {}
        self.items_by_output = {}   # output -> ([(label, ws)], segments)
        self.bounds_cache = {}
        self.refresh_pending = False
        self.state = self._load_state()
        self.blocks = self.state.setdefault("blocks", {})     # output name -> block index
        self.last_ws_text = {}
        self.passthrough = False
        self.expect = {}            # class -> (workspace, when): "open the next window here"
        self.focus_order = []       # con ids, most recently focused first (Alt+Tab walks it)
        self.alt_tab = None         # the Alt+Tab round while Alt is held: {"order", "idx", "since"}
        self.above = set()          # client windows that asked to stay on top (_NET_WM_STATE_ABOVE)
        self.x_counts = {}          # DESKD_DEBUG: X events per type, logged every 10 s

        root_mask = X.SubstructureNotifyMask | X.PropertyChangeMask
        self.xs.root.change_attributes(event_mask=root_mask)
        self.A = {n: self.xs.atom(n) for n in (
            "WM_CHANGE_STATE", "_NET_WM_STATE", "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_STATE_MODAL", "_NET_WM_PID", "_NET_ACTIVE_WINDOW",
            "_NET_WM_STATE_ABOVE", "_NET_WM_WINDOW_TYPE", "_KDE_NET_WM_WINDOW_TYPE_OVERRIDE")}
        self.switcher = switcher.Switcher(self.xs, self.dpi())
        GLib.io_add_watch(self.xs.d.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self.on_x)
        self.monitors = Monitors(self.xs)
        self.sub = i3ipc.Subscription(["window", "workspace", "output", "binding", "shutdown", "tick", "mode"],
                                      self.on_i3)
        self.normalize_marks()
        self.outputs_changed()
        self.refresh()
        self.skip_dock_existing()
        if self.share_frame_present():
            self.set_sharing(True)
        # the panel can restart or reflow; keep the click layer on the workspace strip
        GLib.timeout_add_seconds(20, self.recheck_strips)
        GLib.timeout_add(1500, lambda: (self.watch_panel_items(), False)[1])
        self.watch_power()
        if DEBUG:
            GLib.timeout_add_seconds(10, self.log_x_counts)
        self.pump()

    def log_x_counts(self):
        """Where the wake-ups come from: X events per type over the last 10 s."""
        log("x events/10s:", dict(sorted(self.x_counts.items(), key=lambda kv: -kv[1])))
        self.x_counts = {}
        return True

    def watch_power(self):
        """The kernel reports the cable the moment it moves (udev, power_supply); the
        battery indicator is refreshed there and then, instead of waiting for its own
        ten-second beat. UPower was tried first and turned out to lag on plugging in."""
        try:
            gi.require_version("GUdev", "1.0")
            from gi.repository import GUdev
            self.udev = GUdev.Client(subsystems=["power_supply"])
            self.udev.connect("uevent", lambda *_: self.refresh_plugin("panel-battery"))
        except Exception as e:                       # noqa: BLE001 - only the quick update
            log("power watch failed:", e)

    def refresh_plugin(self, command):
        """Make every genmon plugin running `command` (one per panel) run it now."""
        xfpanel.refresh(command)

    def place_audio_layer(self):
        """genmon gets left clicks only; the wheel and the middle button over the sound
        indicator go through a transparent window of ours (the plugin sits under it)."""
        # one layer per speaker: the second screen's panel has its own
        pids = [int(k.split("/")[2].split("-")[1]) for k, v in panels.read_all().items()
                if k.endswith("/command") and os.path.basename(v.strip()) == "panel-audio"]
        for pid in pids:
            geom = self.plugin_geometry(pid)
            if not geom:
                continue
            win = self.audio_layers.get(pid)
            if win is None:
                win = self.xs.window(self.xs.root, *geom, input_only=True,
                                     events=X.ButtonPressMask, cursor=self.xs.cursors["hand"])
                self.audio_layers[pid] = win
            win.configure(x=geom[0], y=geom[1], width=geom[2], height=geom[3], stack_mode=X.Above)
            self.audio_geoms[pid] = geom
            out = self.output_rect_at(geom[0] + geom[2] // 2, geom[1] + 2)
            self.show_layer(win, (out or {}).get("name") not in self.busy_outputs)
        for pid in [p for p in self.audio_layers if p not in pids]:   # a panel that went away
            try:
                self.audio_layers.pop(pid).destroy()
            except error.XError:
                pass
            self.audio_geoms.pop(pid, None)

    def audio_click(self, e):
        if e.detail in (4, 5):
            self.osd(f"vol {'up' if e.detail == 4 else 'down'}")
        elif e.detail == 2:
            self.osd("vol mute")
        elif e.detail == 1:
            self.osd("menu audio")                   # hosted by osd-daemon: one instance, toggled

    def osd(self, line):
        try:
            with open(os.path.join(RUN, "osd.fifo"), "w") as f:
                f.write(line + "\n")
        except OSError as e:
            log("osd fifo:", e)

    def watch_panel_items(self):
        """Follow the pointer across the panel and work out what it is over. Pointer
        events are not exclusive, so watching the panel's own window takes nothing
        away from it, and it is the only way to see the plugins that have no window
        of their own - the clock, the volume, the shutdown button."""
        self.panel_items = self.panel_regions()
        # StructureNotify: a plugin that changes width (the ping reads "offline", the
        # dock gains an icon) reflows the whole panel, and the hole in the veil must
        # follow the new positions at once, not at the next 20 s recheck
        mask = X.PointerMotionMask | X.EnterWindowMask | X.LeaveWindowMask | X.StructureNotifyMask
        watch = []
        frames = {}
        for frame, geom in self.dock_frames():
            frames[frame.id] = geom
            watch += self.children(frame)
            veil = self.veils.get(frame.id)
            if veil is None or not veil.matches(geom):
                if veil is not None:                  # the panel changed size: the old veil goes
                    veil.set_visible(False)
                    veil.win.destroy()
                    self.xs.gc_cache.pop(veil.win.id, None)
                self.veils[frame.id] = PanelDim(self.xs, geom)
                if self.sharing:
                    self.veils[frame.id].set_visible(False)
        for fid in [f for f in self.veils if f not in frames]:   # the panel restarted: its old
            self.veils.pop(fid).set_visible(False)                # frame is gone, so is its veil
        watch += [win for win, _ in self.panel_wrappers()]
        for win in watch:
            try:
                win.change_attributes(event_mask=mask)
                self.panel_windows.add(win.id)
            except error.XError:
                pass
        self.place_audio_layer()
        self.raise_overlays()
        return True

    def raise_overlays(self):
        """Our own windows over the panel: the pentagram first, then the veil on top of
        it - the mark belongs to the panel and dims with it."""
        for win in self.sky_marks():                 # sky-stars' fire and pentagrams first
            win.configure(stack_mode=X.Above)
        if self.ws_mark is not None and self.ws_mark.shown:
            self.ws_mark.win.configure(stack_mode=X.Above)
        for veil in self.veils.values():
            veil.raise_above()

    def panel_regions(self):
        """[(x, y, w, h)] of everything the pointer can light up on the panel: the
        plugins that run in their own process, and the gaps between them, which is
        where the panel's own plugins sit. The workspace strip is left out - there
        the number under the pointer lights up on its own."""
        regions = []
        try:
            strips = {pid for pid, _ in self.strip_plugins()}
            for pid, out in self.strip_plugins():        # one number at a time
                view = self.strip_view(pid, out)
                if not view:
                    continue
                (_, gy, _, gh), items, bounds = view
                for (lo, hi), _ in zip(bounds, items):
                    regions.append((int(lo), gy, int(hi - lo), gh))
            for frame, (dx, dy, dw, dh) in self.dock_frames():
                boxes = []
                for win, pid in self.panel_wrappers():
                    g = win.get_geometry()
                    t = win.translate_coords(self.xs.root, 0, 0)
                    box = (-t.x, -t.y, g.width, g.height)
                    if not (dx <= box[0] < dx + dw):
                        continue
                    boxes.append((box, pid))
                boxes.sort(key=lambda b: b[0][0])
                regions += [box for box, pid in boxes if pid not in strips]
                edges = [dx] + [x for (x, _, w, _), _ in boxes for x in (x, x + w)] + [dx + dw]
                for left, right in zip(edges[::2], edges[1::2]):
                    width = right - left
                    if width < 24:
                        continue
                    # the last gap holds the clock and the square shutdown button
                    if width > dh * 1.6:
                        regions.append((left, dy, int(width - dh), dh))
                        regions.append((int(right - dh), dy, int(dh), dh))
                    else:
                        regions.append((left, dy, int(width), dh))
        except error.XError as e:
            log("panel regions failed:", e)
        return regions

    def panel_pointer(self, x, y):
        """Open the hole in the veil over whatever the pointer is on."""
        hole = None
        for rect in self.panel_items:
            rx, ry, rw, rh = rect
            if rx <= x < rx + rw and ry <= y < ry + rh:
                hole = rect
                break
        for veil in self.veils.values():
            veil.set_hole(hole)
        return None

    def sky_marks(self):
        """The mark windows sky-stars keeps over the panel (class sky-marks)."""
        found = []
        try:
            for w in self.xs.root.query_tree().children:
                try:
                    cls = w.get_wm_class()
                except error.XError:
                    continue
                if cls and cls[0] == "sky-marks":
                    found.append(w)
        except error.XError:
            pass
        return found

    def panel_wrappers(self):
        """[(window, plugin id)] of the panel plugins that run in their own process."""
        found = []
        for top in self.xs.root.query_tree().children:
            for kid in self.children(top):
                cls = kid.get_wm_class()
                if not cls or cls[1] != "Xfce4-panel":
                    continue
                stack = [kid]
                while stack:
                    w = stack.pop()
                    for c in self.children(w):
                        stack.append(c)
                        wc = c.get_wm_class()
                        if not wc or wc[0] != "wrapper-2.0":
                            continue
                        prop = c.get_full_property(self.A["_NET_WM_PID"], Xatom.CARDINAL)
                        if not prop:
                            continue
                        try:
                            args = open(f"/proc/{prop.value[0]}/cmdline").read().split("\0")
                        except OSError:
                            continue
                        if len(args) > 2 and args[2].isdigit():
                            found.append((c, int(args[2])))
        return found

    def children(self, win):
        """A window's children, or none if it vanished meanwhile (windows come and go
        between two requests; one BadWindow must not abort a whole pass)."""
        try:
            return win.query_tree().children
        except error.XError:
            return []

    def recheck_strips(self):
        """Every 20 s and after every panel reflow. It must never raise: GLib drops a
        timer whose callback raises, and then the fire stayed wherever the strip used to
        be (a vanished window during the walk did exactly that)."""
        try:
            self.strip_plugins(fresh=True)
            self.panel_windows = set()  # the panel may have restarted with new windows
            self.watch_panel_items()
            self.__dict__.pop("_panel_font", None)     # the panel may have been restyled
            self.bounds_cache.clear()                   # the strip may have moved
            self.place_ws_clicks()
        except Exception as e:                          # noqa: BLE001 - keep the timer alive
            log("recheck failed:", e)
        return True

    def unstick(self, con):
        """An ordinary window asked to be on every workspace (EWMH _NET_WM_DESKTOP = -1;
        Firefox did it during a full-screen video) and i3 made it sticky: it then
        showed on every workspace. Only small overlays are allowed that -
        picture-in-picture, notifications, dialogs - everything else goes back."""
        props = con.get("window_properties") or {}
        title = con.get("name") or ""
        if con.get("window_type") in ("dialog", "utility", "notification", "tooltip", "popup_menu", "dock",
                                      "unknown") \
                or props.get("transient_for") or "Picture-in-Picture" in title \
                or props.get("class") == "Xfce4-panel":         # the panel's own windows belong everywhere
            return
        log("unsticking", props.get("class"), title[:40])
        self.cmd(f'[con_id={con["id"]}] sticky disable')

    def skip_dock(self, wid):
        """Mark a client window as not for task lists, so the dock ignores it."""
        if not wid:
            return
        try:
            win = self.xs.d.create_resource_object("window", wid)
            atom = self.A["_NET_WM_STATE"]
            skip = self.xs.d.intern_atom("_NET_WM_STATE_SKIP_TASKBAR")
            pager = self.xs.d.intern_atom("_NET_WM_STATE_SKIP_PAGER")
            prop = win.get_full_property(atom, Xatom.ATOM)
            states = [a for a in (prop.value if prop else []) if a not in (skip, pager)]
            # two changes on purpose: docklike decides "on the task list" from the state
            # it had *before* a change, so the second change is the one that hides it
            win.change_property(atom, Xatom.ATOM, 32, states + [skip])
            self.xs.flush()
            win.change_property(atom, Xatom.ATOM, 32, states + [skip, pager])
            self.xs.flush()
        except error.XError as e:
            log("skip-dock failed:", e)

    def skip_dock_existing(self):
        """At start: the windows already open - those of the classes kept out of the
        dock, and those that asked to stay on top before deskd was there to see it."""
        try:
            for n, _ in walk(self.i3.tree()):
                if not n.get("window"):
                    continue
                if (n.get("window_properties") or {}).get("class") in NO_DOCK:
                    self.skip_dock(n["window"])
                self.read_above(n["window"])
        except Exception as e:                       # noqa: BLE001
            log("skip-dock scan failed:", e)

    # ------------------------------------------------------------ EWMH state i3 leaves to us
    def net_state(self, wid):
        """The atoms in a client's _NET_WM_STATE (empty if it is gone)."""
        try:
            win = self.xs.d.create_resource_object("window", wid)
            prop = win.get_full_property(self.A["_NET_WM_STATE"], Xatom.ATOM)
            return set(prop.value) if prop else set()
        except error.XError:
            return set()

    def set_net_state(self, wid, atom, on):
        """Add or drop one atom of a client's _NET_WM_STATE, the rest left as they are -
        i3 keeps its own atoms (fullscreen, hidden, focused) the same way."""
        try:
            win = self.xs.d.create_resource_object("window", wid)
            prop = win.get_full_property(self.A["_NET_WM_STATE"], Xatom.ATOM)
            states = [a for a in (prop.value if prop else []) if a != atom]
            win.change_property(self.A["_NET_WM_STATE"], Xatom.ATOM, 32, states + ([atom] if on else []))
        except error.XError:
            pass

    def read_above(self, wid):
        """A window that set "keep above" before it was mapped (Telegram's and Firefox's
        picture-in-picture, a pinned Telegram call). i3 has no such layer; deskd keeps
        these on top of their workspace, as KWin does."""
        if wid and self.A["_NET_WM_STATE_ABOVE"] in self.net_state(wid):
            self.above.add(wid)

    def draws_own_frame(self, wid):
        """A Qt window that asked for no frame (FramelessWindowHint: Qt marks it with
        _KDE_NET_WM_WINDOW_TYPE_OVERRIDE): Telegram's photo viewer, call window and
        picture-in-picture draw their own title and buttons. A second title bar of
        ours on top of theirs is what KWin never does."""
        try:
            win = self.xs.d.create_resource_object("window", wid)
            prop = win.get_full_property(self.A["_NET_WM_WINDOW_TYPE"], Xatom.ATOM)
            return bool(prop) and self.A["_KDE_NET_WM_WINDOW_TYPE_OVERRIDE"] in prop.value
        except error.XError:
            return False

    def normalize_marks(self):
        """deskd's marks carry the container id (i3 marks are unique), and i3 gives every
        container a new id when it restarts in place: a "_deskd_max_<old id>" could then
        never be taken off, and the window stayed "maximized" for good. Re-label them."""
        try:
            prefixes = [MARK_MAX, MARK_MIN] + [MARK_SNAP + k for k in SNAP_KINDS]
            for n, _ in walk(self.i3.tree()):
                for m in n.get("marks") or []:
                    for p in prefixes:
                        if m.startswith(p + "_") and m != f"{p}_{n['id']}":
                            self.cmd(f'[con_id={n["id"]}] unmark {m}, mark --add {p}_{n["id"]}')
                            old = m[len(p) + 1:]           # the saved place moves with it
                            wins = self.state.setdefault("windows", {})
                            if old in wins and str(n["id"]) not in wins:
                                wins[str(n["id"])] = wins.pop(old)
                                self.save_state()
        except Exception as e:                       # noqa: BLE001
            log("mark check failed:", e)

    def focus_modal(self, cid, wid):
        """A window blocked by its own modal dialog (Save As, a GTK file chooser) takes
        no input; clicking it gives the keyboard to the dialog instead, as KWin and
        Windows do. Without this the click focused the blocked window and typing went
        nowhere."""
        try:
            tree = self.i3.tree()
            ws = i3ipc.workspace_of(tree, cid)
            node, _ = find(tree, cid)
            # only while the click's window is still the focused one on a real workspace:
            # run late, after it was minimized, this "focused" the dialog out of the
            # scratchpad and the dialog came back on its own
            if not ws or (ws.get("num") or 0) <= 0 or not node or not node.get("focused"):
                return False
            clients = {n["window"]: n for n, _ in walk(ws) if n.get("window")}
            for other, n in clients.items():
                if other != wid and wid in self.dialog_owners(other, clients) \
                        and self.A["_NET_WM_STATE_MODAL"] in self.net_state(other):
                    self.cmd(f'[con_id={n["id"]}] focus')
                    break
        except Exception as e:                       # noqa: BLE001
            log("modal check failed:", e)
        return False

    def panel_reflowed(self):
        """A panel plugin was moved or resized: rebuild the regions after the burst of
        ConfigureNotify events settles, and re-aim the hole at the pointer."""
        if self.reflow_pending:
            return
        self.reflow_pending = True

        def rebuild():
            self.reflow_pending = False
            self.recheck_strips()
            try:
                q = self.xs.root.query_pointer()
                self.panel_pointer(q.root_x, q.root_y)
            except error.XError:
                pass
            if DEBUG:
                log("panel reflowed: regions rebuilt")
            return False
        GLib.timeout_add(150, rebuild)

    # ------------------------------------------------------------ state
    def _load_state(self):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_state(self):
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.state, f)
        os.replace(tmp, STATE_FILE)

    def saved(self, con_id):
        return self.state.setdefault("windows", {}).get(str(con_id))

    def set_saved(self, con_id, value):
        wins = self.state.setdefault("windows", {})
        if value is None:
            wins.pop(str(con_id), None)
        else:
            wins[str(con_id)] = value
        self.save_state()

    # ------------------------------------------------------------ plumbing
    def cmd(self, command):
        res = self.i3.command(command)
        for r in res:
            if not r.get("success"):
                log("i3 refused:", command, "->", r.get("error"))
        return res

    def pump(self):
        try:
            while self.xs.d.pending_events():
                e = self.xs.d.next_event()
                if DEBUG:
                    key = type(e).__name__
                    self.x_counts[key] = self.x_counts.get(key, 0) + 1
                self.handle_x(e)
        except (error.ConnectionClosedError, BrokenPipeError):
            log("X connection lost")
            loop.quit()
        self.xs.flush()

    def on_x(self, *_):
        self.pump()
        return True

    def schedule_refresh(self, delay=15):
        if not self.refresh_pending:
            self.refresh_pending = True
            GLib.timeout_add(delay, self.refresh)

    def on_i3(self, name, ev):
        if DEBUG:
            key = "i3:" + name + ":" + str(ev.get("change", ""))
            self.x_counts[key] = self.x_counts.get(key, 0) + 1
        if name == "shutdown":
            log("i3 went away:", ev.get("change"))
            if ev.get("change") == "restart":
                GLib.timeout_add(1500, lambda: os.execv(sys.executable, [sys.executable] + sys.argv))
            else:
                loop.quit()
            return
        if name == "binding":
            cmdline = ev.get("binding", {}).get("command", "")
            for part in cmdline.split(","):
                part = part.strip()
                if part.startswith("nop deskd"):
                    self.command(part[len("nop deskd"):].split())
        elif name == "window":
            change = ev.get("change")
            con = ev.get("container", {})
            if con.get("sticky") and change in ("new", "floating", "focus"):
                self.unstick(con)
            if change in ("new", "title", "focus") and con.get("border") == "none" and \
                    ((con.get("window_properties") or {}).get("class") or "").lower() in TITLED_CLASSES and \
                    con.get("window_type") == "normal" and con.get("name") not in UNTITLED_TITLES:
                # the app asked for no decorations (Motif hint): no title bar means no
                # buttons, nothing to drag - it could be neither moved nor minimized
                self.cmd(f'[con_id={con["id"]}] border normal 2')
            if change in ("new", "title"):
                props = con.get("window_properties") or {}
                if (props.get("class"), con.get("name")) in DISMISS:
                    self.cmd(f'[con_id={con["id"]}] kill')
                    return
                if change == "new" and props.get("class") in NO_DOCK:
                    self.skip_dock(con.get("window"))
                if change == "new":
                    self.read_above(con.get("window"))
                    if con.get("border") != "none" and self.draws_own_frame(con.get("window")) and \
                            (props.get("class") or "").lower() not in TITLED_CLASSES:
                        # the i3 rule gives every window a title bar; not one with its own
                        self.cmd(f'[con_id={con["id"]}] border none')
            if change in ("title", "urgent"):
                # neither moves, stacks or focuses anything; a busy terminal (spinner
                # in the title) would otherwise cost a full tree refresh every 100 ms
                return
            if change == "new":
                # one path for every new window: its workspace, then its place and size,
                # 100 ms later - after the app's own first resize (Qt and Zoom do one)
                GLib.timeout_add(100, lambda c=con: self.place_new_window(c))
            elif change == "close":
                self.forget(con)
                if con.get("id") in self.focus_order:
                    self.focus_order.remove(con["id"])
                self.above.discard(con.get("window"))
                self.switcher.forget(con.get("window"))
                self.drop_from_round(con.get("id"))
            elif change == "focus":
                if con.get("id") in self.focus_order:
                    self.focus_order.remove(con["id"])
                self.focus_order.insert(0, con.get("id"))
                del self.focus_order[40:]
                if any(m.startswith(MARK_MIN) for m in (con.get("marks") or [])):
                    GLib.idle_add(lambda cid=con["id"]: self.unminimize(cid) and False)
                GLib.idle_add(self.focus_modal, con.get("id"), con.get("window"))
                self.passthrough_for(con)
        elif name == "workspace":
            current = (ev.get("current") or {}).get("num")
            if current is not None:
                try:
                    # the strip and the mark together, right now: the full refresh that
                    # follows (tree, title buttons, handles) can take 100 ms on a busy
                    # workspace, and the digit would turn black after the fire arrived
                    self.render_workspaces(self.i3.workspaces())
                except Exception as e:           # noqa: BLE001 - the refresh will redo it
                    log("strip render failed:", e)
                self.sync_active_mark(current)
                self.pump()
        elif name == "output":
            GLib.timeout_add(700, self.outputs_changed)
        elif name == "mode":
            self.passthrough = ev.get("change") == "passthrough"
        elif name == "tick":
            payload = ev.get("payload", "")
            if payload.startswith("deskd "):            # from deskd-ctl / gestures
                self.command(payload.split()[1:])
        self.schedule_refresh()
        self.pump()

    def apps_conf(self):
        import configparser
        cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#",))
        cp.optionxform = str
        cp.read(os.path.expanduser("~/.config/deskd/apps.conf"))
        return cp

    def favorite_homes(self):
        """{window class (lower): workspace N} of the favourites pinned to a workspace
        (the Apple-button menu writes ~/.config/deskd/apps.conf). The N-th workspace of
        the screen in front of the user; this used to be an i3 `assign` rule, which
        sent *every* window of the app there - a Telegram call panel included."""
        homes = {}
        try:
            cp = self.apps_conf()
            for name in cp.sections():
                if name == "settings":
                    continue
                cls, ws = cp[name].get("class", "").strip().lower(), cp[name].get("workspace", "").strip()
                if cls and ws.isdigit():
                    homes[cls] = int(ws)
        except Exception as e:                       # noqa: BLE001 - no homes, no harm
            log("apps.conf:", e)
        return homes

    def place_new_window(self, con):
        """A second window of an app (a Telegram call or media viewer, a sign-in
        pop-up, "open in new window") goes where that app already is - the i3 assign
        rule of a favourite would send it to the app's home workspace even when the
        user has moved the app elsewhere, and a call panel opened there was simply
        never seen. Ctrl on a panel button asks for the window right here instead."""
        cid = con.get("id")
        cls = ((con.get("window_properties") or {}).get("class") or "").lower()
        tree = self.i3.tree()
        node, _ = find(tree, cid)
        if node is None:
            return False
        if not cls:
            self.clamp_floating(cid)
            return False
        want = None
        hint = self.expect.pop(cls, None)
        if hint and time.monotonic() - hint[1] < 20:
            want = hint[0]                                  # Ctrl + panel button: here
        else:
            # minimized windows do not count: their "workspace" is the scratchpad (-1)
            others = [n for n, _ in walk(tree)
                      if n.get("window") and n["id"] != cid
                      and ((n.get("window_properties") or {}).get("class") or "").lower() == cls
                      and ((i3ipc.workspace_of(tree, n["id"]) or {}).get("num") or 0) > 0]
            if not others:
                home = self.favorite_homes().get(cls)       # the app's first window: its home, if pinned
                if home:
                    here = i3ipc.workspace_of(tree, cid)
                    want = self.target_ws(home)
                    if here and here.get("num") != want:
                        self.cmd(f"[con_id={cid}] move container to workspace number {want}")
                self.clamp_floating(cid)
                return False
            visible = {w["name"] for w in self.i3.workspaces() if w["visible"]}

            def rank(n):
                ws = i3ipc.workspace_of(tree, n["id"])
                return (ws is not None and ws["name"] in visible, bool(n.get("focused")))
            others.sort(key=rank, reverse=True)
            ws = i3ipc.workspace_of(tree, others[0]["id"])
            want = ws["num"] if ws else None
        here = i3ipc.workspace_of(tree, cid)
        if want and here and here.get("num") != want:
            self.cmd(f"[con_id={cid}] move container to workspace number {want}")
            if any(w["num"] == want and w["visible"] for w in self.i3.workspaces()):
                self.cmd(f"[con_id={cid}] focus")
        self.clamp_floating(cid)
        self.cascade(cid)
        return False

    def cascade(self, cid):
        """A second window of an app opening exactly where one already sits (kitty, Thunar:
        same size, centred) steps down and right by CASCADE px, as Windows does, so both
        can be seen and grabbed."""
        tree = self.i3.tree()
        node, parent = find(tree, cid)
        if not node or not parent or parent.get("type") != "floating_con" or self.is_fitted(node) \
                or node.get("fullscreen_mode"):
            return
        ws = i3ipc.workspace_of(tree, cid)
        area = self.workarea(self.con_output(cid))
        if not ws or not area:
            return
        taken = []
        for n, p in walk(ws):
            if n.get("window") and n["id"] != cid and p and p.get("type") == "floating_con":
                taken.append((p["rect"]["x"], p["rect"]["y"]))
        r = parent["rect"]
        x, y = r["x"], r["y"]
        for _ in range(8):
            if not any(abs(x - tx) < 8 and abs(y - ty) < 8 for tx, ty in taken):
                break
            x, y = x + CASCADE, y + CASCADE
            if x + r["width"] > area["x"] + area["width"] or y + r["height"] > area["y"] + area["height"]:
                x, y = area["x"] + CASCADE, area["y"] + CASCADE
        if (x, y) != (r["x"], r["y"]):
            self.cmd(f"[con_id={cid}] move position {x} px {y} px")

    def passthrough_for(self, con):
        """RustDesk focused: every key (Super+...) goes to the remote machine - but only
        while the pointer is on its window. When it leaves, the keyboard goes with it
        (X focus follows the pointer) and i3's own keys work again; back in, both return.
        The user found a focused RustDesk swallowing everything he typed elsewhere."""
        cls = ((con.get("window_properties") or {}).get("class") or "").lower()
        want = cls in PASSTHROUGH_CLASSES
        if want and not self.passthrough:
            self.cmd('mode "passthrough"')
        elif not want and self.passthrough:
            self.cmd('mode "default"')
        if want:
            self.watch_passthrough(con)
        else:
            self.passthrough_frame = None

    def watch_passthrough(self, con):
        got = self.frame_of(con.get("window"))
        if not got:
            return
        frame, _ = got
        self.passthrough_frame, self.passthrough_client = frame.id, con.get("window")
        try:
            frame.change_attributes(event_mask=X.EnterWindowMask | X.LeaveWindowMask)
        except error.XError:
            pass

    def passthrough_pointer(self, e):
        """The pointer left or entered the remote-desktop window: i3's passthrough mode
        (every key to the remote machine) holds only while the pointer is on it. Which
        window has the keyboard is left to i3 alone - a second opinion on X focus made
        "selected" and "typing goes here" disagree."""
        if e.mode != X.NotifyNormal or e.detail == X.NotifyInferior:
            return
        if e.type == X.LeaveNotify:
            if self.passthrough:
                self.cmd('mode "default"')
        elif not self.passthrough:
            self.cmd('mode "passthrough"')

    # ------------------------------------------------------------ refresh
    def refresh(self):
        self.refresh_pending = False
        try:
            self.tree = self.i3.tree()
            workspaces = self.i3.workspaces()
        except Exception as e:
            log("refresh failed:", e)
            return False
        self.sync_strips()
        self.raise_focused()
        if not self.resizing:
            self.sync_handles(workspaces)
        self.render_workspaces(workspaces)
        self.hide_over_fullscreen(workspaces)
        self.pump()
        return False

    def raise_focused(self):
        """Unify i3's tiled/floating stacks for the active workspace.

        Only managed frames participate: menus, notifications and the panel keep
        their own stacking. Compare first so ConfigureNotify cannot cause a loop.
        """
        node, _ = i3ipc.focused(self.tree)
        if not node or not node.get("window"):
            return
        workspace = i3ipc.workspace_of(self.tree, node["id"])
        if not workspace:
            return
        focused = self.frame_of(node["window"])
        if not focused:
            return
        try:
            frames = {self.frame_of(n["window"])[0].id for n, _ in walk(workspace)
                      if n.get("window") and self.frame_of(n["window"])}
            stack = [w for w in self.xs.root.query_tree().children
                     if w.id in frames and w.get_attributes().map_state == X.IsViewable]
            if stack and stack[-1].id != focused[0].id:
                focused[0].configure(sibling=stack[-1], stack_mode=X.Above)
                for win, info, _ in self.handles:
                    if info and info.get("frame") == focused[0]:
                        win.configure(sibling=focused[0], stack_mode=X.Above)
            # a dialog (WM_TRANSIENT_FOR) belongs on top of the window it came from.
            # i3 re-pushes its own order (focused floating window on top) on every
            # focus change, so check every pair on the workspace, not only the
            # focused window's children, and touch only what is actually wrong -
            # each configure comes back as ConfigureNotify and another refresh.
            clients = {n["window"]: n for n, _ in walk(workspace) if n.get("window")}
            for wid in clients:
                for owner_id in self.dialog_owners(wid, clients):
                    child, parent = self.frame_of(wid), self.frame_of(owner_id)
                    if not child or not parent:
                        continue
                    order = [w.id for w in self.xs.root.query_tree().children]
                    if child[0].id in order and parent[0].id in order and \
                            order.index(child[0].id) < order.index(parent[0].id):
                        child[0].configure(sibling=parent[0], stack_mode=X.Above)
            self.raise_above(clients, node)
        except error.XError:
            pass

    def raise_above(self, clients, focused):
        """Windows that asked to stay on top (KWin's Above layer) go over every other
        window of the workspace - except over a focused full-screen one, which KWin puts
        higher still (a video you are watching is not covered by a picture-in-picture)."""
        tops = [self.frame_of(w)[0] for w in clients if w in self.above and self.frame_of(w)]
        if not tops or focused.get("fullscreen_mode"):
            return
        top_ids = {f.id for f in tops}
        frames = {self.frame_of(w)[0].id for w in clients if self.frame_of(w)}
        order = [w.id for w in self.xs.root.query_tree().children if w.id in frames]
        others = [i for i, wid in enumerate(order) if wid not in top_ids]
        if not others:
            return
        highest = others[-1]
        anchor = self.xs.d.create_resource_object("window", order[highest])
        for f in sorted(tops, key=lambda f: order.index(f.id) if f.id in order else -1):
            if f.id in order and order.index(f.id) < highest:
                f.configure(sibling=anchor, stack_mode=X.Above)
                anchor = f
                for win, info, _ in self.handles:
                    if info and info.get("frame") == f:
                        win.configure(sibling=f, stack_mode=X.Above)

    def dialog_owners(self, wid, clients):
        """The windows a dialog must stay above. Normally its WM_TRANSIENT_FOR. A modal
        dialog without one (Parole's "Additional software required" had none) belongs to
        every window of the same program: while it is open they take no input, so one of
        them coming to the front hid the only thing that could be clicked."""
        try:
            client = self.xs.d.create_resource_object("window", wid)
            owner = client.get_wm_transient_for()
        except error.XError:
            return []
        if owner is not None:
            return [owner.id] if owner.id in clients and owner.id != wid else []
        node = clients[wid]
        if node.get("window_type") != "dialog":
            return []
        try:
            state = client.get_full_property(self.A["_NET_WM_STATE"], Xatom.ATOM)
        except error.XError:
            return []
        if not state or self.A["_NET_WM_STATE_MODAL"] not in state.value:
            return []
        cls = (node.get("window_properties") or {}).get("class")
        return [w for w, n in clients.items()
                if w != wid and cls and (n.get("window_properties") or {}).get("class") == cls
                and n.get("window_type") != "dialog"]

    def dock_frames(self):
        """The frames i3 gave to dock windows - the panel. Looked up again every few
        seconds, because the panel is restarted now and then."""
        now = time.monotonic()
        if self.docks is not None and now - self.docks_at < 5:
            return self.docks
        self.docks_at = now
        found = []
        kind = self.xs.d.get_atom("_NET_WM_WINDOW_TYPE")
        dock = self.xs.d.get_atom("_NET_WM_WINDOW_TYPE_DOCK")
        try:
            frames = self.xs.root.query_tree().children
        except Exception as e:                               # noqa: BLE001
            log("dock lookup failed:", e)
            frames = []
        for frame in frames:
            try:                                             # a window can close mid-scan
                for win in [frame] + frame.query_tree().children:
                    cls = win.get_wm_class()
                    if not cls or cls[1] != "Xfce4-panel":   # only the panel, never our own overlays
                        continue
                    prop = win.get_full_property(kind, Xatom.ATOM)
                    if prop and dock in list(prop.value):
                        g = frame.get_geometry()
                        found.append((frame, (g.x, g.y, g.width, g.height)))
                        break
            except error.XError:
                continue
        self.docks = found
        return found

    def tooltip_over_menu(self, win):
        """A panel tooltip appearing while one of our pop-ups (the Wi-Fi or power menu,
        the calendar) is open would sit on top of it: hide it instead."""
        try:
            kind = win.get_full_property(self.xs.d.get_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM)
            if not kind or self.xs.d.get_atom("_NET_WM_WINDOW_TYPE_TOOLTIP") not in list(kind.value):
                return False
            menu_type = self.xs.d.get_atom("_NET_WM_WINDOW_TYPE_POPUP_MENU")
            for w in self.xs.root.query_tree().children:
                try:
                    cls = w.get_wm_class()
                    if not cls or w.get_attributes().map_state != X.IsViewable:
                        continue
                    if cls[0] in POPUP_OWNERS:
                        win.unmap()
                        return True
                    if cls[0] in MENU_HOSTS:              # the network menus live in osd-daemon
                        t = w.get_full_property(self.xs.d.get_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM)
                        if t and menu_type in list(t.value):
                            win.unmap()
                            return True
                except error.XError:
                    continue
        except error.XError:
            pass
        return False

    def raise_popup(self, win):
        """Put someone else's override-redirect window (a menu, a tooltip, a
        notification, the clock's calendar) on top of the stack when it appears."""
        try:
            if win.id in self.own_windows():
                return
            attrs = win.get_attributes()
            if not attrs.override_redirect or attrs.map_state != X.IsViewable:
                return
            geom = win.get_geometry()
            if geom.width < 8 or geom.height < 8:      # ignore the 1x1 helper windows
                return
            win.configure(stack_mode=X.Above)
        except error.XError:
            pass

    def own_windows(self):
        """The ids of the windows deskd itself puts on the screen."""
        ids = set(self.handle_by_win) | set(self.click_by_win) | set(self.strip_by_win)
        if self.ws_mark is not None:
            ids.add(self.ws_mark.win.id)
        if self.switcher.win is not None:
            ids.add(self.switcher.win.id)
        for name in ("preview", "targets"):
            holder = getattr(self, name, None)
            if isinstance(holder, dict):
                ids |= {w.id for w in holder.values() if hasattr(w, "id")}
        return ids

    def over_dock(self, x, y):
        """Is the pointer on a panel?"""
        return any(dx <= x < dx + dw and dy <= y < dy + dh
                   for _, (dx, dy, dw, dh) in self.dock_frames())

    def frame_of(self, client_id):
        cached = self.frames.get(client_id)
        if cached:
            return cached
        try:
            w = self.xs.d.create_resource_object("window", client_id)
            parent = w.query_tree().parent
            depth = parent.get_geometry().depth
        except Exception:
            return None
        self.frames[client_id] = (parent, depth)
        return parent, depth

    def sync_strips(self):
        want = {}
        for node, parent in walk(self.tree):
            if not node.get("window") or node.get("type") != "con":
                continue
            if node.get("border") != "normal" or node["deco_rect"]["height"] <= 0:
                continue
            if parent is None or parent.get("layout") in ("tabbed", "stacked"):
                continue
            if node.get("fullscreen_mode"):
                continue
            want[node["id"]] = node
        for cid in list(self.strips):
            if cid not in want:
                s = self.strips.pop(cid)
                self.strip_by_win.pop(s.win.id, None)
                s.destroy()
        for cid, node in want.items():
            strip = self.strips.get(cid)
            if strip is None:
                fr = self.frame_of(node["window"])
                if not fr:
                    continue
                strip = ButtonStrip(self.xs, fr[0], fr[1])
                self.strips[cid] = strip
                self.strip_by_win[strip.win.id] = cid
            rect = node["rect"]
            deco_h = node["deco_rect"]["height"]
            # a floating window's frame is its floating_con; the rect we get is the frame
            strip.layout(rect["width"], deco_h, node.get("focused", False))

    def forget(self, con):
        cid = con.get("id")
        s = self.strips.pop(cid, None)
        if s:
            self.strip_by_win.pop(s.win.id, None)
            s.destroy()
        if con.get("window"):
            self.frames.pop(con["window"], None)
        if self.saved(cid):
            self.set_saved(cid, None)

    # ------------------------------------------------------------ resize handles
    def visible_workspaces(self, workspaces):
        names = {w["name"] for w in workspaces if w.get("visible")}
        return [n for n, _ in walk(self.tree) if n.get("type") == "workspace" and n.get("name") in names]

    def sync_handles(self, workspaces):
        specs = []
        for ws in self.visible_workspaces(workspaces):
            if any(n.get("fullscreen_mode") and n.get("window") for n, _ in walk(ws)):
                continue
            area = ws["rect"]                     # the work area: handles stop at the panel
            for fl in ws.get("floating_nodes", []):
                r = fl["rect"]
                x, y, w, h, t = r["x"], r["y"], r["width"], r["height"], HANDLE
                frame = self.floating_frame(fl)
                # the window's own container: it carries the marks and the saved place, and
                # i3 moves only it - "[con_id=<the floating wrapper>] move position" is
                # refused, which made a left or top edge grow the window right or down
                leaf = next((n for n, _ in walk(fl) if n.get("window")), None)
                if leaf is None:
                    continue
                ring = [((x - t, y - t, t, t), "tl", "tl"), ((x, y - t, w, t), "t", "t"),
                        ((x + w, y - t, t, t), "tr", "tr"), ((x + w, y, t, h), "r", "r"),
                        ((x + w, y + h, t, t), "br", "br"), ((x, y + h, w, t), "b", "b"),
                        ((x - t, y + h, t, t), "bl", "bl"), ((x - t, y, t, h), "l", "l")]
                for geom, cur, edges in ring:
                    gx, gy, gw, gh = geom
                    cx, cy = max(gx, area["x"]), max(gy, area["y"])
                    cw = min(gx + gw, area["x"] + area["width"]) - cx
                    ch = min(gy + gh, area["y"] + area["height"]) - cy
                    if cw <= 0 or ch <= 0:
                        continue              # a maximized window's edge: nothing to grab there
                    specs.append(((cx, cy, cw, ch), cur, {"kind": "float", "con": leaf["id"], "edges": edges,
                                                          "rect": dict(r), "frame": frame, "xid": leaf["window"]}))
        # reuse windows; create or destroy the difference
        while len(self.handles) < len(specs):
            w = self.xs.window(self.xs.root, 0, 0, 1, 1, input_only=True,
                               events=X.ButtonPressMask | X.ButtonReleaseMask | X.PointerMotionMask)
            self.handles.append([w, None, None])
        for i, h in enumerate(self.handles):
            w = h[0]
            if i >= len(specs):
                if h[1] is not None:
                    w.unmap()
                    h[1] = None
                    self.handle_by_win.pop(w.id, None)
                continue
            geom, cur, info = specs[i]
            x, y, gw, gh = geom
            key = (geom, cur, info.get("frame"))
            if h[2] != key:
                w.change_attributes(cursor=self.xs.cursors[cur])
                w.configure(x=x, y=y, width=max(1, gw), height=max(1, gh))
                h[2] = key
            if info.get("frame"):
                # every time: i3 restacks frames on each focus change, and a handle
                # left above a frame that is now higher would take that window's clicks
                w.configure(sibling=info["frame"], stack_mode=X.Above)
            if h[1] is None:
                w.map()
            h[1] = info
            self.handle_by_win[w.id] = h

    def floating_frame(self, floating_con):
        for leaf, _ in walk(floating_con):
            if leaf.get("window"):
                fr = self.frame_of(leaf["window"])
                return fr[0] if fr else None
        return None

    # ------------------------------------------------------------ X events
    def handle_x(self, e):
        t = e.type
        if t in (X.ButtonPress, X.ButtonRelease, X.MotionNotify, X.EnterNotify, X.LeaveNotify, X.Expose):
            wid = e.window.id
            if wid == self.passthrough_frame and t in (X.EnterNotify, X.LeaveNotify):
                return self.passthrough_pointer(e)
            if wid in self.strip_by_win:
                return self.strip_event(self.strips.get(self.strip_by_win[wid]), e)
            if wid in self.handle_by_win:
                return self.handle_event(self.handle_by_win[wid], e)
            if wid in self.panel_windows:
                if t == X.LeaveNotify:
                    if e.detail == X.NotifyInferior:    # only stepped into a child
                        return None
                    return self.panel_pointer(-1, -1)
                if t in (X.MotionNotify, X.EnterNotify):
                    return self.panel_pointer(e.root_x, e.root_y)
                return None
            if any(wid == w.id for w in self.audio_layers.values()):
                if t == X.ButtonPress:
                    return self.audio_click(e)
                return None
            if self.ws_mark is not None and wid == self.ws_mark.win.id:
                return self.ws_mark.draw()
            if self.switcher.win is not None and wid == self.switcher.win.id:
                return self.switcher.draw()
            if wid in self.click_by_win:
                # the strip's click layer covers the panel, so the pointer is followed
                # here as well - otherwise the veil would never see the numbers
                if t == X.ButtonPress:
                    return self.ws_clicked(e)
                if t == X.LeaveNotify:
                    return self.panel_pointer(-1, -1)
                return self.panel_pointer(e.root_x, e.root_y)
        elif t == X.ClientMessage:
            self.client_message(e)
        elif self.monitors.is_randr(e):
            self.monitors.changed()
        elif t == X.DestroyNotify:
            self.frames.pop(e.window.id, None)
            if self.sharing and not self.share_frame_present():
                self.set_sharing(False)
        elif t == X.UnmapNotify:
            if self.sharing and not self.share_frame_present():
                self.set_sharing(False)
        elif t == X.MapNotify:
            if not self.sharing and self.is_share_frame(e.window):
                self.set_sharing(True)
                return None
            # a menu or a popup (the clock's calendar, a plugin's menu) is an
            # override-redirect window: a menu, a notification, the clock's calendar.
            # Keep it above everything, whatever the window below is doing.
            if self.tooltip_over_menu(e.window):
                return None
            self.raise_popup(e.window)
        elif t == X.ConfigureNotify:
            if e.window.id in self.panel_windows:
                return self.panel_reflowed()
            # i3 can restore its tiled/floating split after a resize or maximize.
            # Only managed frames need reconciliation, never our own overlays - and
            # not while we are the ones moving the window (drag_end refreshes once).
            if self.drag is None and self.resizing is None and any(
                    frame.id == e.window.id for frame, _ in self.frames.values()):
                self.schedule_refresh()


    def strip_event(self, strip, e):
        if strip is None:
            return
        cid = self.strip_by_win.get(strip.win.id)
        if e.type == X.Expose:
            strip.draw()
        elif e.type in (X.EnterNotify, X.MotionNotify):
            idx = strip.index_at(e.event_x) if e.type == X.MotionNotify else 0
            if strip.hover < 0 or e.type == X.EnterNotify:
                strip.hover = max(0, idx)
                strip.draw()
        elif e.type == X.LeaveNotify:
            strip.hover = -1
            strip.pressed = -1
            strip.draw()
        elif e.type == X.ButtonPress and e.detail == 1:
            strip.pressed = strip.index_at(e.event_x)
            strip.draw()
        elif e.type == X.ButtonRelease and e.detail == 1:
            idx = strip.index_at(e.event_x)
            was = strip.pressed
            strip.pressed = -1
            strip.draw()
            if idx >= 0 and idx == was:
                self.button_action(cid, idx)

    def button_action(self, cid, idx):
        if idx == 0:
            self.minimize(cid)
        elif idx == 1:
            self.toggle_maximize(cid)
        else:
            self.cmd(f"[con_id={cid}] kill")

    def handle_event(self, h, e):
        info = h[1]
        if info is None:
            return
        if e.type == X.ButtonPress and e.detail == 1:
            if DEBUG:
                log("handle press", info["edges"], info["con"], e.root_x, e.root_y)
            self.resizing = {"info": info, "x": e.root_x, "y": e.root_y, "last": None,
                             "min": self.min_frame_size(info)}
        elif e.type == X.MotionNotify and self.resizing:
            self.resizing["pos"] = (e.root_x, e.root_y)
            if not self.resizing.get("timer"):
                self.resizing["timer"] = GLib.timeout_add(30, self.apply_resize)
        elif e.type == X.ButtonRelease and self.resizing:
            self.resizing["pos"] = (e.root_x, e.root_y)
            self.apply_resize(final=True)
            self.resizing = None
            self.schedule_refresh()

    def min_frame_size(self, info):
        """The smallest frame the window may be resized to: the app's minimum size
        (WM_NORMAL_HINTS) plus i3's title bar and borders, and never under 160x100."""
        min_w, min_h = 160, 100
        try:
            client = self.xs.d.create_resource_object("window", info["xid"])
            hints = client.get_wm_normal_hints()
            g = client.get_geometry()
            dw, dh = info["rect"]["width"] - g.width, info["rect"]["height"] - g.height
            if hints and hints.flags & Xutil.PMinSize:
                min_w, min_h = max(min_w, hints.min_width + dw), max(min_h, hints.min_height + dh)
        except (error.XError, KeyError, TypeError, AttributeError):
            pass
        return min_w, min_h

    def apply_resize(self, final=False):
        r = self.resizing
        if not r:
            return False
        r["timer"] = None
        if "pos" not in r:
            return False
        info = r["info"]
        px, py = r["pos"]
        dx, dy = px - r["x"], py - r["y"]
        rect, edges = info["rect"], info["edges"]
        x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
        min_w, min_h = r["min"]
        # the app's own minimum size holds (WM_NORMAL_HINTS): a left or top edge pulled
        # past it stops there, instead of the whole window sliding along with the pointer
        if "l" in edges:
            w = max(min_w, w - dx)
            x = rect["x"] + rect["width"] - w
        if "r" in edges:
            w = max(min_w, w + dx)
        if "t" in edges:
            h = max(min_h, h - dy)
            y = rect["y"] + rect["height"] - h
        if "b" in edges:
            h = max(min_h, h + dy)
        key = (x, y, w, h)
        if key != r["last"]:
            if r["last"] is None:
                # a maximized / snapped window being resized by hand is neither any more
                self.cmd(f'[con_id={info["con"]}] {self.unfit(info["con"])}')
                self.set_saved(info["con"], None)
            self.cmd(f'[con_id={info["con"]}] resize set {w} px {h} px, move position {x} px {y} px')
            r["last"] = key
        self.pump()
        return False

    def client_message(self, e):
        """Apps asking the window manager to minimize or maximize (their own buttons)."""
        con = self.con_for_window(e.window.id)
        if not con:
            return
        data = e.data[1]
        if e.client_type == self.A["WM_CHANGE_STATE"] and data[0] == 3:      # IconicState
            self.minimize(con["id"])
        elif e.client_type == self.A["_NET_WM_STATE"]:
            maxed = {self.A["_NET_WM_STATE_MAXIMIZED_VERT"], self.A["_NET_WM_STATE_MAXIMIZED_HORZ"]}
            above = self.A["_NET_WM_STATE_ABOVE"]
            if above in (data[1], data[2]):
                # "keep above" asked while the window is up (Telegram's pin on a call)
                wid = con.get("window")
                on = {0: False, 1: True}.get(data[0], wid not in self.above)
                (self.above.add if on else self.above.discard)(wid)
                self.set_net_state(wid, above, on)
                self.schedule_refresh()
            if data[1] in maxed or data[2] in maxed:
                action = data[0]       # 0 remove, 1 add, 2 toggle
                is_max = self.is_maximized(con)
                if action == 2 or (action == 1 and not is_max) or (action == 0 and is_max):
                    self.toggle_maximize(con["id"])

    def con_for_window(self, xid):
        tree = self.i3.tree()
        for node, _ in walk(tree):
            if node.get("window") == xid:
                return node
        return None

    # ------------------------------------------------------------ geometry helpers
    def outputs(self):
        """The output list; frozen for the length of a drag, like workspaces(): it was
        asked of i3 on every pointer poll (60 Hz) and screens do not change mid-drag."""
        if self.drag is None:
            return self.i3.outputs()
        if self.drag.get("outputs") is None:
            self.drag["outputs"] = self.i3.outputs()
        return self.drag["outputs"]

    def output_rect_at(self, x, y):
        for o in self.outputs():
            if o.get("active"):
                r = o["rect"]
                if r["x"] <= x < r["x"] + r["width"] and r["y"] <= y < r["y"] + r["height"]:
                    return o
        return None

    def workspaces(self):
        """The workspace list. While a drag is running it is asked for on every poll
        of the pointer, so it is kept for half a second: the layout does not change
        mid-drag, and re-parsing it at 60 Hz churned tens of megabytes."""
        if self.drag is None:
            return self.i3.workspaces()
        now = time.monotonic()
        if self._ws_snap is None or now - self._ws_snap_at > 0.5:
            self._ws_snap, self._ws_snap_at = self.i3.workspaces(), now
        return self._ws_snap

    def workarea(self, output_name):
        for w in self.workspaces():
            if w["output"] == output_name and w["visible"]:
                return w["rect"]
        return None

    def con_output(self, cid):
        ws = i3ipc.workspace_of(self.i3.tree(), cid)
        if not ws:
            return None
        for w in self.i3.workspaces():
            if w["name"] == ws["name"]:
                return w["output"]
        return None

    # ------------------------------------------------------------ maximize / restore
    def find_mark(self, mark):
        for node, _ in walk(self.i3.tree()):
            if mark in (node.get("marks") or []):
                return node
        return None

    def remember(self, cid):
        """Where the window is now (its floating frame), so restore can put it back."""
        node, parent = find(self.i3.tree(), cid)
        if node is None or not parent or parent.get("type") != "floating_con":
            return None
        r = parent["rect"]
        return {"mode": "floating", "rect": [r["x"], r["y"], r["width"], r["height"]]}

    def unfit(self, cid):
        """The i3 commands that make a window plain again: neither maximized nor snapped."""
        return ", ".join([f"unmark {MARK_MAX}_{cid}"] + [f"unmark {MARK_SNAP}{k}_{cid}" for k in SNAP_KINDS])

    def fit(self, cid, rect, mark, saved=None, focus=True):
        """ONE engine for maximize and for snapping to a half of the screen: the window
        becomes a floating one filling `rect`, carrying `mark`; where it was before is
        kept so that restore - or dragging it away - gives that place back. Going from
        maximized to a half (or back) keeps the original place, as Windows does."""
        node, _ = find(self.i3.tree(), cid)
        if node is None:
            return
        if node.get("fullscreen_mode"):
            self.cmd(f"[con_id={cid}] fullscreen disable")
        if saved is None:
            saved = self.saved(cid) if self.is_fitted(node) else self.remember(cid)
        self.set_saved(cid, saved)
        x, y, w, h = rect
        self.cmd(f"[con_id={cid}] floating enable, {self.unfit(cid)}, mark --add {mark}_{cid}, "
                 f"move position {x} px {y} px, resize set {w} px {h} px")
        self.fit_floating(cid, (x, y, w, h))
        if focus:
            self.cmd(f"[con_id={cid}] focus")

    @staticmethod
    def fit_rect(area, kind):
        """The rectangle a window fills for a kind of fit: the whole work area, a half
        (left/right) or a quarter (tl/tr/bl/br - a corner of the screen, as in Windows)."""
        x, y, w, h = area["x"], area["y"], area["width"], area["height"]
        hw, hh = w // 2, h // 2
        return {"max": (x, y, w, h),
                "left": (x, y, hw, h), "right": (x + w - hw, y, hw, h),
                "tl": (x, y, hw, hh), "tr": (x + w - hw, y, hw, hh),
                "bl": (x, y + h - hh, hw, hh), "br": (x + w - hw, y + h - hh, hw, hh)}[kind]

    def maximize(self, cid, saved=None, focus=True):
        output = self.con_output(cid)
        area = self.workarea(output) if output else None
        if area:
            self.fit(cid, self.fit_rect(area, "max"), MARK_MAX, saved, focus)

    def snap(self, cid, side, saved=None, focus=True):
        """The window fills a half (Super+Left/Right, or dropped at that edge) or a
        quarter (dropped in a corner) of the work area."""
        output = self.con_output(cid)
        area = self.workarea(output) if output else None
        if area:
            self.fit(cid, self.fit_rect(area, side), MARK_SNAP + side, saved, focus)

    def fit_floating(self, cid, target):
        """i3 sizes floating windows without decorations; correct once to the exact frame."""
        node, parent = find(self.i3.tree(), cid)
        if not parent or parent.get("type") != "floating_con":
            return
        r = parent["rect"]
        x, y, w, h = target
        dw, dh = r["width"] - w, r["height"] - h
        if dw or dh or r["x"] != x or r["y"] != y:
            self.cmd(f"[con_id={cid}] resize set {w - dw} px {h - dh} px, move position {x} px {y} px")

    def is_maximized(self, node):
        return any(m.startswith(MARK_MAX) for m in (node.get("marks") or []))

    def snapped_side(self, node):
        """"left" / "right" for a window snapped to that half of the screen, else None."""
        for m in node.get("marks") or []:
            if m.startswith(MARK_SNAP):
                return m[len(MARK_SNAP):].split("_", 1)[0]
        return None

    def is_fitted(self, node):
        """Maximized or snapped: filling a rectangle of the screen rather than its own."""
        return self.is_maximized(node) or self.snapped_side(node) is not None

    def toggle_maximize(self, cid):
        node, _ = find(self.i3.tree(), cid)
        if node is None:
            return
        if self.is_maximized(node):
            self.restore(cid)
        else:
            self.maximize(cid)

    def restore(self, cid):
        """Back to the place and size the window had before maximize / snap / minimize.
        A window with nothing remembered (it was never anywhere else) gets a sensible
        size in the middle of its screen."""
        saved = self.saved(cid)
        rect = saved.get("rect") if saved else None
        if not rect:
            area = self.workarea(self.con_output(cid))
            if not area:                      # still in the scratchpad: show it where it was
                self.cmd(f"[con_id={cid}] {self.unfit(cid)}, unmark {MARK_MIN}_{cid}, scratchpad show, focus")
                self.set_saved(cid, None)
                return
            w, h = int(area["width"] * 0.6), int(area["height"] * 0.7)
            rect = [area["x"] + (area["width"] - w) // 2, area["y"] + (area["height"] - h) // 2, w, h]
        else:
            rect = self.onto_screen(rect, self.workarea(self.con_output(cid)))
        x, y, w, h = rect
        self.cmd(f"[con_id={cid}] {self.unfit(cid)}, unmark {MARK_MIN}_{cid}, floating enable, "
                 f"resize set {w} px {h} px, move position {x} px {y} px")
        self.fit_floating(cid, (x, y, w, h))
        self.set_saved(cid, None)
        self.cmd(f"[con_id={cid}] focus")

    @staticmethod
    def onto_screen(rect, area):
        """A remembered place made valid for the screen the window is on now. Remembered
        on another screen (maximized there, then moved with Super+Shift+arrow, or the
        monitor unplugged): the same size, centred here - i3 refused the old place, or
        moved the window back to the old screen. Then no bigger than the work area, and
        the title bar on it (the resolution may have changed meanwhile)."""
        if not area or not rect:
            return rect
        x, y, w, h = rect
        ax, ay, aw, ah = area["x"], area["y"], area["width"], area["height"]
        if not (ax <= x + w // 2 < ax + aw and ay <= y + 15 < ay + ah):
            x, y = ax + (aw - w) // 2, ay + (ah - h) // 2
        w, h = min(w, aw), min(h, ah)
        x = min(max(x, ax - w + 100), ax + aw - 100)       # 100 px of the title bar stay reachable
        y = min(max(y, ay), ay + ah - DRAG_KEEP)
        return [x, y, w, h]

    def minimize(self, cid):
        tree = self.i3.tree()
        node, parent = find(tree, cid)
        if node is None:
            return
        # a dialog is never hidden on its own: while a modal one sits in the scratchpad
        # its owner takes no clicks at all (Sublime's "Save File" did exactly that).
        # Minimizing a dialog minimizes the window it belongs to, dialog and all.
        owner = (node.get("window_properties") or {}).get("transient_for")
        if node.get("window_type") == "dialog" or owner:
            main = next((n for n, _ in walk(tree) if owner and n.get("window") == owner), None)
            if main is not None and main["id"] != cid:
                return self.minimize(main["id"])
            return
        # the window's own dialogs go with it, so none stays behind blocking nothing -
        # and none is left on screen for a hidden owner
        for n, _ in walk(tree):
            if n.get("window") and n["id"] != cid and \
                    (n.get("window_properties") or {}).get("transient_for") == node.get("window"):
                self.cmd(f"[con_id={n['id']}] mark --add {MARK_MIN}_{n['id']}, move scratchpad")
        saved = self.saved(cid) or self.remember(cid) or {}
        ws = i3ipc.workspace_of(tree, cid)
        saved["ws"] = ws["name"] if ws else None          # Alt+Tab there still lists it
        self.set_saved(cid, saved)
        self.cmd(f"[con_id={cid}] mark --add {MARK_MIN}_{cid}, move scratchpad")

    def minimized_owner(self, tree, node):
        """The minimized window a dialog belongs to, if it is one: the dialog comes back
        only with it (and then on top), never on its own in front of an empty spot."""
        owner = (node.get("window_properties") or {}).get("transient_for")
        main = next((n for n, _ in walk(tree) if owner and n.get("window") == owner), None)
        if main is not None and main["id"] != node["id"] and \
                any(m.startswith(MARK_MIN) for m in (main.get("marks") or [])):
            return main
        return None

    def unminimize(self, cid):
        tree = self.i3.tree()
        node, _ = find(tree, cid)
        if node is None or not any(m.startswith(MARK_MIN) for m in (node.get("marks") or [])):
            return
        main = self.minimized_owner(tree, node)
        if main is not None:
            if (i3ipc.workspace_of(tree, main["id"]) or {}).get("num", -1) < 0:
                self.cmd(f"[con_id={main['id']}] scratchpad show")
            return self.unminimize(main["id"])
        self.cmd(f"[con_id={cid}] unmark {MARK_MIN}_{cid}")
        side = self.snapped_side(node)
        if self.is_maximized(node):
            self.maximize(cid, self.saved(cid))
        elif side:
            self.snap(cid, side, self.saved(cid))
        else:
            self.restore(cid)
        # its dialogs come back with it, on top
        for n, _ in walk(self.i3.tree()):
            if n.get("window") and n["id"] != cid and \
                    (n.get("window_properties") or {}).get("transient_for") == node.get("window") and \
                    f"{MARK_MIN}_{n['id']}" in (n.get("marks") or []):
                self.cmd(f"[con_id={n['id']}] unmark {MARK_MIN}_{n['id']}, scratchpad show, floating enable, focus")

    def unminimize_last(self):
        """Super+Shift+-: the most recently used minimized window comes back (its dialogs
        with it); before, it was whichever the tree listed first - a dialog, say."""
        tree = self.i3.tree()
        rank = {cid: i for i, cid in enumerate(self.focus_order)}
        mins = [n for n, _ in walk(tree) if n.get("window")
                and any(m.startswith(MARK_MIN) for m in (n.get("marks") or []))
                and self.minimized_owner(tree, n) is None]
        if mins:
            node = min(mins, key=lambda n: rank.get(n["id"], len(rank)))
            self.cmd(f"[con_id={node['id']}] scratchpad show")
            self.unminimize(node["id"])
            return
        self.cmd("scratchpad show")

    # ------------------------------------------------------------ title bar: clicks and drags
    # ONE engine for every title bar drag (left or right button): the window follows the
    # pointer; top edge = maximize, left/right edge = that half of the screen, a workspace
    # number in any panel = move there. Fixes here apply to both buttons.
    def titlebar_press(self, button, attempt=0):
        tree = self.i3.tree()
        target = next((n for n, _ in walk(tree) if MARK_CLICK in (n.get("marks") or [])), None)
        if not target:
            if attempt < 3:        # the binding event can arrive a moment before the mark
                GLib.timeout_add(20, lambda: self.titlebar_press(button, attempt + 1) and False)
            return
        self.cmd(f"[con_id={target['id']}] unmark {MARK_CLICK}")
        x, y, mask = self.xs.pointer()
        bmask = X.Button1Mask if button == 1 else X.Button3Mask
        if not mask & bmask:
            self.titlebar_click(target["id"], button, x, y)
            return
        _, parent = find(tree, target["id"])
        frame = parent["rect"] if parent is not None and parent.get("type") == "floating_con" else target["rect"]
        self.drag = {"con": target["id"], "xid": target.get("window"), "x0": x, "y0": y, "moving": False,
                     "zone": None, "button": button, "mask": bmask,
                     "rect": dict(frame), "fitted": self.is_fitted(target)}
        GLib.timeout_add(POLL_MS, self.drag_poll)

    def titlebar_click(self, cid, button, x, y):
        """Left double click: maximize <-> restore. A right click only focuses (i3 did that)."""
        if button != 1:
            return
        now, last = time.monotonic(), self.last_click
        self.last_click = (cid, now, x, y)
        if last and last[0] == cid and now - last[1] < DOUBLE_CLICK_S \
                and abs(x - last[2]) + abs(y - last[3]) < 12:
            self.last_click = None
            self.toggle_maximize(cid)

    def drag_poll(self):
        """One frame of a drag. The window is moved by moving i3's frame window directly
        (one X request, as KWin does), not with an i3 command per frame: each of those
        was a round trip through i3 - parse, re-render, a synthetic configure to the app -
        and that is what made a window lag behind the pointer while the browser kept the
        X server busy. i3 learns the final place once, when the window is let go; until
        then it has nothing to redraw, because its own idea of the window did not change."""
        d = self.drag
        if not d:
            return False
        x, y, mask = self.xs.pointer()
        if not mask & d["mask"]:
            self.drag_end(x, y)
            return False
        if not d["moving"]:
            if abs(x - d["x0"]) + abs(y - d["y0"]) < DRAG_START:
                return True
            self.drag_begin(x, y)
        nx, ny = self.magnet(x - d["off_x"], y - d["off_y"], x, y)
        nx, ny = self.inside_workarea(nx, ny, x, y)
        if (nx, ny) != d.get("pos"):
            d["pos"] = (nx, ny)
            try:
                d["frame"].configure(x=nx + d["dx"], y=ny + d["dy"])
            except (error.XError, KeyError, AttributeError):
                self.cmd(f'[con_id={d["con"]}] move position {nx} px {ny} px')
        self.drag_zone(x, y)
        self.pump()
        return True

    def area_at(self, x, y):
        """The work area of the screen under (x, y), from the list taken at drag start."""
        d = self.drag
        out = self.output_rect_at(x, y)
        areas = d.get("areas", {}) if d else {}
        return areas.get(out["name"]) if out else None

    def inside_workarea(self, x, y, px, py):
        """Where a dragged window is allowed to be: its title bar stays on the screen.
        The panel is always on top, so a window pushed against it stops at its edge
        instead of sliding underneath; at the bottom the window may hang off the
        screen, as in Windows, as long as DRAG_KEEP px of it stay reachable. (Keeping
        the whole window inside meant a window nearly as tall as the screen could
        hardly be moved down at all.) The screen is the one under the pointer."""
        area = self.area_at(px, py) or (self.drag or {}).get("area")
        if not area:
            return x, y
        return x, max(area["y"], min(y, area["y"] + area["height"] - DRAG_KEEP))

    def magnet(self, x, y, px, py):
        """Magnetic edges while dragging (KWin's border and window snap zones): an edge
        of the window within SNAP_ZONE px of the work area's edge or of another
        window's facing edge jumps onto it, so windows line up without pixel hunting.
        Each axis on its own, the nearest candidate wins."""
        d = self.drag
        w, h = d["size"]
        area = self.area_at(px, py)
        xs, ys = [], []
        if area:
            xs += [area["x"], area["x"] + area["width"] - w]
            ys += [area["y"], area["y"] + area["height"] - h]
        for rx, ry, rw, rh in d["others"]:
            if ry < y + h and y < ry + rh:                 # side by side: left/right edges meet
                xs += [rx + rw, rx - w]
            if rx < x + w and x < rx + rw:                 # one above the other
                ys += [ry + rh, ry - h]
        bx = min(xs, key=lambda c: abs(c - x), default=x)
        by = min(ys, key=lambda c: abs(c - y), default=y)
        return (bx if abs(bx - x) <= SNAP_ZONE else x), (by if abs(by - y) <= SNAP_ZONE else y)

    def drag_begin(self, x, y):
        d = self.drag
        d["moving"] = True
        cid, r = d["con"], d["rect"]
        # measured once, used every frame: the work areas, the other windows' frames
        d["area"] = self.workarea(self.con_output(cid))
        d["areas"] = {w["output"]: w["rect"] for w in self.workspaces() if w["visible"]}
        d["others"] = []
        for ws in self.visible_workspaces(self.workspaces()):
            for fl in ws.get("floating_nodes", []):
                if fl["id"] != cid and not any(n["id"] == cid for n, _ in walk(fl)):
                    fr = fl["rect"]
                    d["others"].append((fr["x"], fr["y"], fr["width"], fr["height"]))
        # where the window was when it was picked up: dropped at an edge, "restore"
        # brings it back here - not to the spot where it was let go, half off the screen
        d["saved"] = {"mode": "floating", "rect": [r["x"], r["y"], r["width"], r["height"]]}
        w, h = r["width"], r["height"]
        if d["fitted"]:
            # a maximized / snapped window pulled away gets its previous size back under
            # the pointer, as in Windows; dropping it at an edge again restores to the same place
            d["saved"] = self.saved(cid)
            rect = (d["saved"] or {}).get("rect")
            if rect:
                w, h = rect[2], rect[3]
            else:
                w, h = max(400, int(r["width"] * 0.6)), max(300, int(r["height"] * 0.6))
            self.cmd(f"[con_id={cid}] {self.unfit(cid)}, resize set {w} px {h} px")
        d["size"] = (w, h)
        # the X frame to move, and where it sits against i3's rectangle (normally 0, 0)
        fr = self.frame_of(d["xid"]) if d.get("xid") else None
        d["frame"], d["dx"], d["dy"] = (fr[0] if fr else None), 0, 0
        if fr:
            try:
                g = fr[0].get_geometry()
                d["dx"], d["dy"] = g.x - r["x"], g.y - r["y"]
            except error.XError:
                d["frame"] = None
        frac = (d["x0"] - r["x"]) / max(1, r["width"])
        d["off_x"], d["off_y"] = int(w * frac), d["y0"] - r["y"]
        self.show_targets()

    def drop_kind(self, out, x, y):
        """The fit a pointer at (x, y) on screen `out` asks for: "max" at the top edge, a
        half at a side, a quarter near a corner (the last CORNER share of an edge -
        a 3 px corner square was hard to hit), None in the open."""
        o = out["rect"]
        top, bottom = y <= o["y"] + EDGE, y >= o["y"] + o["height"] - 1 - EDGE
        left, right = x <= o["x"] + EDGE, x >= o["x"] + o["width"] - 1 - EDGE
        near_top = y < o["y"] + o["height"] * CORNER
        near_bottom = y > o["y"] + o["height"] * (1 - CORNER)
        near_left = x < o["x"] + o["width"] * CORNER
        near_right = x > o["x"] + o["width"] * (1 - CORNER)
        if (left and near_top) or (top and near_left):
            return "tl"
        if (right and near_top) or (top and near_right):
            return "tr"
        if (left and near_bottom) or (bottom and near_left):
            return "bl"
        if (right and near_bottom) or (bottom and near_right):
            return "br"
        if top:
            return "max"
        if left:
            return "left"
        if right:
            return "right"
        return None

    def inner_edge(self, out, x, y):
        """Is the pointer at an edge another screen continues past? Crossing to that
        screen must not snap the window on the way (KWin waits 250 ms there)."""
        o = out["rect"]
        probes = []
        if x <= o["x"] + EDGE:
            probes.append((o["x"] - 1 - EDGE, y))
        if x >= o["x"] + o["width"] - 1 - EDGE:
            probes.append((o["x"] + o["width"] + EDGE, y))
        if y <= o["y"] + EDGE:
            probes.append((x, o["y"] - 1 - EDGE))
        if y >= o["y"] + o["height"] - 1 - EDGE:
            probes.append((x, o["y"] + o["height"] + EDGE))
        return any(self.output_rect_at(px, py) for px, py in probes)

    def drag_zone(self, x, y):
        """Which drop zone the pointer is in, and its preview rectangle."""
        d = self.drag
        zone, rect = None, None
        ws_hit = self.target_at(x, y)
        out = self.output_rect_at(x, y)
        if ws_hit is not None:
            zone = ("ws", ws_hit)
        elif out:
            kind = self.drop_kind(out, x, y)
            if kind and self.inner_edge(out, x, y):
                now = time.monotonic()
                key = (out["name"], kind)
                if d.get("dwell", (None, 0))[0] != key:
                    d["dwell"] = (key, now)
                if now - d["dwell"][1] < INNER_EDGE_S:
                    kind = None
            else:
                d["dwell"] = (None, 0)
            if kind:
                area = self.workarea(out["name"]) or out["rect"]
                zone, rect = (kind,), self.fit_rect(area, kind)
        if zone != d["zone"]:
            d["zone"] = zone
            self.show_preview(rect)
            self.draw_targets(zone[1] if zone and zone[0] == "ws" else None)

    def drag_end(self, x, y):
        d, self.drag = self.drag, None
        self.show_preview(None)
        self.hide_targets()
        if not d["moving"]:
            self.titlebar_click(d["con"], d["button"], x, y)
            return
        cid, zone, saved = d["con"], d["zone"], d.get("saved")
        kind = zone[0] if zone else None
        if d.get("pos") and kind != "ws":
            # i3 hears where the window is now (the frame was moved behind its back);
            # this also moves it to the workspace of the screen it was dropped on
            self.cmd(f'[con_id={cid}] move position {d["pos"][0]} px {d["pos"][1]} px')
        if kind == "max":
            self.maximize(cid, saved)
        elif kind in ("left", "right", "tl", "tr", "bl", "br"):
            self.snap(cid, kind, saved)
        elif kind == "ws":
            # it lands on that workspace where it was picked up, not up on the panel: the
            # frame goes back to the spot i3 still has for it, then the window moves
            if d.get("frame") is not None:
                try:
                    d["frame"].configure(x=d["rect"]["x"] + d["dx"], y=d["rect"]["y"] + d["dy"])
                except error.XError:
                    pass
            self.cmd(f"[con_id={cid}] move container to workspace number {zone[1]}")
            self.set_saved(cid, None)
        else:
            # let go in the open (or over the panel but not on a workspace number: the
            # drag already keeps the window inside the work area): it stays right there
            self.set_saved(cid, None)
        self.schedule_refresh()

    def clamp_floating(self, cid):
        """A window that just became floating must be reachable: title bar below the
        panel, and no bigger than the screen area (Firefox used to end up under it).
        A window that opened full screen is the app's own choice and stays so:
        Telegram shows a photo full screen, and this used to turn the viewer into a
        maximized window with a title bar, which the main window could then cover."""
        if self.drag:
            return False
        node, parent = find(self.i3.tree(), cid)
        if not parent or parent.get("type") != "floating_con" or self.is_fitted(node) \
                or node.get("fullscreen_mode"):
            return False
        area = self.workarea(self.con_output(cid))
        if not area:
            return False
        r = parent["rect"]
        if r["width"] >= area["width"] * 0.95 and r["height"] >= area["height"] * 0.95 \
                and not self.saved(cid):
            # it remembers being maximized (Firefox, Thunar, Telegram...): give it that
            self.maximize(cid)
            return False
        w, h = min(r["width"], int(area["width"] * 0.9)), min(r["height"], int(area["height"] * 0.9))
        x = min(max(r["x"], area["x"]), area["x"] + area["width"] - w)
        y = min(max(r["y"], area["y"]), area["y"] + area["height"] - h)
        if (x, y, w, h) != (r["x"], r["y"], r["width"], r["height"]):
            self.cmd(f"[con_id={cid}] resize set {w} px {h} px, move position {x} px {y} px")
            self.fit_floating(cid, (x, y, w, h))
        return False

    # ------------------------------------------------------------ preview
    def show_preview(self, rect):
        if rect is None:
            if self.preview:
                self.preview["win"].unmap()
            return
        if not self.preview:
            win = self.xs.window(self.xs.root, 0, 0, 1, 1, argb=True, bg=argb_pixel(ACCENT, 0.22))
            win.set_wm_class("deskd", "deskd")
            edges = [self.xs.window(win, 0, 0, 1, 1, argb=True, bg=argb_pixel(ACCENT_LIGHT, 0.95))
                     for _ in range(4)]
            for e in edges:
                e.map()
            self.preview = {"win": win, "edges": edges}
        x, y, w, h = rect
        p, b = self.preview, 3
        p["win"].configure(x=x, y=y, width=w, height=h, stack_mode=X.Above)
        for e, g in zip(p["edges"], [(0, 0, w, b), (0, h - b, w, b), (0, 0, b, h), (w - b, 0, b, h)]):
            e.configure(x=g[0], y=g[1], width=max(1, g[2]), height=max(1, g[3]))
        p["win"].map()
        p["win"].configure(stack_mode=X.Above)

    # ------------------------------------------------------------ panel workspace strips
    # Every panel has a strip (genmon running panel-workspaces [output]). Its text, the
    # click zones over it and the drop targets during a drag all come from strip_segments().
    def strip_plugins(self, fresh=False):
        """[(plugin_id, output)] - output None means the primary screen."""
        if fresh or self._strips is None:
            self._strips = panels.strips()
        return self._strips

    def strip_output(self, out):
        return out or self.primary_output()

    def primary_output(self):
        outs = self.outputs_sorted()
        return outs[0]["name"] if outs else None

    def plugin_geometry(self, plugin_id):
        """Screen rectangle of a panel plugin (its wrapper-2.0 window)."""
        try:
            for top in self.xs.root.query_tree().children:
                for kid in self.children(top):
                    cls = kid.get_wm_class()
                    if not cls or cls[1] != "Xfce4-panel":
                        continue
                    stack = [kid]
                    while stack:
                        w = stack.pop()
                        for c in self.children(w):
                            stack.append(c)
                            wc = c.get_wm_class()
                            if not wc or wc[0] != "wrapper-2.0":
                                continue
                            prop = c.get_full_property(self.A["_NET_WM_PID"], Xatom.CARDINAL)
                            if not prop:
                                continue
                            args = open(f"/proc/{prop.value[0]}/cmdline").read().split("\0")
                            if len(args) > 2 and args[2] == str(plugin_id):
                                g = c.get_geometry()
                                t = c.translate_coords(self.xs.root, 0, 0)
                                return (-t.x, -t.y, g.width, g.height)
        except Exception as e:
            log("panel lookup failed:", e)
        return None

    def strip_segments(self, items, by_num):
        """[(plain, markup)] per workspace number - the single source of the strip's text."""
        segs = []
        for label, num in items:
            w = by_num.get(num)
            # the workspace in front of you is black: its shape is the hole in the fire
            # sky-stars draws over it, as the letters of the game's logo; one that has
            # just received a window (i3 "urgent") is the accent - the window itself is
            # not marked, only the strip
            if w and w.get("focused"):
                colour, extra = THEME["background"], ' weight="bold"'
            elif w and w.get("urgent"):
                colour, extra = THEME["accent"], ' weight="bold"'
            elif w and w.get("visible"):
                colour, extra = THEME["light"], ""
            elif w:
                colour, extra = THEME["text"], ""
            else:
                colour, extra = THEME["dim"], ""
            # the workspace in front of you is marked by the pentagram drawn over it
            # (see ActiveMark), and the one under the pointer by the hole in the veil
            segs.append((STRIP_PAD + label + STRIP_PAD,
                         f'<span foreground="{colour}"{extra}>{STRIP_PAD}{label}{STRIP_PAD}</span>'))
        if segs:                                     # the last cell ends in the thin end pad
            plain, markup = segs[-1]
            segs[-1] = (plain[:-1] + STRIP_END, markup.replace(STRIP_PAD + "</span>", STRIP_END + "</span>"))
        return segs

    def render_workspaces(self, workspaces):
        by_num = {w["num"]: w for w in workspaces}
        primary = self.primary_output()
        self.items_by_output = {}
        for o in self.outputs_sorted():
            items = self.items_for_output(o["name"], workspaces)
            segs = self.strip_segments(items, by_num)
            self.items_by_output[o["name"]] = (items, segs)
            text = ('<css>* { background-color: transparent; background-image: none; box-shadow: none; } '
                    f'button {{ padding: {2 * STRIP_SHIFT}px 0 0 0; }}</css>\n'
                    '<txt><span font_features="tnum">' + "".join(m for _, m in segs) + STRIP_TAIL
                    + "</span></txt>\n"
                    "<tool>Workspaces: click to switch · drag a window here to move it</tool>\n")
            files = [ws_file(o["name"])] + ([WS_FILE] if o["name"] == primary else [])
            if self.last_ws_text.get(o["name"]) == text:
                continue
            self.last_ws_text[o["name"]] = text
            for path in files:
                with open(path + ".tmp", "w") as f:
                    f.write(text)
                os.replace(path + ".tmp", path)
            for pid, out in self.strip_plugins():
                if self.strip_output(out) == o["name"]:
                    xfpanel.plugin_event(f"genmon-{pid}")      # D-Bus, not a process: the digit
                    # must turn black together with the fire that sky-stars moves onto it
            self.bounds_cache.clear()
        GLib.timeout_add(400, self.place_ws_clicks)

    def strip_view(self, pid, out):
        """(geometry, items, bounds) of one strip as it is on screen now."""
        geom = self.strip_geoms.get(pid)
        entry = self.items_by_output.get(self.strip_output(out))
        if not geom or not entry:
            return None
        items, segs = entry
        key = (pid, geom, tuple(p for p, _ in segs))
        if key not in self.bounds_cache:
            self.bounds_cache[key] = self.measure(geom, [p for p, _ in segs], STRIP_TAIL)
        return geom, items, self.bounds_cache[key]

    def panel_font(self):
        """The font the panel really draws the strip with. Read from xfconf, because a
        guess that is one size out puts every click area beside its number."""
        if "_panel_font" not in self.__dict__:
            self._panel_font = PANEL_FONT
            plugins = self.strip_plugins()
            if plugins:
                got = panels.q("-p", f"/plugins/plugin-{plugins[0][0]}/font").strip()
                if got:
                    self._panel_font = got
        return self._panel_font

    def measure(self, geom, plains, tail=""):
        """x range of every segment, measured with Pango in the panel font (genmon centres it)."""
        x0, _, w, _ = geom
        n = len(plains)
        try:
            Pango, layout = self.strip_layout("".join(plains) + tail)
            total = layout.get_pixel_size()[0]
            left = x0 + (w - total) / 2
            starts, pos = [], 0
            for p in plains:
                starts.append(pos)
                pos += len(p.encode())
            # the last number ends where the numbers end, not where the trailing
            # spacer does - otherwise its click area is a whole em too wide
            xs = [left + layout.index_to_pos(i).x / Pango.SCALE for i in starts + [pos]]
            return [(xs[i], xs[i + 1]) for i in range(n)]
        except Exception as e:
            log("measure failed:", e)
            return [(x0 + i * w / n, x0 + (i + 1) * w / n) for i in range(n)]

    def dpi(self):
        if not hasattr(self, "_dpi"):
            self._dpi = 96.0
            out = subprocess.run(["xrdb", "-query"], capture_output=True, text=True).stdout
            for line in out.splitlines():
                if line.startswith("Xft.dpi:"):
                    self._dpi = float(line.split()[1])
        return self._dpi

    def show_layer(self, win, visible):
        try:
            if visible:
                win.map()
                win.configure(stack_mode=X.Above)
            else:
                win.unmap()
        except error.XError:
            pass

    def place_ws_clicks(self):
        """A transparent click layer over every strip: click a number = go there."""
        for pid, out in self.strip_plugins():
            geom = self.plugin_geometry(pid)
            if not geom:
                continue
            self.strip_geoms[pid] = geom
            win = self.click_layers.get(pid)
            if win is None:
                win = self.xs.window(self.xs.root, *geom, input_only=True,
                                     events=(X.ButtonPressMask | X.PointerMotionMask
                                             | X.EnterWindowMask | X.LeaveWindowMask),
                                     cursor=self.xs.cursors["hand"])
                self.click_layers[pid] = win
                self.click_by_win[win.id] = (pid, out)
            win.configure(x=geom[0], y=geom[1], width=geom[2], height=geom[3], stack_mode=X.Above)
            self.show_layer(win, self.strip_output(out) not in self.busy_outputs)
        self.sync_active_mark()
        self.pump()
        return False

    def is_share_frame(self, win):
        try:
            return win.get_wm_name() == SHARE_FRAME
        except error.XError:
            return False

    def share_frame_present(self):
        try:
            return any(self.is_share_frame(w) and w.get_attributes().map_state == X.IsViewable
                       for w in self.xs.root.query_tree().children)
        except error.XError:
            return False

    def set_sharing(self, sharing):
        """Zoom's share frame appeared or went: hide every overlay of ours, or bring
        them back the way the screens' full-screen state allows."""
        self.sharing = sharing
        log("screen share", "started: overlays hidden" if sharing else "ended: overlays back")
        if sharing:
            for veil in self.veils.values():
                veil.set_visible(False)
            if self.ws_mark is not None:
                self.ws_mark.hide()
                self.mark_file.hide()
            return
        try:
            self.hide_over_fullscreen(self.i3.workspaces())
        except Exception as e:                       # noqa: BLE001
            log("veils after share:", e)
        self.sync_active_mark()

    def hide_over_fullscreen(self, workspaces):
        """A full-screen window (a photo in Telegram, a video, a game) covers the panel
        as well, and our veil and mark would still be sitting on top of it."""
        outputs = {w["name"]: w["output"] for w in workspaces}
        self.busy_outputs = {outputs.get(ws.get("name")) for ws in self.visible_workspaces(workspaces)
                             if any(n.get("fullscreen_mode") and n.get("window") for n, _ in walk(ws))}
        busy = self.busy_outputs
        front = next((w["output"] for w in workspaces if w.get("focused")), None)
        for frame, geom in self.dock_frames():
            veil = self.veils.get(frame.id)
            if veil is None:
                continue
            out = self.output_rect_at(geom[0] + geom[2] // 2, geom[1] + geom[3] // 2)
            clear = (out or {}).get("name") not in busy and not self.sharing
            veil.set_visible(clear)
            # the mark sits on the strip of the screen in front only: a full-screen video
            # on the other monitor hid it here at every refresh (it flickered)
            if not clear and self.ws_mark is not None and (out or {}).get("name") == front:
                self.ws_mark.hide()
                self.mark_file.hide()
        # the click layers over the strip and the sound indicator too: a full-screen
        # window (RustDesk, a video) covers the panel, and a click on its own toolbar up
        # there must reach it, not switch the workspace
        for pid, win in self.click_layers.items():
            out = self.click_by_win.get(win.id, (None, None))[1]
            self.show_layer(win, self.strip_output(out) not in busy)
        for pid, win in self.audio_layers.items():
            geom = self.audio_geoms.get(pid)
            if geom:
                out = self.output_rect_at(geom[0] + geom[2] // 2, geom[1] + 2)
                self.show_layer(win, (out or {}).get("name") not in busy)

    def sync_active_mark(self, focused=None):
        """Put the pentagram over the number of the workspace in front of you. The
        number can be given directly: on a switch the mark moves at once, before the
        workspace itself has finished drawing."""
        if self.ws_mark is None:
            self.ws_mark = ActiveMark(self.xs)
            self.mark_file = MarkFile(self.i3)
        if self.sharing:
            self.ws_mark.hide()
            self.mark_file.hide()
            return
        if focused is None:
            focused = next((w["num"] for w in self.i3.workspaces() if w.get("focused")), None)
        for pid, out in self.strip_plugins():
            if self.strip_output(out) in self.busy_outputs:   # a full-screen window there
                continue
            view = self.strip_view(pid, out)
            if not view:
                continue
            (gx, gy, gw, gh), items, bounds = view
            for (lo, hi), (label, num) in zip(bounds, items):
                if num == focused:
                    centre = self.digit_centre(label, lo, hi)
                    width = min(hi - lo, gh * 1.15)
                    self.mark_file.show(label, centre, self.digit_top(label, gy, gh))
                    if STAR_MARK:
                        self.ws_mark.place(int(centre - width / 2), gy, int(width), gh,
                                           label, self.panel_font(), self.dpi())
                    else:
                        self.ws_mark.hide()
                    return
        self.mark_file.hide()
        self.ws_mark.hide()

    def strip_layout(self, text):
        """A Pango layout of the strip exactly as the panel draws it - including the
        tabular figures. Without them "1" measures narrower than the rest and every
        number after it drifts away from where it really is."""
        gi.require_version("Pango", "1.0")
        gi.require_version("PangoCairo", "1.0")
        from gi.repository import Pango, PangoCairo
        ctx = PangoCairo.create_context(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)))
        PangoCairo.context_set_resolution(ctx, self.dpi())
        layout = Pango.Layout.new(ctx)
        layout.set_font_description(Pango.FontDescription.from_string(self.panel_font()))
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_font_features_new("tnum=1"))
        layout.set_attributes(attrs)
        layout.set_text(text, -1)
        return Pango, layout

    def digit_top(self, label, gy, gh):
        """The top of the digit's ink: the strip is one line centred in the plugin."""
        try:
            _, layout = self.strip_layout(STRIP_PAD + label + STRIP_PAD)
            ink, logical = layout.get_pixel_extents()
            return gy + (gh - logical.height) / 2 + ink.y + STRIP_SHIFT
        except Exception as e:                       # noqa: BLE001
            log("digit top failed:", e)
            return gy + gh / 2 - 11

    def digit_centre(self, label, lo, hi):
        """Where the digit's ink really sits in its cell. The cell is padded evenly, but
        a glyph is not centred inside its own advance - which is why a mark placed on
        the cell looks right on a 1 and off on a 4."""
        try:
            _, layout = self.strip_layout(STRIP_PAD + label + STRIP_PAD)
            ink, _ = layout.get_pixel_extents()
            return lo + ink.x + ink.width / 2
        except Exception as e:                       # noqa: BLE001 - fall back to the cell
            log("digit ink failed:", e)
            return (lo + hi) / 2

    def strip_hit(self, x, y):
        """(ws number) under the pointer in any strip, or None."""
        for pid, out in self.strip_plugins():
            view = self.strip_view(pid, out)
            if not view:
                continue
            (gx, gy, gw, gh), items, bounds = view
            if not (gx <= x < gx + gw and gy <= y < gy + gh + 6):
                continue
            for (lo, hi), (_, num) in zip(bounds, items):
                if lo <= x < hi:
                    return num
        return None

    def ws_clicked(self, e):
        if e.detail == 1:
            num = self.strip_hit(e.root_x, e.root_y)
            if num is not None:
                self.cmd(f"workspace number {num}")

    def show_targets(self):
        """While dragging: every strip turns into big drop targets."""
        self.place_ws_clicks()
        self.targets = {}
        for pid, out in self.strip_plugins():
            view = self.strip_view(pid, out)
            if not view:
                continue
            (x, y, w, h), _, _ = view
            # wider than the strip by a margin each side: the frames are centred on the
            # numbers and the outer ones reach past the strip's edges
            win = self.xs.window(self.xs.root, x - TARGET_MARGIN, y, w + 2 * TARGET_MARGIN, h, argb=True)
            win.map()
            win.configure(stack_mode=X.Above)
            self.targets[pid] = {"win": win, "out": out, "surface": None}
        self.targets_hot = False          # nothing drawn yet, so the first draw happens
        self.draw_targets(None)

    def target_at(self, x, y):
        return self.strip_hit(x, y) if self.targets else None

    def draw_targets(self, hot):
        """Redraw only when the target under the pointer changes: this runs on every
        poll of the drag, and a fresh surface each time cost tens of megabytes."""
        if hot == self.targets_hot:
            return
        self.targets_hot = hot
        for pid, t in (self.targets or {}).items():
            view = self.strip_view(pid, t["out"])
            if not view:
                continue
            (gx, _, w, h), items, bounds = view
            gx, w = gx - TARGET_MARGIN, w + 2 * TARGET_MARGIN
            s = t.get("surface")
            if s is None or s.get_width() != w or s.get_height() != h:
                s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                t["surface"] = s
            c = cairo.Context(s)
            c.set_operator(cairo.OPERATOR_SOURCE)      # the strip is reused, so overwrite
            c.set_source_rgba(0, 0, 0, 0)              # see-through: the numbers stay the panel's
            c.paint()
            c.set_operator(cairo.OPERATOR_OVER)
            # a red frame, in the palette, centred on each number's ink (the cells are
            # wider than the numbers and a glyph is not centred in its advance), as wide
            # as a cell less a 6 px gap - the space between the numbers is a target too;
            # the one under the pointer fills with the same red at 20 %
            wide = max(hi - lo for lo, hi in bounds) - 6 if bounds else 0
            tall = h - 14
            for (lo, hi), (label, num) in zip(bounds, items):
                x0 = round(self.digit_centre(label, lo, hi) - gx - wide / 2) + 0.5
                if num == hot:
                    c.set_source_rgba(*rgb(DANGER, 0.2))
                    c.rectangle(x0, 7.5, wide, tall)
                    c.fill()
                c.set_source_rgba(*rgb(DANGER, 0.9))
                c.set_line_width(1)
                c.rectangle(x0, 7.5, wide, tall)
                c.stroke()
            s.flush()
            self.xs.paint(t["win"], s, 32)

    def hide_targets(self):
        for t in (self.targets or {}).values():
            try:
                t["win"].destroy()
            except Exception:
                pass
            self.xs.gc_cache.pop(t["win"].id, None)
        self.targets = None
        self.targets_hot = False

    # ------------------------------------------------------------ workspaces
    def outputs_sorted(self):
        outs = [o for o in self.i3.outputs() if o.get("active")]
        outs.sort(key=lambda o: (not o.get("primary"), o["rect"]["x"], o["rect"]["y"]))
        return outs

    def block_for(self, name):
        if name not in self.blocks:
            used = set(self.blocks.values())
            self.blocks[name] = next(k for k in range(0, 10) if k not in used)
            self.save_state()
        return self.blocks[name]

    def items_for_output(self, out_name, workspaces):
        """(label, ws_number) as shown for one screen: its own 1..5 always, its own
        6..9 when they exist, then workspaces inherited from a screen that is gone."""
        k = self.block_for(out_name)
        mine = {w["num"] for w in workspaces if w["output"] == out_name}
        items = []
        for n in range(1, 10):
            num = k * BLOCK + n
            if n <= PANEL_WS_COUNT or num in mine:
                items.append(num)
        foreign = sorted(n for n in mine if n > 0 and n // BLOCK != k)
        items += foreign
        return [(str(i + 1) if i < 9 else "0", num) for i, num in enumerate(items)]

    def target_ws(self, n):
        """Super+N: the N-th workspace of the focused screen."""
        workspaces = self.i3.workspaces()
        out = next((w["output"] for w in workspaces if w["focused"]), None)
        if not out:
            return n
        items = self.items_for_output(out, workspaces)
        if 1 <= n <= len(items):
            return items[n - 1][1]
        return self.block_for(out) * BLOCK + n

    def outputs_changed(self):
        """A screen appeared or went away. i3 already moved the workspaces of a
        vanished screen to a remaining one; here, workspaces whose screen is gone
        move to a newly connected screen."""
        outs = self.outputs_sorted()
        names = [o["name"] for o in outs]
        workspaces = self.i3.workspaces()
        focused = next((w["name"] for w in workspaces if w["focused"]), None)
        active_blocks = {self.block_for(n) for n in names}
        orphan_blocks = sorted({w["num"] // BLOCK for w in workspaces
                                if w["num"] > 0 and w["num"] // BLOCK not in active_blocks})
        moved = False
        for o in outs:
            k = self.blocks.get(o["name"])
            has_own = any(w["num"] // BLOCK == k for w in workspaces if w["output"] == o["name"])
            if o.get("primary") or has_own or not orphan_blocks:
                continue
            # a new screen with nothing of its own: it takes over the oldest orphan block
            k_new = orphan_blocks.pop(0)
            for name, blk in list(self.blocks.items()):
                if blk == k_new and name != o["name"]:
                    del self.blocks[name]
            self.blocks[o["name"]] = k_new
            for w in workspaces:
                if w["num"] // BLOCK == k_new:
                    self.cmd(f'workspace number {w["num"]}; move workspace to output {o["name"]}')
                    moved = True
        # a workspace from a screen that IS present, sitting on another screen (i3's
        # default placement, or moved by hand): it becomes that screen's own
        workspaces = self.i3.workspaces()
        active_blocks = {self.block_for(o["name"]): o["name"] for o in outs}
        for o in outs:
            k = self.block_for(o["name"])
            taken = {w["num"] for w in workspaces}
            for w in sorted(workspaces, key=lambda w: w["num"]):
                home = w["num"] // BLOCK
                if w["output"] != o["name"] or w["num"] <= 0 or home == k or home not in active_blocks:
                    continue
                free = next((k * BLOCK + n for n in range(1, 10) if k * BLOCK + n not in taken), None)
                if free is None:
                    continue
                self.cmd(f'rename workspace "{w["name"]}" to "{free}"')
                taken.add(free)
                if w["name"] == focused:
                    focused = str(free)
                moved = True

        # a screen showing an empty workspace that belongs to another screen (i3 names
        # a fresh screen's workspace "2", "3"...): switch it to its own first one
        tree = self.i3.tree()
        workspaces = self.i3.workspaces()
        for o in outs:
            k = self.block_for(o["name"])
            cur = next((w for w in workspaces if w["output"] == o["name"] and w["visible"]), None)
            if not cur or cur["num"] // BLOCK == k:
                continue
            node = next((n for n, _ in walk(tree) if n.get("type") == "workspace"
                         and n.get("name") == cur["name"]), None)
            if node and not i3ipc.leaves(node):
                self.cmd(f'focus output {o["name"]}; workspace number {k * BLOCK + 1}')
                if cur["name"] == focused:
                    focused = str(k * BLOCK + 1)
                moved = True
        self.save_state()
        if moved and focused:
            self.cmd(f"workspace {focused}")
        self.sync_panels(outs)
        GLib.timeout_add(600, self.refit_all)
        self.schedule_refresh()
        return False

    def refit_all(self):
        """Maximized and snapped windows fill the screen they are on now: when a screen
        goes away or arrives, i3 moves workspaces and leaves such windows at their old
        size - they looked restored while deskd still held them as maximized."""
        self._ws_snap = None
        # without focusing each one: that made the focus (and the workspace in front)
        # jump to the last fitted window at every deskd start and every screen change
        for node, _ in walk(self.i3.tree()):
            if not node.get("window"):
                continue
            side = self.snapped_side(node)
            if self.is_maximized(node):
                self.maximize(node["id"], self.saved(node["id"]), focus=False)
            elif side:
                self.snap(node["id"], side, self.saved(node["id"]), focus=False)
        return False

    def sync_panels(self, outs):
        """One panel per screen: add panels for new screens, drop those of gone ones."""
        names = [o["name"] for o in outs]
        if not names or os.environ.get("DESKD_NO_PANELS"):     # tests in a nested X server
            return
        width = {o["name"]: o["rect"]["width"] for o in outs}
        narrow = {n for n in names[1:] if width.get(n, 0) < width.get(names[0], 0)}
        add, drop, props = panels.plan(names, names[0], narrow)
        if not add and not drop:
            return
        log("panels: adding", add, "dropping", drop, "narrow", sorted(narrow))
        panels.apply(add, drop, props, lambda: self.cmd("exec --no-startup-id xfce4-panel"), narrow)
        self._strips = None
        self.last_ws_text = {}

        def after():
            self.strip_plugins(fresh=True)
            self.refresh()
            self.place_ws_clicks()
            return False
        GLib.timeout_add(3000, after)

    # ------------------------------------------------------------ commands
    def command(self, args):
        if not args:
            return
        what = args[0]
        if what == "overlays":
            return self.raise_overlays()
        tree = self.i3.tree()
        node, parent = i3ipc.focused(tree)
        cid = node["id"] if node and node.get("window") else None
        if what == "titlebar":
            self.titlebar_press(int(args[1]) if len(args) > 1 else 3)
        elif what == "ws" and len(args) > 1:
            self.cmd(f"workspace number {self.target_ws(int(args[1]))}")
        elif what == "move" and len(args) > 1:
            self.cmd(f"move container to workspace number {self.target_ws(int(args[1]))}")
        elif what == "cycle":
            self.cycle(tree, -1 if len(args) > 1 and args[1] == "prev" else 1)
        elif what == "expect" and len(args) > 2:
            self.expect[args[1].lower()] = (int(args[2]), time.monotonic())
        elif what == "unminimize":
            self.unminimize_last()
        elif what == "refit":
            self.refit_all()
        elif cid is None:
            return
        elif what == "maximize":
            if node.get("fullscreen_mode"):
                self.cmd(f"[con_id={cid}] fullscreen disable")
            else:
                self.toggle_maximize(cid)
        elif what == "maximize-on":
            if not self.is_maximized(node):
                self.maximize(cid)
        elif what == "restore":
            if node.get("fullscreen_mode"):
                self.cmd(f"[con_id={cid}] fullscreen disable")
            elif self.is_fitted(node):
                self.restore(cid)
        elif what == "minimize":
            self.minimize(cid)
        elif what == "key" and len(args) > 1:
            k = args[1]
            if k in ("shift-left", "shift-right"):
                self.to_output(cid, k.split("-")[1])
            elif node.get("fullscreen_mode") and k == "down":
                self.cmd(f"[con_id={cid}] fullscreen disable")
            else:
                self.arrow(cid, node, k)
        self.schedule_refresh()

    def to_output(self, cid, direction, side=None):
        """Super+Shift+Left/Right as in Windows: the window goes to the screen on that
        side, and stays maximized / snapped there if it was (`side` asks for another
        half or quarter there instead)."""
        node, _ = find(self.i3.tree(), cid)
        if node is None:
            return False
        before = self.con_output(cid)
        self.cmd(f"[con_id={cid}] move container to output {direction}, focus")
        if self.con_output(cid) == before:
            return False
        side = side or self.snapped_side(node)
        if side:
            self.snap(cid, side, self.saved(cid))
        elif self.is_maximized(node):
            self.maximize(cid, self.saved(cid))
        else:
            self.clamp_floating(cid)
        return True

    # Super + arrows, as in Windows 10/11 (and KWin's quick tiling): what each key does
    # from each state. A half goes to a quarter with Up/Down, a quarter back to its half;
    # the opposite side restores; the same side again carries the window to the next
    # screen in that direction (">"), taking the mirrored half or quarter there.
    ARROWS = {
        None:    {"up": "max",   "down": "min",     "left": "left",  "right": "right"},
        "max":   {"up": None,    "down": "restore", "left": "left",  "right": "right"},
        "left":  {"up": "tl",    "down": "bl",      "left": ">",     "right": "restore"},
        "right": {"up": "tr",    "down": "br",      "left": "restore", "right": ">"},
        "tl":    {"up": "max",   "down": "left",    "left": ">",     "right": "tr"},
        "tr":    {"up": "max",   "down": "right",   "left": "tl",    "right": ">"},
        "bl":    {"up": "left",  "down": "min",     "left": ">",     "right": "br"},
        "br":    {"up": "right", "down": "min",     "left": "bl",    "right": ">"},
    }
    MIRROR = {"left": "right", "right": "left", "tl": "tr", "tr": "tl", "bl": "br", "br": "bl"}

    def arrow(self, cid, node, key):
        state = "max" if self.is_maximized(node) else self.snapped_side(node)
        action = self.ARROWS.get(state, self.ARROWS[None]).get(key)
        if action is None:
            return
        if action == "max":
            self.maximize(cid)
        elif action == "min":
            self.minimize(cid)
        elif action == "restore":
            self.restore(cid)
        elif action == ">":
            # only to a screen that really is on that side (i3 would wrap around)
            out = next((o for o in self.outputs() if o.get("active") and o["name"] == self.con_output(cid)), None)
            if out:
                o = out["rect"]
                probe = (o["x"] - 10 if key == "left" else o["x"] + o["width"] + 10, o["y"] + o["height"] // 2)
                if self.output_rect_at(*probe):
                    self.to_output(cid, key, self.MIRROR[state])
        else:
            self.snap(cid, action)

    def cycle(self, tree, step):
        """Alt+Tab as in Windows and Plasma: while Alt is held, Tab walks the windows of
        this workspace in the order they were last used - minimized ones included, as
        both do - and the window is switched to when Alt is let go. A quick Alt+Tab goes
        to the previous window without showing anything; held a moment longer, the
        switcher shows where Tab has got to. Nothing is focused or raised on the way.
        (The first version focused every window it passed and guessed the end of a
        round from a 1.5 s pause; a slow second Alt+Tab went two windows back.)"""
        r = self.alt_tab
        if r:
            r["idx"] = (r["idx"] + step) % len(r["order"])
            self.switcher.select(r["idx"])
            return
        node, _ = i3ipc.focused(tree)
        ws = i3ipc.workspace_of(tree, node["id"]) if node else None
        if not ws:
            return
        entries = [(w, False) for w in i3ipc.leaves(ws) if w.get("window")]
        for n, _ in walk(tree):
            if n.get("window") and any(m.startswith(MARK_MIN) for m in n.get("marks") or []):
                if (self.saved(n["id"]) or {}).get("ws") in (None, ws["name"]) \
                        and self.minimized_owner(tree, n) is None:     # a dialog comes with its window
                    entries.append((n, True))
        if len(entries) < 2:
            return
        rank = {cid: i for i, cid in enumerate(self.focus_order)}
        focused_id = node["id"] if node.get("window") else None
        entries.sort(key=lambda e: (e[0]["id"] != focused_id, rank.get(e[0]["id"], len(rank))))
        order = [(n["id"], n["window"], n.get("name") or "", mini) for n, mini in entries]
        start = 0 if focused_id is None else step
        self.alt_tab = {"order": order, "idx": start % len(order), "since": time.monotonic(),
                        "area": ws["rect"]}
        GLib.timeout_add(20, self.alt_tab_poll)

    def drop_from_round(self, cid):
        """A window closed while Alt+Tab is held leaves the list at once."""
        r = self.alt_tab
        if not r:
            return
        ids = [e[0] for e in r["order"]]
        if cid not in ids:
            return
        i = ids.index(cid)
        r["order"].pop(i)
        if i < r["idx"] or r["idx"] >= len(r["order"]):
            r["idx"] = max(0, r["idx"] - 1)
        if len(r["order"]) < 2:
            self.alt_tab = None
            self.switcher.hide()
        elif self.switcher.shown:
            self.switcher.show([(xid, title, mini) for _, xid, title, mini in r["order"]], r["idx"], r["area"])

    def alt_tab_poll(self):
        """Watch Alt while a round is on (20 ms, only then): released - switch."""
        r = self.alt_tab
        if not r:
            return False
        _, _, mask = self.xs.pointer()
        now = time.monotonic()
        if not mask & X.Mod1Mask or now - r["since"] > 60:
            self.alt_tab = None
            self.switcher.hide()
            self.cmd(f'[con_id={r["order"][r["idx"]][0]}] focus')     # a minimized one comes back
            self.pump()
            return False
        if not self.switcher.shown and now - r["since"] >= ALT_TAB_SHOW_S:
            self.switcher.show([(xid, title, mini) for _, xid, title, mini in r["order"]], r["idx"], r["area"])
            self.pump()
        return True


if __name__ == "__main__":
    loop = GLib.MainLoop()
    try:
        app = Deskd()
    except Exception as e:
        log("start failed:", e)
        raise
    log("running")
    loop.run()
