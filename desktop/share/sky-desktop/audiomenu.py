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
from gi.repository import GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from popmenu import PopMenu  # noqa: E402

SLIDER = 480                    # px: four times the Xfce plugin's
ICON = 48                       # px: twice the plugin's
LIMIT = 150                     # percent, the same ceiling the volume keys have
KEYSOUND = os.path.expanduser("~/.config/sky-desktop/keysound")
ICONS = os.path.expanduser("~/.local/share/icons/Sky-Dark-Icons/scalable/status")
FIFO = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "osd.fifo")

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


def toggle():
    """Open the menu under the panel's speaker, or close it if it is open."""
    MENU.toggle()


def close(*_):
    return MENU.close()


def fill(grid, close):

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


MENU = PopMenu("audio-menu", fill)
