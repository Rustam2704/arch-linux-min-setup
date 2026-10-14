# Task: passive stall probe for the live desktop (find what freezes typing, drag and workspace switching)

## Goal
The owner's X11 desktop (display :0, i3 + our Python daemon deskd + xcompmgr + xfce4-panel) has
short freezes: typed text stops appearing and then catches up all at once; window drag and
workspace switching jerk. CPU and RAM look fine. Build a PASSIVE probe that runs for 15 minutes
while the owner works normally, catches every freeze, and shows who was busy at that moment.
Do not assume Zoom or RustDesk are the cause; record them like everything else.

## Working root
`/home/fanatic/ai/claude/setup/tools/xstall/`. Script: `xstall.py`. Outputs:
`./logs/samples.jsonl`, `./logs/stalls.jsonl`, report `./report.md`.
Python: system `python3` with python-xlib (`from Xlib import display`) — installed.
i3 IPC: `/home/fanatic/.local/share/sky-desktop/i3ipc.py` (read it; or talk the i3 socket from `i3 --get-socketpath` yourself).

## What the probe does (all at once, one process, threads ok)
1. **X responsiveness:** its own X connection to :0; every 20 ms a round trip
   (`d.get_input_focus()`); record the latency. Latency > 40 ms = a stall: log start, duration.
2. **i3 responsiveness:** every 100 ms an i3 IPC `GET_VERSION` round trip; > 50 ms = i3 stall.
3. **deskd responsiveness:** deskd is `/usr/bin/python3 /home/fanatic/.local/share/deskd/deskd.py`
   (find its PID by reading /proc/*/cmdline, never `pgrep -f`). Record its state (R/S/D) and CPU every
   100 ms; also record its `/proc/<pid>/status` VmSwap and its `voluntary/nonvoluntary_ctxt_switches`.
4. **Who is busy (every 100 ms):** per-process CPU delta (utime+stime from /proc/<pid>/stat) for
   all processes; keep the top 8 per sample with comm and PID; plus /proc/vmstat `pswpin` and
   `pgmajfault` deltas, /proc/pressure/{cpu,memory,io} `some total` deltas (microseconds stalled),
   ACPI `/sys/firmware/acpi/interrupts/sci` delta, CPU MHz of each core (`/proc/cpuinfo` or
   cpufreq `scaling_cur_freq`), package temperature (`/sys/class/thermal/*` or hwmon coretemp).
5. **What the owner was doing (counts only, never key codes or text):** XInput2 raw events on the
   root window via the XI extension (python-xlib `xinput` — `XI_RawKeyPress`, `XI_RawButtonPress`,
   `XI_RawMotion`); count per 100 ms. If XI2 raw events are not available in python-xlib, poll
   `query_pointer` every 50 ms for motion and skip key counts; say so.
   Subscribe to i3 events `workspace` and `window` (move/focus/new/close) and log them with time.
6. For every stall (X > 40 ms or i3 > 50 ms) write one line in stalls.jsonl: time, duration, which
   probe saw it, the owner's activity counts in the surrounding 500 ms, the i3 events within ±1 s,
   and the 100-ms samples covering the stall (top processes, swap-ins, major faults, PSI deltas,
   sci delta, deskd state).
7. Run 15 minutes (`--minutes 15`), sampling overhead must stay under 3 % of one core (measure
   the probe's own CPU and report it). Flush logs every second.

## Report (report.md and your final message, English, under 60 lines)
1. Method + anything not possible.
2. Stall count and distribution (X / i3, durations: 40-100, 100-300, >300 ms), and how many
   happened during owner activity (typing / pointer / workspace switch / window move).
3. For the 10 longest stalls: time, duration, activity, top 3 busy processes with CPU, swap-ins,
   major faults, PSI, deskd state.
4. Which process(es) are busiest across all stalls vs. their average outside stalls (a ranking).
5. Your conclusion: the most likely cause(s), with the numbers that support it.

## Do not
- No changes to any file outside the working root. No sudo. Do not kill, stop, renice, focus,
  move or start anything; no screenshots; do not send input; do not grab keyboard or pointer.
- Never record key codes or typed text.
- Never use `pkill -f`/`pgrep -f`.
