# Task: make deskd cheap on the hot paths (drag, resize, workspace switch, periodic scans) + no frame on notifications

## Context
The owner's desktop jerks during window drag and workspace switching; typing sometimes freezes.
A static review (yours, earlier today) found these deskd issues — fix them:
1. `recheck_strips()` every 20 s (deskd.py ~692): two unbounded `xfconf-query` subprocesses + X tree
   walk with per-window round trips, even during a drag. → Cache panel window ids/geometry, re-scan
   only on real change signals (panel window created/destroyed/configured, xfconf channel change
   if cheap to watch, or at most every 20 s but only when the cached ids are gone), never during a
   drag/resize; subprocess timeouts (2 s).
2. Workspace switch (deskd.py ~1198, refresh ~1366): several serial i3 queries + full refresh +
   second render. → One i3 snapshot per switch (tree + workspaces + outputs fetched once and
   passed down), strip rendered once, window-control rebuild deferred/coalesced into one GLib idle.
3. `sync_strips`/handle restacking (~1628) and `raise_focused()` (~1398): ~8 ConfigureWindow per
   floating window on every refresh even when unchanged; per-frame GetWindowAttributes. → Keep
   last applied geometry/stack per handle and send requests only on change; one stack snapshot.
4. Event pump (~1111): every queued MotionNotify handled; veil repaint uploads 0.68 MB per
   hovered-region change (~518). → Compress motion (only the latest pending motion per window per
   pump), cap batch size per pump, repaint the veil only for the changed region or reuse pixmaps.
5. Edge resize (~1828): an i3 command round trip every 30 ms. → Move the X frame directly during the
   gesture (as title-bar drag already does) and commit one i3 resize on release; if that breaks
   i3's view of the window, keep i3 commands but never more than one in flight.
6. Title-bar drag start (~3019, ~2158, ~2259): full tree fetched twice + panel scan. → Reuse the
   tree, use cached strip geometry.
7. Notifications: `for_window [all] floating enable, border normal 2` in i3 config gives
   xfce4-notifyd windows (type notification) a title bar, and `sync_strips` (~1586) adds the
   min/max/close dots, so a notification pops in twice. At deskd.py ~1170 treat windows with
   `window_type == "notification"` like windows that draw their own frame (border none, no strip,
   no handles, never clamped/moved/raised by deskd beyond what i3 does). A tested one-line version
   of that condition exists in
   /tmp/claude-1000/-home-fanatic/614f9629-afe8-4732-8a6d-898c41e15ffb/scratchpad/notify/deskd2/ (diff it).

## Working root and files
Edit ONLY the sources in the setup project: `/home/fanatic/ai/claude/setup/desktop/share/deskd/`
(deskd.py, panels.py, switcher.py) and, if needed, `/home/fanatic/ai/claude/setup/desktop/share/sky-desktop/i3ipc.py`
(check where i3ipc.py lives in `desktop/`). Tests: `/home/fanatic/ai/claude/setup/tests/`.
Do NOT edit the installed copies in ~/.local, do NOT run `make apply`, do NOT restart the live deskd,
do NOT touch display :0 (no xdotool/screenshots there). Nested tests only: `make test` and
`make test-deskd` (Xephyr :9) in /home/fanatic/ai/claude/setup. Do not git commit.

## Acceptance
- `make test` and `make test-deskd` pass (run before and after; report both).
- Measure, on the nested X server, X requests and i3 IPC calls deskd issues for: one workspace
  switch with 5 floating windows; a 2-second title-bar drag; a 2-second edge resize; one idle
  minute. Count by wrapping python-xlib's `Display.send_request`/i3ipc calls in a test harness
  (do not leave instrumentation in deskd), before (git stash or a copy of the original) and after.
  Report a table.
- Behaviour unchanged otherwise: drag snapping, maximize/half/quarter, Alt+Tab, workspace strip
  clicks, title buttons — covered by deskd_smoke; add smoke cases for notification windows (no
  strip, border none) and for resize commit-on-release.

## Final message (English, under 60 lines)
What changed per item (file:line), the before/after table, test results, anything you chose not to
do and why, risks the owner might notice.
