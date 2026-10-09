"""Poke an xfce4-panel plugin over D-Bus, the way `xfce4-panel --plugin-event` does,
without spawning a process (that took ~130 ms: fork, GTK start-up, D-Bus). Used by
deskd and osd-daemon to make a genmon plugin rerun its script the moment its
data changed. The call is asynchronous: the caller's GLib loop carries on and a
missing panel is not an error worth logging."""
import os
import subprocess
import time

from gi.repository import Gio, GLib

_bus = None
_ids = {"at": 0.0, "by_command": {}}


def plugin_event(plugin, name="refresh", value=True):
    """plugin: 'genmon-45' style id (as in the xfconf key); the panel returns at once."""
    global _bus
    try:
        if _bus is None:
            _bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        _bus.call("org.xfce.Panel", "/org/xfce/Panel", "org.xfce.Panel", "PluginEvent",
                  GLib.Variant("(ssv)", (plugin, name, GLib.Variant("b", value))),
                  GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 1000, None, _done)
    except GLib.Error:
        _bus = None


def _done(bus, result):
    try:
        bus.call_finish(result)
    except GLib.Error:
        pass


def plugin_ids(command):
    """Ids of every genmon plugin running `command` (basename) - one per panel, so the
    second screen's copy is refreshed too. Looked up again at most every 10 s (panels
    come and go with screens)."""
    now = time.monotonic()
    if now - _ids["at"] > 10:
        found = {}
        try:
            out = subprocess.run(["xfconf-query", "-c", "xfce4-panel", "-l", "-v"],
                                 capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        for line in out.splitlines():
            key, _, value = line.partition(" ")
            if key.startswith("/plugins/plugin-") and key.endswith("/command"):
                found.setdefault(os.path.basename(value.strip().split()[0] if value.strip() else ""),
                                 []).append(key.split("/")[2].split("-")[1])
        _ids.update(at=now, by_command=found)
    return _ids["by_command"].get(command, [])


def refresh(command):
    """Make every genmon plugin running `command` rerun it now."""
    for pid in plugin_ids(command):
        plugin_event(f"genmon-{pid}")
