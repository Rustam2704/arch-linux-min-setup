"""The power menu under the panel's battery: the battery line and the power mode -
Automatic, Performance, Balanced, Power saver. The modes are TLP's profiles (tuned in
/etc/tlp.d/50-sky-desktop.conf); Automatic hands the choice back to TLP (performance on
the charger, balanced on battery). The choice is kept in ~/.config/sky-desktop/power-mode
and put back by osd-daemon at the next session. Hosted by osd-daemon (`osd menu power`)."""
import os
import subprocess
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from popmenu import PopMenu  # noqa: E402

STATE = os.path.expanduser("~/.config/sky-desktop/power-mode")
TLP_RUN = "/run/tlp/last_pwr"            # "<profile> <power source>", profile 0/1/2
BATTERY = "/sys/class/power_supply/BAT0"
MODES = [("auto", "Automatic", "Performance on the charger, balanced on battery"),
         ("performance", "Performance", "Full speed, turbo on"),
         ("balanced", "Balanced", "TLP's battery settings"),
         ("power-saver", "Power saver", "No turbo, CPU capped at 60 %, deepest PCIe power saving")]
PROFILE_NAMES = {"0": "performance", "1": "balanced", "2": "power-saver"}


def saved_mode():
    try:
        mode = open(STATE).read().strip()
        return mode if mode in dict((m, 1) for m, _, _ in MODES) else "auto"
    except OSError:
        return "auto"


def active_profile():
    try:
        return PROFILE_NAMES.get(open(TLP_RUN).read().split()[0], "")
    except (OSError, IndexError):
        return ""


def apply(mode=None):
    """Switch TLP to the mode (the saved one by default); 'auto' = `tlp start`."""
    mode = mode or saved_mode()
    if mode == "auto" and active_profile() == "":
        return                                    # nothing set yet, TLP is already automatic
    arg = "start" if mode == "auto" else mode
    subprocess.run(["sudo", "-n", "/usr/bin/tlp", arg], capture_output=True, timeout=30)


def set_mode(mode):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE + ".tmp", "w") as f:
        f.write(mode)
    os.replace(STATE + ".tmp", STATE)
    apply(mode)


def battery_line():
    def read(name):
        try:
            return open(os.path.join(BATTERY, name)).read().strip()
        except OSError:
            return ""
    line = f"Battery {read('capacity')}% · {read('status') or 'unknown'}"
    for kind in ("energy", "charge"):            # batteries report one or the other
        try:
            full, design = int(read(f"{kind}_full")), int(read(f"{kind}_full_design"))
            line += f" · health {round(100 * full / design)}%"
            break
        except (ValueError, ZeroDivisionError):
            continue
    return line


def fill(grid, close):
    info = Gtk.Label(label=battery_line(), xalign=0)
    info.get_style_context().add_class("row-label")
    grid.attach(info, 0, 0, 1, 1)

    current = saved_mode()
    buttons = {}
    state = {"busy": False}

    def chosen(button, mode):
        if state["busy"] or not button.get_active():
            return
        state["busy"] = True
        for other, b in buttons.items():          # one lit at a time, like radio buttons
            b.set_active(other == mode)
        state["busy"] = False
        GLib.idle_add(lambda: (set_mode(mode), False)[1])

    for row, (mode, label, hint) in enumerate(MODES, start=1):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=label, xalign=0)
        sub = Gtk.Label(label=hint, xalign=0)
        sub.get_style_context().add_class("row-label")
        box.add(title)
        box.add(sub)
        button = Gtk.ToggleButton()
        button.add(box)
        button.set_active(mode == current)
        button.connect("toggled", chosen, mode)
        buttons[mode] = button
        grid.attach(button, 0, row, 1, 1)


MENU = PopMenu("power-menu", fill)


def toggle():
    MENU.toggle()
