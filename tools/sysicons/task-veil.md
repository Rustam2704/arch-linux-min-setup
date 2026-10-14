# Task: deskd does not recreate its panel veil after the panel restarts

Live repro (done by the coordinator, 15.10 00:40): `xfce4-panel -q`, then `i3-msg 'exec --no-startup-id xfce4-panel'`.
The panel came back, but deskd's veil (override-redirect window class `deskd`, 0,0 2560x67, above the
panel; the darkening with a "hole" under the pointer) was NOT recreated — the panel stayed undimmed;
`journalctl --user -u deskd` showed nothing. Restarting deskd fixed it. Before yesterday's optimization
(commit 914ce29 "deskd hot paths cheaper", your work) the 20-second `recheck_strips` timer re-found the panel;
now rechecks run only on panel events (`schedule_recheck(150)` on dock `new`/`close` i3 events,
`check_panel_ids` fallback).

Source: `/home/fanatic/ai/claude/setup/desktop/share/deskd/deskd.py` (+ panels.py, sky-desktop i3ipc.py).
Find why the restart was missed (which events arrive when the panel quits and starts: i3 window events
for a dock? X DestroyNotify/CreateNotify of the panel windows? does recheck create veils at all, or are
veils created elsewhere, e.g. on startup only?) and fix it so that after a panel restart the veil, the
workspace click layers and the strip all come back within ~1 s, without reintroducing periodic polling
(the cheap `check_panel_ids` fallback may stay). Also cover `xfce4-panel -r`. Add a smoke test if the
nested harness can run a dock window that disappears and reappears (simulate the panel with a dock-type
window if xfce4-panel cannot run nested).
Rules: edit only setup sources/tests; `make test` and `make test-deskd` (nested Xephyr :9) must pass;
do NOT restart the live deskd or panel, no `make apply`, no display :0, no commit.
Final message (under 25 lines): root cause (file:line), the fix, tests.
