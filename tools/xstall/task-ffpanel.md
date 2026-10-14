# Task: a newly opened Firefox window ends up over the panel — reproduce, find the cause, fix

## Live facts (15.10 ~01:10, owner's screen; do not touch it)
A Firefox Developer Edition window opened (session restore / new window) and covered the xfce4-panel
(top 66 px dock). i3 tree afterwards: the window con has mark `_deskd_max_<id>` (deskd maximized it),
its floating_con parent rect is (0,67,2560,1533) — correct — but the child con rect is (0,0,2560,1600)
and window_rect (3,32,2554,1565); the i3 frame X window is 0,0 2560x1600. WM_NORMAL_HINTS: min/base
957x180, gravity NorthWest; no _NET_WM_STATE. A further `i3-msg '[con_id=..] resize set 2560 px 1533 px,
move position 0 px 67 px'` did not change the child rect while its workspace was hidden.
Suspect: round 66 (commit 914ce29) changed `clamp_floating` (deskd.py ~2604) — new near-fullscreen windows
now wait 200 ms (`settle_fullscreen`) before `maximize()`; before 914ce29 they were maximized at once.
Other suspects: fit()/fit_floating() (~2153-2210), Firefox's own ConfigureRequests after map, i3's
render of hidden workspaces.

## Do
Repo `/home/fanatic/ai/claude/setup`, deskd source `desktop/share/deskd/deskd.py`; nested harness:
`tests/deskd_smoke.py` / `make test-deskd` (Xephyr :9). Reproduce on a nested X server with a panel-like
dock (66 px) and i3 (owner's config copy without exec lines, like the smoke test does):
1. A real Firefox window: `firefox-developer-edition --no-remote --profile <fresh temp profile under
   ./work/ff>` with `user.js` making it open maximized/at screen size (e.g. xulstore sizemode maximized,
   or `--window-size 2560,1600` / screen-size window), on DISPLAY of the nested server; also a synthetic
   client that maps at 0,0 screen size, min size 957x180, then sends ConfigureRequests (same size,
   or position 0,0) at 20/100/250/400 ms after map.
2. Compare current deskd vs `git show 2b87e79:desktop/share/deskd/deskd.py` (pre-66) — does the
   window end up over the dock (i3 child con rect / X frame geometry overlapping y<66)?
3. Find the cause (file:line) and fix it in the source so a maximized new window always ends inside the
   work area (frame below the dock), without bringing back periodic polling and keeping the rule that
   deskd tells i3 a dragged window's position only on release. Add a smoke case for it.
`make test` and `make test-deskd` must pass. Do NOT restart the live deskd/panel, no `make apply`, no
display :0, no commit, never `pkill -f`/`pgrep -f`; kill what you started by PID.

## Final message (under 30 lines)
Repro result old vs new, root cause, fix (file:line), tests.
