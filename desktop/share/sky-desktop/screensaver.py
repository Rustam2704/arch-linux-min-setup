"""org.freedesktop.ScreenSaver for a session without a screensaver daemon.

Firefox, Zoom, Telegram and the desktop portal ask this name to keep the screen on
while a video or a call is running. Nothing owned it here (no xfce4-screensaver, no
light-locker), so every such request failed and the screen went black after the
power manager's timeout in the middle of a call. This is a thin proxy: Inhibit and
UnInhibit are forwarded to xfce4-power-manager's own interface,
org.freedesktop.PowerManagement.Inhibit, which holds DPMS off while a cookie is out.
A client that vanishes from the bus takes its inhibits with it.

Two things keep this from looping: the power manager, on every Inhibit it gets, asks
org.freedesktop.ScreenSaver (through libxfce4ui) to inhibit as well - that request
comes back here and is answered with a cookie *without* forwarding (the first
version forwarded it, and xfce4-power-manager ended up with a permanent "libxfce4ui"
inhibit of its own making: DPMS off for good). And the forwarding is asynchronous,
so this process never blocks its main loop waiting for the power manager while the
power manager waits for it.

Hosted by osd-daemon (it already lives in the session with a GLib loop): `start()`.
"""
from gi.repository import Gio, GLib

NAME = "org.freedesktop.ScreenSaver"
PATHS = ("/org/freedesktop/ScreenSaver", "/ScreenSaver")      # both spellings are in use
XFPM = ("org.freedesktop.PowerManagement", "/org/freedesktop/PowerManagement/Inhibit",
        "org.freedesktop.PowerManagement.Inhibit")
XML = """
<node>
  <interface name="org.freedesktop.ScreenSaver">
    <method name="Inhibit"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="out"/></method>
    <method name="UnInhibit"><arg type="u" direction="in"/></method>
    <method name="GetActive"><arg type="b" direction="out"/></method>
    <method name="GetActiveTime"><arg type="u" direction="out"/></method>
    <method name="GetSessionIdleTime"><arg type="u" direction="out"/></method>
    <method name="SetActive"><arg type="b" direction="in"/><arg type="b" direction="out"/></method>
    <method name="SimulateUserActivity"/>
    <method name="Lock"/>
    <method name="Throttle"><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="u" direction="out"/></method>
    <method name="UnThrottle"><arg type="u" direction="in"/></method>
  </interface>
</node>
"""


def log(*a):
    print("screensaver:", *a, flush=True)


class ScreenSaver:
    def __init__(self):
        self.bus = None
        self.cookies = {}          # our cookie -> (power manager's cookie or None, sender)
        self.watches = {}          # sender -> name watch id
        self.next = 1

    def start(self):
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        Gio.bus_own_name(Gio.BusType.SESSION, NAME, Gio.BusNameOwnerFlags.NONE,
                         lambda bus, name: self._acquired(bus, info), None,
                         lambda bus, name: log("name lost", name))

    def _acquired(self, bus, info):
        self.bus = bus
        for path in PATHS:
            bus.register_object(path, info.interfaces[0], self._call, None, None)

    def _call(self, bus, sender, path, iface, method, params, invocation):
        if method == "Inhibit":
            app, reason = params.unpack()
            self._inhibit(sender, app, reason, invocation)
        elif method == "UnInhibit":
            self._uninhibit(params.unpack()[0])
            invocation.return_value(None)
        elif method == "GetActive":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method in ("GetActiveTime", "GetSessionIdleTime"):
            invocation.return_value(GLib.Variant("(u)", (0,)))
        elif method == "SetActive":
            invocation.return_value(GLib.Variant("(b)", (False,)))
        elif method == "Throttle":
            invocation.return_value(GLib.Variant("(u)", (0,)))
        else:                                       # SimulateUserActivity, Lock, UnThrottle
            invocation.return_value(None)

    def _power_manager(self):
        """The unique bus name of xfce4-power-manager right now (None when it is not up)."""
        try:
            reply = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                       "GetNameOwner", GLib.Variant("(s)", (XFPM[0],)), GLib.VariantType("(s)"),
                                       Gio.DBusCallFlags.NONE, 500, None)
            return reply.unpack()[0]
        except GLib.Error:
            return None

    def _inhibit(self, sender, app, reason, invocation):
        cookie, self.next = self.next, self.next + 1
        if sender == self._power_manager():
            # the power manager inhibiting "the screensaver" because someone inhibited
            # it: it already holds DPMS off, there is nothing more to do
            self.cookies[cookie] = (None, sender)
            invocation.return_value(GLib.Variant("(u)", (cookie,)))
            return

        def done(bus, result):
            try:
                pm_cookie = bus.call_finish(result).unpack()[0]
            except GLib.Error as e:
                log("power manager refused", app, "-", e)
                invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(e))
                return
            first = not any(c is not None for c, _ in self.cookies.values())
            self.cookies[cookie] = (pm_cookie, sender)
            if sender not in self.watches:
                self.watches[sender] = Gio.bus_watch_name_on_connection(
                    self.bus, sender, Gio.BusNameWatcherFlags.NONE, None, self._vanished)
            if first:
                log("inhibited", app, "-", reason)
            invocation.return_value(GLib.Variant("(u)", (cookie,)))

        self.bus.call(XFPM[0], XFPM[1], XFPM[2], "Inhibit", GLib.Variant("(ss)", (app, reason)),
                      GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 2000, None, done)

    def _uninhibit(self, cookie):
        pm_cookie, sender = self.cookies.pop(cookie, (None, None))
        if pm_cookie is not None:
            self.bus.call(XFPM[0], XFPM[1], XFPM[2], "UnInhibit", GLib.Variant("(u)", (pm_cookie,)),
                          None, Gio.DBusCallFlags.NONE, 2000, None, self._uninhibited)
            if not any(c is not None for c, _ in self.cookies.values()):
                log("uninhibited")
        if sender and sender in self.watches and all(s != sender for _, s in self.cookies.values()):
            Gio.bus_unwatch_name(self.watches.pop(sender))

    def _uninhibited(self, bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error as e:
            log("uninhibit failed:", e)

    def _vanished(self, bus, name):
        for cookie, (_, sender) in list(self.cookies.items()):
            if sender == name:
                self._uninhibit(cookie)


def start():
    ScreenSaver().start()
