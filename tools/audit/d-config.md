# Audit D: configuration collisions, packages and documentation drift
Include `common.md` rules (read it: /home/fanatic/ai/claude/setup/tools/audit/common.md).
Output: `/home/fanatic/ai/claude/setup/research/audit-2026-10-15/d-config.md`.
1. Declared vs installed: run `make status` and `make diff` in the project (read-only commands; if
   `make diff` triggers `build` that writes only into the project's build dir, that is fine) and report
   every drift (file differs, file missing, extra file installed but no longer declared).
2. Packages: `packages.txt` / `packages-aur.txt` vs `pacman -Qe` (explicit packages not declared),
   orphans `pacman -Qdtq`, packages installed by `lab pkg` for finished experiments (`lab/journal.tsv`
   action pkg; e.g. 51-friend-arch-stick: archiso, qemu-base, edk2-ovmf; olx-lab tools), packages of
   removed features (picom? xfce4-appfinder? fastcompmgr?), their sizes (`pacman -Qi` Installed Size).
3. Key/gesture collisions: every binding in `~/.config/i3/config` (and generated includes), xfconf
   `xfce4-keyboard-shortcuts` (`xfconf-query -c xfce4-keyboard-shortcuts -lv`), touchegg
   (`~/.config/touchegg/touchegg.conf`), kitty (`kitty.conf` map lines), Thunar accels, deskd chords,
   osd-daemon key handling, rofi. Build one table key → owners; report every key with 2+ owners, and
   bindings that call scripts/commands that no longer exist.
4. Autostart: i3 `exec`/`exec_always`, `xfce-i3-session`, `~/.config/autostart` (dex), systemd user units
   enabled (`systemctl --user list-unit-files --state=enabled`), XDG autostart in /etc/xdg/autostart
   that dex might run; anything started twice or started but unused.
5. Theming/env: environment.d, GTK2/3/4 settings (`gtk-3.0/settings.ini`, xsettings in xfconf, gtk-4.0),
   Qt (QT_QPA_PLATFORMTHEME), cursor theme/size consistency, fontconfig, DPI (Xresources, xsettings,
   144 dpi) — mismatches between toolkits; `mimeapps.list` handlers that point to missing .desktop files.
6. Docs drift: pick 15 concrete claims from FEATURES.md and ARCHITECTURE.md (bindings, periods, file
   paths, plugin ids, services) and check each against the code/config; report every false one.
   Also stale references to removed things (picom, i3-mouse-resize, panel-sys 2 s period, eDP-1, etc.).
