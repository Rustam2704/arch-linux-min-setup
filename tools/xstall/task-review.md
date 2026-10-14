# Task: review deskd for anything that blocks or delays standard desktop operations

## Goal
The owner's desktop freezes briefly during typing, window drag and workspace switching, then
catches up. CPU looks fine. deskd is a ~3200-line Python daemon that handles window drag/resize
(it moves frames itself), workspace switching side effects, the panel workspace strip, Alt+Tab,
title-bar buttons, overlays (fire digit animation, pentagram, veil). Find code paths that can
stall the X server, i3, or deskd's own event handling.

## Read
`/home/fanatic/.local/share/deskd/deskd.py`, `switcher.py`, `panels.py`,
`/home/fanatic/.local/share/sky-desktop/i3ipc.py` (and other modules there that deskd imports),
`/home/fanatic/.config/i3/config`. Also `/home/fanatic/.local/bin/sky-stars` (a star animation
window under all windows) and `/home/fanatic/.local/bin/netqd` if referenced. Read-only: the
installed copies are the same as the setup project's `desktop/` sources.

## Look for (with file:line)
- X server grabs (`grab_server`, `GrabPointer`/`GrabKeyboard`, sync grab modes, `allow_events`) and
  how long they can be held.
- Synchronous X round trips in hot paths (per MotionNotify during drag, per i3 event): `query_pointer`,
  `get_geometry`, `get_property`, `query_tree`, `sync()`; how many per event.
- i3 IPC calls per event (`get_tree` is heavy: how often is it called per drag / per workspace
  switch?), and whether deskd waits on i3 while i3 waits on deskd (`nop` bindings round trip).
- Motion handling: is motion compressed (only the latest MotionNotify processed) or is every event
  processed with i3 commands; timers (GLib timeouts) firing during drag.
- subprocess calls or file I/O on the event path; json writes of state files per event.
- Redraws: full-window cairo repaints / big PutImage uploads per event or per animation frame
  (fire digits, panel strip), any per-frame work that scales with screen size (2560x1600).
- Anything that could make one slow step delay all following input (single-threaded loop doing
  blocking work).
- Same questions for sky-stars on every i3 event (it reads the i3 tree to know what is covered).

## Output
Final message (English, under 70 lines): a ranked list of findings, each: file:line, what happens,
when (which operation), estimated cost per event (count round trips / requests), why it can cause a
visible freeze, and a concrete fix. Mark how confident you are. Do not edit any file.
