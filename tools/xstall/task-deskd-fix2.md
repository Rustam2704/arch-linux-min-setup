# Task: fix review findings in your uncommitted deskd optimization

## Working root
`/home/fanatic/ai/claude/setup` — the uncommitted changes in `desktop/share/deskd/deskd.py`,
`panels.py`, `tests/deskd_smoke.py`, `tests/deskd_bench.py` are yours from the previous task
(`tools/xstall/task-deskd-fix.md`). Same rules: edit only these sources/tests, no `make apply`, no live
deskd restart, no display :0, no commit. Do not touch `desktop/bin/sky-stars` (another agent's change).

## Fix
1. CRITICAL `recheck_strips` (deskd.py ~938-968) still `return True`, but it is now scheduled as a
   one-shot via `idle_add` (~1944, ~2549), `timeout_add(150)` (~1239) and `timeout_add_seconds(2)`
   (~947) → endless loops (xfconf-query in a tight cycle). Make every scheduling one-shot (return
   False), and guard against stacking several pending rechecks (one pending id at a time).
   Add a smoke/unit test that would have caught it (e.g. count calls after one scheduling).
2. The workspace-click layer is never re-raised above the panel (~2793, show_layer ~2766-2778
   returns early when visibility unchanged). Re-raise it (stack_mode=Above) on every recheck and
   when the panel frame is restacked/configured (you already get panel X events).
3. REVERT item 5 (edge resize preview on the X frame + one commit on release) to the original
   behaviour from `git show HEAD:desktop/share/deskd/deskd.py` (live `resize set`/`move position`
   through i3 every 30 ms) — the frame-only preview shows a black gap and the content jumps on
   release; the owner's "tell i3 only on release" rule is for title-bar DRAG and stays as it is.
   Keep a guard so at most one resize command is in flight. Also undo the early returns on
   `self.resizing` in `refresh`/`refresh_controls` if they were added only for the preview; if they
   stay, end the gesture when the button is found up (pointer mask check in the 30 ms tick) so a lost
   ButtonRelease cannot freeze refreshes. Remove the resize-commit smoke case or adapt it.
4. `strip_view` (~2959): fall back to `plugin_geometry` when `strip_geoms` is empty, so dropping a
   window on a workspace number works right after a panel restart.

## Acceptance
`make test` and `make test-deskd` pass. Re-run `tests/deskd_bench.py` and report the updated table
(workspace switch / drag / resize / idle minute). `python3 -m py_compile` on the changed files.

## Final message (under 30 lines)
Per fix: what changed (file:line). Test results. The table.
