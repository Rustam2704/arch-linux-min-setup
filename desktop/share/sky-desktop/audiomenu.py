"""The sound menu under the panel's speaker: output and input sliders (long ones),
mute buttons, the key-sound switch and the mixer. Every change applies at once.
Escape or a click outside closes it. Hosted by osd-daemon (`osd menu audio`): one
instance, toggled - a second click on the speaker closes it instead of opening
another; `audio-menu` is the thin command."""
import os
import re
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from sky_theme import THEME, css  # noqa: E402

PANEL, GAP = 66, 6
SLIDER = 480                    # px: four times the Xfce plugin's
ICON = 48                       # px: twice the plugin's
LIMIT = 150                     # percent, the same ceiling the volume keys have
KEYSOUND = os.path.expanduser("~/.config/sky-desktop/keysound")
ICONS = os.path.expanduser("~/.local/share/icons/Sky-Dark-Icons/scalable/status")
FIFO = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "osd.fifo")

STYLE = css("""
#audio-menu { background-color: @COLOUR_BACKGROUND@; border: 1px solid @COLOUR_BORDER@; border-radius: 8px; }
#audio-menu * { font-family: @FONT@; color: @COLOUR_FOREGROUND@; }
#audio-menu .row-label { color: @COLOUR_MUTED@; font-size: 9pt; }
#audio-menu scale trough { min-height: 8px; background-color: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; }
#audio-menu scale highlight { background-color: @COLOUR_LIGHT@; border-color: @COLOUR_LIGHT@; }
#audio-menu scale slider { min-width: 22px; min-height: 22px; background-color: @COLOUR_FOREGROUND@; border: none; }
#audio-menu button { background: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; border-radius: 8px; padding: 6px 12px; box-shadow: none; }
#audio-menu button:hover { border-color: @COLOUR_LIGHT@; }
#audio-menu button:checked { background: @COLOUR_ACCENT@; color: @COLOUR_BACKGROUND@; }
#audio-menu switch { background-color: @COLOUR_SURFACE@; border: 1px solid @COLOUR_BORDER@; }
#audio-menu switch:checked { background-color: @COLOUR_ACCENT@; }
#audio-menu switch slider { background-color: @COLOUR_FOREGROUND@; }
""")


def pactl(*args):
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=3).stdout
    except OSError:
        return ""


def percent(out):
    m = re.search(r"(\d+)%", out)
    return int(m.group(1)) if m else 0


ECHO = os.path.expanduser("~/.config/sky-desktop/echo-cancel")   # "on": echo cancellation for calls
ECHO_SOURCE, ECHO_SINK = "echo-cancel-source", "echo-cancel-sink"


def echo_on():
    try:
        return open(ECHO).read().strip() == "on"
    except OSError:
        return False                       # off by default: it costs CPU, Zoom has its own


def set_echo(on):
    """PipeWire's WebRTC echo canceller as a Pulse module, loaded only when wanted:
    virtual "echo cancelled" microphone and speakers, made the defaults so every app on
    "Default" gets them (Discord in the browser has no canceller of its own that works).
    Off: the module goes, the hardware devices are the defaults again."""
    os.makedirs(os.path.dirname(ECHO), exist_ok=True)
    with open(ECHO + ".tmp", "w") as f:
        f.write("on" if on else "off")
    os.replace(ECHO + ".tmp", ECHO)
    apply_echo()


def apply_echo():
    """Make the sound server match the saved state (also run by osd-daemon at start)."""
    loaded = [line.split("\t")[0] for line in pactl("list", "short", "modules").splitlines()
              if "module-echo-cancel" in line]
    if echo_on():
        if not loaded:
            pactl("load-module", "module-echo-cancel", "aec_method=webrtc",
                  f"source_name={ECHO_SOURCE}", f"sink_name={ECHO_SINK}",
                  "source_properties=device.description=Microphone-echo-cancelled",
                  "sink_properties=device.description=Speakers-echo-cancelled")
        pactl("set-default-source", ECHO_SOURCE)
        pactl("set-default-sink", ECHO_SINK)
    else:
        for module in loaded:
            pactl("unload-module", module)


def keysound_on():
    try:
        return open(KEYSOUND).read().strip() != "off"
    except OSError:
        return True


_state = {"win": None}


def toggle():
    """Open the menu under the panel's speaker, or close it if it is open."""
    win = _state["win"]
    if win is not None:
        close()
        return
    win = build()
    _state["win"] = win


def close(*_):
    win = _state.pop("win", None)
    _state["win"] = None
    if win is not None:
        try:
            Gdk.Display.get_default().get_default_seat().ungrab()
        except Exception:                                   # noqa: BLE001
            pass
        win.destroy()
    return False


def build():
    win = Gtk.Window(type=Gtk.WindowType.POPUP)
    win.set_name("audio-menu")
    provider = Gtk.CssProvider()
    provider.load_from_data(STYLE.encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    grid = Gtk.Grid(column_spacing=14, row_spacing=12, margin=16)
    win.add(grid)

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf

    def icon(name):
        return Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.join(ICONS, name), ICON, ICON))

    pending = {}

    def slider_row(row, label, get_cmd, set_cmd, mute_get, mute_set, icon_on, icon_off):
        img = icon(icon_on)
        grid.attach(img, 0, row, 1, 1)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, LIMIT, 1)
        scale.set_size_request(SLIDER, -1)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.add_mark(100, Gtk.PositionType.BOTTOM, None)
        scale.set_value(percent(pactl(*get_cmd)))
        grid.attach(scale, 1, row, 1, 1)
        mute = Gtk.ToggleButton(label="Mute")
        mute.set_active("yes" in pactl(*mute_get))
        grid.attach(mute, 2, row, 1, 1)

        def apply_volume():
            pending.pop(label, None)
            pactl(*set_cmd, f"{int(scale.get_value())}%")
            return False

        def changed(*_):                              # a moving slider: one write per 60 ms at most
            if label not in pending:
                pending[label] = GLib.timeout_add(60, apply_volume)
        scale.connect("value-changed", changed)

        def toggled(button):
            pactl(*mute_set, "1" if button.get_active() else "0")
            img.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(ICONS, icon_off if button.get_active() else icon_on), ICON, ICON))
        mute.connect("toggled", toggled)
        if mute.get_active():
            toggled(mute)

    slider_row(0, "Output", ("get-sink-volume", "@DEFAULT_SINK@"), ("set-sink-volume", "@DEFAULT_SINK@"),
               ("get-sink-mute", "@DEFAULT_SINK@"), ("set-sink-mute", "@DEFAULT_SINK@"),
               "audio-volume-high-symbolic.svg", "audio-volume-muted-symbolic.svg")
    slider_row(1, "Input", ("get-source-volume", "@DEFAULT_SOURCE@"), ("set-source-volume", "@DEFAULT_SOURCE@"),
               ("get-source-mute", "@DEFAULT_SOURCE@"), ("set-source-mute", "@DEFAULT_SOURCE@"),
               "microphone-sensitivity-high-symbolic.svg", "microphone-sensitivity-muted-symbolic.svg")

    # key sounds (the Diablo "accept" on Enter): off for online lessons, saved at once
    keys = Gtk.Label(label="Key sounds", xalign=0)
    grid.attach(keys, 0, 2, 2, 1)
    switch = Gtk.Switch(halign=Gtk.Align.END)
    switch.set_active(keysound_on())

    def keysound(sw, _):
        os.makedirs(os.path.dirname(KEYSOUND), exist_ok=True)
        with open(KEYSOUND + ".tmp", "w") as f:
            f.write("on" if sw.get_active() else "off")
        os.replace(KEYSOUND + ".tmp", KEYSOUND)
    switch.connect("notify::active", keysound)
    grid.attach(switch, 2, 2, 1, 1)

    # echo cancellation for calls: off unless wanted (Zoom cancels echo itself)
    echo_label = Gtk.Label(label="Echo cancellation", xalign=0)
    grid.attach(echo_label, 0, 3, 2, 1)
    echo = Gtk.Switch(halign=Gtk.Align.END)
    echo.set_active(echo_on())
    echo.connect("notify::active", lambda sw, _: set_echo(sw.get_active()))
    grid.attach(echo, 2, 3, 1, 1)

    mixer = Gtk.Button(label="Audio mixer…")
    mixer.connect("clicked", lambda *_: (subprocess.Popen(["pavucontrol"], start_new_session=True), close()))
    grid.attach(mixer, 0, 4, 3, 1)
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
        if status == Gdk.GrabStatus.SUCCESS or _state["win"] is not win:
            return False
        tries["n"] += 1
        if tries["n"] < 20:
            GLib.timeout_add(50, grab)
        else:
            GLib.timeout_add(8000, close)
        return False

    def pressed(_w, event):
        inside = 0 <= event.x < win.get_allocated_width() and 0 <= event.y < win.get_allocated_height()
        if not inside:
            close()
        return not inside

    win.connect("map-event", grab)
    win.connect("button-press-event", pressed)
    win.connect("key-press-event", lambda _w, e: close() if e.keyval == Gdk.KEY_Escape else None)
    return win


