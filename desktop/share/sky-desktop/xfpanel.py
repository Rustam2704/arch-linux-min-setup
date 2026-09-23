"""Poke an xfce4-panel plugin over D-Bus, the way `xfce4-panel --plugin-event` does,
without spawning a process (that took ~130 ms: fork, GTK start-up, D-Bus). Used by
deskd and osd-daemon to make a genmon plugin rerun its script the moment its
data changed. The call is asynchronous: the caller's GLib loop carries on and a
missing panel is not an error worth logging."""
from gi.repository import Gio, GLib

_bus = None


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
