#!/usr/bin/env python3
"""Passive X11/i3 latency and process sampler. Records input counts, never key details."""
import argparse
import collections
import ctypes
import datetime as dt
import json
import os
import select
import socket
import struct
import threading
import time
from pathlib import Path

from Xlib import display
from Xlib.ext import xinput

ROOT = Path(__file__).resolve().parent
HZ = os.sysconf("SC_CLK_TCK")
MAGIC = b"i3-ipc"
HEADER = struct.Struct("=6sII")
GET_VERSION = 7
SUBSCRIBE = 2
EVENT_NAMES = {0: "workspace", 3: "window"}


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).astimezone().isoformat(timespec="milliseconds")


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("i3 socket closed")
        data.extend(chunk)
    return bytes(data)


def ipc(sock, kind, payload=b""):
    sock.sendall(HEADER.pack(MAGIC, len(payload), kind) + payload)
    magic, length, rtype = HEADER.unpack(read_exact(sock, HEADER.size))
    if magic != MAGIC:
        raise ValueError("invalid i3 IPC header")
    return rtype, read_exact(sock, length)


def socket_path():
    path = os.environ.get("I3SOCK")
    if path and os.path.exists(path):
        return path
    # i3 --get-socketpath is read-only and runs once, before sampling.
    import subprocess
    return subprocess.check_output(["i3", "--get-socketpath"], text=True).strip()


def read_number(path, key=None):
    try:
        with open(path) as f:
            if key is None:
                return int(f.read().split()[0])
            for line in f:
                if line.startswith(key):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    return None


def vmstat():
    wanted = {"pswpin", "pgmajfault"}
    try:
        with open("/proc/vmstat") as f:
            return {p[0]: int(p[1]) for line in f if (p := line.split()) and p[0] in wanted}
    except OSError:
        return {}


def psi():
    result = {}
    for kind in ("cpu", "memory", "io"):
        try:
            with open(f"/proc/pressure/{kind}") as f:
                row = f.readline().split()
            result[kind] = int(next(x[6:] for x in row if x.startswith("total=")))
        except (OSError, StopIteration, ValueError):
            pass
    return result


def cpu_mhz():
    result = []
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("cpu MHz"):
                    result.append(round(float(line.split(":", 1)[1]), 1))
    except (OSError, ValueError):
        pass
    return result


def temp_path():
    for base in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (base / "name").read_text().strip() == "coretemp":
                for label in base.glob("temp*_label"):
                    if label.read_text().strip() == "Package id 0":
                        return label.with_name(label.name.replace("_label", "_input"))
                return base / "temp1_input"
        except OSError:
            pass
    for base in Path("/sys/class/thermal").glob("thermal_zone*"):
        try:
            if (base / "type").read_text().strip() in ("x86_pkg_temp", "acpitz"):
                return base / "temp"
        except OSError:
            pass
    return None


class ProcScanner:
    def __init__(self):
        class Row(ctypes.Structure):
            _fields_ = [("pid", ctypes.c_int), ("ticks", ctypes.c_uint64),
                        ("start", ctypes.c_uint64), ("state", ctypes.c_char),
                        ("comm", ctypes.c_char * 64)]
        self.row_type = Row
        self.rows = (Row * 4096)()
        self.native = ctypes.CDLL(str(ROOT / "procscan.so"))
        self.native.procscan.argtypes = (ctypes.POINTER(Row), ctypes.c_int)
        self.native.procscan.restype = ctypes.c_int
        self.previous = {}
        self.deskd_pid = None

    def scan(self, interval):
        live = set()
        rows = []
        count = self.native.procscan(self.rows, len(self.rows))
        if count < 0:
            raise OSError("cannot scan /proc")
        for row in self.rows[:count]:
            pid = row.pid
            live.add(pid)
            name = row.comm.decode("utf-8", "replace")
            state = row.state.decode()
            ticks = row.ticks
            start = row.start
            prior = self.previous.get(pid)
            delta = max(0, ticks - prior[1]) if prior and prior[0] == start else 0
            cpu = round(100 * delta / (HZ * interval), 2) if interval else 0
            rows.append((cpu, pid, name, state, ticks, start))
            self.previous[pid] = (start, ticks)
            if name == "python3" and (pid == self.deskd_pid or self.deskd_pid is None):
                try:
                    args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                    if b"/home/fanatic/.local/share/deskd/deskd.py" in args:
                        self.deskd_pid = pid
                except OSError:
                    pass
        for pid in self.previous.keys() - live:
            self.previous.pop(pid, None)
            if pid == self.deskd_pid:
                self.deskd_pid = None
        rows.sort(reverse=True)
        top = [{"pid": pid, "comm": name, "cpu_pct": cpu} for cpu, pid, name, *_ in rows[:8]]
        deskd = None
        if self.deskd_pid is not None:
            match = next((r for r in rows if r[1] == self.deskd_pid), None)
            if match:
                deskd = {"pid": match[1], "state": match[3], "cpu_pct": match[0]}
                try:
                    with open(f"/proc/{self.deskd_pid}/status") as f:
                        for line in f:
                            if line.startswith("VmSwap:"):
                                deskd["vm_swap_kb"] = int(line.split()[1])
                            elif line.startswith("voluntary_ctxt_switches:"):
                                deskd["voluntary_ctxt_switches"] = int(line.split()[1])
                            elif line.startswith("nonvoluntary_ctxt_switches:"):
                                deskd["nonvoluntary_ctxt_switches"] = int(line.split()[1])
                except OSError:
                    pass
        return top, deskd

    def close(self):
        pass


class Probe:
    x_period, x_threshold = .020, .040
    i3_period, i3_threshold = .100, .050

    def __init__(self, minutes):
        self.duration = minutes * 60
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.stalls = collections.deque()
        self.activity = collections.deque()
        self.events = collections.deque()
        self.latencies = collections.deque()
        self.samples = collections.deque()
        self.errors = []
        self.input_mode = "XI2 raw counts"
        self.i3path = socket_path()
        self.thermal = temp_path()
        self.scanner = ProcScanner()

    def fail(self, source, error):
        with self.lock:
            self.errors.append(f"{source}: {type(error).__name__}: {error}")

    def add_stall(self, source, a, b):
        with self.lock:
            self.stalls.append({"probe": source, "start_mono": a, "end_mono": b,
                                "time": iso(time.time() - (time.monotonic() - a)),
                                "duration_ms": round((b - a) * 1000, 2)})

    def x_loop(self):
        try:
            d = display.Display(os.environ.get("DISPLAY", ":0"))
            next_at = time.monotonic()
            while not self.stop.is_set():
                a = time.monotonic()
                d.get_input_focus()
                b = time.monotonic()
                with self.lock:
                    self.latencies.append((b, "X", round((b - a) * 1000, 3)))
                if b - a > self.x_threshold:
                    self.add_stall("X", a, b)
                next_at += self.x_period
                self.stop.wait(max(0, next_at - time.monotonic()))
                if next_at < time.monotonic() - self.x_period:
                    next_at = time.monotonic()
            d.close()
        except Exception as e:
            self.fail("X probe", e)

    def i3_loop(self):
        try:
            sock = socket.socket(socket.AF_UNIX)
            sock.connect(self.i3path)
            next_at = time.monotonic()
            while not self.stop.is_set():
                a = time.monotonic()
                ipc(sock, GET_VERSION)
                b = time.monotonic()
                with self.lock:
                    self.latencies.append((b, "i3", round((b - a) * 1000, 3)))
                if b - a > self.i3_threshold:
                    self.add_stall("i3", a, b)
                next_at += self.i3_period
                self.stop.wait(max(0, next_at - time.monotonic()))
                if next_at < time.monotonic() - self.i3_period:
                    next_at = time.monotonic()
            sock.close()
        except Exception as e:
            self.fail("i3 probe", e)

    def input_loop(self):
        try:
            d = display.Display(os.environ.get("DISPLAY", ":0"))
            if not d.has_extension("XInputExtension"):
                raise RuntimeError("XInput extension unavailable")
            d.xinput_query_version()
            mask = xinput.RawKeyPressMask | xinput.RawButtonPressMask | xinput.RawMotionMask
            d.screen().root.xinput_select_events([(xinput.AllMasterDevices, mask)])
            d.flush()
            while not self.stop.is_set():
                if not d.pending_events():
                    select.select([d.fileno()], [], [], .05)
                while d.pending_events():
                    ev = d.next_event()
                    kind = {xinput.RawKeyPress: "key", xinput.RawButtonPress: "button",
                            xinput.RawMotion: "motion"}.get(getattr(ev, "evtype", None))
                    if kind:
                        with self.lock:
                            self.activity.append((time.monotonic(), kind))
            d.close()
        except Exception as e:
            self.fail("XI2", e)
            self.input_mode = "pointer polling fallback; key counts unavailable"
            try:
                d = display.Display(os.environ.get("DISPLAY", ":0"))
                last = None
                while not self.stop.is_set():
                    p = d.screen().root.query_pointer()
                    pos = (p.root_x, p.root_y)
                    if last is not None and pos != last:
                        with self.lock:
                            self.activity.append((time.monotonic(), "motion"))
                    last = pos
                    self.stop.wait(.05)
                d.close()
            except Exception as e2:
                self.fail("pointer fallback", e2)

    def events_loop(self):
        try:
            sock = socket.socket(socket.AF_UNIX)
            sock.connect(self.i3path)
            ipc(sock, SUBSCRIBE, b'["workspace","window"]')
            sock.settimeout(.2)
            while not self.stop.is_set():
                try:
                    head = read_exact(sock, HEADER.size)
                    magic, length, rtype = HEADER.unpack(head)
                    body = read_exact(sock, length)
                except socket.timeout:
                    continue
                if magic != MAGIC or not rtype & 0x80000000:
                    continue
                name = EVENT_NAMES.get(rtype & 0x7fffffff)
                if name:
                    payload = json.loads(body)
                    con = payload.get("container") or payload.get("current") or {}
                    event = {"type": name, "change": payload.get("change"),
                             "id": con.get("id"), "workspace": con.get("name") if name == "workspace" else None}
                    with self.lock:
                        self.events.append((time.monotonic(), event))
            sock.close()
        except Exception as e:
            self.fail("i3 events", e)

    def flush_stalls(self, out, now, force=False):
        with self.lock:
            ready = []
            while self.stalls and (force or self.stalls[0]["end_mono"] + 1.05 <= now):
                ready.append(self.stalls.popleft())
            activity = list(self.activity)
            events = list(self.events)
            samples = list(self.samples)
            while self.activity and self.activity[0][0] < now - 3:
                self.activity.popleft()
            while self.events and self.events[0][0] < now - 3:
                self.events.popleft()
            while self.samples and self.samples[0]["end_mono"] < now - 3:
                self.samples.popleft()
            while self.latencies and self.latencies[0][0] < now - 3:
                self.latencies.popleft()
        for stall in ready:
            a, b = stall.pop("start_mono"), stall.pop("end_mono")
            stall["activity"] = {kind: sum(1 for t, k in activity if k == kind and a - .5 <= t <= b + .5)
                                 for kind in ("key", "button", "motion")}
            stall["i3_events"] = [{"time": iso(time.time() - (now - t)), **ev}
                                  for t, ev in events if a - 1 <= t <= b + 1]
            stall["samples"] = [{k: v for k, v in sample.items() if k not in ("start_mono", "end_mono")}
                                for sample in samples if sample["start_mono"] <= b and sample["end_mono"] >= a]
            out.write(json.dumps(stall, separators=(",", ":")) + "\n")

    def run(self):
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        start = time.monotonic()
        start_cpu = time.process_time()
        threads = [threading.Thread(target=fn, daemon=True) for fn in
                   (self.x_loop, self.i3_loop, self.input_loop, self.events_loop)]
        for thread in threads:
            thread.start()
        prev_vm, prev_psi = vmstat(), psi()
        prev_sci = read_number("/sys/firmware/acpi/interrupts/sci")
        prev_end = time.monotonic()
        next_at = prev_end + .1
        last_flush = prev_end
        try:
            with (logs / "samples.jsonl").open("w", buffering=1) as samples_out, \
                 (logs / "stalls.jsonl").open("w", buffering=1) as stalls_out:
                while time.monotonic() - start < self.duration:
                    self.stop.wait(max(0, next_at - time.monotonic()))
                    now = time.monotonic()
                    interval = max(.001, now - prev_end)
                    top, deskd = self.scanner.scan(interval)
                    current_vm, current_psi = vmstat(), psi()
                    current_sci = read_number("/sys/firmware/acpi/interrupts/sci")
                    with self.lock:
                        acts = list(self.activity)
                        events = list(self.events)
                        latencies = list(self.latencies)
                    sample = {"time": iso(time.time()), "start_mono": prev_end, "end_mono": now,
                              "interval_ms": round(interval * 1000, 2), "top": top, "deskd": deskd,
                              "activity": {kind: sum(1 for t, k in acts if k == kind and prev_end < t <= now)
                                           for kind in ("key", "button", "motion")},
                              "roundtrip_ms": {kind: [ms for t, k, ms in latencies
                                                      if k == kind and prev_end < t <= now]
                                               for kind in ("X", "i3")},
                              "i3_events": [{"time": iso(time.time() - (now - t)), **event}
                                            for t, event in events if prev_end < t <= now],
                              "pswpin": max(0, current_vm.get("pswpin", 0) - prev_vm.get("pswpin", 0)),
                              "pgmajfault": max(0, current_vm.get("pgmajfault", 0) - prev_vm.get("pgmajfault", 0)),
                              "psi_us": {k: max(0, v - prev_psi.get(k, v)) for k, v in current_psi.items()},
                              "sci": None if current_sci is None or prev_sci is None else max(0, current_sci - prev_sci),
                              "cpu_mhz": cpu_mhz(),
                              "package_temp_c": None if self.thermal is None else
                              (lambda n: round(n / 1000, 1) if n is not None else None)(read_number(self.thermal))}
                    with self.lock:
                        self.samples.append(sample)
                    samples_out.write(json.dumps({k: v for k, v in sample.items() if k not in ("start_mono", "end_mono")},
                                                 separators=(",", ":")) + "\n")
                    self.flush_stalls(stalls_out, now)
                    if now - last_flush >= 1:
                        samples_out.flush()
                        stalls_out.flush()
                        last_flush = now
                    prev_vm, prev_psi, prev_sci, prev_end = current_vm, current_psi, current_sci, now
                    next_at += .1
                    if next_at < now:
                        next_at = now + .1
                self.stop.set()
                for thread in threads:
                    thread.join(timeout=1.5)
                self.flush_stalls(stalls_out, time.monotonic(), force=True)
        finally:
            self.stop.set()
            self.scanner.close()
        elapsed = time.monotonic() - start
        cpu_pct = 100 * (time.process_time() - start_cpu) / elapsed
        report(logs / "samples.jsonl", logs / "stalls.jsonl", elapsed, cpu_pct,
               self.input_mode, self.errors)
        print(f"Captured {elapsed:.1f}s; probe CPU {cpu_pct:.2f}% of one core; report: {ROOT / 'report.md'}")


LIGHT_NAMES = ("Xorg", "xcompmgr", "i3", "deskd", "sky-stars", "xfce4-panel")
ACTIVITY_KINDS = ("key", "button", "motion")


def proc_stat(pid):
    """Return identity and CPU ticks for one known PID."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        end = raw.rfind(")")
        fields = raw[end + 2:].split()
        return raw[raw.find("(") + 1:end], int(fields[11]) + int(fields[12]), int(fields[19])
    except (OSError, ValueError, IndexError):
        return None


def resolve_light_pids():
    """Look up six service PIDs once a minute; no CPU scan here."""
    found = {}
    socket_name = Path(os.environ.get("I3SOCK", "")).name
    i3_pid = int(socket_name.rsplit(".", 1)[-1]) if socket_name.rsplit(".", 1)[-1].isdecimal() else None
    for entry in os.scandir("/proc"):
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name)
        try:
            comm = Path(f"/proc/{pid}/comm").read_text().strip()
            if comm == "i3" and i3_pid is not None and pid != i3_pid:
                continue
            if comm in LIGHT_NAMES:
                found[comm] = pid
            elif comm in ("python", "python3"):
                args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if any(arg.endswith(b"/deskd.py") for arg in args):
                    found["deskd"] = pid
                elif any(arg.endswith(b"/sky-stars") for arg in args):
                    found["sky-stars"] = pid
        except OSError:
            continue
    return found


def deltas(before, after):
    return {key: max(0, value - before.get(key, value)) for key, value in after.items()}


class LightProbe(Probe):
    x_period, x_threshold = .050, .060
    i3_period, i3_threshold = .250, .080

    def __init__(self, minutes):
        self.duration = minutes * 60
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.stalls = collections.deque()
        self.activity = collections.deque(maxlen=30)  # 100-ms bins, last three seconds
        self.events = collections.deque()
        self.latencies = collections.deque()
        self.errors = []
        self.input_mode = "XI2 raw counts"
        self.i3path = socket_path()
        self.scanner = ProcScanner()
        self.pids = resolve_light_pids()
        baseline_at = time.monotonic()
        count = self.scanner.native.procscan(self.scanner.rows, len(self.scanner.rows))
        if count < 0:
            raise OSError("cannot take initial /proc snapshot")
        self.tracked = {row.pid: (row.start, row.ticks, baseline_at)
                        for row in self.scanner.rows[:count]}
        self.last_fixed = {}
        self.background = None
        self.minute_stalls = 0
        self.minute_max_ms = 0
        self.minute_activity = collections.Counter()
        self.minute_start = time.monotonic()
        self.minute_number = 0

    def add_stall(self, source, a, b):
        with self.lock:
            self.stalls.append({"type": "stall", "probe": source, "start_mono": a,
                                "end_mono": b, "time": iso(time.time() - (time.monotonic() - a)),
                                "duration_ms": round((b - a) * 1000, 2),
                                "pre_activity": list(self.activity), "pre_events": list(self.events)})

    def input_loop(self):
        try:
            d = display.Display(os.environ.get("DISPLAY", ":0"))
            if not d.has_extension("XInputExtension"):
                raise RuntimeError("XInput extension unavailable")
            d.xinput_query_version()
            mask = xinput.RawKeyPressMask | xinput.RawButtonPressMask | xinput.RawMotionMask
            d.screen().root.xinput_select_events([(xinput.AllMasterDevices, mask)])
            d.flush()
            counts = collections.Counter()
            bucket_end = time.monotonic() + .1
            kinds = {xinput.RawKeyPress: "key", xinput.RawButtonPress: "button",
                     xinput.RawMotion: "motion"}
            while not self.stop.is_set():
                select.select([d.fileno()], [], [], max(0, min(.1, bucket_end - time.monotonic())))
                while d.pending_events():
                    kind = kinds.get(getattr(d.next_event(), "evtype", None))
                    if kind:
                        counts[kind] += 1
                now = time.monotonic()
                if now >= bucket_end:
                    with self.lock:
                        self.activity.append((bucket_end, dict(counts)))
                        self.minute_activity.update(counts)
                    counts.clear()
                    bucket_end += .1 * max(1, int((now - bucket_end) / .1) + 1)
            d.close()
        except Exception as e:
            self.fail("XI2", e)

    def read_tracked(self, now):
        """Sample only PIDs that used CPU on the previous second, plus fixed services."""
        keep = set(self.tracked) | set(self.pids.values())
        next_tracked = {}
        fixed = {}
        for pid in keep:
            stat = proc_stat(pid)
            if stat is None:
                continue
            name, ticks, start = stat
            prior = self.last_fixed.get(pid) or self.tracked.get(pid)
            cpu = 0.0
            if prior and prior[0] == start:
                cpu = round(100 * max(0, ticks - prior[1]) / (HZ * max(.001, now - prior[2])), 2)
            if cpu > 0:
                next_tracked[pid] = (start, ticks, now)
            for label, fixed_pid in self.pids.items():
                if fixed_pid == pid:
                    fixed[label] = {"pid": pid, "cpu_pct": cpu}
                    self.last_fixed[pid] = (start, ticks, now)
        self.tracked = next_tracked
        self.last_fixed = {pid: row for pid, row in self.last_fixed.items() if pid in self.pids.values()}
        return fixed

    def full_scan(self, now):
        count = self.scanner.native.procscan(self.scanner.rows, len(self.scanner.rows))
        if count < 0:
            self.fail("stall process scan", OSError("cannot scan /proc"))
            return []
        rows = []
        for row in self.scanner.rows[:count]:
            prior = self.tracked.get(row.pid) or self.last_fixed.get(row.pid)
            if not prior or prior[0] != row.start:
                continue
            cpu = 100 * max(0, row.ticks - prior[1]) / (HZ * max(.001, now - prior[2]))
            if cpu > 0:
                rows.append({"pid": row.pid, "comm": row.comm.decode("utf-8", "replace"),
                             "cpu_pct": round(cpu, 2)})
        return sorted(rows, key=lambda row: row["cpu_pct"], reverse=True)[:8]

    def write(self, out, row):
        out.write(json.dumps(row, separators=(",", ":")) + "\n")

    def finish_stalls(self, out, now, force=False):
        with self.lock:
            ready = []
            while self.stalls and (force or self.stalls[0]["end_mono"] + 2.05 <= now):
                ready.append(self.stalls.popleft())
            activity = list(self.activity)
            events = list(self.events)
            while self.events and self.events[0][0] < now - 3:
                self.events.popleft()
            while self.latencies and self.latencies[0][0] < now - 3:
                self.latencies.popleft()
        for stall in ready:
            a, b = stall.pop("start_mono"), stall.pop("end_mono")
            bins = {t: counts for t, counts in stall.pop("pre_activity") + activity
                    if a - 1 <= t <= b + 1}
            stall["activity"] = {kind: sum(c.get(kind, 0) for c in bins.values())
                                 for kind in ACTIVITY_KINDS}
            event_rows = {t: ev for t, ev in stall.pop("pre_events") + events
                          if a - 2 <= t <= b + 2}
            stall["i3_events"] = [{"time": iso(time.time() - (now - t)), **ev}
                                  for t, ev in sorted(event_rows.items())]
            self.write(out, stall)

    def write_minute(self, out, now, force=False):
        if not force and now - self.minute_start < 60:
            return
        with self.lock:
            activity = {kind: self.minute_activity[kind] for kind in ACTIVITY_KINDS}
            self.minute_activity.clear()
        self.write(out, {"type": "minute", "time": iso(time.time()), "minute": self.minute_number,
                         "seconds": round(now - self.minute_start, 2), "stalls": self.minute_stalls,
                         "max_latency_ms": round(self.minute_max_ms, 2), "activity": activity,
                         "active": any(activity.values())})
        self.minute_number += 1
        self.minute_start = now
        self.minute_stalls = 0
        self.minute_max_ms = 0

    def run(self):
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        path = logs / f"light-{dt.date.today().isoformat()}.jsonl"
        start = time.monotonic()
        start_cpu = time.process_time()
        threads = [threading.Thread(target=fn, daemon=True) for fn in
                   (self.x_loop, self.i3_loop, self.input_loop, self.events_loop)]
        prev_vm, prev_psi = vmstat(), psi()
        prev_sci = read_number("/sys/firmware/acpi/interrupts/sci")
        next_second = start + 1
        next_resolve = start + 60
        next_tick = start + .1
        last_latency_check = start
        with path.open("a", buffering=1) as out:
            self.write(out, {"type": "run", "time": iso(time.time()), "minutes": self.duration / 60,
                             "x_period_ms": 50, "i3_period_ms": 250,
                             "x_threshold_ms": 60, "i3_threshold_ms": 80})
            for thread in threads:
                thread.start()
            try:
                while time.monotonic() - start < self.duration:
                    self.stop.wait(max(0, next_tick - time.monotonic()))
                    now = time.monotonic()
                    with self.lock:
                        pending = [s for s in self.stalls if "top" not in s]
                        latencies = list(self.latencies)
                    for stall in pending:
                        stall["top"] = self.full_scan(time.monotonic())
                        stall["background"] = self.background
                        self.minute_stalls += 1
                    if now >= next_second:
                        fixed = self.read_tracked(now)
                        current_vm, current_psi = vmstat(), psi()
                        current_sci = read_number("/sys/firmware/acpi/interrupts/sci")
                        self.background = {"type": "background", "time": iso(time.time()),
                                           "fixed": fixed, "pswpin": deltas(prev_vm, current_vm).get("pswpin", 0),
                                           "pgmajfault": deltas(prev_vm, current_vm).get("pgmajfault", 0),
                                           "psi_us": deltas(prev_psi, current_psi),
                                           "sci": None if prev_sci is None or current_sci is None else
                                           max(0, current_sci - prev_sci)}
                        self.write(out, self.background)
                        prev_vm, prev_psi, prev_sci = current_vm, current_psi, current_sci
                        next_second = now + 1
                    self.minute_max_ms = max(self.minute_max_ms,
                                             *(ms for t, _, ms in latencies if t > last_latency_check), 0)
                    last_latency_check = now
                    self.finish_stalls(out, now)
                    self.write_minute(out, now)
                    if now >= next_resolve:
                        self.pids = resolve_light_pids()
                        next_resolve = now + 60
                    next_tick = now + .1
            finally:
                self.stop.set()
                for thread in threads:
                    thread.join(timeout=1)
                self.finish_stalls(out, time.monotonic(), force=True)
                self.write_minute(out, time.monotonic(), force=True)
                elapsed = time.monotonic() - start
                self.write(out, {"type": "end", "time": iso(time.time()), "seconds": round(elapsed, 2),
                                 "probe_cpu_pct": round(100 * (time.process_time() - start_cpu) / elapsed, 3),
                                 "errors": self.errors})
        print(f"Light log: {path}")


def light_summary(path):
    rows = [json.loads(line) for line in Path(path).open() if line.strip()]
    # A daily log may contain a short calibration run before the long session.
    last_run = next((i for i in range(len(rows) - 1, -1, -1)
                     if rows[i].get("type") == "run"), 0)
    rows = rows[last_run:]
    stalls = [row for row in rows if row.get("type") == "stall"]
    minutes = [row for row in rows if row.get("type") == "minute" and row.get("seconds", 0) >= 50]
    backgrounds = [row for row in rows if row.get("type") == "background"]
    for label, active in (("active", True), ("idle", False)):
        group = [m for m in minutes if m["active"] == active]
        print(f"Stalls per {label} minute: {sum(m['stalls'] for m in group) / len(group):.2f} ({len(group)} minutes)"
              if group else f"Stalls per {label} minute: unavailable (0 minutes)")
    bins = ((0, 100), (100, 300), (300, 1000), (1000, float("inf")))
    print("Durations (ms): " + ", ".join(f"{lo}-{hi if hi != float('inf') else 'inf'}: "
          f"{sum(lo <= s['duration_ms'] < hi for s in stalls)}" for lo, hi in bins))
    groups = {"typing": lambda s: s["activity"]["key"] > 0,
              "pointer motion": lambda s: s["activity"]["motion"] > 0,
              "workspace switch": lambda s: any(e["type"] == "workspace" for e in s["i3_events"]),
              "window move": lambda s: any(e["type"] == "window" and e["change"] == "move" for e in s["i3_events"])}
    print("During: " + ", ".join(f"{label}: {sum(fn(s) for s in stalls)}" for label, fn in groups.items()))
    print("Processes over-represented in stalls (mean CPU % of one core, stall/background):")
    if not stalls:
        print("  unavailable: no stalls recorded")
        return
    ranked = []
    for name in LIGHT_NAMES:
        inside = [s.get("background", {}).get("fixed", {}).get(name, {}).get("cpu_pct", 0)
                  for s in stalls if s.get("background")]
        outside = [b.get("fixed", {}).get(name, {}).get("cpu_pct", 0) for b in backgrounds]
        a = sum(inside) / len(inside) if inside else 0
        b = sum(outside) / len(outside) if outside else 0
        ranked.append((a - b, name, a, b))
    for _, name, a, b in sorted(ranked, reverse=True):
        print(f"  {name}: {a:.2f} / {b:.2f} (difference {a-b:+.2f})")


def report(samples_path, stalls_path, elapsed, cpu_pct, input_mode, errors):
    samples = [json.loads(line) for line in samples_path.open()]
    stalls = [json.loads(line) for line in stalls_path.open()]
    lines = ["# Passive desktop stall probe", "",
             f"Run: {elapsed / 60:.2f} min; {len(samples)} process samples at 100 ms; "
             f"X round trips at 20 ms and i3 GET_VERSION at 100 ms.",
             f"Input: {input_mode}; counts only. Probe CPU: {cpu_pct:.2f}% of one core "
             f"({'within' if cpu_pct < 3 else 'above'} 3% target).",
             "Stalls: X >40 ms or i3 >50 ms. Attribution uses ±500 ms input, ±1 s i3 events, and overlapping samples."]
    limitations = []
    if samples and "roundtrip_ms" not in samples[0]:
        limitations.append("successful round-trip latencies were not persisted")
    if samples and "i3_events" not in samples[0]:
        limitations.append("i3 events outside stall windows were not persisted")
    if cpu_pct >= 3:
        limitations.append("the requested CPU overhead limit was not met")
    if limitations:
        lines.append("Limitations: " + "; ".join(limitations) + ".")
    if errors:
        lines += ["Limitations/errors: " + "; ".join(dict.fromkeys(errors))]
    lines += ["", "## Counts", ""]
    for source in ("X", "i3"):
        subset = [s for s in stalls if s["probe"] == source]
        buckets = [sum(lo <= s["duration_ms"] < hi for s in subset)
                   for lo, hi in ((0, 100), (100, 300), (300, float("inf")))]
        lines.append(f"{source}: {len(subset)} stalls; threshold–100 ms: {buckets[0]}, 100–300 ms: {buckets[1]}, >300 ms: {buckets[2]}.")
    kinds = {"typing": lambda s: s["activity"]["key"] > 0,
             "pointer": lambda s: s["activity"]["motion"] > 0 or s["activity"]["button"] > 0,
             "workspace switch": lambda s: any(e["type"] == "workspace" for e in s["i3_events"]),
             "window move": lambda s: any(e["type"] == "window" and e["change"] == "move" for e in s["i3_events"])}
    lines.append("During activity (categories overlap): " + ", ".join(f"{k} {sum(fn(s) for s in stalls)}" for k, fn in kinds.items()) + ".")
    if not any(s["activity"]["key"] for s in samples):
        lines.append("No raw key presses were observed; typing freezes were not reproduced in this run.")
    lines += ["", "## Ten longest stalls", "",
              "| Time | Probe / ms | Activity | Top 3 CPU (% core) | Swap-ins / major faults | PSI some (cpu/mem/io, ms) | deskd |",
              "|---|---:|---|---|---:|---:|---|"]
    for s in sorted(stalls, key=lambda x: x["duration_ms"], reverse=True)[:10]:
        ss = s["samples"]
        procs = collections.defaultdict(list)
        for row in ss:
            for p in row["top"]:
                procs[(p["comm"], p["pid"])].append(p["cpu_pct"])
        top = sorted(((max(v), name, pid) for (name, pid), v in procs.items()), reverse=True)[:3]
        topstr = ", ".join(f"{name}({pid}) {cpu:.1f}" for cpu, name, pid in top) or "—"
        activity = ", ".join(k for k, fn in kinds.items() if fn(s)) or "none counted"
        fault = sum(x["pgmajfault"] for x in ss)
        swap = sum(x["pswpin"] for x in ss)
        pressure = [sum(x["psi_us"].get(k, 0) for x in ss) / 1000 for k in ("cpu", "memory", "io")]
        d = next((x["deskd"] for x in ss if x["deskd"]), None)
        desk = f"{d['state']} {d['cpu_pct']:.1f}%" if d else "unavailable"
        lines.append(f"| {s['time']} | {s['probe']} {s['duration_ms']:.1f} | {activity} | {topstr} | {swap} / {fault} | "
                     f"{'/'.join(f'{n:.1f}' for n in pressure)} | {desk} |")
    # Top-8 values are the persisted process data. Missing entries count as zero, so
    # these are conservative means for processes that fall below eighth place.
    stall_times = {x["time"] for s in stalls for x in s["samples"]}
    rates = collections.defaultdict(lambda: [0.0, 0.0])
    counts = [0, 0]
    for sample in samples:
        group = 0 if sample["time"] in stall_times else 1
        counts[group] += 1
        for p in sample["top"]:
            rates[p["comm"]][group] += p["cpu_pct"]
    ranking = sorted(((v[0] / max(1, counts[0]), v[1] / max(1, counts[1]), k)
                      for k, v in rates.items()), reverse=True)[:10]
    lines += ["", "## Busy process ranking", "",
              "Mean % of one core in stall samples vs other samples (top-eight entries; absent = 0):", "",
              "| Process | Stall | Outside |", "|---|---:|---:|"]
    lines += [f"| {name} | {a:.2f} | {b:.2f} |" for a, b, name in ranking]
    lines += ["", "## Conclusion", ""]
    if not stalls:
        lines.append("No threshold-crossing stall was captured. This run cannot identify the cause.")
    else:
        inside = [s for s in samples if s["time"] in stall_times]
        outside = [s for s in samples if s["time"] not in stall_times]
        def mean_cpu(group, name):
            return sum(sum(p["cpu_pct"] for p in row["top"] if p["comm"] == name)
                       for row in group) / max(1, len(group))
        x_in, x_out = mean_cpu(inside, "Xorg"), mean_cpu(outside, "Xorg")
        psi_in = sum(s["psi_us"].get("cpu", 0) for s in inside) / max(1, len(inside)) / 1000
        psi_out = sum(s["psi_us"].get("cpu", 0) for s in outside) / max(1, len(outside)) / 1000
        swap_stalls = sum(any(s["pswpin"] for s in x["samples"]) for x in stalls)
        fault_stalls = sum(any(s["pgmajfault"] for s in x["samples"]) for x in stalls)
        deskd_sleep = sum(s["deskd"] and s["deskd"].get("state") == "S" for s in inside)
        lines.append(f"X was delayed far more often than i3 ({sum(x['probe']=='X' for x in stalls)} vs "
                     f"{sum(x['probe']=='i3' for x in stalls)}). Xorg averaged {x_in:.1f}% CPU in "
                     f"overlapping samples vs {x_out:.1f}% outside; CPU PSI was {psi_in:.1f} vs "
                     f"{psi_out:.1f} ms per 100-ms sample. This points to X-server/CPU contention, "
                     "without isolating one client as the cause.")
        lines.append(f"deskd was sleeping in {deskd_sleep}/{len(inside)} overlapping samples; "
                     f"swap-ins occurred in {swap_stalls}/{len(stalls)} stalls and major faults in "
                     f"{fault_stalls}/{len(stalls)}. Memory pressure is a secondary possibility for those episodes.")
        if cpu_pct >= 3:
            lines.append(f"The probe itself used {cpu_pct:.2f}% of a core, so it may have added "
                         "contention; causal attribution is limited.")
    (ROOT / "report.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=15)
    parser.add_argument("--light", action="store_true", help="low-overhead long-running JSONL logger")
    parser.add_argument("--summary", metavar="FILE", help="summarize a light JSONL log")
    args = parser.parse_args()
    if args.summary:
        light_summary(args.summary)
    elif args.light:
        LightProbe(args.minutes).run()
    else:
        Probe(args.minutes).run()
