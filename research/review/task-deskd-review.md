# Task: bug hunt in deskd (a Windows-style floating window layer on top of i3 4.25)

## Goal
Find real bugs - wrong behaviour a user would notice - in
`/home/fanatic/ai/claude/setup/desktop/share/deskd/deskd.py` (~3100 lines, Python 3,
python-xlib, GLib, i3 IPC) and `switcher.py`, `panels.py` next to it. Read the WHOLE files.

Known bug class already found (use it as a model, and look for every other instance):
resize handles stored the id of i3's *floating_con wrapper* (`fl["id"]` in `sync_handles`)
and later ran `[con_id=<that id>] move position ...`; i3 refuses position changes on the
wrapper ("not floating"), so dragging a left/top edge grew the window to the right/bottom,
and `unfit()`/`set_saved()` used the wrong id, so a maximized window resized by hand kept its
`_deskd_max_<id>` mark. In i3's tree a floating window is `floating_con` (type
"floating_con", no window) -> `con` (has "window", carries the marks); deskd's marks and
saved state are keyed by the inner con id.

Look especially for:
1. Any other place mixing floating_con ids and window con ids (marks, saved state,
   commands, focus_order, comparisons).
2. i3 commands that i3 will refuse or misinterpret (check against i3 4.25 semantics:
   `move position` only on floating cons, workspace numbers <= 0 such as the scratchpad's -1,
   criteria on wrong ids, commands chained with `,` vs `;`).
3. Stale state: cached trees/geometry used after they changed; state keyed by ids that
   change; things never cleaned up (memory growth over days).
4. Geometry mistakes: frame vs client size (title bar + borders), multi-monitor coordinates,
   negative coordinates, rounding, off-by-one at screen edges, rects from a screen that is
   no longer connected (saved restore rects).
5. Event-handling races: GLib timeouts firing after the window closed, double handling,
   handlers that raise and kill a GLib timer (a callback returning None vs False/True).
6. Python errors on rarely used paths (None dereferences, KeyError, wrong argument counts).

## Working root
Read-only on the source. Write only `/home/fanatic/ai/claude/setup/research/review/deskd-review.md`.

## Output
`deskd-review.md`: a numbered list of findings, most severe first. Each: file:line, what the
code does, the concrete user-visible failure scenario (steps -> wrong result), confidence
(high/medium/low), and a suggested fix in 1-3 lines. No style nits, no refactoring ideas,
no speculative "could be cleaner". 10-40 findings. Do not include the known resize-handle
bug above.

## Do not
Do not edit any source file. Do not run deskd or i3. Do not touch the user's session.

## Final report
Path of the file and the count of findings by confidence.
