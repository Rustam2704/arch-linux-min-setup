## Common rules for every audit brief (15.10.2026)
Project: `/home/fanatic/ai/claude/setup` — the owner's long-running "ricing" of this laptop (whitebook:
MacBookPro11,1, Haswell 2c/4t, Iris 5100, 8 GB RAM, 16 GB swap on SSD, Arch, kernel 6.18 LTS, X11,
lightdm autologin → `desktop/system/usr/local/bin/xfce-i3-session` → i3 with every window floating,
our Python daemon deskd (Windows-style window handling), xcompmgr, xfce4-panel with our genmon
scripts, sky-stars wallpaper, osd-daemon, netqd, sysqd). Read first: README.md, ARCHITECTURE.md,
FEATURES.md, MAINTENANCE.md, the newest ~15 entries of CHANGELOG.md (it is long; newest rounds are near
the top of the numbered part, e.g. `## 71 — sleep-mark`), and AUDIT-2026-10-10.md (the previous audit —
do not re-report what it found unless it is still broken; say "still open" then).
Deliberate decisions to respect (do not report them as bugs, but you may say if one costs a lot):
deskd tells i3 a dragged window's position only on release; xcompmgr chosen over picom by
measurement; click-to-focus; all windows floating; UI text in English; one code path per behaviour;
remove dead config fully (no "kept for rollback" leftovers — rollback lives in `lab/journal.tsv`);
UI elements must not jump; small tools must be cheap in RAM/CPU (8 GB laptop).
The sources in `desktop/` are installed by `make apply` (`tools/desktop.py`) into ~/.local, ~/.config,
/etc, /usr/local; every change is journaled by `lab/lab` under an experiment id.

READ-ONLY AUDIT: do not edit any file outside your output file, do not run `make apply`, do not
restart, kill, renice or stop anything, do not touch display :0 (no xdotool/screenshots/input there),
no sudo writes (read-only `sudo journalctl`, `sudo cat` are fine), never `pkill -f`/`pgrep -f`.
Nested X tests are allowed only on Xvfb with a free display number ≥ :50 (not Xephyr — it shows a
window on the owner's screen), with XDG_RUNTIME_DIR set to a short temp dir; kill what you start by PID.

Report format (Russian is NOT required — write English; the coordinator translates): a markdown file
with a table per area: `# | severity | finding | evidence (file:line / command output) | suggested fix
| effort`. Severities: **bug** (visible wrong behaviour or crash), **risk** (can break / leak / race),
**collision** (two mechanisms fight), **dup** (same thing done twice), **cruft** (dead/outdated),
**perf** (measurable CPU/RAM/IO/wakeup waste — give numbers), **ux** (works, could be better).
For every finding say how sure you are: verified (ran/measured/traced) or inferred (read only).
End with "Top 5 by value/effort" and "What I did not cover".
