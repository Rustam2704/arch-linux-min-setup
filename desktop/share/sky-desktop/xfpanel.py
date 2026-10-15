"""Poke an xfce4-panel plugin over D-Bus, the way `xfce4-panel --plugin-event` does,
without spawning a process (that took ~130 ms: fork, GTK start-up, D-Bus). Used by
deskd and osd-daemon to make a genmon plugin rerun its script the moment its
data changed. The call is asynchronous: the caller's GLib loop carries on and a
missing panel is not an error worth logging."""
import os
import subprocess
import threading

from gi.repository import Gio, GLib

_bus = None
_ids = {"dirty": True, "by_command": {}}
_watch_started = False


def _watch_panel():
    # netqd and sysqd have no GLib main loop; give the name watch its own context.
    context = GLib.MainContext()
    context.push_thread_default()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.signal_subscribe("org.freedesktop.DBus", "org.freedesktop.DBus",
                             "NameOwnerChanged", "/org/freedesktop/DBus",
                             "org.xfce.Panel", Gio.DBusSignalFlags.NONE,
                             lambda *_: _ids.__setitem__("dirty", True))
        GLib.MainLoop.new(context, False).run()
    finally:
        context.pop_thread_default()


def _connection():
    global _bus, _watch_started
    if _bus is None:
        _bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if not _watch_started:
        _watch_started = True
        threading.Thread(target=_watch_panel, daemon=True).start()
    return _bus


def plugin_event(plugin, name="refresh", value=True):
    """plugin: 'genmon-45' style id (as in the xfconf key); the panel returns at once."""
    global _bus
    try:
        bus = _connection()
        bus.call("org.xfce.Panel", "/org/xfce/Panel", "org.xfce.Panel", "PluginEvent",
                  GLib.Variant("(ssv)", (plugin, name, GLib.Variant("b", value))),
                  GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 1000, None, _done)
    except GLib.Error:
        _bus = None
        _ids["dirty"] = True


def _done(bus, result):
    try:
        bus.call_finish(result)
    except GLib.Error:
        _ids["dirty"] = True


def plugin_ids(command):
    """Ids of every genmon plugin running `command` (basename) - one per panel, so the
    second screen's copy is refreshed too. Re-read after a panel restart or failed refresh."""
    context = GLib.MainContext.default()
    if threading.current_thread() is threading.main_thread() and not context.is_owner():
        while context.pending():
            context.iteration(False)      # deliver async refresh results in daemons without a GLib loop
    try:
        _connection()
    except GLib.Error:
        pass
    if _ids["dirty"]:
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
        _ids.update(dirty=not bool(out), by_command=found)
    return _ids["by_command"].get(command, [])


def refresh(command):
    """Make every genmon plugin running `command` rerun it now."""
    for pid in plugin_ids(command):
        plugin_event(f"genmon-{pid}")
