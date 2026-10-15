# Audit A: deskd, the window engine, and i3
Include `common.md` rules (read it: /home/fanatic/ai/claude/setup/tools/audit/common.md).
Output: `/home/fanatic/ai/claude/setup/research/audit-2026-10-15/a-deskd.md`.
Scope: `desktop/share/deskd/deskd.py` (3464 lines, heavily changed 14–15.10: rounds 66, 68, 69 —
`git log -p --since=2026-10-13 -- desktop/share/deskd`), `panels.py`, `switcher.py`,
`desktop/share/sky-desktop/i3ipc.py`, `desktop/config/i3/config` (+ generated parts), `desktop/bin/deskd-ctl`,
`desktop/bin/deskd-favorites`, `tests/deskd_smoke.py`, `tests/deskd_bench.py`.
Look for: logic bugs, races between i3 events and X events, stale caches (panel ids, strip geometry,
workspace snapshots, `_held`, `layer_visible`, handle caches) after panel restart / monitor change /
i3 restart, leaks (X windows, pixmaps, GCs, GLib sources, dict entries that grow per window and are
never pruned — check every dict keyed by window/con id for cleanup on close), exceptions swallowed
silently, recursion between refresh paths, multi-monitor paths (`BLOCK` workspaces, eDP1/HDMI2 names —
the intel driver now names outputs without a dash), anything that can crash i3 (the journal shows 7 i3
segfaults on 14.10 21:11–21:16 — correlate with which i3 commands deskd sends; `coredumpctl list i3`
and `coredumpctl info <pid>` are read-only), Alt+Tab switcher edge cases, the notification-window
handling added in round 66.
Also: the deskd smoke test has a flaky check "a keep-above window stays over the focused one" (failed
2/6 runs on 15.10). Find why (test or code). You may run `make test-deskd` (it uses Xephyr :9 — allowed
for this one harness only) at most 3 times.
