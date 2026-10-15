# Fix task B1: daemons, panel scripts, small apps (audit `research/audit-2026-10-15/b-daemons.md`)
Rules: `tools/audit/fix-common.md`. Files you may edit: `desktop/bin/*` EXCEPT deskd-ctl,
deskd-favorites, light-year; `desktop/share/sky-desktop/*.py` EXCEPT i3ipc.py; `desktop/config/systemd/user/*`;
docs lines about these.
Fix: B1, B2, B4, B5, B6, B7, B8, B9, B10, B11, B12, B13, B29; B14 only the low-risk part (one shared
helper for "fixed-width digits with transparent zero padding" and one for "atomic write only if changed",
used by sysqd/netqd/panel-battery — keep visual output byte-identical; verify by rendering before/after
outputs for a set of values); B27: delete `desktop/bin/audio-menu` and its doc references (check nothing
calls it: grep desktop/ and the live ~/.config, ~/.local/share/applications); B28: check live references to
`app-focus-or-launch` (grep ~/.config ~/.local/share/applications /usr/share/applications for it, read-only);
if none, delete it and its doc references, else report where it is used. B3: skip (keep the poll).

## Added from the runtime audit (`research/audit-2026-10-15/c-runtime.md`, `d-config.md`, `e-research.md`)
- C10 + e-research idea 3: replace the 5-second `panel-telegram` poll (Python + xdotool every 5 s ≈ 2.4 % of a
  core) with push: listen on the session bus for Telegram's `com.canonical.Unity.LauncherEntry` `Update`
  signal (count / count-visible) — in an existing long-running daemon (osd-daemon already owns a GLib loop and
  D-Bus; or sysqd) — write the panel markup file atomically only on change and `xfpanel.refresh` the plugin;
  `panel-telegram` becomes a reader that prints the ready file; keep its click behaviour and today's look
  (number, accent, offline icon when Telegram is not running — detect Telegram start/exit via NameOwnerChanged
  or the window list the daemon already has, no polling); genmon period → 60000 in `desktop/xfconf/xfce4-panel.xml`
  (you may edit that file only for this period). Verify the signal really exists by reading Telegram Desktop
  sources/docs (do not touch the live Telegram); if it does not, report and leave the poll but make it cheap
  (shell + cat of a file the daemon writes).
- C11: `xfpanel.plugin_ids()` spawns `xfconf-query` up to every 10 s in each of deskd, osd-daemon, sysqd, netqd;
  sysqd re-queries all the time. Cache it per process and invalidate only on a panel restart signal or on a
  failed refresh (you may edit `desktop/share/sky-desktop/xfpanel.py`; deskd uses it too — keep its API).
- C12: `panel-clock` and `panel-net` (1 Hz): avoid fork+exec where the shell can do it with builtins
  (`read -r` from a file instead of `cat`, no `date` fork if the clock text can come from a daemon file or
  shell builtin `printf '%(%H:%M)T'` in bash); keep output byte-identical.
- C4: osd-daemon logs every `screensaver: inhibit/uninhibit` (582 lines/boot) — log only state changes of the
  whole inhibition (first inhibitor in / last out), not each call.
- A2 (d-config): unit files `deskd.service`, `osd.service`, `sky-stars.service` claim
  `After=/WantedBy=graphical-session.target`, which is never active (they are started by i3 `exec`). Make
  the units describe the real wiring (no misleading WantedBy; `PartOf`/`After` only if true).
