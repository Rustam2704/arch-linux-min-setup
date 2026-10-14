# Task: turn xstall.py into a light long-running stall logger and start it

## Context
`/home/fanatic/ai/claude/setup/tools/xstall/xstall.py` (yours, earlier today) ran 15 min at 13 % of a
core and caught no owner activity. Make a light mode that can run for hours while the owner works.

## Change
Add `--light` (keep the full mode working):
- X round trip every 50 ms (threshold 60 ms), i3 GET_VERSION every 250 ms (threshold 80 ms).
- XI2 raw event counts (keys, buttons, motion) per 100 ms kept in a ring buffer (last 3 s); never key
  codes. i3 `workspace`/`window` events kept in a 3-s ring buffer.
- NO periodic all-process scan. Instead keep a cheap 1-s background record of: Xorg, xcompmgr, i3,
  deskd, sky-stars, xfce4-panel CPU (fixed PIDs, re-resolved every 60 s), /proc/vmstat pswpin and
  pgmajfault, PSI totals, sci count. When a stall starts, take ONE full /proc scan (top 8 by CPU
  over the last second, using a snapshot taken every 1 s only of pids with nonzero CPU last time —
  your call, but total probe CPU must be < 2 % of one core), and log the stall with: duration,
  activity counts in ±1 s, i3 events in ±2 s, the cheap record, the top 8.
- Additionally log per minute: count of stalls, max latency, activity totals (so idle vs active
  minutes can be compared).
- Output: `./logs/light-<date>.jsonl`. Add `--summary <file>` that prints: stalls per active
  minute vs idle minute, durations histogram, stalls during typing / pointer motion / workspace
  switch / window move, and the processes most over-represented in stalls vs the 1-s background.

## Run
Measure its own CPU over 2 minutes first (must be < 2 %; if not, lower the rates and say so).
Then start it detached for 3 hours so it survives your exit:
`systemd-run --user --unit=xstall-light --collect -p CPUQuota=5% -p MemoryMax=150M /usr/bin/python3 /home/fanatic/ai/claude/setup/tools/xstall/xstall.py --light --minutes 180`
(adjust the env: it needs DISPLAY=:0 and I3SOCK or the i3 socket path; pass them with
`-E DISPLAY=:0 -E I3SOCK=...`). Verify it is running and writing (`systemctl --user status xstall-light`),
then finish. Do not wait for it.

## Do not
No sudo; do not kill/stop/renice/focus/move anything; no screenshots; no input; no grabs; never
record key codes; never `pkill -f`/`pgrep -f`; edit only files in tools/xstall/.

## Final message (under 25 lines)
Measured own CPU, the exact unit name and log path, how to stop it, how to get the summary.
