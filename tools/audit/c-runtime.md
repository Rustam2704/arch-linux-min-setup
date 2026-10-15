# Audit C: live system health (runtime, kernel, hardware, storage)
Include `common.md` rules (read it: /home/fanatic/ai/claude/setup/tools/audit/common.md).
Output: `/home/fanatic/ai/claude/setup/research/audit-2026-10-15/c-runtime.md`.
Measure and inspect, read-only:
1. Journal: messages per unit/identifier for the current and previous boot (`journalctl -b -1 -o json`
   or `--output=short` + counting); top spammers with examples (known: touchegg logs "bcm5974: kernel bug:
   Invalid fake finger state" ~86 000 lines per boot — how much disk/CPU does it cost, how do others fix
   it: libinput quirks, touchegg config, journald rate limit for that unit?). Journal disk usage.
2. Crashes: `coredumpctl list` (all), backtraces of the 7 i3 segfaults on 14.10 21:11–21:16
   (`coredumpctl info`), and any other repeated crashes; failed units (`systemctl --failed`, `--user`).
3. Boot and session start: `systemd-analyze`, `blame`, `critical-chain`, user units; time from lightdm
   to a usable desktop if derivable from the journal.
4. CPU and wakeups at idle: per-process CPU over 120 s from /proc (utime+stime), context switches,
   and timer wakeups if `powertop` is installed (do not install anything; if absent, say so). Which
   of our daemons / genmon plugins / apps cost most at idle?
5. Memory: PSS of every process (smaps_rollup), grouped (Firefox, Telegram, Zoom, our daemons,
   Claude CLI sessions, Xorg), swap per process (VmSwap), zswap disabled on the cmdline — why (grep
   CHANGELOG) and whether zram/zswap would help an 8 GB machine with 7+ GB swapped; sysctl vm.*
   (swappiness, vfs_cache_pressure, dirty_*), THP.
6. Thermal and power: temperatures at idle (coretemp, applesmc), fan speed and min/max
   (`/sys/devices/platform/applesmc.768/fan*`), whether a fan daemon (mbpfan / macfanctld) exists — the
   CPU sits at ~85 °C under moderate load; TLP config (`/etc/tlp.conf`, `/etc/tlp.d/`), governor, turbo,
   GPU frequency, power draw on battery if readable (`/sys/class/power_supply/BAT0/power_now`).
7. Storage: disk usage summary (`df -h`, `du` of ~/.cache, pacman cache `/var/cache/pacman/pkg`,
   journal, coredumps, ~/.local/share/Trash, docker/flatpak if any), SSD TRIM (`fstrim.timer`), mount
   options, swap file/partition placement.
8. Leftover processes from agents/tests: e.g. `Xvfb :99` running for days, stray Xephyr/geckodriver,
   python http.server — list with age and RSS (do not kill).
9. Kernel/modules: tainted flags, out-of-tree modules (wl, facetimehd), dmesg warnings this boot.
