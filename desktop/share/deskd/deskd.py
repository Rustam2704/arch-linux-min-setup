#!/usr/bin/env python3
"""deskd — Windows-style window handling on top of i3.

What it adds (all event driven; idle cost is zero):
  * title bar buttons on every window: minimize / maximize / close as coloured
    circles on the right (yellow, green, red), drawn inside i3's own frame;
  * resize by dragging the gap between windows, or the edge of a floating window,
    with no modifier key;
  * right click on a title bar: tiled <-> floating;
    right drag on a title bar: the window follows the pointer, and dropping it on
    the top edge maximizes it, on the left/right edge tiles it as a half, on a
    workspace number in the panel moves it there (blue preview while dragging);
  * maximize keeps the panel visible; restore puts a tiled window back exactly
    where it was; app buttons (Telegram, ...) asking to minimize/maximize are obeyed;
  * Windows keys: Super+Up/Down/Left/Right, Alt+Tab (focus within the workspace);
  * every screen has its own workspaces 1..5; when a screen goes away its
    workspaces join the laptop screen, and move to the next screen plugged in;
  * the panel's workspace strip (rendered here, clickable).

Commands arrive as i3 `nop deskd ...` bindings (see ~/.config/i3/config) or from
`deskd-ctl`, which sends the same `nop` through i3.
"""
import json
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))   # i3ipc, sky_theme
import gi  # noqa: E402
from gi.repository import GLib  # noqa: E402
import cairo  # noqa: E402
from Xlib import X, Xatom, display, error  # noqa: E402
from Xlib.ext import shape  # noqa: E402
from Xlib.protocol import event as xevent  # noqa: E402

import i3ipc  # noqa: E402
import panels  # noqa: E402
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
MARK_ORANGE = (0xf4, 0x81, 0x1e)   # the orange stripe of the apple in the corner
PANEL_WS_COUNT = 5            # workspaces always shown per screen
MARK_FILE = os.path.join(RUN, "deskd-mark.json")   # where the active digit is, for sky-stars
STAR_MARK = False             # the drawn pentagram over the digit; off while the game's spinning ones are tried
POPUP_OWNERS = ("net-menu", "power-menu", "panel-calendar")   # our pop-ups: no tooltip may cover them
BLOCK = 10                    # screen k owns workspaces k*10+1 .. k*10+9
HANDLE = 10                   # grab width around floating windows (px)
DRAG_START = 8                # px of movement before a right press becomes a drag
EDGE = 3                      # px from a screen edge that counts as "at the edge"
POLL_MS = 16
PANEL_FONT = THEME["panel_font"]
POPUP_APPS = "firefox-developer-edition"   # default for [settings] popup_apps
PASSTHROUGH_CLASSES = {"rustdesk"}   # remote desktops: keys go to the remote machine       # genmon font of the workspace strip
DEBUG = bool(os.environ.get("DESKD_DEBUG"))

MARK_MAX = "_deskd_max"
MARK_MIN = "_deskd_min"
MARK_CLICK = "_deskd_click"
DOUBLE_CLICK_S = 0.4          # two left clicks on a title bar within this = maximize/restore
STRIP_PAD = "\u2003"           # em space on both sides of each panel workspace number (2x wider)
STRIP_TAIL = "\u2003"          # one more at the end: genmon centres the strip, so this
                              # shifts the numbers left, away from the separator next to them


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
        self.gc_cache = {}

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
    def __init__(self):
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
        self.veils = {}             # dock frame id -> the dimming veil over that panel
        self.panel_items = []       # (rectangle, plugin id) of everything on the panel
        self.panel_windows = set()  # panel windows we watch the pointer on
        self.click_by_win = {}
        self.items_by_output = {}   # output -> ([(label, ws)], segments)
        self.bounds_cache = {}
        self.refresh_pending = False
        self.state = self._load_state()
        self.blocks = self.state.setdefault("blocks", {})     # output name -> block index
        self.last_ws_text = {}
        self.passthrough = False
        self.expect = {}            # class -> (workspace, when): "open the next window here"

        root_mask = X.SubstructureNotifyMask | X.PropertyChangeMask
        self.xs.root.change_attributes(event_mask=root_mask)
        self.A = {n: self.xs.atom(n) for n in (
            "WM_CHANGE_STATE", "_NET_WM_STATE", "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_PID", "_NET_ACTIVE_WINDOW")}
        GLib.io_add_watch(self.xs.d.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self.on_x)
        self.monitors = Monitors(self.xs)
        self.sub = i3ipc.Subscription(["window", "workspace", "output", "binding", "shutdown", "tick", "mode"],
                                      self.on_i3)
        self.outputs_changed()
        self.refresh()
        # the panel can restart or reflow; keep the click layer on the workspace strip
        GLib.timeout_add_seconds(20, self.recheck_strips)
        GLib.timeout_add(1500, lambda: (self.watch_panel_items(), False)[1])
        self.watch_power()
        self.pump()

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
        """Make one genmon plugin run its script now."""
        cache = self.__dict__.setdefault("plugin_ids", {})
        if command not in cache:                     # one xfconf query, then remembered
            for key, value in panels.read_all().items():
                if key.endswith("/command") and os.path.basename(value.strip()) == command:
                    cache[command] = key.split("/")[2].split("-")[1]
        if command in cache:
            spawn(["xfce4-panel", f"--plugin-event=genmon-{cache[command]}:refresh:bool:true"])

    def watch_panel_items(self):
        """Follow the pointer across the panel and work out what it is over. Pointer
        events are not exclusive, so watching the panel's own window takes nothing
        away from it, and it is the only way to see the plugins that have no window
        of their own - the clock, the volume, the shutdown button."""
        self.panel_items = self.panel_regions()
        mask = X.PointerMotionMask | X.EnterWindowMask | X.LeaveWindowMask
        watch = []
        frames = {}
        for frame, geom in self.dock_frames():
            frames[frame.id] = geom
            watch += frame.query_tree().children
            veil = self.veils.get(frame.id)
            if veil is None or not veil.matches(geom):
                self.veils[frame.id] = PanelDim(self.xs, geom)
        for fid in [f for f in self.veils if f not in frames]:   # the panel restarted: its old
            self.veils.pop(fid).set_visible(False)                # frame is gone, so is its veil
        watch += [win for win, _ in self.panel_wrappers()]
        for win in watch:
            try:
                win.change_attributes(event_mask=mask)
                self.panel_windows.add(win.id)
            except error.XError:
                pass
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
            for kid in top.query_tree().children:
                cls = kid.get_wm_class()
                if not cls or cls[1] != "Xfce4-panel":
                    continue
                stack = [kid]
                while stack:
                    w = stack.pop()
                    for c in w.query_tree().children:
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

    def recheck_strips(self):
        self.strip_plugins(fresh=True)
        self.panel_windows = set()  # the panel may have restarted with new windows
        self.watch_panel_items()
        self.__dict__.pop("_panel_font", None)     # the panel may have been restyled
        self.place_ws_clicks()
        return True

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
                self.handle_x(self.xs.d.next_event())
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
            if change in ("title", "urgent"):
                # neither moves, stacks or focuses anything; a busy terminal (spinner
                # in the title) would otherwise cost a full tree refresh every 100 ms
                return
            if change == "new":
                GLib.timeout_add(60, lambda c=con: self.place_new_window(c))
            elif change == "close":
                self.forget(con)
            elif change == "floating" and str(con.get("floating", "")).endswith("_on"):
                GLib.timeout_add(80, lambda cid=con["id"]: self.clamp_floating(cid))
            elif change == "focus":
                if any(m.startswith(MARK_MIN) for m in (con.get("marks") or [])):
                    GLib.idle_add(lambda cid=con["id"]: self.unminimize(cid) and False)
                self.passthrough_for(con)
        elif name == "workspace":
            current = (ev.get("current") or {}).get("num")
            if current is not None:
                self.sync_active_mark(current)      # the mark leads, the strip follows
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

    def popup_classes(self):
        """Apps whose extra windows follow the app (sign-in pop-ups and the like)."""
        try:
            import configparser
            cp = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#",))
            cp.optionxform = str
            cp.read(os.path.expanduser("~/.config/deskd/apps.conf"))
            raw = cp["settings"].get("popup_apps", POPUP_APPS)
        except Exception:
            raw = POPUP_APPS
        return {c.strip().lower() for c in raw.split(",") if c.strip()}

    def place_new_window(self, con):
        """A second window of an app (a sign-in pop-up, "open in new window"):
        put it where that app already is - or where the user asked for it with
        Ctrl on a panel button - and let it float, as such windows expect."""
        cid = con.get("id")
        cls = ((con.get("window_properties") or {}).get("class") or "").lower()
        if not cls or cls not in self.popup_classes():
            return False
        tree = self.i3.tree()
        node, parent = find(tree, cid)
        if node is None:
            return False
        want = None
        hint = self.expect.pop(cls, None)
        if hint and time.monotonic() - hint[1] < 20:
            want = hint[0]                                  # Ctrl + panel button: here
        else:
            others = [n for n, _ in walk(tree)
                      if n.get("window") and n["id"] != cid
                      and ((n.get("window_properties") or {}).get("class") or "").lower() == cls]
            if not others:
                return False                                # the app's first window: leave it
            others.sort(key=lambda n: n.get("focused", False), reverse=True)
            ws = i3ipc.workspace_of(tree, others[0]["id"])
            want = ws["num"] if ws else None
        here = i3ipc.workspace_of(tree, cid)
        if want and here and here.get("num") != want:
            self.cmd(f"[con_id={cid}] move container to workspace number {want}")
        if not (parent and parent.get("type") == "floating_con"):
            self.cmd(f"[con_id={cid}] floating enable")
        GLib.timeout_add(120, lambda: self.clamp_floating(cid))
        return False

    def passthrough_for(self, con):
        """RustDesk focused: every key (Super+...) goes to the remote machine."""
        cls = ((con.get("window_properties") or {}).get("class") or "").lower()
        want = cls in PASSTHROUGH_CLASSES
        if want and not self.passthrough:
            self.cmd('mode "passthrough"')
        elif not want and self.passthrough:
            self.cmd('mode "default"')

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
                try:
                    client = self.xs.d.create_resource_object("window", wid)
                    owner = client.get_wm_transient_for()
                except error.XError:
                    continue
                if owner is None or owner.id not in clients or owner.id == wid:
                    continue
                child, parent = self.frame_of(wid), self.frame_of(owner.id)
                if not child or not parent:
                    continue
                order = [w.id for w in self.xs.root.query_tree().children]
                if child[0].id in order and parent[0].id in order and \
                        order.index(child[0].id) < order.index(parent[0].id):
                    child[0].configure(sibling=parent[0], stack_mode=X.Above)
        except error.XError:
            pass

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
            for w in self.xs.root.query_tree().children:
                try:
                    cls = w.get_wm_class()
                    if cls and cls[0] in POPUP_OWNERS and w.get_attributes().map_state == X.IsViewable:
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
        saved = self.saved(cid)
        if saved:
            self.drop_saved(cid, saved)

    # ------------------------------------------------------------ resize handles
    def visible_workspaces(self, workspaces):
        names = {w["name"] for w in workspaces if w.get("visible")}
        return [n for n, _ in walk(self.tree) if n.get("type") == "workspace" and n.get("name") in names]

    def sync_handles(self, workspaces):
        specs = []
        for ws in self.visible_workspaces(workspaces):
            if any(n.get("fullscreen_mode") and n.get("window") for n, _ in walk(ws)):
                continue
            for node, _ in walk(ws):
                kids = node.get("nodes", [])
                if node.get("layout") in ("splith", "splitv") and len(kids) > 1:
                    for a, b in zip(kids, kids[1:]):
                        ra, rb = a["rect"], b["rect"]
                        if node["layout"] == "splith":
                            x1, x2 = ra["x"] + ra["width"], rb["x"]
                            if x2 - x1 < 6:
                                x1, x2 = x1 - 3, x1 + 3
                            y = min(ra["y"], rb["y"])
                            h = max(ra["y"] + ra["height"], rb["y"] + rb["height"]) - y
                            specs.append(((x1, y, x2 - x1, h), "h", {"kind": "split", "con": a["id"],
                                          "axis": "width", "start": ra["width"], "origin": ra["x"]}))
                        else:
                            y1, y2 = ra["y"] + ra["height"], rb["y"]
                            if y2 - y1 < 6:
                                y1, y2 = y1 - 3, y1 + 3
                            x = min(ra["x"], rb["x"])
                            w = max(ra["x"] + ra["width"], rb["x"] + rb["width"]) - x
                            specs.append(((x, y1, w, y2 - y1), "v", {"kind": "split", "con": a["id"],
                                          "axis": "height", "start": ra["height"], "origin": ra["y"]}))
            for fl in ws.get("floating_nodes", []):
                r = fl["rect"]
                x, y, w, h, t = r["x"], r["y"], r["width"], r["height"], HANDLE
                frame = self.floating_frame(fl)
                ring = [((x - t, y - t, t, t), "tl", "tl"), ((x, y - t, w, t), "t", "t"),
                        ((x + w, y - t, t, t), "tr", "tr"), ((x + w, y, t, h), "r", "r"),
                        ((x + w, y + h, t, t), "br", "br"), ((x, y + h, w, t), "b", "b"),
                        ((x - t, y + h, t, t), "bl", "bl"), ((x - t, y, t, h), "l", "l")]
                for geom, cur, edges in ring:
                    specs.append((geom, cur, {"kind": "float", "con": fl["id"], "edges": edges,
                                              "rect": dict(r), "frame": frame}))
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
                if info["kind"] == "float" and info.get("frame"):
                    w.configure(x=x, y=y, width=max(1, gw), height=max(1, gh),
                                sibling=info["frame"], stack_mode=X.Above)
                else:
                    w.configure(x=x, y=y, width=max(1, gw), height=max(1, gh), stack_mode=X.Below)
                h[2] = key
            if h[1] is None:
                w.map()
                if info["kind"] != "float":
                    w.configure(stack_mode=X.Below)
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
            if self.ws_mark is not None and wid == self.ws_mark.win.id:
                return self.ws_mark.draw()
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
        elif t == X.MapNotify:
            # a menu or a popup (the clock's calendar, a plugin's menu) is an
            # override-redirect window: a menu, a notification, the clock's calendar.
            # Keep it above everything, whatever the window below is doing.
            if self.tooltip_over_menu(e.window):
                return None
            self.raise_popup(e.window)
        elif t == X.ConfigureNotify:
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
                log("handle press", info["kind"], info.get("edges") or info.get("axis"), info["con"], e.root_x, e.root_y)
            self.resizing = {"info": info, "x": e.root_x, "y": e.root_y, "last": None}
        elif e.type == X.MotionNotify and self.resizing:
            self.resizing["pos"] = (e.root_x, e.root_y)
            if not self.resizing.get("timer"):
                self.resizing["timer"] = GLib.timeout_add(30, self.apply_resize)
        elif e.type == X.ButtonRelease and self.resizing:
            self.resizing["pos"] = (e.root_x, e.root_y)
            self.apply_resize(final=True)
            self.resizing = None
            self.schedule_refresh()

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
        if info["kind"] == "split":
            # move only the edge under the pointer: grow/shrink towards the neighbour
            # behind it (resize set would take space from every sibling)
            target = max(60, info["start"] + (dx if info["axis"] == "width" else dy))
            if final:
                node, _ = find(self.i3.tree(), info["con"])
                have = node["rect"][info["axis"]] if node else target
            else:
                have = r["last"] if r["last"] is not None else info["start"]
            step = target - have
            if step:
                side = "right" if info["axis"] == "width" else "down"
                verb = "grow" if step > 0 else "shrink"
                self.cmd(f'[con_id={info["con"]}] resize {verb} {side} {abs(step)} px')
            r["last"] = target
        else:
            rect, edges = info["rect"], info["edges"]
            x, y, w, h = rect["x"], rect["y"], rect["width"], rect["height"]
            if "l" in edges:
                x, w = x + dx, w - dx
            if "r" in edges:
                w = w + dx
            if "t" in edges:
                y, h = y + dy, h - dy
            if "b" in edges:
                h = h + dy
            w, h = max(160, w), max(100, h)
            key = (x, y, w, h)
            if key != r["last"]:
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
    def output_rect_at(self, x, y):
        for o in self.i3.outputs():
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

    def remember(self, cid, placeholder=False):
        """Record where a window lives now, so restore can put it back exactly.

        placeholder=True (maximize, pulling a tile out): an empty i3 container takes
        the window's place, so the layout does not change at all and restore is a swap.
        Otherwise (minimize) a neighbour is marked, and the space is given to others."""
        tree = self.i3.tree()
        node, parent = find(tree, cid)
        if node is None:
            return None
        if parent and parent.get("type") == "floating_con":
            r = parent["rect"]
            return {"mode": "floating", "rect": [r["x"], r["y"], r["width"], r["height"]]}
        if placeholder:
            mark = f"_deskd_p{cid}"
            self.cmd(f"[con_id={cid}] focus")
            self.cmd(f"open, mark --add {mark}")
            ph = self.find_mark(mark)
            if ph:
                self.cmd(f"[con_id={cid}] swap container with con_id {ph['id']}")
                return {"mode": "tiled", "placeholder": mark}
        siblings = [n for n in parent.get("nodes", [])] if parent else []
        idx = next((i for i, n in enumerate(siblings) if n["id"] == cid), -1)
        entry = {"mode": "tiled", "percent": node.get("percent"),
                 "axis": "width" if parent and parent.get("layout") == "splith" else "height"}
        if len(siblings) > 1 and idx >= 0:
            if idx > 0:
                anchor, entry["place"] = siblings[idx - 1], "after"
            else:
                anchor, entry["place"] = siblings[idx + 1], "before"
            mark = f"_deskd_a{cid}"
            self.cmd(f'[con_id={anchor["id"]}] mark --add {mark}')
            entry["anchor_mark"], entry["anchor"] = mark, anchor["id"]
            entry["anchor_leaf"] = bool(anchor.get("window"))
        return entry

    def maximize(self, cid, saved=None):
        output = self.con_output(cid)
        area = self.workarea(output) if output else None
        if not area:
            return
        node, parent = find(self.i3.tree(), cid)
        if node and node.get("fullscreen_mode"):
            self.cmd(f"[con_id={cid}] fullscreen disable")
        if saved is None:
            saved = self.remember(cid, placeholder=True)
        self.set_saved(cid, saved)
        x, y, w, h = area["x"], area["y"], area["width"], area["height"]
        self.cmd(f"[con_id={cid}] floating enable, mark --add {MARK_MAX}_{cid}, "
                 f"move position {x} px {y} px, resize set {w} px {h} px")
        self.fit_floating(cid, (x, y, w, h))
        # remember() opened an empty placeholder, and i3 gives a new container the
        # focus - so the window that fills the screen would be the one without it
        self.cmd(f"[con_id={cid}] focus")

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

    def toggle_maximize(self, cid):
        node, _ = find(self.i3.tree(), cid)
        if node is None:
            return
        if self.is_maximized(node):
            self.restore(cid)
        else:
            self.maximize(cid)

    def restore(self, cid, keep_floating=False):
        saved = self.saved(cid) or {"mode": "tiled"}
        self.cmd(f"[con_id={cid}] unmark {MARK_MAX}_{cid}, unmark {MARK_MIN}_{cid}")
        if saved.get("mode") == "floating" or keep_floating:
            if saved.get("rect"):
                x, y, w, h = saved["rect"]
                self.cmd(f"[con_id={cid}] floating enable, resize set {w} px {h} px, move position {x} px {y} px")
                self.fit_floating(cid, (x, y, w, h))
        elif saved.get("placeholder"):
            ph = self.find_mark(saved["placeholder"])
            self.cmd(f"[con_id={cid}] floating disable")
            if ph:
                self.cmd(f"[con_id={cid}] swap container with con_id {ph['id']}")
                self.cmd(f"[con_id={ph['id']}] kill")
        else:
            self.cmd(f"[con_id={cid}] floating disable")
            mark = saved.get("anchor_mark")
            if mark:
                res = self.cmd(f"[con_id={cid}] move container to mark {mark}")
                if res and res[0].get("success"):
                    horizontal = saved.get("axis", "width") == "width"
                    if saved.get("anchor_leaf", True):
                        # a window: we land right after it; "before" means swap
                        if saved.get("place") == "before":
                            self.cmd(f'[con_id={cid}] swap container with con_id {saved["anchor"]}')
                    else:
                        # a container: we land inside it; step out on the right side
                        after = saved.get("place") == "after"
                        step = ("right" if after else "left") if horizontal else ("down" if after else "up")
                        self.cmd(f"[con_id={cid}] move {step}")
                self.cmd(f"unmark {mark}")
            if saved.get("percent") and mark:          # only when it shared the space
                pct = max(5, min(95, round(saved["percent"] * 100)))
                self.cmd(f'[con_id={cid}] resize set {saved.get("axis", "width")} {pct} ppt')
        self.set_saved(cid, None)
        self.cmd(f"[con_id={cid}] focus")

    def minimize(self, cid):
        node, parent = find(self.i3.tree(), cid)
        if node is None:
            return
        if not self.saved(cid):
            self.set_saved(cid, self.remember(cid))
        self.cmd(f"[con_id={cid}] mark --add {MARK_MIN}_{cid}, move scratchpad")

    def unminimize(self, cid):
        node, _ = find(self.i3.tree(), cid)
        if node is None or not any(m.startswith(MARK_MIN) for m in (node.get("marks") or [])):
            return
        self.cmd(f"[con_id={cid}] unmark {MARK_MIN}_{cid}")
        if self.is_maximized(node):
            saved = self.saved(cid)
            self.maximize(cid, saved)
        else:
            self.restore(cid)

    def unminimize_last(self):
        tree = self.i3.tree()
        for node, _ in walk(tree):
            if any(m.startswith(MARK_MIN) for m in (node.get("marks") or [])):
                self.cmd(f"[con_id={node['id']}] scratchpad show")
                self.unminimize(node["id"])
                return
        self.cmd("scratchpad show")

    # ------------------------------------------------------------ snap half
    def snap(self, cid, side):
        """Tile the window at the left or right half of its workspace; other windows
        keep their arrangement in the other half."""
        node, parent = find(self.i3.tree(), cid)
        if node is None:
            return
        if parent and parent.get("type") == "floating_con":
            self.cmd(f"[con_id={cid}] unmark {MARK_MAX}_{cid}, floating disable")
        self.drop_saved(cid, self.saved(cid))
        direction = "left" if side == "left" else "right"
        last = None
        for _ in range(12):
            tree = self.i3.tree()
            node, parent = find(tree, cid)
            ws = i3ipc.workspace_of(tree, cid)
            if node is None or ws is None:
                return
            tiles = ws.get("nodes", [])
            if len(i3ipc.leaves({"nodes": tiles, "floating_nodes": []})) <= 1:
                return                      # alone: nothing to share the screen with
            at_root = parent is ws and ws.get("layout") == "splith"
            edge = tiles[0]["id"] if side == "left" else tiles[-1]["id"]
            if at_root and edge == cid:
                break
            sig = json.dumps([parent["id"] if parent else 0, [n["id"] for n in tiles]])
            if sig == last:
                break                       # no progress (would jump to another screen)
            last = sig
            self.cmd(f"[con_id={cid}] move {direction}")
        self.cmd(f"[con_id={cid}] resize set width 50 ppt, focus")

    # ------------------------------------------------------------ title bar: clicks and drags
    # ONE engine for every title bar drag (left or right button, tiled or floating):
    #   left button on a tiled window -> "tile" mode: rearrange tiles, blue preview on the target
    #   right button, or a floating window -> "float" mode: the window follows the pointer
    # In both modes the same zones apply: top edge = maximize, left/right edge = half,
    # a workspace number in any panel = move there. Fixes here apply to all of them.
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
        floating = parent is not None and parent.get("type") == "floating_con"
        frame = parent["rect"] if floating else target["rect"]
        self.drag = {"con": target["id"], "x0": x, "y0": y, "moving": False, "zone": None,
                     "button": button, "mask": bmask, "floating": floating,
                     "rect": dict(frame), "max": self.is_maximized(target)}
        GLib.timeout_add(POLL_MS, self.drag_poll)

    def titlebar_click(self, cid, button, x, y):
        """Right click: tiled <-> floating. Left double click: maximize <-> restore."""
        node, parent = find(self.i3.tree(), cid)
        if node is None:
            return
        if button == 1:
            now, last = time.monotonic(), self.last_click
            self.last_click = (cid, now, x, y)
            if last and last[0] == cid and now - last[1] < DOUBLE_CLICK_S \
                    and abs(x - last[2]) + abs(y - last[3]) < 12:
                self.last_click = None
                self.toggle_maximize(cid)
            return
        if self.is_maximized(node):
            self.restore(cid)
        elif parent and parent.get("type") == "floating_con":
            self.cmd(f"[con_id={cid}] floating disable")
        else:
            self.cmd(f"[con_id={cid}] floating enable")

    def drag_poll(self):
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
        if d["mode"] == "float":
            nx, ny = self.inside_workarea(x - d["off_x"], y - d["off_y"])
            if (nx, ny) != d.get("pos"):
                self.cmd(f'[con_id={d["con"]}] move position {nx} px {ny} px')
                d["pos"] = (nx, ny)
        self.drag_zone(x, y)
        self.pump()
        return True

    def inside_workarea(self, x, y):
        """Where a dragged window is allowed to be: the panel is always on top, so a
        window pushed against it stops at its edge instead of sliding underneath.
        The area and the window's height are worked out once, when the drag starts -
        this runs on every frame of the drag."""
        d = self.drag
        area = d.get("area") if d else None
        if not area:
            return x, y
        bottom = area["y"] + area["height"] - max(60, min(d.get("height", 0), area["height"]))
        return x, max(area["y"], min(y, bottom))

    def drag_begin(self, x, y):
        d = self.drag
        d["moving"] = True
        cid, r = d["con"], d["rect"]
        d["area"] = self.workarea(self.con_output(cid))     # measured once, used every frame
        d["height"] = r["height"]
        tiled = not d["floating"] and not d["max"]
        d["mode"] = "tile" if (d["button"] == 1 and tiled) else "float"
        d["saved"] = None
        if d["mode"] == "float":
            if d["max"]:
                d["saved"] = self.saved(cid)          # dropping it again restores to this
                w, h = max(400, int(r["width"] * 0.6)), max(300, int(r["height"] * 0.6))
                self.cmd(f"[con_id={cid}] unmark {MARK_MAX}_{cid}, resize set {w} px {h} px")
            elif tiled:
                d["saved"] = self.remember(cid, placeholder=True)
                area = self.workarea(self.con_output(cid)) or r
                w = min(r["width"], int(area["width"] * 0.6))
                h = min(r["height"], int(area["height"] * 0.7))
                self.cmd(f"[con_id={cid}] floating enable, resize set {w} px {h} px")
            else:
                w, h = r["width"], r["height"]
            frac = (d["x0"] - r["x"]) / max(1, r["width"])
            d["off_x"], d["off_y"] = int(w * frac), d["y0"] - r["y"]
        self.show_targets()

    def drag_zone(self, x, y):
        """Which drop zone the pointer is in, and its preview rectangle."""
        d = self.drag
        zone, rect = None, None
        ws_hit = self.target_at(x, y)
        out = self.output_rect_at(x, y)
        if ws_hit is not None:
            zone = ("ws", ws_hit)
        elif out:
            o = out["rect"]
            area = self.workarea(out["name"]) or o
            if y <= o["y"] + EDGE:
                zone, rect = ("max",), (area["x"], area["y"], area["width"], area["height"])
            elif x <= o["x"] + EDGE:
                zone, rect = ("left",), (area["x"], area["y"], area["width"] // 2, area["height"])
            elif x >= o["x"] + o["width"] - 1 - EDGE:
                half = area["width"] // 2
                zone, rect = ("right",), (area["x"] + area["width"] - half, area["y"], half, area["height"])
            elif d["mode"] == "tile":
                zone, rect = self.tile_zone(x, y, d["con"])
        if zone != d["zone"]:
            d["zone"] = zone
            self.show_preview(rect)
            self.draw_targets(zone[1] if zone and zone[0] == "ws" else None)

    def tile_zone(self, x, y, cid):
        """Over another tiled window: its nearest side (or its centre = swap)."""
        for ws in self.visible_workspaces(self.workspaces()):
            for leaf in i3ipc.leaves({"nodes": ws.get("nodes", []), "floating_nodes": []}):
                r = leaf["rect"]
                if leaf["id"] == cid or not (r["x"] <= x < r["x"] + r["width"] and r["y"] <= y < r["y"] + r["height"]):
                    continue
                rx, ry = (x - r["x"]) / r["width"], (y - r["y"]) / r["height"]
                sides = {"left": rx, "right": 1 - rx, "top": ry, "bottom": 1 - ry}
                side = min(sides, key=sides.get)
                if sides[side] > 0.3:
                    side = "center"
                X0, Y0, W, H = r["x"], r["y"], r["width"], r["height"]
                rect = {"left": (X0, Y0, W // 2, H), "right": (X0 + W - W // 2, Y0, W // 2, H),
                        "top": (X0, Y0, W, H // 2), "bottom": (X0, Y0 + H - H // 2, W, H // 2),
                        "center": (X0, Y0, W, H)}[side]
                return ("tile", leaf["id"], side), rect
        return None, None

    def drag_end(self, x, y):
        d, self.drag = self.drag, None
        self.show_preview(None)
        self.hide_targets()
        if not d["moving"]:
            self.titlebar_click(d["con"], d["button"], x, y)
            return
        cid, zone, saved = d["con"], d["zone"], d.get("saved")
        kind = zone[0] if zone else None
        if kind == "max":
            self.maximize(cid, saved)
        elif kind in ("left", "right"):
            if saved:
                self.set_saved(cid, saved)
            self.snap(cid, kind)
        elif kind == "ws":
            self.cmd(f"[con_id={cid}] move container to workspace number {zone[1]}")
            if saved and saved.get("mode") == "tiled":
                self.cmd(f"[con_id={cid}] floating disable")
            self.drop_saved(cid, saved)
        elif kind == "tile":
            self.tile_move(cid, zone[1], zone[2])
        elif self.over_dock(x, y):
            # let go over the panel but not on a workspace number: the window is already
            # held inside the work area by the drag, so it simply stays where it is,
            # right under the panel at the point it was let go
            self.drop_saved(cid, saved)
        elif d["mode"] == "float":
            self.drop_saved(cid, saved)         # dropped in the open: stays floating right there
        self.schedule_refresh()

    def drop_saved(self, cid, saved):
        """Forget where a window came from: close its placeholder / unmark its anchor."""
        if saved and saved.get("placeholder"):
            ph = self.find_mark(saved["placeholder"])
            if ph:
                self.cmd(f"[con_id={ph['id']}] kill")
        if saved and saved.get("anchor_mark"):
            self.cmd(f'unmark {saved["anchor_mark"]}')
        self.set_saved(cid, None)

    def tile_move(self, cid, tid, side):
        """Put tiled window cid next to tile tid (or swap them for the centre)."""
        if side == "center":
            self.cmd(f"[con_id={cid}] swap container with con_id {tid}")
            return
        _, parent = find(self.i3.tree(), tid)
        want = "splith" if side in ("left", "right") else "splitv"
        if not parent or parent.get("layout") != want:
            self.cmd(f"[con_id={tid}] split {'h' if want == 'splith' else 'v'}")
        mark = f"_deskd_t{cid}"
        self.cmd(f"[con_id={tid}] mark --add {mark}")
        self.cmd(f"[con_id={cid}] move container to mark {mark}")      # lands after tid
        if side in ("left", "top"):
            self.cmd(f"[con_id={cid}] swap container with con_id {tid}")
        self.cmd(f"unmark {mark}")
        self.cmd(f"[con_id={cid}] focus")

    def clamp_floating(self, cid):
        """A window that just became floating must be reachable: title bar below the
        panel, and no bigger than the screen area (Firefox used to end up under it)."""
        if self.drag:
            return False
        node, parent = find(self.i3.tree(), cid)
        if not parent or parent.get("type") != "floating_con" or self.is_maximized(node):
            return False
        area = self.workarea(self.con_output(cid))
        if not area:
            return False
        r = parent["rect"]
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
                for kid in top.query_tree().children:
                    cls = kid.get_wm_class()
                    if not cls or cls[1] != "Xfce4-panel":
                        continue
                    stack = [kid]
                    while stack:
                        w = stack.pop()
                        for c in w.query_tree().children:
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
            # the workspace in front of you is red like a close button; one that has
            # just received a window (i3 "urgent") is the accent - the window itself is
            # not marked, only the strip
            if w and w.get("focused"):
                colour, extra = THEME["danger"], ' weight="bold"'
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
        return segs

    def render_workspaces(self, workspaces):
        by_num = {w["num"]: w for w in workspaces}
        primary = self.primary_output()
        self.items_by_output = {}
        for o in self.outputs_sorted():
            items = self.items_for_output(o["name"], workspaces)
            segs = self.strip_segments(items, by_num)
            self.items_by_output[o["name"]] = (items, segs)
            text = ('<txt><span font_features="tnum">' + "".join(m for _, m in segs) + STRIP_TAIL
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
                    spawn(["xfce4-panel", f"--plugin-event=genmon-{pid}:refresh:bool:true"])
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
            win.map()
        self.sync_active_mark()
        self.pump()
        return False

    def hide_over_fullscreen(self, workspaces):
        """A full-screen window (a photo in Telegram, a video, a game) covers the panel
        as well, and our veil and mark would still be sitting on top of it."""
        outputs = {w["name"]: w["output"] for w in workspaces}
        self.busy_outputs = {outputs.get(ws.get("name")) for ws in self.visible_workspaces(workspaces)
                             if any(n.get("fullscreen_mode") and n.get("window") for n, _ in walk(ws))}
        busy = self.busy_outputs
        for frame, geom in self.dock_frames():
            veil = self.veils.get(frame.id)
            if veil is None:
                continue
            out = self.output_rect_at(geom[0] + geom[2] // 2, geom[1] + geom[3] // 2)
            clear = (out or {}).get("name") not in busy
            veil.set_visible(clear)
            if not clear and self.ws_mark is not None:
                self.ws_mark.hide()
                self.mark_file.hide()

    def sync_active_mark(self, focused=None):
        """Put the pentagram over the number of the workspace in front of you. The
        number can be given directly: on a switch the mark moves at once, before the
        workspace itself has finished drawing."""
        if self.ws_mark is None:
            self.ws_mark = ActiveMark(self.xs)
            self.mark_file = MarkFile()
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
            return gy + (gh - logical.height) / 2 + ink.y
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
            win = self.xs.window(self.xs.root, x, y, w, h, argb=True)
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
            s = t.get("surface")
            if s is None or s.get_width() != w or s.get_height() != h:
                s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
                t["surface"] = s
            c = cairo.Context(s)
            c.set_operator(cairo.OPERATOR_SOURCE)      # the strip is reused, so overwrite
            c.set_source_rgba(0.04, 0.06, 0.07, 0.96)
            c.paint()
            c.set_operator(cairo.OPERATOR_OVER)
            c.select_font_face("Inter", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            c.set_font_size(h * 0.42)
            for (lo, hi), (label, num) in zip(bounds, items):
                x0, cw = lo - gx, hi - lo
                c.set_source_rgba(*rgb(ACCENT, 0.9 if num == hot else 0.18))
                c.rectangle(x0 + 2, 4, cw - 4, h - 8)
                c.fill()
                c.set_source_rgba(*(rgb((255, 255, 255)) if num == hot else rgb(ACCENT_LIGHT)))
                ext = c.text_extents(label)
                c.move_to(x0 + cw / 2 - ext.width / 2 - ext.x_bearing, h / 2 - ext.height / 2 - ext.y_bearing)
                c.show_text(label)
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
        self.schedule_refresh()
        return False

    def sync_panels(self, outs):
        """One panel per screen: add panels for new screens, drop those of gone ones."""
        names = [o["name"] for o in outs]
        if not names or os.environ.get("DESKD_NO_PANELS"):     # tests in a nested X server
            return
        add, drop, props = panels.plan(names, names[0])
        if not add and not drop:
            return
        log("panels: adding", add, "dropping", drop)
        panels.apply(add, drop, props, lambda: self.cmd("exec --no-startup-id xfce4-panel"))
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
            elif self.is_maximized(node):
                self.restore(cid)
        elif what == "minimize":
            self.minimize(cid)
        elif what == "key" and len(args) > 1:
            k = args[1]
            if k == "up":
                if not self.is_maximized(node):
                    self.maximize(cid)
            elif k == "down":
                if node.get("fullscreen_mode"):
                    self.cmd(f"[con_id={cid}] fullscreen disable")
                elif self.is_maximized(node):
                    self.restore(cid)
                else:
                    self.minimize(cid)
            elif k in ("left", "right"):
                self.snap(cid, k)
        self.schedule_refresh()

    def cycle(self, tree, step):
        node, _ = i3ipc.focused(tree)
        ws = i3ipc.workspace_of(tree, node["id"]) if node else None
        if not ws:
            return
        wins = i3ipc.leaves(ws)
        if len(wins) < 2:
            return
        cur = next((i for i, w in enumerate(wins) if w.get("focused")), -1)
        self.cmd(f'[con_id={wins[(cur + step) % len(wins)]["id"]}] focus')


if __name__ == "__main__":
    loop = GLib.MainLoop()
    try:
        app = Deskd()
    except Exception as e:
        log("start failed:", e)
        raise
    log("running")
    loop.run()
