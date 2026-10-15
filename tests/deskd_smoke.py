#!/usr/bin/env python3
"""deskd smoke run on a nested X server: never on the user's screen.

    make test-deskd            (or: python3 tests/deskd_smoke.py [--keep])

Starts Xephyr :9, an i3 with the installed config (minus exec/include lines) and the
source deskd with its own XDG_RUNTIME_DIR, opens kitty windows and drives them with
xdotool and deskd's own tick commands. Checks the window engine end to end: maximize,
drag away from the top (the window must not stay glued to the panel edge), drop at the
left edge and in a corner, restore, minimize and back, a second window of the same app,
Alt+Tab (with Alt held: the switcher, the switch on release), keep-above, Super+arrows,
magnetic edges, a screen size change (RANDR) with a maximized window, and a window
that opens full screen. A synthetic dock checks panel veil teardown and recreation.
Units of the daemon that need no screen (layers, error log, Alt+Tab list, state sweeps ...)
run first on mock objects.

Timing: nothing waits a fixed time for a state it can poll. deskd is started and waited for
until it prints its "running" marker; checks that depend on the daemon catching up poll with
a deadline. A failed check prints a diagnostic dump (deskd log tail, X stack, i3 focus).

The Xephyr window is moved to workspace 9 of the real i3 the moment it appears, so the
user's workspace is not covered. Run time ~20 s. Exit code 1 on the first failed check.
"""
import atexit
import json
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Xlib import X as XX, display as xdisplay
from Xlib import Xatom
from Xlib import error as xerror
from Xlib.protocol import event as xevent

DISPLAY = ":9"
SIZE = (1600, 1000)
HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".config/i3/config")
SOURCE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DESKD = os.path.join(SOURCE, "desktop/share/deskd/deskd.py")
KEEP = "--keep" in sys.argv

tmp = tempfile.mkdtemp(prefix="deskd-smoke-")
run_dir = os.path.join(tmp, "run")
os.makedirs(run_dir)
env = dict(os.environ, DISPLAY=DISPLAY, XDG_RUNTIME_DIR=run_dir, DESKD_NO_PANELS="1")
env["PYTHONPATH"] = os.path.join(SOURCE, "desktop/share/sky-desktop") + os.pathsep + env.get("PYTHONPATH", "")
env.pop("I3SOCK", None)          # inherited from the real session: everything would talk to the real i3
real_sock = os.environ.get("I3SOCK") or subprocess.run(["i3", "--get-socketpath"], capture_output=True,
                                                         text=True).stdout.strip()
procs = []
failed = []
deskd_log_path = None


def say(*a):
    print("smoke:", *a, flush=True)


def check(name, ok, detail=""):
    say(("ok  " if ok else "FAIL"), name, detail)
    if not ok:
        failed.append(name)
        diagnose(name)
        if not KEEP:
            finish(1)


def wait_until(predicate, timeout=3.0, step=0.05):
    """Poll `predicate` until it is true or the deadline passes; True if it became true."""
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(step)


def diagnose(why):
    """What a failed check needs to be understood: the daemon's log, the top of the X stack
    (frames, our overlays, the panel), i3's focus. Best effort - never raises."""
    say("diagnostic dump for:", why)
    try:
        if deskd_log_path:
            with open(deskd_log_path) as f:
                tail = f.read().splitlines()[-25:]
            print("smoke: deskd.log tail:", *tail, sep="\n    ", flush=True)
    except OSError:
        pass
    try:
        rows = []
        for w in xconn().screen().root.query_tree().children[-14:]:
            try:
                cls = (w.get_wm_class() or ("", ""))[0]
                g = w.get_geometry()
                rows.append(f"{w.id:#x} {cls or '-'} {g.width}x{g.height}+{g.x}+{g.y} "
                            f"map={w.get_attributes().map_state}")
            except Exception:
                rows.append(f"{w.id:#x} (gone)")
        print("smoke: X stack, top last:", *rows, sep="\n    ", flush=True)
        say("i3 focused window:", focused_id())
    except Exception as e:
        say("no X dump:", e)


def reap():
    """Whatever is still running of what this run started - also after a crash of the script."""
    for p in reversed(procs):
        try:
            p.terminate()
        except OSError:
            pass
    time.sleep(0.3)
    for p in reversed(procs):
        try:
            p.kill()
        except OSError:
            pass


atexit.register(reap)


def finish(code):
    for p in reversed(procs):
        try:
            p.terminate()
        except OSError:
            pass
    time.sleep(0.5)
    for p in reversed(procs):
        try:
            p.kill()
        except OSError:
            pass
    if not KEEP:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        say("kept", tmp)
    sys.exit(code)


def msg(cmd):
    out = subprocess.run(["i3-msg", "-q", cmd], env=env, capture_output=True, text=True)
    return out.returncode == 0


def tick(cmd):
    subprocess.run(["i3-msg", "-q", "-t", "send_tick", "deskd " + cmd], env=env, capture_output=True)


def tree():
    return json.loads(subprocess.run(["i3-msg", "-t", "get_tree"], env=env, capture_output=True, text=True).stdout)


def walk(n, ws=None, parent=None):
    if n.get("type") == "workspace":
        ws = n["name"]
    yield n, ws, parent
    for k in ("nodes", "floating_nodes"):
        for c in n.get(k, []):
            yield from walk(c, ws, n)


def windows():
    """[(node, workspace, frame rect)] of the test windows."""
    out = []
    for n, ws, p in walk(tree()):
        if n.get("window") and (n.get("window_properties") or {}).get("class") == "smoke":
            frame = p["rect"] if p and p.get("type") == "floating_con" else n["rect"]
            out.append((n, ws, frame))
    return out


def window(cid):
    for n, ws, frame in windows():
        if n["id"] == cid:
            return n, ws, frame
    return None, None, None


def wait_windows(count, timeout=8):
    t0 = time.time()
    while time.time() - t0 < timeout:
        w = windows()
        if len(w) >= count:
            time.sleep(0.4)          # let deskd place it
            return windows()
        time.sleep(0.1)
    return windows()


def xdo(*args):
    subprocess.run(["xdotool", *args], env=env, check=False)


def drag(cid, to_x, to_y, steps=12):
    """Press the title bar of window cid and pull it to (to_x, to_y); the button stays down."""
    n, _, frame = window(cid)
    deco = n["deco_rect"]["height"] or 30
    x0, y0 = frame["x"] + frame["width"] // 2, frame["y"] + deco // 2
    xdo("mousemove", str(x0), str(y0))
    time.sleep(0.1)
    xdo("mousedown", "1")
    time.sleep(0.15)
    for i in range(1, steps + 1):
        x = x0 + (to_x - x0) * i // steps
        y = y0 + (to_y - y0) * i // steps
        xdo("mousemove", str(x), str(y))
        time.sleep(0.05)
    time.sleep(0.3)


def release():
    xdo("mouseup", "1")
    time.sleep(0.5)


def marks(n):
    return n.get("marks") or []


_xd = []


def xconn():
    if not _xd:
        _xd.append(xdisplay.Display(DISPLAY))
    return _xd[0]


def frame_of(n):
    return xconn().create_resource_object("window", n["window"]).query_tree().parent


def frame_rect(n):
    """Where the window really is on the nested screen (its i3 frame), not i3's idea."""
    g = frame_of(n).get_geometry()
    return {"x": g.x, "y": g.y, "width": g.width, "height": g.height}


def set_state(n, action, atom):
    """An EWMH _NET_WM_STATE request from the window, as an app would send it."""
    d = xconn()
    e = xevent.ClientMessage(window=d.create_resource_object("window", n["window"]),
                             client_type=d.intern_atom("_NET_WM_STATE"),
                             data=(32, [action, d.intern_atom(atom), 0, 1, 0]))
    d.screen().root.send_event(e, event_mask=XX.SubstructureRedirectMask | XX.SubstructureNotifyMask)
    d.flush()


def switcher_shown():
    for w in xconn().screen().root.query_tree().children:
        try:
            if (w.get_wm_class() or ("",))[0] == "deskd-switcher":
                return w.get_attributes().map_state == XX.IsViewable
        except Exception:
            pass
    return False


def focused_id():
    return next((n["id"] for n, _, _ in windows() if n.get("focused")), None)


# Exercise the one-shot GLib scheduling contract without starting a second daemon.
sys.path.insert(0, os.path.join(SOURCE, "desktop/share/sky-desktop"))
spec = importlib.util.spec_from_file_location("deskd_under_test", DESKD)
deskd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deskd)
unit = deskd.Deskd.__new__(deskd.Deskd)
unit.drag = unit.resizing = None
unit.panel_dirty = False
unit.recheck_pending = None
unit._panel_props = None
unit.click_layers = {}
unit.strip_geoms = {}
unit.panel_windows = set()
unit.bounds_cache = {}
unit.xs = SimpleNamespace(gc_cache={})
unit.strip_plugins = Mock(side_effect=lambda fresh=False: setattr(unit, "_strips", [(45, None)]))
unit.watch_panel_items = Mock()
unit.place_ws_clicks = Mock()
queued = []


def queue_recheck(callback):
    queued.append(callback)
    return len(queued)


with patch.object(deskd.GLib, "idle_add", side_effect=queue_recheck), \
        patch.object(deskd.panels, "read_all", return_value={"panel": "ready"}) as read_panel:
    unit.schedule_recheck()
    unit.schedule_recheck()
    check("panel rechecks coalesce", len(queued) == 1, str(len(queued)))
    result = queued.pop()()
    check("panel recheck runs once", result is False and read_panel.call_count == 1 and
          unit.recheck_pending is None, str((result, read_panel.call_count)))
    check("panel recheck rebuilds strip and click layer",
          unit.strip_plugins.call_args.kwargs == {"fresh": True} and
          unit.watch_panel_items.call_count == 1 and unit.place_ws_clicks.call_count == 1)

click_layer = SimpleNamespace(id=42, configure=Mock())
unit.click_layers = {1: click_layer}
unit.layer_visible = {42: True}
unit.raise_click_layers()
check("mapped workspace layer is re-raised", click_layer.configure.call_count == 1 and
      click_layer.configure.call_args.kwargs == {"stack_mode": deskd.X.Above})
unit.items_by_output = {"primary": ([("1", 1)], [("1", "markup")])}
unit.strip_output = lambda out: "primary"
unit.plugin_geometry = lambda pid: (10, 20, 100, 30)
unit.measure = lambda geom, plains, tail: [(10, 20)]
check("workspace hit area falls back after panel restart",
      unit.strip_view(1, None)[0] == (10, 20, 100, 30))


# ------------------------------------------------------------------ units on mock objects (no screen needed)
def new_deskd():
    """A Deskd with only what the unit under test touches."""
    u = deskd.Deskd.__new__(deskd.Deskd)
    u.drag = u.resizing = None
    u.sharing = False
    u.busy_outputs = set()
    u.layer_visible = {}
    u.click_layers, u.click_layouts, u.click_by_win, u.strip_geoms = {}, {}, {}, {}
    u.audio_layers, u.audio_geoms = {}, {}
    u.strips, u.strip_by_win, u.frames = {}, {}, {}
    u.xs = SimpleNamespace(gc_cache={}, cursors={"hand": 1}, d=Mock(), root=SimpleNamespace(id=1))
    return u


def fake_layer(wid):
    return SimpleNamespace(id=wid, map=Mock(), unmap=Mock(), configure=Mock(), destroy=Mock())


def x_error(cls, major=12, minor=0, resource=0x1234):
    err = cls.__new__(cls)
    err._data = {"major_opcode": major, "minor_opcode": minor, "resource_id": resource}
    return err


# A6: the X error handler drops the races and tells the journal about the rest, rate limited
clock, lines = [100.0], []
errlog = deskd.XErrorLog()
with patch.object(deskd, "time", SimpleNamespace(monotonic=lambda: clock[0])), \
        patch.object(deskd, "log", side_effect=lambda *a: lines.append(a)):
    errlog(x_error(xerror.BadWindow), None)
    errlog(x_error(xerror.BadDrawable), None)
    errlog(x_error(xerror.BadMatch), None)
    errlog(x_error(xerror.BadMatch), None)                 # the same one again within a minute
    errlog(x_error(xerror.BadMatch, major=72), None)       # another request: its own line
    clock[0] += 61
    errlog(x_error(xerror.BadMatch), None)                 # a minute on: again, with what was dropped
check("X errors: races dropped, the rest logged once per request and error a minute",
      len(lines) == 3 and "1 like it dropped" in " ".join(map(str, lines[2])), str(lines))

# A7: a panel plugin that is gone for now must not leave its layer mapped over the screen
u = new_deskd()
layer = fake_layer(7)
u.click_layers, u.layer_visible = {45: layer}, {7: True}
u.strip_plugins = lambda fresh=False: [(45, None)]
u.strip_output = lambda out: "primary"
u.plugin_geometry = lambda pid: None
u.sync_active_mark, u.pump, u.last_focused_ws = Mock(), Mock(), None
u.place_ws_clicks()
check("a strip that left the panel unmaps its click layer", layer.unmap.call_count == 1 and
      u.layer_visible[7] is False)
u.plugin_geometry = lambda pid: (10, 20, 100, 30)
u.place_ws_clicks()
check("... and the layer returns with the strip", layer.map.call_count == 1 and u.layer_visible[7] is True)
u.sharing = True                                            # A9: no layer of ours while Zoom shares
u.place_ws_clicks()
check("a click layer stays unmapped while the screen is shared", u.layer_visible[7] is False)
u.sharing = False
audio = fake_layer(8)
u.audio_layers, u.audio_geoms, u.layer_visible[8] = {9: audio}, {9: (0, 0, 10, 10)}, True
u._panel_props = {"/plugins/plugin-9/command": "/usr/bin/panel-audio"}
u.plugin_geometry = lambda pid: None
u.place_audio_layer()
check("a sound indicator that left the panel unmaps its layer", audio.unmap.call_count == 1 and
      u.layer_visible[8] is False and 9 not in u.audio_geoms)
u._panel_props = {}
u.place_audio_layer()
check("A8: the layer of a panel that went away is destroyed and forgotten",
      audio.destroy.call_count == 1 and 8 not in u.layer_visible and 9 not in u.audio_layers)
u = new_deskd()
shown, shown_audio = fake_layer(11), fake_layer(12)
u.click_layers, u.audio_layers = {1: shown}, {2: shown_audio}
u.layer_visible = {11: True, 12: True}
u.veils, u.ws_mark = {}, None
u.set_sharing(True)
check("starting a screen share unmaps the click and sound layers", u.layer_visible == {11: False, 12: False})


# A2: Alt+Tab never lists a notification; a focused one is no starting point either
def leaf(i, wtype="normal", focused=False):
    return {"id": i, "type": "con", "window": 1000 + i, "window_type": wtype, "name": f"w{i}",
            "focused": focused, "marks": [], "nodes": [], "floating_nodes": []}


def floating(i, **kw):
    return {"id": 500 + i, "type": "floating_con", "nodes": [leaf(i, **kw)], "floating_nodes": [], "marks": []}


def tree_of(*cons):
    ws = {"id": 9003, "type": "workspace", "name": "1", "num": 1, "marks": [], "nodes": [],
          "floating_nodes": list(cons), "rect": {"x": 0, "y": 0, "width": 800, "height": 600}}
    return {"id": 9000, "type": "root", "marks": [], "floating_nodes": [], "nodes": [
        {"id": 9001, "type": "output", "marks": [], "floating_nodes": [], "nodes": [
            {"id": 9002, "type": "con", "marks": [], "floating_nodes": [], "nodes": [ws]}]}]}


u = new_deskd()
u.alt_tab, u.focus_order, u.switcher, u.state = None, [3, 2, 1], Mock(), {}
with patch.object(deskd.GLib, "timeout_add"):
    u.cycle(tree_of(floating(1), floating(2), floating(3, wtype="notification", focused=True)), 1)
    ids = [e[0] for e in u.alt_tab["order"]]
    check("Alt+Tab lists no notification, and a focused one starts the walk at the last used window",
          ids == [2, 1] and u.alt_tab["idx"] == 0, str((ids, u.alt_tab["idx"])))
    u.alt_tab = None
    u.cycle(tree_of(floating(1), floating(2, focused=True), floating(3, wtype="notification")), 1)
    ids = [e[0] for e in u.alt_tab["order"]]
    check("Alt+Tab from a normal window skips the notification too", sorted(ids) == [1, 2] and
          u.alt_tab["idx"] == 1, str((ids, u.alt_tab["idx"])))

# A3: a round does not outlive the workspace it was built for
u.schedule_refresh, u.pump, u.workspace_event_at = Mock(), Mock(), 0.0
u.on_i3("workspace", {"change": "init"})
check("a new workspace leaves the round alone", u.alt_tab is not None)
u.on_i3("workspace", {"change": "focus"})
check("switching workspace with Alt held cancels the round", u.alt_tab is None and
      u.switcher.hide.call_count == 1)

# A4: a frame event dropped right after a workspace switch is not lost for a window deskd holds
u = new_deskd()
u.monitors, u.panel_windows, u.veils = SimpleNamespace(is_randr=lambda e: False), set(), {}
u.guarded_frames, u.debounce_timer = {100}, None
u.workspace_event_at = time.monotonic()
u.schedule_refresh = Mock()
with patch.object(deskd.GLib, "timeout_add", return_value=77) as later:
    u.handle_x(SimpleNamespace(type=deskd.X.ConfigureNotify, window=SimpleNamespace(id=100)))
    u.handle_x(SimpleNamespace(type=deskd.X.ConfigureNotify, window=SimpleNamespace(id=100)))
    u.handle_x(SimpleNamespace(type=deskd.X.ConfigureNotify, window=SimpleNamespace(id=101)))
check("a held frame's configure inside the workspace debounce books one refresh for its end",
      later.call_count == 1 and later.call_args.args[0] <= 205 and u.debounce_timer == 77 and
      u.schedule_refresh.call_count == 0, str(later.call_args))
u.debounce_over()
check("... which refreshes once", u.debounce_timer is None and u.schedule_refresh.call_count == 1)

# A5: the frame cached for a client follows what i3 does
u = new_deskd()
old_frame = SimpleNamespace(id=100)
strip = SimpleNamespace(win=SimpleNamespace(id=300), frame=old_frame, destroy=Mock())
u.frames, u.strips, u.strip_by_win = {7: (old_frame, 32)}, {70: strip}, {300: 70}
parent = u.xs.d.create_resource_object.return_value.query_tree.return_value
parent.parent = SimpleNamespace(id=100)
u.recheck_frame({"window": 7, "id": 70})
check("a client still in its frame keeps the cache and its buttons", 7 in u.frames and 70 in u.strips)
parent.parent = SimpleNamespace(id=200)
u.recheck_frame({"window": 7, "id": 70})
check("a client reparented by i3 loses the cached frame and the buttons drawn on the old one",
      7 not in u.frames and 70 not in u.strips and strip.destroy.call_count == 1)
u.frames, u.strips, u.strip_by_win = {7: (old_frame, 32)}, {70: strip}, {300: 70}
u.monitors, u.panel_windows, u.veils = SimpleNamespace(is_randr=lambda e: False), set(), {}
u.handle_x(SimpleNamespace(type=deskd.X.DestroyNotify, window=SimpleNamespace(id=100)))
check("the destruction of a frame under a live client drops it from the cache",
      7 not in u.frames and 70 not in u.strips)
parent.parent = SimpleNamespace(id=1)               # the root: no frame at all
check("a client whose parent is the root has no frame", u.frame_of(8) is None and 8 not in u.frames)

# A10: a screen event in the middle of a gesture waits for its end
u = new_deskd()
u.outputs_pending, u.outputs_sorted = False, Mock(return_value=[])
for gesture in ("drag", "resizing"):
    setattr(u, gesture, {"con": 1})
    result = u.outputs_changed()
    check(f"a screen event during a {gesture} is held back", result is False and u.outputs_pending and
          u.outputs_sorted.call_count == 0)
    with patch.object(deskd.GLib, "timeout_add") as later:
        setattr(u, gesture, None)
        u.gesture_ended()
    check(f"... and replayed when the {gesture} is over", later.call_count == 1 and
          later.call_args.args[1] == u.outputs_changed and not u.outputs_pending)
    u.outputs_pending = False

# A11: retained ids and classes are pruned
u = new_deskd()
u.i3, u.schedule_refresh = SimpleNamespace(tree=lambda: {"id": 1}), Mock()
u.expect = {"stale": (1, time.monotonic() - 100), "recent": (2, time.monotonic())}
u.command(["expect", "kitty", "3"])
check("an unmatched launch request expires when the next one is made", set(u.expect) == {"recent", "kitty"})
now = time.monotonic()
u._held, u.frames, u.above, u.guarded_frames = {5: [now - 10], 6: [now]}, {}, set(), set()
u.hold_fitted({"id": 1, "nodes": [], "floating_nodes": []}, [])
check("fit corrections older than 3 s are dropped from the rate limiter", list(u._held) == [6])
u = new_deskd()
u.state = {"windows": {"1": {"mode": "floating"}, "77": {"mode": "floating"}}}
u.i3, u.save_state = SimpleNamespace(tree=lambda: tree_of(floating(1))), Mock()
u.sweep_saved()
check("saved places of windows that closed while deskd was down are swept at start",
      list(u.state["windows"]) == ["1"] and u.save_state.call_count == 1)

# A12: ten remembered output names do not exhaust the workspace blocks
u = new_deskd()
u.blocks = {f"o{i}": i for i in range(10)}
u.outputs = lambda: [{"name": "o0", "active": True}]
u.i3 = SimpleNamespace(workspaces=lambda: [{"num": 11}, {"num": 1}])
u.save_state = Mock()
got = u.block_for("new")
check("a block is taken back from a gone screen without workspaces", got == 2 and "o2" not in u.blocks and
      u.blocks["new"] == 2 and u.blocks["o0"] == 0 and u.blocks["o1"] == 1, str((got, u.blocks)))

# A13: a refresh that fails halfway leaves no stale screens behind
u = new_deskd()
u.refresh_pending = u.refresh_deferred = False
u._refresh_outputs = None
u.i3 = SimpleNamespace(tree=lambda: {}, workspaces=lambda: [], outputs=lambda: [{"name": "x"}])
u.render_workspaces = Mock(side_effect=RuntimeError("boom"))
with patch.object(deskd, "log"):
    failed_refresh = u.refresh()
check("a failing refresh returns False and forgets its snapshot of the screens",
      failed_refresh is False and u._refresh_outputs is None)

# K1: three-finger swipe: the strip's neighbour, empty workspaces included, stops at the ends
u = new_deskd()
u.blocks, u.save_state = {"eDP1": 0}, Mock()


def workspaces_with(focused, extra=()):
    return [{"num": n, "name": str(n), "output": "eDP1", "focused": n == focused}
            for n in sorted({focused, *extra})]


def step_from(focused, step, extra=()):
    u.i3 = SimpleNamespace(workspaces=lambda: workspaces_with(focused, extra))
    return u.step_ws(step)


check("ws next/prev walk the strip, empty workspaces included",
      (step_from(1, 1), step_from(3, -1), step_from(6, -1)) == (2, 2, 5))
check("ws next/prev stop at the ends, and take in 7..9 once they exist",
      (step_from(1, -1), step_from(6, 1), step_from(6, 1, extra=(7,)), step_from(7, 1, extra=(7,))) ==
      (None, None, 7, None))


# ------------------------------------------------------------------ start everything
say("display", DISPLAY, "runtime", run_dir)


def display_alive():
    try:
        xdisplay.Display(DISPLAY).close()
        return True
    except Exception:
        return False


# the server of a run that just ended can still be shutting down: it is not ours to talk to
if not wait_until(lambda: not display_alive(), 8):
    say("refusing to run: display", DISPLAY, "is in use")
    finish(1)
procs.append(subprocess.Popen(["Xephyr", DISPLAY, "-screen", f"{SIZE[0]}x{SIZE[1]}", "-resizeable",
                               "-nolisten", "tcp", "-name", "deskd-smoke"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
if not wait_until(lambda: display_alive() or procs[0].poll() is not None, 10, 0.1):
    say("Xephyr did not come up")
    finish(1)
check("Xephyr running", procs[0].poll() is None)
time.sleep(0.5)                  # its window reaches the real screen's i3
# out of the user's way: the nested screen lives on workspace 9 of the real i3
subprocess.run(["i3-msg", "-q", '[class="Xephyr"] move container to workspace number 9'],
               capture_output=True)

cfg = os.path.join(tmp, "i3.conf")
with open(CONFIG) as src, open(cfg, "w") as dst:
    for line in src:
        s = line.strip()
        if s.startswith(("exec ", "exec_always ", "include ")):
            continue
        dst.write(line)
procs.append(subprocess.Popen(["i3", "-c", cfg], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
for _ in range(50):
    if msg("nop"):
        break
    time.sleep(0.1)
nested_sock = subprocess.run(["i3", "--get-socketpath"], env=env, capture_output=True, text=True).stdout.strip()
if not nested_sock or nested_sock == real_sock:
    say("refusing to run: the nested i3 socket is the real one", nested_sock)
    finish(1)
deskd_log_path = os.path.join(tmp, "deskd.log")
log = open(deskd_log_path, "w")
procs.append(subprocess.Popen([sys.executable, DESKD], env=env, stdout=log, stderr=subprocess.STDOUT))


def deskd_ready():
    """deskd prints "running" when its start-up is done: the root events are being read,
    the panel watcher is armed. A window mapped before that is not seen by the event path."""
    with open(deskd_log_path) as f:
        return "deskd: running" in f.read()


ready = wait_until(lambda: deskd_ready() or procs[-1].poll() is not None, 15, 0.1)
check("deskd running", ready and procs[-1].poll() is None, "see " + log.name)

# T1: the resize-handle cursors are the theme's (libXcursor, at Xcursor.size), not core-font bitmaps
saved_display = os.environ.get("DISPLAY")
os.environ["DISPLAY"] = DISPLAY                  # XServer() connects to $DISPLAY: the nested one, never :0
try:
    probe = deskd.XServer()
    themed = {name: isinstance(probe.cursors[name], int) for name in deskd.THEMED_CURSORS}
    check("resize-handle cursors come from the Xcursor theme", all(themed.values()) and
          set(probe.cursors) == set(deskd.GLYPH_CURSORS), str(themed))
    probe.d.close()
finally:
    if saved_display is None:
        os.environ.pop("DISPLAY", None)
    else:
        os.environ["DISPLAY"] = saved_display

# Synthetic docks need neither the host panel nor xfconf. Exercise both a dock
# outside i3 and one framed by i3, including immediate X window ID reuse.
def fake_panel(managed=False):
    d = xconn()
    win = d.screen().root.create_window(0, 0, SIZE[0], 50, 0, d.screen().root_depth,
                                        XX.InputOutput, XX.CopyFromParent,
                                        override_redirect=not managed, background_pixel=0)
    win.set_wm_class("xfce4-panel", "Xfce4-panel")
    win.change_property(d.intern_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM, 32,
                        [d.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
    win.map()
    d.flush()
    return win


def veil_ids():
    found = set()
    for win in xconn().screen().root.query_tree().children:
        try:
            if (win.get_wm_class() or (None,))[0] == "deskd" and win.get_geometry().height == 50:
                found.add(win.id)
        except Exception:
            pass
    return found


def wait_veils(expected, timeout=1.0, old=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        got = veil_ids()
        if len(got) == expected and (old is None or got != old):
            return got
        time.sleep(0.03)
    return veil_ids()


first_panel = fake_panel()
t_first = time.monotonic()
first_veil = wait_veils(1, timeout=3.0)          # the cold path: the first veil loads Pango and Cairo
check("dock map creates the first panel veil within 3 s", len(first_veil) == 1,
      f"{time.monotonic() - t_first:.2f} s")
first_panel.destroy()
xconn().flush()
check("dock destroy removes panel veil within 1 s", not wait_veils(0))
second_panel = fake_panel()
second_veil = wait_veils(1)
check("panel quit and start recreates veil within 1 s", len(second_veil) == 1 and
      second_veil != first_veil)
second_panel.destroy()
third_panel = fake_panel()       # xfce4-panel -r can replace the dock without a long gap
third_veil = wait_veils(1, old=second_veil)
check("panel -r replaces veil within 1 s", len(third_veil) == 1 and
      third_veil != second_veil, f"old={second_veil} new={third_veil}")
third_panel.destroy()
xconn().flush()
check("replacement dock cleanup removes veil", not wait_veils(0))
dock_events = deskd.i3ipc.subscribe(["window"], nested_sock)
dock_events.settimeout(0.2)
managed_panel = fake_panel(managed=True)
check("i3 framed dock creates panel veil within 1 s", len(wait_veils(1)) == 1)
managed_panel.destroy()
xconn().flush()
check("i3 framed dock cleanup removes veil", not wait_veils(0))
data = b""
try:
    while True:
        chunk = dock_events.recv(65536)
        if not chunk:
            break
        data += chunk
except TimeoutError:
    pass
dock_events.close()
events, _ = deskd.i3ipc.decode(data)
say("i3 dock window events", [(name, ev.get("change"),
                               (ev.get("container") or {}).get("window_type"),
                               ((ev.get("container") or {}).get("window_properties") or {}).get("class"))
                              for name, ev in events])

area = {"x": 0, "y": 0, "width": SIZE[0], "height": SIZE[1]}      # no panel: the whole screen


def focused_workspace():
    got = json.loads(subprocess.run(["i3-msg", "-t", "get_workspaces"], env=env, capture_output=True,
                                    text=True).stdout)
    return next((w["name"] for w in got if w["focused"]), None)


# ------------------------------------------------------------------ 0. workspace swipe: next / prev, empty ones included
# (three fingers: i3's own next_on_output skipped the empty workspaces the panel strip shows)
tick("ws next")
check("ws next goes to the next workspace of the strip, empty or not",
      wait_until(lambda: focused_workspace() == "2", 2), str(focused_workspace()))
tick("ws prev")
check("ws prev goes back", wait_until(lambda: focused_workspace() == "1", 2), str(focused_workspace()))
tick("ws prev")
time.sleep(0.4)
check("ws prev at the first workspace stays (Windows does not wrap)", focused_workspace() == "1",
      str(focused_workspace()))
tick("ws 3")
check("ws N still works", wait_until(lambda: focused_workspace() == "3", 2), str(focused_workspace()))
tick("ws 1")
check("back on workspace 1", wait_until(lambda: focused_workspace() == "1", 2), str(focused_workspace()))


def fills(frame, rect):
    return all(abs(frame[k] - rect[k]) <= 2 for k in ("x", "y", "width", "height"))


# ------------------------------------------------------------------ 1. a new window floats
procs.append(subprocess.Popen(["kitty", "--class", "smoke", "--title", "smoke-1", "-o", "initial_window_width=700",
                               "-o", "initial_window_height=500"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
w = wait_windows(1)
check("window opened", len(w) == 1)
n1, ws1, f1 = w[0]
cid = n1["id"]
check("floats", ws1 == "1" and f1["width"] < area["width"], json.dumps(f1))
inside = f1["x"] >= 0 and f1["y"] >= 0 and f1["x"] + f1["width"] <= area["width"] and f1["y"] + f1["height"] <= area["height"]
check("inside the screen", inside, json.dumps(f1))
plain = dict(f1)

# ------------------------------------------------------------------ 2. maximize (Super+Up)
msg(f"[con_id={cid}] focus")
tick("key up")
time.sleep(0.6)
n, _, f = window(cid)
check("maximized fills the work area", fills(f, area) and any(m.startswith("_deskd_max") for m in marks(n)),
      json.dumps(f) + " " + str(marks(n)))

# ------------------------------------------------------------------ 3. drag it away from the top edge
drag(cid, 800, 600)
n, _, _ = window(cid)
f = frame_rect(n)                     # mid-drag only the X frame moves; i3 hears it on release
check("dragged window leaves the top edge (W1)", f["y"] > 150, f"y={f['y']} h={f['height']}")
check("dragged window has its old size back", abs(f["width"] - plain["width"]) <= 4 and abs(f["height"] - plain["height"]) <= 4,
      json.dumps(f))
release()
n, _, f = window(cid)
check("dropped in the open: stays there, not fitted", f["y"] > 150 and not any(m.startswith("_deskd_") for m in marks(n)),
      json.dumps(f) + " " + str(marks(n)))
check("i3 and the screen agree on where it was dropped", fills(frame_rect(n), f), json.dumps(frame_rect(n)) + " vs " + json.dumps(f))
before_snap = dict(f)

# ------------------------------------------------------------------ 4. drop at the left edge = left half
drag(cid, 2, 500)
release()
n, _, f = window(cid)
half = {"x": 0, "y": 0, "width": area["width"] // 2, "height": area["height"]}
check("left edge drop snaps to the left half", fills(f, half) and "_deskd_snapleft_%d" % cid in marks(n),
      json.dumps(f) + " " + str(marks(n)))

# ------------------------------------------------------------------ 4b. a corner = a quarter
drag(cid, 2, SIZE[1] - 2)
release()
n, _, f = window(cid)
quarter = {"x": 0, "y": area["height"] - area["height"] // 2, "width": area["width"] // 2, "height": area["height"] // 2}
check("bottom-left corner drop snaps to that quarter", fills(f, quarter) and "_deskd_snapbl_%d" % cid in marks(n),
      json.dumps(f) + " " + str(marks(n)))

# ------------------------------------------------------------------ 5. quarter -> half -> restore (Super+Up, Super+Right)
msg(f"[con_id={cid}] focus")
tick("key up")
time.sleep(0.6)
n, _, f = window(cid)
check("Super+Up on the bottom-left quarter gives the left half", fills(f, half) and "_deskd_snapleft_%d" % cid in marks(n),
      json.dumps(f) + " " + str(marks(n)))
tick("key right")
time.sleep(0.6)
n, _, f = window(cid)
check("Super+Right on the left half restores it where it was", fills(f, before_snap) and not marks(n),
      json.dumps(f) + " vs " + json.dumps(before_snap))

# ------------------------------------------------------------------ 6. minimize and back
tick("key down")
time.sleep(0.6)
n, ws, f = window(cid)
check("minimized into the scratchpad", ws == "__i3_scratch" and "_deskd_min_%d" % cid in marks(n), str(ws) + " " + str(marks(n)))
tick("unminimize")
time.sleep(0.8)
n, ws, f = window(cid)
check("unminimized to the same place", ws == "1" and fills(f, before_snap) and not marks(n), str(ws) + " " + json.dumps(f))

# ------------------------------------------------------------------ 7. a second window of the same app
procs.append(subprocess.Popen(["kitty", "--class", "smoke", "--title", "smoke-2"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
w = wait_windows(2)
check("second window opened on the app's workspace", len(w) == 2 and all(ws == "1" for _, ws, _ in w),
      str([ws for _, ws, _ in w]))
other = next(n["id"] for n, _, _ in w if n["id"] != cid)
f1, f2 = window(cid)[2], window(other)[2]
check("second window is not exactly on top of the first (cascade)", (f1["x"], f1["y"]) != (f2["x"], f2["y"]),
      json.dumps(f1) + " " + json.dumps(f2))

# ------------------------------------------------------------------ 7b. Alt+Tab: most recently used first
msg(f"[con_id={cid}] focus")
time.sleep(0.3)
msg(f"[con_id={other}] focus")
time.sleep(0.3)
tick("cycle")
time.sleep(0.4)
check("Alt+Tab goes to the previously used window", focused_id() == cid, str(focused_id()))
tick("cycle")
time.sleep(0.4)
check("a second Alt+Tab (Alt let go between) goes back", focused_id() == other, str(focused_id()))

# ------------------------------------------------------------------ 7c. Alt held: walk, switcher, switch on release
procs.append(subprocess.Popen(["kitty", "--class", "smoke", "--title", "smoke-3", "-o", "initial_window_width=500",
                               "-o", "initial_window_height=300"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
w = wait_windows(3)
third = next(n["id"] for n, _, _ in w if n["id"] not in (cid, other))
for c in (cid, third, other):         # most recent first: other, third, cid
    msg(f"[con_id={c}] focus")
    time.sleep(0.25)
xdo("keydown", "Alt_L")
time.sleep(0.1)
tick("cycle")
time.sleep(0.1)
tick("cycle")
time.sleep(0.4)
check("while Alt is held the switcher shows and nothing is focused yet", switcher_shown() and focused_id() == other,
      f"shown={switcher_shown()} focused={focused_id()}")
xdo("keyup", "Alt_L")
time.sleep(0.4)
check("letting Alt go switches to the window Tab got to", focused_id() == cid and not switcher_shown(), str(focused_id()))

# ------------------------------------------------------------------ 7d. keep above
# The window that asked to stay on top must be over the focused one - and stay there, with no
# restacking back and forth (raise_focused used to lift the focused window over it and
# raise_above put it back, each request answered by a ConfigureNotify and another refresh,
# 25 times a second). Steps: focus another window, ask for "above" and wait until deskd has
# put the state on the window, focus cid (i3 raises its frame), wait for the stack to settle.
n3, _, _ = window(third)
msg(f"[con_id={other}] focus")
time.sleep(0.2)
set_state(n3, 1, "_NET_WM_STATE_ABOVE")


def has_above_state():
    d = xconn()
    prop = d.create_resource_object("window", n3["window"]).get_full_property(
        d.intern_atom("_NET_WM_STATE"), Xatom.ATOM)
    return bool(prop) and d.intern_atom("_NET_WM_STATE_ABOVE") in prop.value


check("the keep-above request reaches the window's state", wait_until(has_above_state, 3))
msg(f"[con_id={cid}] focus")


def stack_index(node):
    stack = [w.id for w in xconn().screen().root.query_tree().children]
    return stack.index(frame_of(node).id)


def above_over_focused():
    return stack_index(window(third)[0]) > stack_index(window(cid)[0])


settled = wait_until(above_over_focused, 3)
check("a keep-above window stays over the focused one", settled, "stack " + str(
    (stack_index(window(third)[0]), stack_index(window(cid)[0]))))


def stays_above(duration=0.5):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        if not above_over_focused():
            return False
        time.sleep(0.05)
    return True


check("... and keeps that place", stays_above())
# no restack storm: once settled the frames are left alone (a loop shows as dozens of events)
d = xconn()
d.screen().root.change_attributes(event_mask=XX.SubstructureNotifyMask)
d.sync()
while d.pending_events():
    d.next_event()
time.sleep(0.8)
frame_ids = {frame_of(window(third)[0]).id, frame_of(window(cid)[0]).id}
restacks = 0
d.sync()
while d.pending_events():
    ev = d.next_event()
    if ev.type == XX.ConfigureNotify and ev.window.id in frame_ids:
        restacks += 1
check("a settled keep-above window is not restacked over and over", restacks <= 2, f"{restacks} events in 0.8 s")
d.screen().root.change_attributes(event_mask=0)
set_state(n3, 0, "_NET_WM_STATE_ABOVE")
msg(f"[con_id={third}] move position 1100 px 650 px")

# ------------------------------------------------------------------ 7e. Super+arrows, as in Windows
msg(f"[con_id={cid}] focus")
time.sleep(0.2)
start = window(cid)[2]
steps = [("left", "left", {"x": 0, "y": 0, "width": area["width"] // 2, "height": area["height"]}),
         ("up", "tl", {"x": 0, "y": 0, "width": area["width"] // 2, "height": area["height"] // 2}),
         ("right", "tr", {"x": area["width"] - area["width"] // 2, "y": 0, "width": area["width"] // 2,
                          "height": area["height"] // 2}),
         ("down", "right", {"x": area["width"] - area["width"] // 2, "y": 0, "width": area["width"] // 2,
                            "height": area["height"]})]
for key, kind, rect in steps:
    tick("key " + key)
    time.sleep(0.5)
    n, _, f = window(cid)
    check(f"Super+{key} -> {kind}", fills(f, rect) and f"_deskd_snap{kind}_{cid}" in marks(n), json.dumps(f) + " " + str(marks(n)))
tick("key left")
time.sleep(0.5)
n, _, f = window(cid)
check("Super+Left on the right half restores", fills(f, start) and not marks(n), json.dumps(f) + " vs " + json.dumps(start))

# ------------------------------------------------------------------ 7f. magnetic edges
msg(f"[con_id={other}] move position 100 px 100 px, resize set 400 px 300 px")
time.sleep(0.4)
fo = window(other)[2]
n, _, f = window(cid)
deco = n["deco_rect"]["height"] or 30
want_x = fo["x"] + fo["width"] + 9          # 9 px short of touching: within the zone
drag(cid, f["x"] + f["width"] // 2 + (want_x - f["x"]), fo["y"] + 40 + deco // 2)
release()
f = window(cid)[2]
check("a window dragged near another's edge sticks to it", f["x"] == fo["x"] + fo["width"],
      f"x={f['x']} want {fo['x'] + fo['width']}")

# ------------------------------------------------------------------ 8. screen size change with a maximized window
msg(f"[con_id={cid}] focus")
tick("key up")
time.sleep(0.6)
# Xephyr -resizeable takes any mode once it is declared (xrandr -s knows only its fixed list)
for args in (["--newmode", "1200x800", "0", "1200", "1200", "1200", "1200", "800", "800", "800", "800"],
             ["--addmode", "default", "1200x800"], ["--output", "default", "--mode", "1200x800"]):
    subprocess.run(["xrandr", *args], env=env, capture_output=True)
time.sleep(2.5)
n, _, f = window(cid)
new_area = {"x": 0, "y": 0, "width": 1200, "height": 800}
check("maximized window refits after a screen change", fills(f, new_area), json.dumps(f) + " " + str(marks(n)))

# ------------------------------------------------------------------ 8b. the left edge grows the window to the left
msg(f"[con_id={cid}] focus")
tick("key down")                       # out of the maximized state
time.sleep(0.6)
msg(f"[con_id={cid}] resize set 600 px 400 px, move position 500 px 200 px")
time.sleep(0.8)
n, _, f = window(cid)
px, py = f["x"] - 5, f["y"] + f["height"] // 2
xdo("mousemove", str(px), str(py)); time.sleep(0.2); xdo("mousedown", "1")
for i in range(1, 11):
    xdo("mousemove", str(px - 10 * i), str(py)); time.sleep(0.04)
time.sleep(0.2)
live = frame_rect(n)
_, _, in_i3 = window(cid)
check("edge resize updates the X frame while held", live["x"] < f["x"] and live["width"] > f["width"],
      json.dumps(live))
check("edge resize updates i3 while held", in_i3["x"] < f["x"] and
      in_i3["width"] > f["width"] and fills(live, in_i3), json.dumps(in_i3))
release()
n, _, g = window(cid)
check("pulling the left edge widens the window to the left, the right edge stays",
      abs(g["x"] - (f["x"] - 100)) <= 3 and abs(g["x"] + g["width"] - (f["x"] + f["width"])) <= 3,
      json.dumps(f) + " -> " + json.dumps(g))

# ------------------------------------------------------------------ 8b2. the resize handles survive a workspace round trip
# deskd keeps its handle windows (rectangle, cursor) while they are unmapped; a window that moved
# on the other workspace must still get its handles on the new rectangle, above its own frame.
def handle_windows():
    """{window id: (x, y, w, h)} of the mapped input-only windows on the root, the 1x1 ones other
    clients keep aside excluded: the resize handles."""
    out = {}
    for w in xconn().screen().root.query_tree().children:
        try:
            a = w.get_attributes()
            if a.win_class == XX.InputOnly and a.map_state == XX.IsViewable:
                g = w.get_geometry()
                if (g.width, g.height) != (1, 1):
                    out[w.id] = (g.x, g.y, g.width, g.height)
        except xerror.BadWindow:
            pass
    return out


def left_handle(frame):
    return (frame["x"] - deskd.HANDLE, frame["y"], deskd.HANDLE, frame["height"])


def handle_above_frame(n, rect):
    ids = [w.id for w in xconn().screen().root.query_tree().children]
    hid = next((i for i, g in handle_windows().items() if g == rect), None)
    return hid in ids and ids.index(hid) > ids.index(frame_of(n).id)


n, _, f = window(cid)
shown = handle_windows()
check("a floating window has its resize handles", left_handle(f) in shown.values() and len(shown) >= 8,
      f"{len(shown)} handles, wanted {left_handle(f)}")
old_left = left_handle(f)
msg("workspace number 4")
check("the handles leave the screen with their workspace",
      wait_until(lambda: not set(shown) & set(handle_windows()), 3), str(len(handle_windows())))
msg(f"[con_id={cid}] move position 250 px 130 px")
time.sleep(0.5)
msg("workspace number 1")
n, _, f = window(cid)
check("the handles follow a window that moved while the workspace was away",
      wait_until(lambda: left_handle(f) in handle_windows().values(), 3), f"{left_handle(f)} not in {len(handle_windows())}")
check("no handle stays on the rectangle the window left", old_left not in handle_windows().values(),
      str(old_left))
check("a returning handle sits above its frame", wait_until(lambda: handle_above_frame(n, left_handle(f)), 3))

# ------------------------------------------------------------------ 8c. the green title button uses the same maximize path
def click_title_button(cid, index):
    node, _, rect = window(cid)
    children = [w for w in frame_of(node).query_tree().children if w.id != node["window"]]
    strip = next((w for w in children if 60 <= w.get_geometry().width <= 200), None)
    if strip is None:
        return False
    sg = strip.get_geometry()
    deco = node["deco_rect"]["height"] or 30
    diameter = max(14, round(deco * 0.63))
    gap = max(6, round(diameter * 0.45))
    pad = max(6, round(diameter * 0.5))
    x = rect["x"] + sg.x + pad + index * (diameter + gap) + diameter // 2
    y = rect["y"] + sg.y + sg.height // 2
    xdo("mousemove", str(x), str(y))
    xdo("click", "1")
    time.sleep(0.5)
    return True


check("green title button is present", click_title_button(cid, 1))
n, _, _ = window(cid)
check("green title button maximizes", any(m.startswith("_deskd_max") for m in marks(n)), str(marks(n)))
click_title_button(cid, 1)
n, _, _ = window(cid)
check("green title button restores", not any(m.startswith("_deskd_max") for m in marks(n)), str(marks(n)))

# ------------------------------------------------------------------ 8d. a notification has no i3 or deskd frame
d = xconn()
notice = d.screen().root.create_window(80, 90, 320, 120, 0, d.screen().root_depth,
                                       XX.InputOutput, XX.CopyFromParent, background_pixel=0)
notice.set_wm_class("deskd-smoke-notification", "deskd-smoke-notification")
notice.set_wm_name("deskd-smoke-notification")
notice.change_property(d.intern_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM, 32,
                       [d.intern_atom("_NET_WM_WINDOW_TYPE_NOTIFICATION")])
notice.map()
d.flush()
time.sleep(0.6)
notif = next((node for node, _, _ in walk(tree()) if node.get("window") == notice.id), None)
check("notification is managed by nested i3", notif is not None)
check("notification has no title border", notif.get("border") == "none", str(notif.get("border")))
children = [w.id for w in frame_of(notif).query_tree().children]
check("notification has no deskd button strip", children == [notice.id], str(children))
notice.destroy()
d.flush()

# ------------------------------------------------------------------ 9. an app's own full screen stays
procs.append(subprocess.Popen(["kitty", "--class", "smoke", "--title", "smoke-fs", "--start-as", "fullscreen"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
w = wait_windows(4)
time.sleep(0.6)
fs = next((n for n, _, _ in windows() if n.get("name") == "smoke-fs"), None)
check("a window opening full screen is left full screen (Telegram's photo viewer)",
      fs is not None and fs.get("fullscreen_mode") == 1 and not marks(fs),
      str(fs and (fs.get("fullscreen_mode"), marks(fs))))

# ------------------------------------------------------------------ 10. a late ConfigureRequest does not push a maximized window out of the work area
# Firefox asks for its saved screen-sized frame again after it was shown; i3 obeys even
# for a floating window deskd has just maximized, and the frame covered the panel.
from Xlib import Xutil
d = xconn()
late = d.screen().root.create_window(0, 0, SIZE[0], SIZE[1], 0, d.screen().root_depth,
                                     XX.InputOutput, XX.CopyFromParent, background_pixel=0)
late.set_wm_class("smoke-late", "smoke-late")
late.set_wm_name("smoke-late")
late.set_wm_normal_hints(flags=Xutil.PMinSize | Xutil.PBaseSize | Xutil.PWinGravity, min_width=300,
                         min_height=180, base_width=300, base_height=180, win_gravity=XX.NorthWestGravity)
late.map()
d.flush()
t0 = time.monotonic()
for delay in (0.02, 0.45, 0.8):
    time.sleep(max(0, t0 + delay - time.monotonic()))
    late.configure(x=0, y=0, width=SIZE[0], height=SIZE[1])
    d.flush()
time.sleep(1.2)
ln = next((node for node, _, _ in walk(tree()) if node.get("window") == late.id), None)
check("a screen-sized window is maximized", ln is not None and any(m.startswith("_deskd_max") for m in marks(ln)),
      str(ln and marks(ln)))
area = next(w["rect"] for w in json.loads(subprocess.run(["i3-msg", "-t", "get_workspaces"], env=env,
            capture_output=True, text=True).stdout) if w["focused"])
fr = frame_rect(ln)
check("a late ConfigureRequest leaves the maximized frame on the work area",
      (fr["x"], fr["y"], fr["width"], fr["height"]) == (area["x"], area["y"], area["width"], area["height"]),
      json.dumps(fr) + " vs " + json.dumps(area))
late.destroy()
d.flush()

say("done:", "all checks passed" if not failed else f"{len(failed)} failed: {failed}")
finish(1 if failed else 0)
