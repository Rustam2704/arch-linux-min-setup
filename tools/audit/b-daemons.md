# Audit B: the other daemons, panel scripts, apps and the installer
Include `common.md` rules (read it: /home/fanatic/ai/claude/setup/tools/audit/common.md).
Output: `/home/fanatic/ai/claude/setup/research/audit-2026-10-15/b-daemons.md`.
Scope: `desktop/bin/*` except deskd-ctl/deskd-favorites (osd-daemon, netqd, sysqd, sky-stars, panel-*,
open-path, snip, paste-image, firefox-limited, firefox-mem, telegram-toggle, app-focus-or-launch,
power-menu, root-black, rofi-toggle, audio-menu, net-menu, light-year, sky-edit, i3-cheatsheet, osd);
`desktop/share/sky-desktop/*.py` (sky_theme, sky_text, xfpanel, sysicons, netmenu, powermenu, …);
`desktop/share/light-year/` (app.py, api.py — find out what it is and audit it); systemd user units in
`desktop/config/systemd/user/`; `tools/desktop.py`, `lab/lab`, `lab/rollback.py`, `Makefile`, `tests/`.
Look for: bugs and unhandled errors (missing files, network down, no battery, second monitor, D-Bus
gone), resource waste (polling loops, subprocess per tick, Python start-ups per genmon tick — list every
genmon plugin with its period and cost; files rewritten every tick; wakeups), duplicated code that should
share one path (e.g. the "value()"/padding helpers, theme colour lookups, refresh helpers), stale or
dead code and files, race conditions on files in $XDG_RUNTIME_DIR (partial writes read by genmon: is
every writer atomic?), security-irrelevant but correctness-relevant shell quoting, installer edge cases
(what `tools/desktop.py apply` does with deleted sources, permissions, xfconf types, rollback
correctness — e.g. a file installed for the first time then rolled back; directories), tests that do not
test what they claim. Measure where cheap: CPU of each daemon over 60 s from /proc (read-only).
