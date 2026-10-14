#!/usr/bin/env python3
"""Count deskd's X requests and i3 IPC calls in Xephyr :9.

Run with --deskd PATH. The wrapper lives in a temporary sitecustomize.py and is
loaded only in the nested deskd process; no profiling code is installed in deskd.
"""
import argparse
import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument("--deskd", required=True)
parser.add_argument("--idle-seconds", type=int, default=60)
parser.add_argument("--trace-querytree", action="store_true")
parser.add_argument("--trace-i3", action="store_true")
parser.add_argument("--trace-refresh", action="store_true")
args = parser.parse_args()
source = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="deskd-bench-"))
profile_dir = tmp / "profile"
profile_dir.mkdir()
log_path = tmp / "requests.tsv"
(profile_dir / "sitecustomize.py").write_text('''\
import os
import time
from Xlib.protocol import display as xdisplay
import i3ipc
_fd = os.open(os.environ["DESKD_PROFILE"], os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
_trace = os.environ.get("DESKD_TRACE_QUERYTREE")
_trace_fd = os.open(_trace, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600) if _trace else None
_i3_trace = os.environ.get("DESKD_TRACE_I3")
_i3_trace_fd = os.open(_i3_trace, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600) if _i3_trace else None
_refresh_trace = os.environ.get("DESKD_TRACE_REFRESH")
if _refresh_trace:
    import sys
    _refresh_fd = os.open(_refresh_trace, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    def _profile(frame, event, arg):
        if event == "call" and frame.f_code.co_name in ("schedule_refresh", "refresh"):
            caller = frame.f_back
            os.write(_refresh_fd, f"{time.time_ns()}:{frame.f_code.co_name}:{caller.f_code.co_name}:{caller.f_lineno}\\n".encode())
    sys.setprofile(_profile)
_x_send = xdisplay.Display.send_request
def send_request(self, request, *args, **kwargs):
    os.write(_fd, f"{time.time_ns()}\\tX\\t{type(request).__name__}\\n".encode())
    if _trace_fd is not None and type(request).__name__ == "QueryTree":
        import traceback
        stack = traceback.extract_stack(limit=8)
        os.write(_trace_fd, (" > ".join(f"{f.name}:{f.lineno}" for f in stack[:-1]) + "\\n").encode())
    return _x_send(self, request, *args, **kwargs)
xdisplay.Display.send_request = send_request
_i3_ask = i3ipc.I3._ask
def ask(self, kind, payload=b""):
    os.write(_fd, f"{time.time_ns()}\\ti3\\t{kind}\\n".encode())
    if _i3_trace_fd is not None:
        import traceback
        stack = traceback.extract_stack(limit=7)
        os.write(_i3_trace_fd, (f"{time.time_ns()}:{kind}:" + " > ".join(f"{f.name}:{f.lineno}" for f in stack[:-1]) + "\\n").encode())
    return _i3_ask(self, kind, payload)
i3ipc.I3._ask = ask
''')
run_dir = tmp / "run"
run_dir.mkdir()
env = dict(os.environ, DISPLAY=":9", XDG_RUNTIME_DIR=str(run_dir), DESKD_NO_PANELS="1",
           DESKD_PROFILE=str(log_path),
           PYTHONPATH=os.pathsep.join((str(profile_dir), str(source / "desktop/share/sky-desktop"))))
env.pop("I3SOCK", None)
if args.trace_querytree:
    env["DESKD_TRACE_QUERYTREE"] = str(tmp / "querytree.txt")
if args.trace_i3:
    env["DESKD_TRACE_I3"] = str(tmp / "i3.txt")
if args.trace_refresh:
    env["DESKD_TRACE_REFRESH"] = str(tmp / "refresh.txt")
procs = []
phases = {}


def command(argv):
    return subprocess.run(argv, env=env, capture_output=True, text=True)


def msg(text):
    return command(["i3-msg", "-q", text])


def tree():
    for _ in range(5):
        result = command(["i3-msg", "-t", "get_tree"])
        if result.returncode == 0 and result.stdout.startswith("{"):
            return json.loads(result.stdout)
        time.sleep(0.1)
    raise RuntimeError(f"nested i3 get_tree failed: {result.stderr.strip()}")


def walk(node):
    yield node
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        yield from walk(child)


def bench_windows():
    return [n for n in walk(tree()) if n.get("window")
            and (n.get("window_properties") or {}).get("class") == "deskd-bench"]


def xdo(*argv):
    command(["xdotool", *map(str, argv)])


def timed(name, action, settle=0.3):
    start = time.time_ns()
    action()
    time.sleep(settle)
    phases[name] = (start, time.time_ns())


try:
    procs.append(subprocess.Popen(["Xephyr", ":9", "-screen", "1600x1000", "-nolisten", "tcp",
                                   "-name", "deskd-bench"], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL))
    for _ in range(50):
        if Path("/tmp/.X11-unix/X9").exists():
            break
        time.sleep(0.1)
    if procs[0].poll() is not None:
        raise RuntimeError("Xephyr :9 did not start")
    time.sleep(0.5)
    config = tmp / "i3.conf"
    config.write_text("".join(line for line in Path.home().joinpath(".config/i3/config").read_text().splitlines(True)
                              if not line.strip().startswith(("exec ", "exec_always ", "include "))))
    procs.append(subprocess.Popen(["i3", "-c", str(config)], env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL))
    for _ in range(50):
        if msg("nop").returncode == 0:
            break
        time.sleep(0.1)
    nested_sock = command(["i3", "--get-socketpath"]).stdout.strip()
    if not nested_sock or nested_sock == os.environ.get("I3SOCK"):
        raise RuntimeError("nested i3 socket is missing or matches the live i3")
    procs.append(subprocess.Popen([sys.executable, args.deskd], env=env,
                                  stdout=(tmp / "deskd.log").open("w"), stderr=subprocess.STDOUT))
    time.sleep(1.5)
    if procs[-1].poll() is not None:
        raise RuntimeError("deskd exited: " + (tmp / "deskd.log").read_text())
    msg("workspace number 2")
    for index in range(5):
        procs.append(subprocess.Popen(["kitty", "--class", "deskd-bench", "--title", f"bench-{index}"],
                                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        deadline = time.monotonic() + 7
        while len(bench_windows()) < index + 1 and time.monotonic() < deadline:
            time.sleep(0.1)
        if len(bench_windows()) < index + 1:
            raise RuntimeError("window failed to open")
    time.sleep(0.7)
    wins = bench_windows()
    for index, node in enumerate(wins):
        msg(f'[con_id={node["id"]}] resize set 400 px 300 px, move position {80 + (index % 3) * 470} px '
            f'{80 + (index // 3) * 420} px')
    time.sleep(0.7)
    msg("workspace number 1")
    time.sleep(0.3)
    timed("switch", lambda: msg("workspace number 2"), 0.6)

    node = bench_windows()[0]
    cid = node["id"]
    msg(f"[con_id={cid}] focus")
    time.sleep(0.3)
    # i3's floating wrapper rectangle encloses the title bar.
    parent = next(n for n in walk(tree()) if any(c.get("id") == cid for c in n.get("nodes", [])))
    rect = parent["rect"]
    x0, y0 = rect["x"] + rect["width"] // 2, rect["y"] + max(10, node["deco_rect"]["height"] // 2)

    def drag():
        xdo("mousemove", x0, y0)
        xdo("mousedown", 1)
        started = time.monotonic()
        for i in range(40):
            time.sleep(max(0, started + (i + 1) * 0.05 - time.monotonic()))
            xdo("mousemove", x0 + i * 4, y0 + i * 3)
        xdo("mouseup", 1)

    timed("drag", drag, 0.3)
    node = next(n for n in bench_windows() if n["id"] == cid)
    parent = next(n for n in walk(tree()) if any(c.get("id") == cid for c in n.get("nodes", [])))
    rect = parent["rect"]
    rx, ry = rect["x"] - 5, rect["y"] + rect["height"] // 2

    def resize():
        xdo("mousemove", rx, ry)
        xdo("mousedown", 1)
        started = time.monotonic()
        for i in range(40):
            time.sleep(max(0, started + (i + 1) * 0.05 - time.monotonic()))
            xdo("mousemove", rx - i * 2, ry)
        xdo("mouseup", 1)

    timed("resize", resize, 0.3)
    start = time.time_ns()
    time.sleep(args.idle_seconds)
    phases["idle minute"] = (start, time.time_ns())
    records = []
    for line in log_path.read_text().splitlines():
        stamp, kind, request = line.split("\t")
        records.append((int(stamp), kind, request))
    for name, (start, end) in phases.items():
        rows = [(kind, request) for stamp, kind, request in records if start <= stamp < end]
        counts = collections.Counter(kind for kind, _ in rows)
        x_requests = collections.Counter(request for kind, request in rows if kind == "X")
        ipc = collections.Counter(request for kind, request in rows if kind == "i3")
        print(json.dumps({"scenario": name, "X": counts["X"], "i3": counts["i3"],
                          "x_detail": x_requests, "i3_detail": ipc}), flush=True)
    if args.trace_querytree:
        for stack, count in collections.Counter((tmp / "querytree.txt").read_text().splitlines()).most_common(10):
            print(f"QueryTree {count}: {stack}", flush=True)
    if args.trace_i3:
        start, end = phases["switch"]
        for line in (tmp / "i3.txt").read_text().splitlines():
            stamp = int(line.split(":", 1)[0])
            if start <= stamp < end:
                print("i3 switch", line.split(":", 1)[1], flush=True)
    if args.trace_refresh:
        start, end = phases["switch"]
        for line in (tmp / "refresh.txt").read_text().splitlines():
            stamp = int(line.split(":", 1)[0])
            if start <= stamp < end:
                print("refresh switch", line.split(":", 1)[1], flush=True)
finally:
    for proc in reversed(procs):
        try:
            proc.terminate()
        except OSError:
            pass
    time.sleep(0.5)
    for proc in reversed(procs):
        try:
            proc.kill()
        except OSError:
            pass
    shutil.rmtree(tmp, ignore_errors=True)
