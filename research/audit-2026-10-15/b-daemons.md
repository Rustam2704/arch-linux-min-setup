# Audit B — daemons, panel scripts, apps, installer (15 October 2026)

Read-only review of the requested source tree. I read `tools/audit/common.md`, README, ARCHITECTURE, FEATURES, MAINTENANCE, the recent CHANGELOG entries and the 10 October audit first. **Verified** means measured, run, or a deterministic control/data-flow trace; **inferred** means the failure needs a live stimulus. Earlier audit findings are identified where relevant rather than repeated as new discoveries.

## Runtime cost and genmon inventory

`/proc/<pid>/stat` user+system tick deltas over **60.45 s** on the running session (one-core percentage; this was a live-session sample, not a controlled idle benchmark):

| Process | CPU seconds | One-core CPU | RSS at end | Source of regular work |
|---|---:|---:|---:|---|
| netqd | 0.11 | 0.182% | 20.23 MiB | 1 s loop; two persistent `ping` children; `nmcli` and `iw` about every 10 s on Wi-Fi |
| sysqd | 0.12 | 0.199% | 17.42 MiB | 2 s `/proc` sampling loop |
| osd-daemon | 0.04 | 0.066% | 53.12 MiB | event driven audio/key input plus 300 ms XKB poll |
| sky-stars | 0.82 | 1.357% | 11.23 MiB | 250 ms star frame; 60 ms fire frame while shown |

The four sampled processes totalled **1.09 CPU seconds** and **102.0 MiB RSS**. Child `ping`/`pactl` processes, the panel, genmon, Xorg and compositor are excluded. Sources: `/proc` sample above; `desktop/bin/netqd:339-422`, `sysqd:87-115`, `osd-daemon:583-600`, `sky-stars:403-429`. Sky-stars' 1.36% exceeds the older architecture note's ≤0.6%, but this one sample does not establish idle cost.

Every declared genmon command in `desktop/xfconf/xfce4-panel.xml` is below. “Cost” describes one invocation from code; counts are per copy of the panel. A second screen can add copies of some plugins, so multiply by the actual plugin instances there. Timers are backup refreshes for the pushed plugins.

| Plugin id / script | Period | Starts/min | Cost per timer run |
|---|---:|---:|---|
| 45 `panel-workspaces` | 60 s | 1 | shell + `cat` one deskd file; event refresh on workspace change |
| 40 `panel-telegram` | 5 s | 12 | Python + theme JSON + one `xdotool` search/name subprocess |
| 41 `panel-net` | 1 s | 60 | shell + `cat` netqd markup |
| 42 `panel-sys` | 60 s | 1 | shell + `cat` CPU markup; sysqd also refreshes on change |
| 63 `panel-ram` | 60 s | 1 | shell + `cat` RAM markup; sysqd also refreshes on change |
| 64 `panel-swap` | 60 s | 1 | shell + `cat` swap markup; sysqd also refreshes on change |
| 43 `panel-weather` | 60 s | 1 | Python + theme JSON + cache read; on cache age >15 min, HTTPS request (8 s timeout) and atomic cache write |
| 44 `panel-battery` | 30 s | 2 | Python + theme JSON + `/sys` reads + compare SVG; writes only on change |
| 55 `panel-layout` | 60 s | 1 | shell + two `cat` reads; osd-daemon refresh on change |
| 60 `panel-wifi` | 60 s | 1 | shell + `cat`; netqd refresh on change |
| 61 `panel-clock` | 1 s | 60 | shell + one `date` subprocess; blink needs 1 s |
| 62 `panel-audio` | 60 s | 1 | Python + theme JSON + audio JSON + SVG compare/write; on missing state, five `pactl` subprocesses; osd-daemon refresh on change |

**Budget:** 142 scheduled plugin command starts/min on the primary panel: 126 shell + 16 Python (12 Telegram + 1 weather + 2 battery + 1 audio). The 1 Hz clock and net reader account for 120 starts/min together. Event refreshes and a second panel add starts. Evidence: `desktop/xfconf/xfce4-panel.xml:53-181` and the scripts above. The 10 October audit's P1 is **partly resolved**: CPU/RAM/SWAP, Wi-Fi, audio, layout and workspaces now have 60 s backup periods, battery 30 s; Telegram remains 5 s, net and clock 1 s.

## Daemons and runtime files

| # | Severity | Finding | Evidence (file:line / command output) | Suggested fix | Effort |
|---|---|---|---|---|---|
| B1 | **perf** | **Verified trace:** netqd rewrites both `netq.txt` and `netq.json` every second even when their content is unchanged: 120 atomic replacements/min, plus one 1 Hz genmon reader. CPU is only 0.182% in the sample; this is mainly avoidable I/O and wakeups. | `desktop/bin/netqd:413-422`; `/proc` sample above | Compare rendered content and state before replacing; keep 1 Hz updates when latency/traffic actually changes. | small |
| B2 | **risk** | **Inferred:** the OSD FIFO client can block indefinitely if a stale FIFO exists with no reader. `osd` checks only `-p`, then opens it for blocking `printf`; it does not start the service in that case. A crashed or start-limited service can leave that path behind. | `desktop/bin/osd:4-6`; `desktop/bin/osd-daemon:703-709`; `desktop/config/systemd/user/osd.service:3-13` | Use a bounded nonblocking write, and start/retry the service when there is no reader; remove/validate stale FIFO at daemon startup. | small |
| B3 | **perf** | **Verified trace:** the external-layout watcher wakes every 300 ms, about 200 wakeups/min, even though the process also receives XRecord key events. Its measured whole-process CPU was only 0.066%, so this is low priority. | `desktop/bin/osd-daemon:583-600`; `/proc` sample above | Subscribe to XKB state notifications if this path is revisited; keep the poll if reliability is better. | medium |
| B4 | **risk** | **Inferred:** layout name and markup are each atomically replaced but are not an atomic pair. A scheduled genmon invocation between the two replacements can briefly show the new tooltip name with old coloured markup; the explicit refresh occurs after both. | `desktop/bin/osd-daemon:535-546`; `desktop/bin/panel-layout:6-17` | Publish one runtime document containing both values, or make the reader derive tooltip name from the single markup/state record. | small |
| B5 | **bug** | **Verified trace:** sound-server failure is rendered as volume 0, unmuted, mic 0 and no recording. The audio watcher publishes this false state on startup or server loss, and panel-audio's fallback does the same; the indicator cannot distinguish “audio unavailable” from true silence. | `desktop/bin/osd-daemon:469-500`; `desktop/bin/panel-audio:22-43` | Include an availability flag from checked `pactl` return codes and show a disabled/unknown state. | medium |
| B6 | **risk** | **Verified trace:** the genmon-facing runtime writers use temp+replace: netqd's net text/JSON/Wi-Fi SVG, sysqd's text/SVG, osd's layout/audio JSON, deskd's workspace text, panel-audio/battery SVG. The exception near this chain is `netmenu.speedtest()` writing `~/.cache/netq-speed.json` in place; netqd and netmenu can read partial JSON, though both catch parse errors, producing a missing speed result for that tick. | `desktop/share/sky-desktop/netmenu.py:55-58`; readers `desktop/bin/netqd:386-393`, `netmenu.py:164-167`; atomic examples `sysqd:60-69`, `desktop/share/deskd/deskd.py:2790-2793` | Use a unique temp file and `os.replace` for the speed result. | small |

## Menus, panel scripts and utility apps

| # | Severity | Finding | Evidence (file:line / command output) | Suggested fix | Effort |
|---|---|---|---|---|---|
| B7 | **bug** | **Verified trace:** the power menu always assumes `BAT0`; without a battery it displays `Battery % · unknown`, whereas the battery indicator hides. | `desktop/share/sky-desktop/powermenu.py:19,63-77`; `desktop/bin/panel-battery:70-73` | Discover a `BAT*` supply as the indicator does, and show “No battery” when absent. | small |
| B8 | **bug** | **Verified trace:** selecting a TLP profile first saves the mode, then calls `sudo -n tlp` without checking the return code. A failed/missing TLP command leaves the selected mode saved and lit even though it did not take effect. This call runs on GTK's idle/main thread and may freeze the whole osd-daemon UI for its 30 s timeout. | `desktop/share/sky-desktop/powermenu.py:46-60,129-138` | Run TLP off the GTK thread; report failure, preserve/revert the previous saved mode, and update the toggle from the actual profile. | medium |
| B9 | **bug** | **Verified trace:** Wi-Fi connect runs `nmcli` in a thread with a 45 s timeout but no exception handler. If `nmcli` is absent or times out while NetworkManager is down, the thread dies and only the initial “Connecting…” notification is shown. | `desktop/share/sky-desktop/netmenu.py:137-148` | Catch `OSError` and `TimeoutExpired` in that worker and notify the failure. | small |
| B10 | **risk** | **Verified trace:** a speed test creates an exclusive lock file and removes it only in `finally`. A killed process leaves the file forever; later clicks always report “already running”. Its two network measurements can each take 40 s. | `desktop/share/sky-desktop/netmenu.py:39-64` | Use `flock` on an open FD (released on process death), or validate a PID before reusing the lock. | small |
| B11 | **risk** | **Inferred:** two `paste-image` processes in the same second can both choose the same unused filename before either writes, and `savev` can overwrite the first image. A failed Thunar D-Bus `CopyInto`/`MoveInto` also has no handled error or feedback. | `desktop/bin/paste-image:60-92,94-103` | Reserve the target name exclusively before saving; catch D-Bus and save errors and show a notification. | medium |
| B12 | **risk** | **Verified trace:** `sky-edit` truncates and rewrites the editor target directly on every 150 ms save and on close; readers can see a partial file, and a failed write may already have destroyed the prior content. | `desktop/bin/sky-edit:35-58` | Write to a same-directory temp file, then atomically replace, preserving needed mode/ownership. | small |
| B13 | **bug** | **Verified trace:** weather cache loading accepts any JSON value, then indexes `cached["fetched"]` and later `data["current"]`. A truncated-but-valid or old-schema cache, or a successful HTTP response containing an API error object, crashes the genmon script every minute rather than showing the last valid reading/fallback. | `desktop/bin/panel-weather:46-83` | Validate required fields before accepting a cache or replacing it; catch response-shape errors and retain last valid data. | small |
| B14 | **dup** | **Verified trace:** the fixed-width `value()`/transparent-zero logic is separate in sysqd, netqd and panel-battery despite the shared `sky_text` builder. Colour selection and refresh/file replacement helpers are also repeated. The existing `sky_theme`/`xfpanel` paths should remain the single sources for theme and panel refresh. | `desktop/bin/sysqd:46-56`, `netqd:302-329`, `panel-battery:98-107`; `desktop/share/sky-desktop/sky_text.py:52-116`, `xfpanel.py:57-60` | Centralize simple fixed-digit markup and atomic changed writes; keep Pango-sensitive padding in `sky_text` rather than copying its measurement logic. | medium |

## light-year

`light-year` is a native GTK month-view calendar (`app.py`, `widgets.py`, `recurrence.py`) with Google Calendar API and optional Zoom meeting creation (`api.py`). `desktop/bin/light-year` starts the app; its `Gtk.Application` id activates the existing instance. It is not a daemon. Network work is offloaded to worker threads, and tokens are stored with mode 0600 via atomic replacement.

| # | Severity | Finding | Evidence (file:line / command output) | Suggested fix | Effort |
|---|---|---|---|---|---|
| B15 | **bug** | **Verified trace:** editing an all-day event creates a dialog with default 10:00–11:00 times. Changing just its title passes those times to `update_event`, which sends `dateTime` fields and converts the all-day event into a timed one. | `desktop/share/light-year/app.py:467-468,550-564,945`; `desktop/share/light-year/api.py:294-305,438-443` | Model all-day events explicitly in the dialog and preserve `date` start/end unless the user elects to convert them. | medium |
| B16 | **bug** | **Verified trace:** `Window.draw()` groups each event only under its start date. Multi-day and overnight events do not appear on subsequent days, despite being returned by Google for the visible interval. | `desktop/share/light-year/app.py:720-723`; `desktop/share/light-year/api.py:239-264` | Expand each event across intersected local dates, using exclusive end semantics for all-day events. | medium |
| B17 | **bug** | **Verified trace:** on a delete/move API error, `mutate.done()` sets the error status then immediately calls `load(force=True)`. A successful reload overwrites the error with “Google”/“Google · Zoom”, so the user may miss a failed change; optimistic drag position also needs restoration. | `desktop/share/light-year/app.py:703-712,993-1009,682-693` | Keep the mutation error until a new user action or explicit dismissal; restore the original event on failed drag. | small |
| B18 | **risk** | **Verified trace:** creating a Zoom meeting occurs before creating the Google event. If the Google POST fails, the Zoom meeting remains orphaned; there is no compensating delete. | `desktop/share/light-year/api.py:271-287` | On Google failure, delete the new Zoom meeting and surface any cleanup failure. | medium |
| B19 | **risk** | **Inferred:** the OAuth loopback handler accepts the first GET on port 8412 regardless of path or state, and handles exactly one request. An unrelated local request can consume that single request, making sign-in fail after the user authorizes. | `desktop/share/light-year/api.py:146-176` | Check callback path and a random state token; continue serving until a valid callback or timeout. | medium |

## Installer, journal and tests

| # | Severity | Finding | Evidence (file:line / command output) | Suggested fix | Effort |
|---|---|---|---|---|---|
| B20 | **bug** | **Verified trace:** removing a source from `desktop/` does not remove its installed target. `sources()` lists only current files; `differences()` and `apply()` only visit those. `build()` also never prunes obsolete `.build/desktop` entries. This violates the declared-tree/decisive-cleanup contract. | `tools/desktop.py:47-49,149-154,187-202,209-234`; `Makefile:14-23` | Maintain a generated install manifest, diff removed targets, and journal removals via `lab remove`; clear or reconcile build output. | medium |
| B21 | **bug** | **Verified trace:** rollback always prepends `sudo` to `backup` and `file` actions when invoked as the user, even for `~/.local` and `~/.config`. A first-time installed user file *is* recorded correctly as `file` and will be deleted, but only after unnecessary privilege escalation; unattended rollback may fail. Root-owned newly created directories are recorded as unprivileged `rmdir` shell commands and fail to disappear. | `lab/lab:36-49`; `lab/rollback.py:24-35`; `tools/desktop.py:212-224` | Choose elevation per target; journal directory ownership/type and remove root directories with the matching privilege. | medium |
| B22 | **risk** | **Verified trace:** conflict detection covers only `backup`/`file` actions. xfconf changes are journaled as arbitrary `cmd`; rolling back an older experiment that changed the same xfconf property as a newer one is allowed and overwrites the newer value. | `lab/rollback.py:12-20,34-36`; `tools/desktop.py:139-145` | Record structured xfconf actions with channel/property keys and include them in conflict checking. | medium |
| B23 | **risk** | **Verified trace:** `differences()` compares bytes only. A missing or incorrect executable bit on an installed script/system hook gives a clean `status` and is never corrected by `apply`; `check()` parses shell/Python but does not check install mode. This is especially relevant after the recent sleep-hook mode fix. | `tools/desktop.py:187-195,225-233`; CHANGELOG round 71 | Include expected mode in drift detection and journal mode-only corrections. | small |
| B24 | **risk** | **Inferred:** xfconf status reads the on-disk XML (`xfconf_live`) instead of querying the running xfconf service, while `apply` changes properties through `xfconf-query`. If xfconf has in-memory updates not yet flushed, status/apply can compare against stale state and record the wrong undo value. The parser also ignores undeclared/deleted properties by design. | `tools/desktop.py:98-125,139-145` | Query live properties and their types through xfconf; distinguish managed-property drift from full-channel drift in the report. | medium |
| B25 | **risk** | **Verified trace:** `lab write` and `lab remove` append the journal record before the final file replacement/removal. An interrupted or failed operation can leave an undo record for a mutation that never happened; rollback can then remove a target placed there later or restore an old backup over later manual changes. The stage/temp and backup files also remain on failures. | `lab/lab:26-50,53-61`; `lab/rollback.py:21-46` | Commit each mutation and journal record as one recoverable transaction (prepared/applied states), and clean staged files on error. | medium/large |
| B26 | **risk** | **Verified trace:** the “failed series split does not truncate original” test makes the *creation* POST fail and asserts no PATCH happened. It never exercises the dangerous case where creation succeeds and truncating the old series fails, nor verifies deletion of the new series or error surfacing. The installer and rollback have no direct tests; `make test` runs only calendar/chords/sysicons and GTK smoke. | `tests/test_calendar.py:56-70`; cleanup branch `desktop/share/light-year/api.py:483-493`; `Makefile:8-11` | Add a focused mock test for post-create PATCH failure/cleanup and isolated temp-tree tests for installer deletion, modes, first-install rollback, directories and xfconf conflict ordering. | medium |

`PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v`: **16 tests passed in 1.081 s**. `PYTHONDONTWRITEBYTECODE=1 python3 -B tools/desktop.py check`: **182 sources checked**. An XML inventory independently confirmed 12 genmon plugins and 142 scheduled starts/min. These results do not cover the missing paths above. `tests/deskd_smoke.py` was not run: it creates a Xephyr window on the real desktop (`:9`), which the audit rules forbid. `tests/gtk_smoke.py` was not run; it is synthetic UI coverage, not a Google/Zoom integration test.

## Stale paths and second-screen fallback

| # | Severity | Finding | Evidence (file:line / command output) | Suggested fix | Effort |
|---|---|---|---|---|---|
| B27 | **bug** | **Verified trace:** the standalone `audio-menu` fallback references `audiomenu._state["win"]`, but `audiomenu` has no `_state`; it now uses `PopMenu.MENU.win`. If osd-daemon is unavailable, invoking this command opens the popup then raises `AttributeError` before entering GTK's loop. No active desktop configuration calls the script; the panel calls `osd menu audio` directly, so this is also a stale entry point. | `desktop/bin/audio-menu:20-26`; `desktop/share/sky-desktop/audiomenu.py:85-91,170`; `desktop/bin/panel-audio:81` | Remove the unused wrapper and update its references in docs, or repair the fallback if direct invocation is intended. | small |
| B28 | **cruft** | **Inferred:** `app-focus-or-launch` has no call site in the declared `desktop/` tree. The changelog says a panel terminal launcher once used it, but current xfconf panel launchers only list `power-menu.desktop`. It may survive as an installed/manual launcher outside the declared tree, so confirm live references before removal. | `desktop/bin/app-focus-or-launch:1-79`; `rg -n 'app-focus-or-launch' desktop` returned only its own file; `desktop/xfconf/xfce4-panel.xml:136-140`; `CHANGELOG.md:467` | Check installed launchers; remove the script and stale documentation if unused, or add its launcher to the declared tree. | small |
| B29 | **bug** | **Inferred:** when deskd has not yet written a requested second screen's workspace file, `panel-workspaces <output>` silently falls back to the primary screen's markup. A secondary panel can briefly display and invoke primary workspace targets. | `desktop/bin/panel-workspaces:6-11`; atomic writer `desktop/share/deskd/deskd.py:2785-2796` | For a named output, show a neutral placeholder until that output's file exists; use primary fallback only for the primary invocation. | small |

## Top 5 by value/effort

1. **B20** — install manifest and journaled deletion of removed sources; otherwise cleanup silently fails.
2. **B21–B22** — correct rollback privilege and xfconf conflict handling before relying on rollback for future experiments.
3. **B15** — preserve all-day events during edits; prevents unintended calendar changes.
4. **B8** — move TLP application off GTK and check its result; prevents false settings and UI freezes.
5. **B17** — keep calendar mutation errors visible and undo optimistic failed drags.

## What I did not cover

- No live clicks, display `:0` access, restarts, service changes, network calls, installer apply/rollback, or write outside this report. The 60 s `/proc` sample was read-only.
- No Google/Zoom credentials or live API operations; no external-monitor hotplug test. Those require state changes outside the audit rules.
- deskd internals, its control/favorites scripts, compositor and desktop configuration are outside Audit B except where their runtime-file contracts or test harness explain a finding.
