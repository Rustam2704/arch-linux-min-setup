# Task C-system: packages, /tmp junk, agents below the desktop (owner-approved 15.10.2026)

Project `/home/fanatic/ai/claude/setup`. Read `tools/audit/common.md` (context, deliberate decisions),
`lab/lab` header (journal commands), `MAINTENANCE.md`, and how round 72 did similar things:
`grep -n "72-audit-cleanup" lab/journal.tsv | head -40`. Experiment id for every journal record:
**`75-followups`**. The owner approved exactly the items below. Other agents edit deskd and light-year
sources at the same time: do not touch `desktop/share/`, do not run `make apply` (the coordinator
applies later), do not restart or kill desktop processes, do not touch display :0, never
`pkill -f`/`pgrep -f`. `sudo -n` works for root commands.

## 1. Remove packages
`ttf-iosevka-nerd` (1.1 GB, believed unused) and the "friend's USB stick" toolset `archiso`,
`qemu-base`, `edk2-ovmf`.
- First prove nothing needs them: `pacman -Qi` (Required By), `grep -rni iosevka ~/.config
  /home/fanatic/ai/claude/setup/desktop /etc/fonts 2>/dev/null`, `fc-match` for the families the desktop
  uses (kitty, GTK, panel, rofi, deskd — find them in the configs). If something does use one, stop and
  report instead of removing it.
- `sudo -n pacman -Rns --noconfirm <pkgs>`; then record the undo **after** success:
  `lab/lab undo 75-followups 'sudo pacman -S --needed --noconfirm <the same pkgs>'`.
- Remove them from `packages.txt` / `packages-aur.txt` if listed; note every package `-Rns` removed and
  the space freed (`df` before/after).
- Do NOT clean the pacman or yay caches (owner said not now).

## 2. Agent junk in /tmp (tmpfs = RAM; it holds ~1.4 GB)
- List `/tmp` entries over 10 MB and every browser-profile directory (`playwright*`,
  `.org.chromium.*`, `*chromium*`, `rust_mozprofile*`, etc.) with size and mtime.
- For each, decide whether it is in use: a process has it as cwd, has a file in it open
  (`ls -l /proc/*/fd`, `/proc/*/cwd`), or names it in its cmdline (`--user-data-dir=`, `-profile`).
  Claude scratchpads are `/tmp/claude-1000/<project>/<session-id>/`: never touch this session's
  (`614f9629-afe8-4732-8a6d-898c41e15ffb`); for the others check whether that session is running
  (a live `claude` process — `~/.claude/sessions/*.json` maps pid → sessionId; check those pids exist).
- Delete everything that is not in use and belongs to agents/tests (browser profiles, finished
  sessions' scratchpads, test leftovers). Do not delete sockets, `.X11-unix`, `.ICE-unix`,
  systemd-private dirs, or anything of a running process. Report what was deleted (path, size) and what
  big item you left and why.
- Recurrence: check `man tmpfiles.d` and `/usr/lib/tmpfiles.d/tmp.conf`. If a tmpfiles.d rule can
  cleanly remove leaked browser-profile directories (not just their contents) older than 1 day without
  touching anything else in /tmp, add it to the tree under `desktop/system/etc/tmpfiles.d/` (follow how
  other `/etc` files are declared there and in `tools/desktop.py`) and verify it with
  `systemd-tmpfiles --clean --dry-run` if available or by reasoning from the man page (say which). If it
  cannot be done cleanly, do not add it and explain why.

## 3. Agents below the desktop in CPU priority
Facts: every kitty window's shell runs in its own transient scope
`user@1000.service/kitty-<pid>-<n>.scope` (Claude Code, Codex and all their children live there);
Firefox and our daemons are in `app.slice`, PipeWire in `session.slice`, i3/kitty/panel in
`session-1.scope`, Xorg in `system.slice/lightdm.service`. Today a kitty scope weighs the same as all of
`app.slice` (CPUWeight unset = 100). Disk scheduler is mq-deadline, so IOWeight does nothing — skip IO.
Goal: everything started from a kitty window gets **CPUWeight=10** and **MemoryHigh=4G** (a single
runaway window gets throttled and pushed to swap before the desktop), via a prefix drop-in
`~/.config/systemd/user/kitty-.scope.d/50-below-desktop.conf` (`[Scope]` section).
- First verify that a prefix drop-in applies to a transient user scope: make a temporary drop-in for a
  test prefix (e.g. `~/.config/systemd/user/labtest-.scope.d/x.conf`), `systemctl --user
  daemon-reload`, `systemd-run --user --scope --unit=labtest-1 sleep 20 &`, then `systemctl --user show
  labtest-1.scope -p CPUWeight,MemoryHigh,DropInPaths`; also check whether an **already running** scope
  picks a new drop-in up after `daemon-reload`. Remove the test drop-in and reload afterwards.
- If it works: add the real file to the tree at `desktop/config/systemd/user/kitty-.scope.d/50-below-
  desktop.conf` with a short comment saying why (desktop above agents, owner decision 15.10), and make
  sure `tools/desktop.py` installs it (directories with a dot in the name, mode; run `make status`/
  `make diff` to see it listed — do not apply). If running scopes do not pick it up, write down the exact
  `systemctl --user set-property --runtime <scope> ...` commands the coordinator should run after apply.
- If prefix drop-ins do not apply to transient scopes, stop and report what does work.

## Checks
`make test` must pass. `lab/lab status` shows the new records. Nothing outside the items above changed.

## Final message (English, under 50 lines)
Per item: done / not done (why), evidence (commands and key output), journal records added, files added
to the tree, space freed (disk and /tmp), what the coordinator must do at apply time.
