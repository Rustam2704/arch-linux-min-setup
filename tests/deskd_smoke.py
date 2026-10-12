#!/usr/bin/env python3
"""deskd smoke run on a nested X server: never on the user's screen.

    make test-deskd            (or: python3 tests/deskd_smoke.py [--keep])

Starts Xephyr :9, an i3 with the installed config (minus exec/include lines) and the
installed deskd with its own XDG_RUNTIME_DIR, opens kitty windows and drives them with
xdotool and deskd's own tick commands. Checks the window engine end to end: maximize,
drag away from the top (the window must not stay glued to the panel edge), drop at the
left edge and in a corner, restore, minimize and back, a second window of the same app,
Alt+Tab (with Alt held: the switcher, the switch on release), keep-above, Super+arrows,
magnetic edges, a screen size change (RANDR) with a maximized window, and a window
that opens full screen.

The Xephyr window is moved to workspace 9 of the real i3 the moment it appears, so the
user's workspace is not covered. Run time ~20 s. Exit code 1 on the first failed check.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from Xlib import X as XX, display as xdisplay
from Xlib.protocol import event as xevent

DISPLAY = ":9"
SIZE = (1600, 1000)
HOME = os.path.expanduser("~")
CONFIG = os.path.join(HOME, ".config/i3/config")
DESKD = os.path.join(HOME, ".local/share/deskd/deskd.py")
KEEP = "--keep" in sys.argv

tmp = tempfile.mkdtemp(prefix="deskd-smoke-")
run_dir = os.path.join(tmp, "run")
os.makedirs(run_dir)
env = dict(os.environ, DISPLAY=DISPLAY, XDG_RUNTIME_DIR=run_dir, DESKD_NO_PANELS="1")
env.pop("I3SOCK", None)          # inherited from the real session: everything would talk to the real i3
real_sock = os.environ.get("I3SOCK") or subprocess.run(["i3", "--get-socketpath"], capture_output=True,
                                                         text=True).stdout.strip()
procs = []
failed = []


def say(*a):
    print("smoke:", *a, flush=True)


def check(name, ok, detail=""):
    say(("ok  " if ok else "FAIL"), name, detail)
    if not ok:
        failed.append(name)
        if not KEEP:
            finish(1)


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


def stack_index(n):
    return [w.id for w in xconn().screen().root.query_tree().children].index(frame_of(n).id)


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


# ------------------------------------------------------------------ start everything
say("display", DISPLAY, "runtime", run_dir)
procs.append(subprocess.Popen(["Xephyr", DISPLAY, "-screen", f"{SIZE[0]}x{SIZE[1]}", "-resizeable",
                               "-nolisten", "tcp", "-name", "deskd-smoke"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
for _ in range(50):
    if os.path.exists("/tmp/.X11-unix/X" + DISPLAY[1:]):
        break
    time.sleep(0.1)
time.sleep(0.5)
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
log = open(os.path.join(tmp, "deskd.log"), "w")
procs.append(subprocess.Popen([sys.executable, DESKD], env=env, stdout=log, stderr=subprocess.STDOUT))
time.sleep(1.5)
check("deskd running", procs[-1].poll() is None, "see " + log.name)

area = {"x": 0, "y": 0, "width": SIZE[0], "height": SIZE[1]}      # no panel: the whole screen


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
n3, _, _ = window(third)
set_state(n3, 1, "_NET_WM_STATE_ABOVE")
time.sleep(0.3)
msg(f"[con_id={cid}] focus")
time.sleep(0.5)
n1, _, _ = window(cid)
check("a keep-above window stays over the focused one", stack_index(n3) > stack_index(n1),
      f"{stack_index(n3)} vs {stack_index(n1)}")
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

# ------------------------------------------------------------------ 9. an app's own full screen stays
procs.append(subprocess.Popen(["kitty", "--class", "smoke", "--title", "smoke-fs", "--start-as", "fullscreen"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
w = wait_windows(4)
time.sleep(0.6)
fs = next((n for n, _, _ in windows() if n.get("name") == "smoke-fs"), None)
check("a window opening full screen is left full screen (Telegram's photo viewer)",
      fs is not None and fs.get("fullscreen_mode") == 1 and not marks(fs),
      str(fs and (fs.get("fullscreen_mode"), marks(fs))))

say("done:", "all checks passed" if not failed else f"{len(failed)} failed: {failed}")
finish(1 if failed else 0)
