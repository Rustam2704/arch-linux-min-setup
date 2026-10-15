# Task C-deskd: global Alt+Tab and bigger resize handles (owner request 15.10.2026)

Project `/home/fanatic/ai/claude/setup`. Read `tools/audit/common.md` (context and deliberate design
decisions to keep — e.g. a dragged window's position goes to i3 only on release; do not change that),
then `ARCHITECTURE.md` (deskd section, Alt+Tab and resize handles) and the CHANGELOG entries that
mention Alt+Tab and resize handles (`grep -n "Alt+Tab\|ручк\|HANDLE" CHANGELOG.md`).

Files you may edit: `desktop/share/deskd/deskd.py`, `desktop/share/deskd/switcher.py` (only if needed),
`desktop/config/i3/config` (only the Alt+Tab comment), `tests/deskd_smoke.py`, `tests/deskd_bench.py`,
the lines about these two behaviours in `ARCHITECTURE.md`, `FEATURES.md` and the Super+/ cheatsheet
source (find it: `grep -rn "Alt+Tab" desktop/`). Do NOT edit CHANGELOG.md (the coordinator writes it).

## 1. Alt+Tab becomes global
Today `Deskd.cycle()` (deskd.py ~3640) lists only the focused workspace's windows plus the windows
minimized from it, and the `workspace` focus event cancels a running round (`cancel_round`, ~1428).
The owner changed their mind: Alt+Tab must walk **all** windows on **all** workspaces of all screens,
so it can jump to another workspace.
- List: every managed window (leaf with `window`, type not in `NO_SWITCH_TYPES`) on every real
  workspace (skip i3's internal `__i3*` workspaces) on every output, plus every minimized window
  (`MARK_MIN`) wherever it was minimized from, still skipping a minimized dialog whose owner is
  minimized (`minimized_owner`) — the dialog comes with its window, as today.
- Order: most recently used first (`focus_order`), as today; windows never focused go after, in tree
  order. The first Alt+Tab still goes to the previous window; a focused notification is still not in
  the list.
- Picking a window on another workspace switches to that workspace with the window focused and raised
  (i3 `[con_id=..] focus` does the switch; check that deskd's per-screen workspace blocks, the panel
  strip and the "fitted window" repair all end up right). A minimized window picked from another
  workspace comes back on **its own** workspace (where it was minimized), and that workspace is shown —
  check what `unminimize()` does today and make it so if it differs.
- A workspace change while Alt is held no longer cancels the round (the list is global now). Remove the
  cancel and `cancel_round()` if nothing else uses it (no dead code). Keep `drop_from_round`.
- The switcher stays as it is (same look, centred on the focused screen's work area). No new UI.
- Update the docstrings/comments that say "this workspace" (module docstring, `cycle`, i3 config comment
  at `desktop/config/i3/config:109`, ARCHITECTURE/FEATURES, cheatsheet).

## 2. Resize handles: bigger outside, same overlap inside
`sync_handles()` (deskd.py ~1957) builds 8 input windows around every floating frame: edges `HANDLE`
(10 px) thick and four `HANDLE`×`HANDLE` corner squares, all **outside** the frame rect, clipped to the
work area. The owner wants:
- edge strips **15 px** thick (+50 %), growing outward only;
- corner squares **20×20 px** (2×), their inner corner exactly at the frame's corner, growing outward
  only (so a corner is `(x-20, y-20, 20, 20)` for top-left, and so on);
- the part that lies on the window itself must stay exactly as it is now (today: nothing inside the
  frame rect) — the frame's own area must not get any new handle pixels.
Use two named constants (edge thickness, corner size) instead of `HANDLE`, with a comment each. Check
every other use of the thickness (hit tests, drag start, snapping, the handle pool keys in
`pick_handles`, the bench/test expectations) and keep them consistent. Clipping to the work area and
the "no handles for a maximized edge / full-screen workspace" rules stay.

## Tests (required)
- `make test` must pass.
- Extend `tests/deskd_smoke.py` with checks for both changes: (a) two windows on workspace 1 and one on
  workspace 2 (plus one minimized on workspace 2): from workspace 1, Alt+Tab rounds reach the
  workspace-2 windows; releasing on one shows workspace 2 with it focused; the minimized one comes back
  on workspace 2; a round still works after a workspace change mid-round. (b) handle geometry: the edge
  handle covers 15 px outside each edge, the corner handle 20×20 outside each corner, and no handle
  covers any pixel inside the frame.
- Run `make test-deskd` (Xephyr :9 — allowed for this harness only) up to 3 times; report pass counts.
- Run `tests/deskd_bench.py` once; report the request counts next to the last ones you find in
  CHANGELOG (round 73: workspace switch 127).
- Do not run `make apply`, do not restart or touch the live session / display :0, do not commit, never
  `pkill -f`/`pgrep -f` (kill what you start by PID).

## Final message (English, under 50 lines)
What changed (file:line), how the minimized-window case works now, test and bench results, anything the
coordinator must do when applying (deskd restart etc.), anything you decided not to do and why.
