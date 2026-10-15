# Task C-media: media keys control whatever is playing now (owner request 15.10.2026)

Project `/home/fanatic/ai/claude/setup`. Read `tools/audit/common.md` (context, deliberate decisions),
the `lab/lab` header (journal commands), `MAINTENANCE.md`, and how user services are started in this
setup (`desktop/config/systemd/user/*.service`, `desktop/system/usr/local/bin/xfce-i3-session`,
`grep -n "exec\|systemctl" desktop/config/i3/config`). Experiment id: **`76-media-keys`**.

Goal: Fn+F7 / Fn+F8 / Fn+F9 on this MacBook (`hid_apple fnmode=2`; they send `XF86AudioPrev`,
`XF86AudioPlay` (keycode 172, shifted `XF86AudioPause`) and `XF86AudioNext` — check with `xmodmap -pke`)
must control **the player that is playing now / was used last** (YouTube or any media in Firefox,
Telegram's player, mpv, …) through MPRIS. The owner said: "the current playback must really be caught
and controlled" — so not "the first player on the bus".

Plan (adjust if the docs say otherwise, and say why):
1. `lab/lab pkg 76-media-keys playerctl` (extra, ~450 KB).
2. `playerctld` (ships with playerctl) tracks the most recently active player; with it running,
   `playerctl` acts on that player (check `man playerctl`/`playerctld --help`: is that automatic or does
   it need `-p playerctld`? use whatever really targets the most recent one). Start it at login and now,
   the same way this setup starts its other user daemons (if the package ships a user unit, use it; if
   not, add a small unit to `desktop/config/systemd/user/` following the existing ones). Note its RAM.
3. `desktop/config/i3/config`: next to the volume keys (~line 96) bind `XF86AudioPlay` and
   `XF86AudioPause` → play-pause, `XF86AudioNext` → next, `XF86AudioPrev` → previous, with
   `exec --no-startup-id`, and a one-line comment. XF86 keysyms are layout-independent (they must work
   in US/RU/UA — confirm from `xmodmap -pke` that all groups carry the same keysym). Check nothing else
   grabs these keys (xfconf `xfce4-keyboard-shortcuts`, osd-daemon, xfsettingsd: `xfconf-query -c
   xfce4-keyboard-shortcuts -l -v | grep -i audio`) — if something does, report it.
4. Firefox exposes MPRIS only if `media.hardwaremediakeys.enabled` is true (default) — check the owner's
   prefs/policies in `desktop/system/usr/lib/firefox-developer-edition/distribution/` and the profile's
   `prefs.js`/`user.js` (read only) and report; do not change Firefox.
5. Docs: the keys line in `FEATURES.md`, `ARCHITECTURE.md` (keys section ~line 244) and the Super+/
   cheatsheet (`desktop/config/i3/cheatsheet.txt`). Do NOT edit CHANGELOG.md.

Checks: `make test` passes. `playerctld` is running (`systemctl --user status ...` or `pgrep -x`), and
`playerctl -l` / `playerctl -p playerctld status` (read-only) work. **Do not play, pause or skip anything
on the owner's real players** (no play-pause/next/previous commands against the live session — the owner
may be listening), do not press keys on display :0, do not run `make apply` and do not reload i3 (the
coordinator applies and reloads), never `pkill -f`/`pgrep -f`, do not commit.

Final message (English, under 30 lines): what you installed/added (paths, journal records), how the
"current player" is chosen (with the doc line), playerctld RAM, Firefox MPRIS status, anything grabbing
the keys, what the coordinator must do to apply.
