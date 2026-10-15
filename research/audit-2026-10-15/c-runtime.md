# Audit C - live system health (runtime, kernel, hardware, storage)

Date 2026-10-15, measured 03:20-03:41 EEST on whitebook (MacBookPro11,1, i5-4278U 2c/4t, 7.8 GB RAM, kernel
6.18.52-1-lts, systemd 261). Read-only audit: nothing restarted, installed, killed or written outside this file
(scratch files only under the session scratchpad). Format follows `tools/audit/common.md`.
Confidence tags: **verified** = ran/measured/traced, **inferred** = read only or reasoned.

## 0. Read this first - measurement caveats

* **There was no idle machine.** Six other audit agents (Claude CLI x4, Codex x3, headless Chromium, Lighthouse, gh,
  java) ran the whole time: load average 5-10, `/proc/stat` 80 % busy over the 120 s sample, PSI cpu `some avg300 = 34 %`.
  A true "idle at the desktop" CPU/wakeup baseline was not obtainable. Per-process deltas for our own daemons are still
  valid (they are attributed to the process), but Xorg/panel numbers are inflated by whatever the other agents did on
  screen. Lifetime CPU (since 02:04, 85-95 min) is quoted next to the 100-120 s samples as a cross-check.
* **Uptime was only 1 h 35 min** (boot at 02:04:28, previous boot 8-15 Oct = 7 days, died at 01:56 in a failed resume).
  "Days-old leftovers" and "7+ GB swapped" cannot exist in this boot: swap used was 2.1-2.5 GB. The previous boot's
  memory state is not observable any more.
* CPU is capped at 60 % (1.86 GHz, turbo off) the whole time because the battery menu is on **power-saver while on AC**
  (see C23). Everything below was measured at that clock, so per-run CPU costs are about 1.4x what Automatic mode shows.
* Per instruction from the coordinator, the 14.10 21:11-21:16 `i3` core dumps are not analysed (one line in section 10).

## 1. Journal

Journal on disk: `journalctl --disk-usage` = **315.9 MB** (`du` of `/var/log/journal` 392 MB), persistent, default caps
(SystemMaxUse = min(10 % of fs, 4 GB) = 4 GB; only `SyncIntervalSec=15s` is set, from `desktop/system/etc/systemd/journald.conf.d/50-sync.conf`).
`/var/log/Xorg.0.log.old` = **37 477 952 B**.

Messages per unit, boot -1 (8-15 Oct, 7 days, 22 suspends), 493 242 entries total, counted with `journalctl -b -1 -o json`:

| unit / identifier | entries | share | top message |
|---|---|---|---|
| touchegg.service | **466 827** | **94.6 %** | `libinput error: event17 - bcm5974: kernel bug: Invalid fake finger state 0x13/0xb/0x15/0xd/0x7/0xf` |
| tailscaled | 7 822 | 1.6 % | `open-conn-track: timeout opening (TCP 100.95.221.125:x => 95.216.195.133:80); no associated peer node` 4 036x |
| kernel | 4 645 | 0.9 % | USB enumeration (108x `new high-speed USB device`) |
| systemd (init.scope, user) | 2 908 | 0.6 % | kitty child scopes 273x, Chromium scopes 265x |
| NetworkManager | 1 880 | 0.4 % | `do-change-link ... failure 23 (Too many open files in system)` 100x |
| archlinux-keyring-wkd-sync | 1 574 | 0.3 % | gpg key listings |
| vcmon-collect.service | 1 162 | 0.2 % | `[collect] ...` / `[recheck] ...` |
| acpid + root (handler.sh logger) | 930 + 1 023 | 0.4 % | `ACPI group/action undefined: button/left / LEFT` (arrow keys) |
| osd-daemon | 1 017 | 0.2 % | `screensaver: uninhibit N` 433x, `inhibit firefox ... Playing video` 149x |
| rtkit-daemon | 706 | | thread RT promotions |
| wpa_supplicant | 653 | | `CTRL-EVENT-DSCP-POLICY clear_all` 71x |
| deskd | 557 | | 455x `i3 refused: ... Cannot change position ... not floating` (last one 12 Oct 19:38; none since, boot 0 = 0) |

Boot 0 (this boot, 2 145 entries): kernel 1 057, systemd 307, tailscaled 225, NM 86, sudo 66, acpid/root 90, touchegg **20**
(2x `Touch jump detected and discarded` - rate-limited by libinput; no 3-4 finger use yet), everything else < 30.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C1 | **perf** (disk + noise), bug upstream | **The touchpad log flood is real and it is not touchegg's.** boot -1: 466 827 touchegg lines (94.6 % of the boot's journal) plus **466 786 identical `(EE)` lines in `/var/log/Xorg.0.log.old` (37.5 MB)** - Xorg's own xf86-input-libinput prints the same message the same number of times, so touchegg only repeats it. 116 bursts of 5-218 lines/s, each during touchpad use (peaks 10-14 Oct: 135 880 lines in the single hour 08.10 20:00; 125 854 in the last hour before the 01:56 suspend). States seen: 0x13 (158 634x, TOUCH+FINGER+QUADTAP), 0xb (150 774x, TOUCH+FINGER+TRIPLETAP), 0x15 (135 480x, TOUCH+DOUBLETAP+QUADTAP), 0xd, 0x7, 0xf - i.e. libinput sees two BTN_TOOL_* finger-count bits set at once. **Cost:** CPU is small (touchegg 3 min 11 s CPU in 4 days; journald not measured separately) but disk is not: the unclean tail file `system@...journal~` holds 212 416 entries in 64 MB = ~316 B/entry, so ~467 k entries = **~140-150 MB, ~45 % of the whole 316 MB journal**, plus 37.5 MB of Xorg log per boot, plus an fsync every 15 s while it runs. Forensics suffer too: the last 4 h of the boot that died at 01:56 are 294 k touchegg lines. **How others fix it:** (1) libinput 1.31.3 source (`src/evdev-mt-touchpad.c:268`, fetched and read): `tp_fake_finger_count()` logs with `evdev_log_bug_kernel()` - **no rate limit** (the sibling "Touch jump detected" uses `evdev_log_bug_kernel_ratelimit`, which is why that one is only 2 lines); there is no quirk or config option to silence it (quirks only set model flags; `touchegg --quiet` does not touch libinput's logger). libinput issues #447/#553/#434 are the same family (bcm5974 "kernel bug" messages flooding the journal), no upstream fix found. (2) The kernel side looks exclusive by construction (`input_mt_report_finger_count()` sets FINGER/DOUBLETAP/TRIPLETAP/QUADTAP with `count == n`), so a stuck bit points at a dropped/reordered release event - not established; `sudo libinput record /dev/input/eventN` during a 3-finger swipe would settle whether the kernel or libinput is wrong. (3) Practical mitigation that works today: systemd 261 `LogFilterPatterns=` (documented in `man systemd.exec`, verified on this box) drops matching lines before they are stored. [verified: counts, sizes, source; cause of the stuck bit inferred] | Add to the tree `desktop/system/etc/systemd/system/touchegg.service.d/50-quiet.conf`: `[Service]` / `LogFilterPatterns=~Invalid fake finger state` and, as a belt, `LogRateLimitIntervalSec=30s` `LogRateLimitBurst=50`. For the Xorg copy (37 MB, rewritten each boot, only one old file kept) either accept it or start X with a log in `/run` (`xserver-command=X -logfile /run/lightdm/Xorg.0.log` in `lightdm.conf.d/50-sky-desktop.conf`, loses the file after reboot). Optional: record one swipe with `libinput record` and report to libinput/linux-input. | S (filter) / M (root cause) |
| C2 | cruft (log noise + 1 wakeup/5 min) | **NetworkManager's connectivity check also probes through `tailscale0`**, tailscaled drops it and logs 4 lines every 5 minutes: boot 0 has timestamps 02:13, 02:18, 02:23 ... 03:33 (every 5 min, 93 lines in 85 min); boot -1 4 036 lines. Destination 95.216.195.133 = `redirect.archlinux.org`; `/usr/lib/NetworkManager/conf.d/20-connectivity.conf` uri `http://ping.archlinux.org/nm-check.txt` (default interval 300 s); `nmcli device`: `tailscale0:tun:connected (externally)`. `tailscale0` lifetime traffic is TX 15 KB / RX 86 B, no exit node, the only peer (Windows box) offline. [verified timing + config; mechanism inferred - could not catch the SYN with `ss`] | `/etc/NetworkManager/conf.d/20-tailscale.conf`: `[keyfile]` `unmanaged-devices=interface-name:tailscale0` (declare it in `desktop/system/etc/`). | S |
| C3 | cruft | `acpid` is enabled, explicitly installed, **required by nothing**; `/etc/acpi/events` is empty, `handler.sh` only calls `logger`. The input layer of acpid reports the Apple keyboard's arrow keys as `button/left|right|up|down`, so **every arrow-key press spawns a root `sh` + `logger`** and a journal line: boot -1 had 930 + 1 023 lines (`acpid`/`root`), boot 0 already 90. logind and xfce4-power-manager already own lid/power/suspend. [verified: unit state, package info, handler, journal counts; "nothing else needs it" inferred] | `lab pkg`/remove `acpid` (disable --now, remove package and `/etc/acpi/`), per the "remove dead config fully" rule; or at least mask the `button/{left,right,up,down}` noise. | S |
| C4 | cruft | Chatty identifiers that can be silenced at the source: osd-daemon logs every `screensaver: inhibit/uninhibit` (582 lines in boot -1), tailscaled `[RATELIMIT]` lines, `archlinux-keyring-wkd-sync` prints gpg listings (1 574 lines/week), `mtp-probe` 344 lines (tablet plugged in), `DeprecationWarning: Gtk.Window.set_opacity` on every osd-daemon start. Individually negligible; together ~3 k lines/week. [verified counts] | Drop the debug `log()` for inhibit in osd-daemon or put it behind a flag; `LogLevelMax=notice` on the keyring unit. | S |
| C5 | ux | No journal size policy: with C1 gone the steady state is ~150 MB/week, but nothing caps it below 4 GB and nothing vacuums; the previous boot's 7-day journal is the only evidence after a hang (as 15.10 01:56 showed). [inferred] | `SystemMaxUse=500M` + `MaxRetentionSec=1month` in the existing `50-sync.conf`. | S |

Deskd's `i3 refused` counter (MAINTENANCE says it must be empty): 465 refusals on 9-12 Oct (4 deskd instances; `resize set + move position -> not floating` 455x, `move container to workspace number -1 -> Could not parse number "-1"` 6x on 11 Oct), **none since 12 Oct 19:38**, boot 0: 0. Closed by the 12.10 rounds, not an open finding.

## 2. Crashes and failed units

`systemctl --failed` and `systemctl --user --failed`: **0 units** in both. `coredumpctl list`: 56 entries (cores still on disk for 19; 20 MB in `/var/lib/systemd/coredump`).

| date | what | count | cause |
|---|---|---|---|
| 17.09 16:54 | xfce4-panel + 2 wrapper-2.0, SIGABRT | 3 | before the lab journal started, not analysed (cores missing) |
| 18.09 01:08 | firefox (live `firefox.scope`) SIGXCPU | 1 | cores missing; nobody sets an RLIMIT_CPU in the tree - unexplained, one-off, 4 weeks ago |
| 24.09 01:44-01:47 | `python3.14 -` SIGSEGV | **30 in 3 min** | agent probe script: `XkbGetState`/`XFlush` via ctypes on a NULL Display (stack in journal, `Command Line: python3 -`, from `kitty-2182` scope). Not a daemon. |
| 25.09 01:56:44-53 | **deskd + 6x genmon `wrapper-2.0` SIGBUS** | 7 | see C6 |
| 11.10, 14.10 | Playwright Chromium / headless-shell SIGTRAP | 10 | agent test browsers |
| 14.10 13:10 | `firefox --headless --screenshot ... launcher-preview.png` SIGSEGV | 2 | agent screenshot runs (lenovo-tab-ricing), not the live Firefox |
| 14.10 10:21, 10:22; 15.10 02:23 | `adb` server SIGABRT | 3 | android-tools 37.0.0-5 server abort with the Lenovo Tab attached; server respawns and stays resident (C33) |
| 14.10 21:11-21:16 | `i3 -c .../scratchpad/notify/i3.conf` | 6 | skipped per coordinator |

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C6 | **risk** | **In-place overwrite of a mapped file killed 7 live processes with SIGBUS** on 25.09 01:56:44-53: deskd.service (exit `status=7/BUS`, auto-restarted after 3 s) and 6 genmon wrappers, all with `hb_ot_layout_table_find_feature_variations` (harfbuzz) in the pango shaping path. `~/.local/share/fonts/Diablo.ttf` has mtime **2026-09-25 01:56:44.258** - the same second - and `lab/journal.tsv` has **no entry** for it (first entry that night is 01:58:26). `lab/lab write` is atomic (`mv -f` of a staged file, comment says so) so this write bypassed lab (a direct `cp`/python write by an agent). The same would happen to any other file mmap'd by long-running GTK/Pango processes (fonts, `libdock-rtl.so`, icon caches). One-off 3 weeks ago, but nothing prevents a repeat. [verified: stack, mtime, journal; "who wrote it" inferred] | Rule in MAINTENANCE/`~/.codex/AGENTS.md`: files in `~/.local/share/fonts`, `*.so`, `*.ttf` are replaced only via `lab write`/temp+`mv`; optional `make check` guard that greps tools for open(...,'wb') on those paths. | S |
| C7 | cruft | The 30 python SIGSEGVs and 10+ Chromium/Firefox/adb dumps are agent test tooling filling `coredumpctl` (56 entries) and hiding the live ones. Coredumps are stored (19 files, 20 MB) with the default 3-day tmpfiles age. [verified] | Tell agents to run test browsers with `ulimit -c 0` or `systemd-run --user -p LimitCORE=0`; or `Storage=none` for UID 1000 test scopes. | S |

## 3. Boot and session start

`systemd-analyze`: **12.323 s** = firmware 3.234 + loader 0.221 + kernel 4.816 + userspace 4.050; graphical.target at 3.591 s of userspace.
Blame top: `dev-sda2.device` 1.320 s, `user@1000` 569 ms, `tlp` 441 ms, `systemd-tmpfiles-setup-dev-early` 433 ms,
`systemd-journal-flush` 416 ms, `upower` 370 ms, `tailscaled` 332 ms, `NetworkManager` 328 ms, `lightdm` 218 ms.
Critical chain of lightdm: `lightdm +218ms <- systemd-user-sessions @3.246 <- network.target @3.240 <- wpa_supplicant @3.277 <- basic.target @2.908`.

Timeline from the journal (boot 0): kernel 02:04:28.9 -> graphical.target 02:04:31.58 -> lightdm autologin session opened **02:04:32.24**
-> `user@1000` ready 02:04:32.96 (521 ms) -> touchegg client connected 02:04:34.2 -> deskd started 02:04:34.6 -> osd-daemon 02:04:35.3,
sky-stars 02:04:35.5 -> **`deskd: running` 02:04:35.98** -> `deskd: saved screen layout as laptop` 02:04:39.2.
So **autologin -> usable (deskd up) = 3.7 s, settled = 7 s**; power button -> deskd up ~ 10.5 s. User manager `--user blame`: only
`xdg-desktop-portal` (483 ms) and `gvfs-mtp-volume-monitor` (281 ms) are slow; `systemd-analyze --user` total 521 ms for basic.target.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C8 | ux (informational) | Boot is already fast; nothing in the desktop's own start costs more than ~0.5 s. The only avoidable slice is lightdm waiting for `network.target` (wpa_supplicant @3.277 vs basic.target @2.908, ~0.37 s) and `tlp.service` (441 ms, not on the critical path). [verified] | `systemd-analyze critical-chain lightdm.service`, `blame` | none needed; if wanted, `After=` override for lightdm dropping `network.target`. | S, gain ~0.3 s |
| C9 | risk (security), cruft | Every boot: `bootctl: Mount point '/boot' which backs the random seed file is world accessible, which is a security hole!` (vfat mounted `fmask=0022,dmask=0022`) and `fsck.fat: There are differences between boot sector and its backup`. [verified in boot 0 journal] | fstab: `/boot` options `fmask=0077,dmask=0077`; once `sudo fsck.fat -a /dev/sda1` (backup sector) - touch the ESP carefully, macOS NVRAM story in MAINTENANCE. | S |

## 4. CPU and wakeups

Samples: 120 s (`/proc` utime+stime, all processes) and 100 s (own + reaped children, which is where genmon script runs are charged to the plugin wrapper),
both taken under the load described in section 0. powertop 2.16 is installed; two 20-30 s runs gave 433 and 333 wakeups/s at 95 % CPU usage - not an idle figure.

Our processes, **% of one core** (100 s sample with children / 85-min lifetime average):

| process | 100 s (own+children) | lifetime avg | ctx switches/s | note |
|---|---|---|---|---|
| genmon-40 wrapper (**panel-telegram**, 5 s) | **2.60** (own 0.17 + children 2.43) | 0.17 + python runs | 40 | child is a Python start per 5 s |
| genmon-61 (panel-clock, 1 s) | 0.97 | 0.34 | | sh + date per second |
| genmon-41 (panel-net, 1 s) | 0.93 | 0.37 | | sh + cat per second |
| genmon-63 (panel-ram), genmon-42 (panel-sys) | 0.90, 0.85 | 0.52, 0.44 | 40 | refreshed by sysqd whenever the value changes |
| sky-stars | 1.24 | 1.20 (61 s CPU) | 33 | deliberate (starfield) |
| Xorg | 2.7 (4.6 in 120 s run) | 3.6 (184 s CPU) | 493 | clients + load from other agents; GFX wakeups 24-79/s |
| xcompmgr | 0.37-0.73 | 0.58 | 93 | deliberate |
| sysqd / netqd | 0.50 / 0.46 (incl. 0.33 / 0.31 children) | 0.17 / 0.16 | | children = `xfconf-query` spawns (C11) |
| deskd | < 0.19 in 100 s, 1.18 in the 120 s run | 0.33 (17 s CPU) | 62 (42 involuntary) | activity-driven |
| osd-daemon | < 0.19 | 0.18 | | |
| xfce4-panel | 0.29 | 0.26 | 49 | |
| light-year/app.py (calendar, always resident) | not in top 30 | 0.40 (20.6 s CPU) | | wakeup source not traced |
| kcompactd0 | 0.44-0.72 | not computed | | THP=madvise already set (R79) |

Sum of all genmon wrappers (own + children) in the 100 s sample: 2.60 + 0.97 + 0.93 + 0.90 + 0.85 + 0.31 + 0.26 + 0.20 = **~7.0 % of one core (1.75 % of the machine)**, of which panel-telegram is a third.
Measured per-run cost of the readers (installed scripts, 10-100 runs each, at the 1.86 GHz cap): clock 6.3 ms CPU, net 5.4, workspaces 5.9, ram 6.0, swap 5.8, sys 5.9,
wifi 6.2, layout 11.3, **battery 112 ms (Python, every 30 s)**, **audio 130 ms (pactl, 60 s)**, **weather 240 ms (60 s)**, **telegram 117 ms (5 s; measured with a stub `xdotool`, never touched display :0)**.
Python start-up alone is 35-43 ms; `from sky_theme import THEME` adds ~51 ms (json 30 ms, pathlib 20 ms - `-X importtime`).

Other system daemons, **CPU time per boot** from systemd's "Consumed" lines (boot -7, 4 days / boot -5, 3.1 days / this boot, 1.5 h): tailscaled **37 min 20 s / 19 min 30 s / 50.7 s** (0.65-1 % of a core, 78-135 MB), thermald 5 min 40 s / 4 min 16 s / 0.6 s, touchegg 3 min 11 s / 1 min 57 s / 4.5 s, NetworkManager 2 min 47 s / 2 min 2 s / 4.2 s, mbpfan 11 s / 8.8 s / 0.24 s.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C10 | **perf** (still open from AUDIT-2026-10-10 "panel-telegram period") | **`panel-telegram` is the most expensive thing we run at the desktop: ~2.4 % of a core, forever.** Every 5 s genmon starts a Python interpreter, imports `sky_theme` (json/pathlib/re) and runs `xdotool search --class TelegramDesktop getwindowname` against X. 117 ms CPU per run (python start 43 + sky_theme 51 + xdotool + script), measured; `ours.py` 100 s: wrapper 1515 children = 2.43 %. The previous audit left the period to the owner; the better fix is to remove the poll, not tune it. [verified] | deskd already receives i3 window events and titles: let it (or sysqd) write `$XDG_RUNTIME_DIR/telegram.txt` whenever a TelegramDesktop title changes and call `xfpanel.refresh("panel-telegram")`; `panel-telegram` becomes a `cat` like `panel-net` (5 ms). Saves ~2.3 % of a core and an X round trip every 5 s. | S-M |
| C11 | perf (small) | `xfpanel.plugin_ids()` spawns `xfconf-query -c xfce4-panel -l -v` (a GLib process) at most every 10 s **in each of deskd, osd-daemon, sysqd, netqd separately** - the cache is per process, and sysqd's value changes every 2 s so it re-queries all the time: children cost 0.33 % (sysqd) + 0.31 % (netqd) of a core in the 100 s sample, an `xfconf-query` shows up in powertop with 46 GFX wakeups. [verified cost; cause read in `share/sky-desktop/xfpanel.py:36-54`] | Resolve ids once at start and on a panel-restart signal (xfconf property change via Gio D-Bus, no process), or let deskd publish `plugin-ids.json` in `$XDG_RUNTIME_DIR`. | S |
| C12 | perf (small) | The 1 Hz plugins (clock, net) cost 6.3 + 5.4 ms CPU per second = ~1.2 % of a core before GTK relayout (wrappers total 0.97 + 0.93 %). The `cat` in `panel-net` and every `date`/`cat` is a fork+exec. [verified] | Use shell builtins (`read -r l < file`, dash `printf`), merge clock+net into one plugin, or accept it. Not worth a rework alone. | S |
| C13 | **perf** | **The `wl` driver costs ~9 % of a core at trivial traffic.** `perf record -a` 20 s: `[wl]` = 2.23 % of all samples (4 CPUs => 8.9 % of one core) while the NIC moved only 39 KB/s rx, 125 KB/s tx, 171 rx packets/s; an earlier 10 s sample gave 1.6 % (6.4 %). One address inside the blob (`wl + 0x181ce9`) is 0.89 % alone. powertop lists `wl_timer [wl]` among the heaviest timers. NetworkManager runs `wifi.powersave=2` (`/etc/NetworkManager/conf.d/20-broadcom-wifi.conf`, outside the tree, set at install). Closed-source, unmaintained (kernel says so at every load), the only driver for the BCM4360 card. [verified under load; idle share unknown] | None cheap in software. Options: keep and accept; test `wifi.powersave=3` (enable) and compare `perf` share and latency; or replace the card/dongle (long-term, hardware). | M/hardware |
| C14 | perf (low) | tailscaled is the biggest always-on system daemon: 0.65-1 % of a core continuously (37 min CPU in 4 days), 62 MB PSS / 135 MB peak, up to 1 226 ctx switches/s during network load (thread `958` 208 k voluntary switches in 85 min), for a link whose only peer is offline and carries no traffic. [verified numbers; the use case is the owner's Windows box] | If the link is occasional: `tailscale down` when unused or start the unit on demand (`systemctl start tailscaled` from a menu); otherwise leave. | S |
| C15 | perf (option, owner decision) | Haswell pays for PTI (Meltdown), MDS buffer clearing, retpolines and L1TF: `/sys/devices/system/cpu/vulnerabilities/*` shows `meltdown: Mitigation: PTI`, `mds: Clear CPU buffers; SMT vulnerable`, `spectre_v2: Retpolines; IBPB conditional; IBRS_FW; STIBP conditional`. The profile is syscall/ctx-switch heavy (`entry_SYSCALL_64`, 490 Xorg ctx/s). Gain from `mitigations=off` not measured. [inferred] | Only if the owner wants it and accepts the security trade-off (browser machine): A/B with the same 120 s sampler. I do not recommend it by default. | S |
| C16 | cruft (known) | 4 independent power/thermal controllers run at once: TLP (profile + `intel_pstate max_perf_pct`), mbpfan (fan), thermald `--adaptive` (no `/etc/thermald/thermal-conf.xml`, logs "Config file ... does not exist" 5x per boot), kernel intel_pstate in passive mode. thermald costs 5 min 40 s CPU per 4 days and on this CPU has nothing to do while TLP caps the clock; no collision observed. [verified costs, inferred value] | Candidate for removal (`lab pkg` remove thermald) or give it a config; keep only if the owner wants the safety net. | S |
| C17 | ux | `light-year/app.py` (calendar) stays resident: 20 MB PSS + 24 MB swapped, 20.6 s CPU in 85 min (0.4 %). Not traced what wakes it. [verified cost] | Check with `strace -c -p` whether it polls (Google sync?) and make it event driven or start on demand (Super+C). | S |

## 5. Memory

Snapshot 03:38: MemTotal 7 842 MB, used 4 913, buff/cache 4 267, available 2 929, **swap used 2 488 MB of 16 384** (single file `/swapfile`, prio -2, on the SSD), Shmem 1 333 MB, Slab 768 MB, AnonPages 3 006 MB.
PSS from `/proc/*/smaps_rollup` (sudo read-only, 161 processes), grouped:

| group | procs | PSS MB | swap MB |
|---|---|---|---|
| Firefox (cgroup `firefox.scope`: current 1 310 MB, `memory.high` 6 GiB, swap 1 040 MB) | 12 | 1 346 | 530 |
| **Claude CLI sessions** (4 x 290-340 MB) | 4 | **1 282** | 116 |
| Codex (3 exec) | 3 | 353 | 0 |
| node (codex plugins) | 3 | 145 | 0 |
| kitty (4) | 4 | 81 | 119 |
| tailscaled | 1 | 62 | 12 |
| Telegram | 1 | 61 (RSS small, **342 MB swapped**) | 342 |
| Xorg | 1 | 50 | 80 |
| our daemons (deskd 13.4, osd-daemon 17.4, sysqd 6.6, netqd 3.9, sky-stars 4.1, xcompmgr 6.1, light-year 20.2, i3 12.5) | 8 | **~52 (+ light-year, i3)** | 101 |
| genmon wrappers (12 x 3-8 MB) + xfce4-panel + docklike | 14 | 53 | ~95 |
| xfce4 other (xfsettingsd, power-manager, Thunar --daemon, xfconfd ...) | 7 | 27 | 50 |
| Zoom | 0 running | | |
| total listed | | 3 820 | 1 633 |

Our whole desktop layer (daemons, panel, genmon, i3, Xorg) is ~175 MB PSS = 2.2 % of RAM; the 8 GB is spent on Firefox, four Claude CLI sessions and agents, as before.
sysctl: `vm.swappiness=30` (`/etc/sysctl.d/99-lab-memory.conf`), `vfs_cache_pressure=100`, `dirty_ratio=20`, `dirty_background_ratio=10`, `dirty_expire_centisecs=6000`, `dirty_writeback_centisecs=6000`, `page-cluster=3`, `laptop_mode=2`, `watermark_scale_factor=10`, `min_free_kbytes=67584`. THP `madvise` (thp_fault_alloc 846, compact_stall 571, kcompactd0 ~0.5 % CPU). KSM off. zswap `N` (cmdline `zswap.enabled=0`).
Counters since boot (85 min): `pswpout` 644 412 pages = **2.46 GB written to the SSD swap**, `pswpin` 133 507 = 0.51 GB, `workingset_refault_anon` 166 574 (650 MB re-faulted), `pgmajfault` 84 758, `allocstall_normal` 315, oom_kill 0. PSI memory `some avg300 0.12 %`, `full 0.00`; io `some avg300 1.3 %` - no user-visible stall right now.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C18 | **perf** (RAM) | **tmpfs `/tmp` holds ~1 GB-1.3 GB of the 8 GB** (Shmem 1 333 MB = 17 % of RAM; it gets swapped to the SSD under pressure, which is where part of the 2.46 GB `pswpout` comes from). `/tmp` is a 3.9 GB tmpfs (`df`); `/tmp/claude-1000` = 962 MB, of which **one agent scratchpad = 933 MB** (a single `sysui-dexdump.txt` of 284 MB, `l3/` 654 MB) and 33 leaked headless-Chromium profile dirs `/tmp/tmp.*` (~2.2 MB each, ~70 MB, never removed until reboot, which happens weekly). [verified] | Agents write bulk output to disk (`/var/tmp` or the project), not the scratchpad; cap `/tmp` (`size=1G` in the tmpfs mount) so a runaway fails instead of eating RAM; tmpfiles.d rule `e /tmp/tmp.* - - - 1d` (needs `D`/age) to reap Chromium profile dirs. | S |
| C19 | ux (decision recorded, not a bug) | **zswap off (owner decision 30.09, CHANGELOG round 77; no measurement behind it is recorded).** Current numbers do not show swap as a bottleneck (PSI above), so there is no urgent case to reverse. If it is revisited: swap traffic is ~29 MB/min written, 6 MB/min read; 2.5 GB of swapped data would fit entirely in a 20 % zswap pool (1.57 GB at roughly 2:1) at the price of ~1 GB RAM, and the SSD-write side of this is not a wear problem: SMART `Host_Writes_MiB` 32 413 865 = **30.9 TiB lifetime** in 14 568 h (~51 GB/day average), health PASSED, 0 reallocated. `page-cluster=3` (8-page read-around) is the default tuned for HDD/zram-less; 0-1 is the usual advice for SSD swap. [verified counters; benefit of zswap here inferred] | Keep off. If thrash returns: A/B by `/proc/pressure/memory` and `pswpout`/h over a day each; try `vm.page-cluster=0` first (free). | S |
| C20 | cruft | **zram leftovers although zram was replaced by zswap+swapfile on 18.09:** `zram-generator 1.2.1-1` installed, `/etc/systemd/zram-generator.conf` (`zram-size = ram / 2`, zstd, prio 100) still present, `/etc/systemd/system/systemd-zram-setup@zram0.service` is a **mask** symlink, and the `zram` module still loads on every boot (`zram: Added device: zram0`, `lsmod`: zram 69 632 B, `Unnecessary job was removed for /dev/zram0`). Violates "remove dead config fully". [verified] | `lab pkg` remove `zram-generator`, delete the conf and the mask symlink; check `packages.txt` (no line for it, so BOOTSTRAP would not install it - the box has drifted from the declaration). | S |
| C21 | ux | `dirty_expire/writeback = 6000 cs` (60 s) and `laptop_mode=2` are TLP's power-saver/battery values and are active **on AC** because the profile is power-saver (C23): up to 60 s of un-flushed data after a hang - exactly the situation of 15.10 01:56. journald's 15 s sync and `zz-sleep-mark` mitigate the log side only. [inferred] | Choose "Automatic" (C23) or set `MAX_LOST_WORK_SECS_ON_SAV=15` in `50-sky-desktop.conf`. | S |
| C22 | ux | The earlier brief said "7+ GB swapped"; this boot shows 2.1-2.5 GB after 1.5 h with 160-tab Firefox history gone (Firefox 1.3 GB). Telegram sits at 61 MB PSS / 342 MB swapped (idle, fine), sysqd 6.6 MB PSS / 29.7 MB swapped - Python daemons that wake every 2 s page their own heap back in. [verified] | none; informational. If the 7-GB case recurs, capture `smem -t`-style table at that moment (the script is in the scratchpad: `grp.py`). | - |

## 6. Thermal and power

* Temperatures (loaded, power-saver cap 1.86 GHz): package 71-72 °C at sensors time (`thermal_zone1 x86_pkg_temp` 71 000), core 67-68 °C, TC0P 61, TC0E/TC0F 66-67, TPCD 64, TH0A 47.8 (SSD 47 °C, max seen 74), battery 35.8, TA0P 44.5. 100 s, 20 samples every 5 s: **package 63-70 °C, fan 1 294-2 354 RPM, average CPU clock 1 800 MHz**. `-127 °C` entries (TH0C, THSP, TW0P, TMLB) are absent sensors, ignore.
* Fan: one fan (`Right Side`), `fan1_min` 1299, `fan1_max` 6199, `fan1_manual=1` (mbpfan in control), 1 317 RPM at 61 °C TC0P.
* mbpfan 2.4.0 runs (`mbpfan -f`, 0.24 s CPU in 85 min), `/etc/mbpfan.conf`: `low_temp=63`, `high_temp=66`, `max_temp=86`, `polling_interval=1` - **these are the program's stock defaults** (compiled-in `low_temp = 63; // try ranges 55-63`, `high_temp = 66; // try ranges 58-66`).
* TLP 1.10.2: `/etc/tlp.conf` has no active settings; only `/etc/tlp.d/50-sky-desktop.conf` (SAV: `CPU_BOOST_ON_SAV=0`, `CPU_MAX_PERF_ON_SAV=60`, `PCIE_ASPM_ON_SAV=powersupersave`; AC/BAT explicit boost 1 and 100 %). `~/.config/sky-desktop/power-mode` = `power-saver`, `/run/tlp/last_pwr` = `2` while `ADP1/online = 1`.
* CPU: `intel_cpufreq`, `intel_pstate status=passive`, governor `schedutil`, `no_turbo=1`, `max_perf_pct=60`, scaling_max 1 860 000 kHz of cpuinfo_max 2 600 000, EPB 15 (power). GPU: Iris 5100, `gt_cur_freq` 200 MHz (= min, max 1100), RC6 residency 34 % of uptime; powertop under load: RC6 25.8 %.
* Battery: `bq20z451`, **cycle_count 1 212**, `charge_full` 4 364 000 vs `charge_full_design` 6 330 000 = **69 % health** (consistent with MAINTENANCE "stops at ~97 %"). `power_now` does not exist on this battery driver and `current_now` is 0 while plugged in, so **draw on battery could not be measured** (the machine was on AC throughout).

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C23 | **ux** (maybe collision with the owner's intent) | **Power-saver is active while on AC**: CPU limited to 60 % (1.86 GHz) with turbo off during the entire session, including a load average of 5-10 from the audit/test agents (CPU PSI `some avg300 = 34.5 %`). CHANGELOG round 59, 10.10 (memory-relief: power mode set to Automatic because "TLP from the mains gives 3.1 GHz and turbo; `lab undo` brings back power-saver") shows this has bitten before. `power-mode` file says `power-saver`; since this mode also sets laptop-mode dirty timing (C21) it affects durability too. [verified state; intent unknown] | Confirm with the owner. If unintended: battery menu -> Automatic. If intended on battery only, make power-saver apply only on BAT (the Automatic profile already does). | S |
| C24 | **ux / risk** (heat) | **mbpfan runs untuned stock thresholds with a quadratic ramp, so the fan stays near minimum until ~66 °C and only reaches ~2.6k RPM at 76 °C.** From `mbpfan.c` (fetched, lines 654-703): `step_up = (fan_max - fan_min) / ((max_temp - high_temp)*(max_temp - high_temp + 1)/2)` = 4 900 / 210 = 23.3 RPM per step; `steps = d(d+1)/2`, `d = temp - high_temp`; speed = 1 299 + steps x 23.3: **70 °C -> 1.5k, 76 °C -> 2.6k, 80 °C -> 3.7k, 85 °C -> 5.7k RPM**. The owner reports "CPU ~85 °C under moderate load" - that is exactly the equilibrium where the fan finally becomes loud; Haswell trip/crit is 100 °C, so it is not dangerous, but sustained 80+ °C ages the already worn battery (69 %) and the SSD (47 °C idle, max 74). Observed here: 63-70 °C -> 1.3-2.35k RPM under the 60 % cap. Fan input matches (TC0P 61 °C -> 1 317 RPM). [verified algorithm and current readings; improvement inferred] | Version `/etc/mbpfan.conf` in the tree (it is not in `desktop/system`) with e.g. `low_temp=55`, `high_temp=60`, `max_temp=80` (the program's own "try ranges"), restart mbpfan, then repeat the 100 s sampler under the same load and compare temperature and noise (owner decides acceptable noise). | S |
| C25 | cruft | `thermald` + `mbpfan` + TLP + passive `intel_pstate`: see C16. | | | |
| C26 | ux | `ENERGY_PERF_BIAS: Set to 'normal', was 'performance'` at every boot, then TLP forces EPB 15; harmless. `cpu*/cpufreq` `min_perf_pct=25`. Nothing to do. [verified] | dmesg | | |

## 7. Storage

`df -h`: `/dev/sda2` 229 GB, **151 GB used (70 %), 67 GB free** (ext4, `rw,noatime`, no `discard`; inodes 11 %); `/boot` vfat 1 GB, 49 MB used; tmpfs `/tmp` 3.9 GB (995 MB-1.3 GB used), `/dev/shm` 29 MB, `/run/user/1000` 160 KB. SSD `APPLE SSD SM0256F`, `rotational 0`, scheduler `mq-deadline`, read_ahead 128 KB.
Largest consumers: `/home/fanatic/ai` **91 GB** (space-rangers 40 GB, gaming-on-linux 24 GB, lenovo-tablet 15 GB, nutri-website 7.5 GB, igor-history-teacher 2.3 GB, google-gen 1.7 GB), `flash-card-25-09-2026` 8.3 GB, `/timeshift` 8.5 GB (snapshot `before-lab-experiments` of 17.09), `~/.local` 3.0 GB, Downloads 2.5 GB, `~/.codex` 1.9 GB, `~/.claude` 1.1 GB, `~/.npm` 871 MB, `/usr` 7.6 GB, `/var` 3.6 GB.
Caches: `/var/cache/pacman/pkg` **3.2 GB (1 115 packages)**, `~/.cache` 3.5 GB (mozilla 1.2 GB, ms-playwright 964 MB, **yay 957 MB**, pip 195 MB, electron 109 MB, yt-lab 48 MB), journal 316-392 MB, coredumps 20 MB, Trash 1.3 MB. No Docker, no Flatpak. `paccache.timer` weekly (last 12.10), `reflector.timer`, `man-db.timer`, `shadow.timer` fine.
TRIM: `fstrim.timer` enabled (weekly, last run 12.10 01:10:28: `/boot` 973 MiB and `/` **101.4 GiB** trimmed = the whole free space each time because ext4 does not remember trimmed ranges; harmless), next 19.10.
SMART (`smartctl`, sudo read-only): PASSED; Reallocated 0; Pending 0; CRC errors 0; error log empty; Power_On_Hours 14 568; **Power_Cycle_Count 29 163** (suspend cycles counted); Power-Off_Retract 304; **Host_Writes 32 413 865 MiB (30.9 TiB)**, Host_Reads 38 869 486 MiB; temperature 47 °C (min 6, max 74).
Swap: `/swapfile` 16 GiB on the root ext4 (not a partition), prio -2.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C27 | cruft | 14 empty root-owned `download-XXXXXX` directories in `/var/cache/pacman/pkg/` (pacman 7 sandbox leftovers of interrupted downloads; `du` prints 14 "Permission denied"). [verified] | `sudo ls -d /var/cache/pacman/pkg/download-* | wc -l` -> 14 | `sudo rmdir` them; keep `paccache` default (3 versions). | S |
| C28 | cruft / ux | Reclaimable without risk: `~/.cache/yay` 957 MB (AUR build dirs), `ms-playwright` 964 MB (only if agents stop using Chromium tests), `~/.npm` 871 MB, pacman cache 3.2 GB (could keep 1 version: `paccache -rk1` ~ -2 GB). Disk at 70 % is fine for the SSD; this is about headroom for the 91 GB of project data. [verified sizes] | `du` | `yay -Sc`, `npm cache clean --force`, `paccache -rk1` when space is needed. | S |
| C29 | ux (informational) | Storage health is good: nothing to fix on TRIM, mount options or swap placement. Write volume (30.9 TiB lifetime) is far below the endurance of a 256 GB MLC SSD; the remaining wear source worth watching is swap (C19) and the journal flood (C1). [verified] | smartctl | | |

## 8. Leftover processes from agents/tests

Checked by name and age at 03:30-03:41 (`ps -eo etimes`): no `Xvfb`, `Xephyr`, `Xnest`, `geckodriver`, `chromedriver`, VNC, `ngrok`/tunnels, `sleep`/`tail -f` strays. Uptime is only 1 h 35 min, so nothing can be days old; only X server is `Xorg :0` (pid 938) and `/tmp/.X11-unix` has only `X0`.

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C30 | cruft | Resident strays right now (not killed): **`adb -L tcp:5037 fork-server`** pid 29729 (1 h 15 min, 8.7 MB RSS; `/tmp/adb.1000.log` is written continuously with `Netlink: SUBSYSTEM/DEVTYPE not found` and `connection terminated: read failed` for the attached Lenovo Tab; the server aborted 3 times: 14.10 10:21, 10:22, 15.10 02:23); `Sublime crash_handler` pid 2204; Firefox `forkserver` pid 2338; `Thunar --daemon`. In-flight agent jobs seen and left alone: `python3 -m http.server 8741/8743 --bind 127.0.0.1` (2-4 min old), Lighthouse + headless Chromium tree (RSS ~700 MB total), `wrangler deploy`, `java -Xmx1024M ... build-tools/34.0.0` (d8/apksigner). [verified] | `adb kill-server` after tablet sessions (put it in the tablet task template); a `trap 'kill $SERVER' EXIT` in agent test scripts that start `http.server`. | S |
| C31 | cruft | 33 leaked `/tmp/tmp.*` Chromium/Lighthouse profile directories (RAM-backed, see C18) from headless runs, plus `/tmp/lighthouse.*`, `n1-browser.mjs`, `unleash-repo-schema-v1-codeium-language-server.json` (463 KB), `node-compile-cache`. [verified] | `ls /tmp` | reap with tmpfiles.d age rule or have the agent task wrapper `rm -rf` its profile dir. | S |

## 9. Kernel and modules

`/proc/sys/kernel/tainted` = **12801** = P (proprietary module) + W (a kernel WARN happened) + O (out-of-tree) + E (unsigned). Out-of-tree modules: `wl` (6 524 928 B, `broadcom-wl-dkms 6.30.223.271-49`, license MIXED/Proprietary, DKMS built for 6.18.52) and `facetimehd` (139 264 B, `facetimehd-dkms 0.7.0.2-1`, camera `/dev/video0` exists). `lsmod` 121 modules. `dkms status`: both installed.
`dmesg` warn+ (this boot): corrupted DMI table (Apple firmware), MDS/VMSCAPE "SMT on" mitigation notices, `hpet_acpi_add: no address`, `rtc_cmos IRQ`, `ENERGY_PERF_BIAS` normal, `ata1.00: unexpected _GTF length (8)` x2, **`systemd-journald: system.journal corrupted or uncleanly shut down, renaming and replacing`** (the 01:56 failed resume), thunderbolt device-link, spi-nor dummy regulator, `facetimehd: Direct firmware load for facetimehd/1871_01XX.dat failed with error -2`, applesmc `hwmon_device_register() is deprecated`, and two WARNs from `wl` (below).

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C32 | **risk** (still open) | **One of 22 suspend cycles in boot -1 never resumed:** `PM: suspend entry` x22, `suspend exit` x21; the journal ends at `01:56:11 PM: suspend entry (deep)`, the next boot is 02:04:28 (8 min later, forced power-off; journald replaced the unclean file). Boots -7..-2 are all balanced (25/25, 6/6, 9/9, 2/2, 1/1, 0/0) and ended cleanly. Round 71 already analysed it and installed `zz-sleep-mark`; this boot has had no real suspend yet (only the `test manual` line at 02:26), so the diagnostic is armed but unproven. Open options listed there (unload `wl`/`facetimehd` in the sleep hook, drop XHC1 from `/proc/acpi/wakeup`, `mem_sleep_default=s2idle`) are still untried. [verified counts; cause unknown] | `journalctl -b -1 -g 'PM: suspend'`, `journalctl -t sleep-mark` | After the next lid close, read `journalctl -b -1 -t sleep-mark` (no `post` = never woke). If it repeats, try unloading `wl` + `facetimehd` in the hook first (cheapest). | S |
| C33 | **risk** | `wl` fires kernel WARNs on every boot and taints the kernel: `WARNING: arch/x86/kernel/cpu/bugs.c:3830 __warn_thunk` "**Unpatched return thunk in use. This should not happen!**" from `wl_module_init -> getvar` (the blob contains an unpatched return, i.e. it bypasses the retbleed/SRSO-style return thunk mitigation), plus `memcpy: detected field-spanning write (size 405) of single field "dst" at src/wl/sys/wl_cfg80211_hybrid.c:3139` (FORTIFY, 02:04:35), `cfg80211` `__cfg80211_connect_result` WARN (sme.c:845, 13.10 20:24:51), `WLC_SCAN error (-22)` / `Scan_results error (-22)` repeating (22x in boot -7), and `NetworkManager ... do-change-link failure 23 (Too many open files in system)` 100x in boot -1 (wl returns ENFILE when NM randomises the MAC on suspend; "assume success"). The kernel itself prints "not maintained and is incompatible with Linux kernel security mitigations". Documented in MAINTENANCE as "harmless"; it is harmless to function but is the prime suspect class for the failed resume and costs ~9 % of a core (C13). [verified messages; link to the resume failure inferred] | Keep the MAINTENANCE note; consider a USB or replacement Wi-Fi card as the real fix (hardware, owner's call). | hardware |
| C34 | risk (hardware, not desktop) | USB enumeration errors on the tablet cable: `usb 1-2: device descriptor read/64, error -110` 53x and `xhci_hcd: Timeout while waiting for setup device command` 38x on 13.10 23:07-23:10, `usb usb1-port2: unable to enumerate USB device` 14.10 04:07, `usb 1-1: ... -110` 14.10 11:03; the Lenovo Tab M10 (17ef:4ee8) is the device. Earlier (round 71) `XHC1._PS0 AE_AML_LOOP_TIMEOUT` twice. [verified] | `journalctl -b -1 -k` | New cable/port for the tablet; part of the suspend suspicion list (XHC1). | S |
| C35 | cruft | `facetimehd` loads at every boot (and **22 times per resume cycle in boot -1**, one firmware-miss line each): `/lib/firmware/facetimehd/` contains only `firmware.bin`, the driver first asks for `1871_01XX.dat`. Camera works via fallback. Module is 139 KB, refcount 0, so the cost is only log lines and the unproven suspend risk. [verified] | `ls /lib/firmware/facetimehd`, journal | Optionally `blacklist facetimehd` and load on demand if the camera is rarely used. | S |
| C36 | dup / cruft | **`/etc/X11/xorg.conf.d/30-touchpad.conf` and `40-touchpad.conf` both match every touchpad:** 30 sets `Tapping on` + `NaturalScrolling true`, 40 (later) sets `Tapping off`, `NaturalScrolling true`, `ClickMethod clickfinger`, `DisableWhileTyping true` - so 30 is fully shadowed (CHANGELOG line 221: tapping off is the fix). Also `00-keyboard.conf` (written by localectl), the two touchpad files, `/etc/modprobe.d/{broadcom-wl,hid_apple}.conf`, `/etc/NetworkManager/conf.d/20-broadcom-wifi.conf`, `/etc/udev/rules.d/80-spd-mtk.rules`, `/etc/mbpfan.conf` exist **outside the tree** (`desktop/system/` has only tlp.d, 20-intel.conf, journald.conf.d, lightdm.conf.d, xfce-i3-session, xsession, firmware policy, zz-sleep-mark), so `make status` cannot see them and BOOTSTRAP cannot rebuild them. Xorg log also prints `(EE) AIGLX error: dlopen of /usr/lib/dri/i965_dri.so failed` (SNA driver asks for the removed i965 DRI driver; Haswell uses `crocus`; harmless), `libinput: bcm5974: Failed to create a device for /dev/input/mouse1`, `client bug: Invalid path /dev/input/event4/5`. [verified files and content] | Merge 30+40 into one tree file `desktop/system/etc/X11/xorg.conf.d/40-touchpad.conf`, delete 30; move the other files above into `desktop/system/etc/` (`make apply` through lab). | S-M |
| C37 | ux (informational) | Mitigation state and warnings are all firmware/driver noise except C32/C33; nothing else repeats. Kernel WARN flag W comes from the `wl` init WARN, so every boot starts "tainted" and `Disabling lock debugging due to kernel taint` is printed - lockdep is off, which only matters for kernel debugging. [verified] | | | |

## 10. Other things seen

| # | severity | finding | evidence | suggested fix | effort |
|---|---|---|---|---|---|
| C38 | perf (low, not desktop) | Two user timers run on this laptop: `vcmon-collect.timer` every 30 min (this boot: 5.9 s, 9.9 s, 14.9 s CPU per run, 26-34 MB peak, wall 1.5, 3.9, 4.7 min - growing) and `ihor-d1-backup.timer` daily (4.5 s CPU, 189 MB peak). Together ~0.5 % of a core on average plus network. [verified] | `journalctl --user -g Consumed` | None for the desktop; keep in mind when sampling idle. | - |
| C39 | cruft | i3 core dumps of 14.10 (6 in `coredumpctl`, not 7): skipped per coordinator. (One line for the record: all six have the identical stack - `strlen(NULL)` in `main()` - and `Command Line: i3 -c .../scratchpad/notify/i3.conf` with `DISPLAY=:37`, `XDG_RUNTIME_DIR=.../notify/rt`, i.e. the nested test i3, not the live session.) | `coredumpctl info 800201` | | |

## Top 5 by value/effort

1. **C1 - silence the libinput flood** with `LogFilterPatterns=~Invalid fake finger state` in a touchegg drop-in (S): removes ~95 % of all journal entries, ~140-150 MB of a 316 MB journal and the fsync churn; the 37 MB Xorg log copy is the remainder.
2. **C10 - make `panel-telegram` push-based** (deskd already sees the title; S-M): -2.3 % of a core permanently and one `xdotool` X round trip every 5 s; closes the item the 10.10 audit left open.
3. **C23 + C24 - decide the power mode and tune mbpfan** (S): power-saver on AC cripples the CPU at 1.86 GHz during all heavy work; mbpfan's stock curve lets the CPU sit at 80+ °C before the fan responds. Put `/etc/mbpfan.conf` in the tree and measure again.
4. **C18 - stop using tmpfs for bulk agent output** (S): ~1 GB of RAM (17 %) is `/tmp` content, one scratchpad is 933 MB; cap `/tmp` and reap the 33 leaked profile dirs.
5. **C6 - forbid in-place writes to mapped files** (S): one rewritten `Diablo.ttf` crashed deskd and six panel plugins; add the rule to MAINTENANCE/AGENTS.md. (Equal value, same effort: **C32** - read `sleep-mark` after the next lid close.)

Also cheap and clean: C20 (remove zram-generator leftovers), C3 (remove acpid), C2 (unmanage tailscale0 in NM), C36 (merge the two touchpad conf files into the tree), C9 (`/boot` fmask).

## What I did not cover

* **True idle**: no quiet window existed (other audits ran throughout); idle CPU/wakeup numbers, the power draw on battery (`power_now` does not exist; machine was on AC) and the idle temperature/fan equilibrium were not measured. powertop's per-timer "usage" (e.g. `wl_timer` 786 ms/s, `tcp_keepalive_timer` 249 ms/s) looked like attribution artefacts and is not relied on; only the `perf record` share is.
* The previous boot's memory/swap state and CPU per process (7 days, gone with the boot); CPU/IO cost of journald itself (no per-unit figure for `systemd-journald` in the logs); the ~0.5 s `xfconf-query`/glycin SVG costs inside the panel beyond the wrapper totals.
* The root cause of the stuck `BTN_TOOL_*` bit (needs `libinput record` during a swipe, i.e. the owner's hands on the pad), and what causes `wl`'s CPU use (closed source).
* Nothing was installed, changed, restarted or killed; the unclean-shutdown evidence of 15.10 01:56 (Round 71) was only re-read, no new suspend test was done. `xdotool`/screenshots on `:0` were not used (panel-telegram was timed with a stub `xdotool` on PATH).
* Items already in AUDIT-2026-10-10 (genmon periods, junk plugin ids, docklike rc) were not re-measured except where they changed (C10).
* The 14.10 i3 core dumps (per coordinator), AUR/pacman package audit, security review of open ports, Firefox profile/extension memory, Zoom/RustDesk (not running).
