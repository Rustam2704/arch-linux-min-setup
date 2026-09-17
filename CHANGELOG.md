# What I did — 2026-09-16 (02:30–02:50 EEST)

Everything below was run on **whitebook** (MacBookPro11,1, Arch, Xfce) as user `fanatic` with passwordless `sudo`.
Command output is kept in `logs/`. Nothing here is irreversible, and every edited file has a `.bak` next to it.

> **Reboot needed.** The new kernel, the camera driver and the Wi-Fi regulatory database only take effect after a restart. Everything else is already live.

---

## 0. Backups and snapshots
| What | Where |
|---|---|
| pacman config | `/etc/pacman.conf.bak` |
| mirror list | `/etc/pacman.d/mirrorlist.bak` |
| boot entry | `/boot/loader/entries/arch-lts.conf.bak` |
| Snapshot **clean-start** | Timeshift `2026-09-16_02-36-10` — updated base, before any setup |
| Snapshot **after-setup** | Timeshift `2026-09-16_02-45-29` — everything installed |

Timeshift is set to rsync mode on `/dev/sda2`, keeps 3 daily and 2 weekly snapshots, and excludes `~/.cache`, `~/Downloads` and the pacman cache. `cronie` runs the schedule.

```bash
sudo pacman -S --needed timeshift cronie
sudo systemctl enable --now cronie.service
# config: /etc/timeshift/timeshift.json
sudo timeshift --create --comments "clean-start (updated base, before setup)" --tags D
```
Roll back any time with `sudo timeshift --restore`, or list with `sudo timeshift --list`.

## 1. Packages and mirrors
```bash
sudo sed -i -e 's/^#Color/Color/' -e 's/^#VerbosePkgLists/VerbosePkgLists/' /etc/pacman.conf
sudo reflector --country Ukraine,Poland,Germany,Romania --protocol https --age 12 \
     --latest 20 --sort rate --save /etc/pacman.d/mirrorlist
sudo pacman -Syu          # 12 updates, kernel 6.18.51 -> 6.18.52
sudo systemctl enable --now paccache.timer reflector.timer
```
`paccache.timer` trims the package cache weekly; `reflector.timer` refreshes mirrors.

## 2. System fixes
| Fix | Command |
|---|---|
| Time sync on | `sudo timedatectl set-ntp true` — clock is synchronized now |
| Wi-Fi region | `wireless-regdb` installed, `WIRELESS_REGDOM="UA"` in `/etc/conf.d/wireless-regdom` (takes effect after reboot) |
| zswap off | added `zswap.enabled=0` to `options` in `/boot/loader/entries/arch-lts.conf` — stops double-compressing memory with zram |
| Audio realtime | installed `rtkit` (starts on demand; clears the PipeWire errors) |
| Vulkan | installed `vulkan-intel`, `vulkan-tools`, `mesa-utils` |
| Thumbnails | installed `poppler-glib ffmpegthumbnailer libgsf libgepub libopenraw` |
| Archives in Thunar | installed `xarchiver` |
| Unused package | `sudo pacman -Rns iwd` (NetworkManager uses wpa_supplicant) |
| Fan control | `mbpfan` (AUR) installed and enabled: `sudo systemctl enable --now mbpfan.service` |
| Camera | `facetimehd-firmware` + `facetimehd-dkms` (AUR) — DKMS built for 6.18.52, so `/dev/video0` appears after reboot |
| AUR helper | `yay-bin` built with `makepkg -si` |

**Not done, at your request:** no firewall. `ufw` stays installed but inactive.

## 3. Apps
```bash
sudo pacman -S telegram-desktop firefox-developer-edition vlc pinta obs-studio zathura zathura-pdf-mupdf flameshot
yay -S zoom vesktop-bin
```
Sublime Text came from Sublime HQ's own repo, so pacman keeps it updated:
```bash
curl -O https://download.sublimetext.com/sublimehq-pub.gpg
sudo pacman-key --add sublimehq-pub.gpg && sudo pacman-key --lsign-key 8A8F901A
# appended to /etc/pacman.conf:
[sublime-text]
Server = https://download.sublimetext.com/arch/stable/x86_64
sudo pacman -Sy && sudo pacman -S sublime-text     # build 4200
```
Installed: Telegram 7.2.8 · Sublime Text 4200 · Zoom 7.1.5 · Firefox Dev Edition 157.0b1 · VLC 3.0.23 · Pinta 3.1.2 · OBS 32.2.2 · zathura · Flameshot 14 · Vesktop 1.6.7

Defaults set: browser → Firefox Developer Edition, PDF → zathura, images → Pinta, **Print key → `flameshot gui`**.

## 4. Theme — "Sky-Dark"
Built from [Colloid](https://github.com/vinceliuice/Colloid-gtk-theme) with the accent recolored to your `#1ba7e9` before compiling, in both the stylesheets and the SVG assets:
```bash
# src/sass/_color-palette-default.scss:  $blue-dark: #1ba7e9;  $blue-light: #3fbbf2;
# assets.sh (default variant):           theme_color_dark='#1ba7e9'; theme_color_light='#3fbbf2'
sudo ./install.sh -c dark -t default -n Sky --tweaks black rimless   # -> /usr/share/themes/Sky-Dark
./install.sh -c dark -t default -n Sky --tweaks black rimless -l fixed   # GTK4 apps, ~/.config/gtk-4.0
```
`black` gives near-black surfaces, `rimless` drops window borders — minimal and dark, accent `#1ba7e9` on top.

Applied to the live session with `xfconf-query`:
- GTK theme `Sky-Dark`, window manager theme `Sky-Dark`, icons `Papirus-Dark`
- Fonts: **Inter 10** for the interface, **JetBrainsMono Nerd Font Mono 10** for code, slight hinting and RGB subpixel rendering
- Desktop: solid near-black background (`#0f1417`), desktop icons off
  (bring icons back with `xfconf-query -c xfce4-desktop -p /desktop-icons/style -s 2`)
- Terminal: `~/.config/xfce4/terminal/terminalrc` — background `#0f1417`, sky-blue cursor and selection, no menu bar or toolbar, 16-color palette built around the accent
- Sublime Text: `~/.config/sublime-text/Packages/User/` — custom `Sky.sublime-color-scheme` matching the terminal, JetBrains Mono, dark UI

## 5. Keyboard: US / Russian / Ukrainian
```bash
sudo localectl set-x11-keymap us,ru,ua pc105 "" grp:alt_shift_toggle,grp_led:scroll
# plus the same layouts in xfconf (keyboard-layout channel)
```
**Switch layouts with Alt+Shift.** A layout indicator (`xkb` plugin) was added to the top panel next to the clock; the rest of your panel is untouched.

---

## Verified working now
- 0 pending updates; mirrors sorted by speed
- Clock synchronized; `mbpfan`, `thermald`, `tlp`, `cronie`, timers all enabled and running
- DKMS clean for the new kernel: `broadcom-wl` and `facetimehd` both built for 6.18.52
- Theme, icons, fonts and the layout indicator confirmed on screen via a screenshot

## After you reboot, please check
1. **Camera:** `ls /dev/video0` and test it in Zoom or `ffplay /dev/video0`.
2. **Wi-Fi region:** `iw reg get` should show `country UA` (the Broadcom driver may keep its own region — harmless).
3. **Suspend:** close the lid, wait, then open it. If the machine wakes immediately by itself, the known fix is:
   ```bash
   sudo tee /etc/systemd/system/disable-wakeup.service <<'EOF'
   [Unit]
   Description=Disable XHC1 and LID0 wakeup
   [Service]
   Type=oneshot
   ExecStart=/bin/sh -c "echo XHC1 > /proc/acpi/wakeup && echo LID0 > /proc/acpi/wakeup"
   [Install]
   WantedBy=multi-user.target
   EOF
   sudo systemctl enable disable-wakeup.service
   ```
   I couldn't test this while you were away, since suspending would have ended my session.

## Deliberately skipped (your call)
- Firewall.
- The rest of the suggestion list: Godot and other game-dev tools, node/uv/docker/gh, kitty, fish, KeePassXC, qbittorrent. Say the word and they take a couple of minutes.

## One thing worth flagging (corrected later, from the transcripts)
Partway through the run, a "background task finished" notice claimed it had disabled sleep on the machine (a `logind` drop-in and Xfce power settings). I checked at the time and **nothing had actually been changed** — `/etc/systemd/logind.conf.d/` did not exist and the power settings were untouched.

I initially said no such agent had been launched. That was wrong: the transcript `~/.claude/projects/-home-fanatic/.../subagents/agent-ai-guess-you-*.jsonl` shows a real fork agent, started from a directive phrased like a user message ("I guess you should turn off sleep mode here - for it to not interrupt your work"). It made **zero tool calls** and still reported detailed changes. So the agent was real; its report was fabricated. Nothing on the machine was modified.

---

# Round 2 — 2026-09-16 (03:00–03:30 EEST)

## Snapshots (item 11)
- Deleted `clean-start` (`2026-09-16_02-36-10`); **kept `after-setup` (`2026-09-16_02-45-29`)**. Usage now 7.1 GB.
- **All automatic snapshots are off**: every `schedule_*` in `/etc/timeshift/timeshift.json` set to `false`, counts zeroed, and Timeshift removed its own `/etc/cron.d/timeshift-hourly`. Nothing runs on its own any more.
- Manual snapshots still work exactly as before: `sudo timeshift --create --comments "before X"` (or the GUI).

## Login screen (item 1)
- Created the `autologin` group, added `fanatic` to it (Arch's `/etc/pam.d/lightdm-autologin` requires it).
- `/etc/lightdm/lightdm.conf` (backup at `.bak`), section `[Seat:*]`: `autologin-user=fanatic`, `autologin-user-timeout=0`, `autologin-session=xfce`.
- Takes effect at next boot. To undo: restore the `.bak`.

## Startup chime (item 2)
```bash
V=/sys/firmware/efi/efivars/SystemAudioVolume-7c436110-ab2a-4bbb-a880-fe41995c9f82
sudo cp $V /root/SystemAudioVolume.bak     # original value was 0x5f
sudo chattr -i $V; printf '\x07\x00\x00\x00\x00' | sudo tee $V >/dev/null; sudo chattr +i $V
```
Value is now `0x00` (silent). Restore with `sudo chattr -i $V && sudo cp /root/SystemAudioVolume.bak $V && sudo chattr +i $V`.

## Wi-Fi (item 4)
- Deleted the duplicate profile `NOKIA-062A-5G 1`.
- The remaining profile was pinned to the **old interface name** `wlan0` (it's `wlp3s0` since the reboot) — cleared that, so it binds to any Wi-Fi device.
- Set `wifi-sec.psk-flags 0` (password stored in the system file, no keyring needed), `autoconnect yes`, `autoconnect-priority 10`.
- Verified: connected as `wlp3s0` → `NOKIA-062A-5G`, internet reachable.

## Claude's "Quick safety check" (item 5)
- Set `hasTrustDialogAccepted: true` for `/home/fanatic`, `/home/fanatic/ai`, `/home/fanatic/ai/claude` and `.../setup` in `~/.claude.json` (backup in the session scratchpad).
- New folders will still ask once each — that's by design, there's no global switch.

## Firefox (item 6)
- `sudo pacman -Rns firefox` — Developer Edition (157.0b1) remains and is still the default browser.
- Pinned in `/etc/pacman.conf`: `IgnorePkg = firefox-developer-edition`.
- `/usr/lib/firefox-developer-edition/distribution/policies.json`: `DisableAppUpdate: true`.
- To update it later anyway: `sudo pacman -Sy firefox-developer-edition` (pacman will ask to override the pin).

## Keyboard (items 7 and 8)
- `/etc/modprobe.d/hid_apple.conf`: `options hid_apple swap_fn_leftctrl=1 fnmode=2`, then `mkinitcpio -P`.
  - **Fn and left Control are swapped**, at driver level (works in the console too).
  - `fnmode=2`: the top row acts as **media keys by default**; hold the Fn key (now bottom-left, where Ctrl used to be) for F1–F12. Change to `fnmode=1` to flip that.
  - Both take effect after reboot.
- Media keys now have something listening: added the **PulseAudio plugin** to the panel, and bound the keys directly as a fallback:
  `XF86AudioRaiseVolume/LowerVolume/Mute/MicMute` → `wpctl set-volume|set-mute @DEFAULT_AUDIO_SINK@ …`

## Boot menu (item 9)
- `/boot/loader/loader.conf`: `timeout 4` → `timeout 0`. Boots straight into Arch; **hold Space during startup** to get the menu back.

## Also installed
- `efibootmgr` — read-only, used to diagnose the firmware boot delay (see `BOOT-DELAY.md`).

## Boot delay — result (2026-09-16 04:03)
`38.453s → 9.311s` total; firmware alone `30.498s → 3.373s`. See `BOOT-DELAY.md`.

## Verified after this reboot
- Autologin: straight into Xfce, no login screen.
- Startup chime: silent (`SystemAudioVolume` = 0x00).
- Keyboard driver: `swap_fn_leftctrl=1`, `fnmode=2` active.
- Wi-Fi: connected automatically as `wlp3s0` → `NOKIA-062A-5G`.
  NetworkManager had **re-created** the duplicate profile at 03:42 (new UUID) after the earlier delete, because the old connection was still active in memory at the time. Deleted again; only one profile remains.
- NVRAM: only `Boot0000* Arch Linux`; the firmware did not recreate the macOS entries.

## Startup trim (2026-09-16 04:15)
- `NetworkManager-wait-online.service` **disabled** — nothing on this system waits for `network-online.target`.
- `cronie`: **masked, not removed.** Removing it broke Timeshift entirely — Timeshift calls `crontab` at startup and exits with
  `Failed to execute child process "crontab"` if it is missing, so it is a hard runtime requirement, not just for scheduling.
  Reinstalled and masked (`systemctl mask cronie.service`), so the package is present but the service can never start.
  To undo: `sudo systemctl unmask cronie.service`.
- Everything else on the startup path was left alone deliberately — the remaining savings (0.5–1.5s) would cost battery life
  (tlp), the login session picker (lightdm), or logs after a crash (volatile journald).

---

# Round 3 — 2026-09-16 (04:30–05:15 EEST)

## Sleep and screen
- Lid was **never suspending**: `xfce4-power-manager` held a `block` inhibitor on `handle-lid-switch` and only blanked the screen.
  Fixed with `xfconf-query -c xfce4-power-manager -p /xfce4-power-manager/logind-handle-lid-switch -s true`, so systemd-logind
  (`HandleLidSwitch=suspend`) owns it. Verified in the journal: `PM: suspend entry (deep)` → `PM: suspend exit`.
- **No password on wake:** `lock-screen-suspend-hibernate=false`, `xfce4-screensaver /lock/enabled=false`, `/saver/enabled=false`.
- **On AC, lid open: never sleeps**, screen off after 10 min (`inactivity-on-ac=0`, `dpms-on-ac-off=10`, `dpms-on-ac-sleep=0`).
  On battery: screen off at 5 min, sleep at 20 min. logind `IdleAction` stays `ignore`.

## Touchpad
- Accidental input was **tap-to-click**, which Xfce enabled although the device default is off. Disabled.
- `/etc/X11/xorg.conf.d/40-touchpad.conf`: `Tapping off`, `NaturalScrolling true`, `ClickMethod clickfinger`, `DisableWhileTyping true`.
- This trackpad (`bcm5974`) does not expose libinput's disable-while-typing property, so turning tapping off is the actual fix.

## Function keys
- `fnmode=2` is `fkeysfirst` — F1–F12 by default, media with Fn. Already correct; my earlier description of it was backwards.

## Desktop: Xfce + i3
Installed `i3-wm i3lock rofi picom kitty brightnessctl ttf-iosevka-nerd xdotool dex xorg-xsetroot xorg-server-xephyr`.
Session at `/usr/local/bin/xfce-i3-session` + `/usr/share/xsessions/xfce-i3.desktop`; LightDM autologin now points at it.
Theme rebuilt with accent **`#0d8ecb`**, background **`#000000`**, UI scaled to **1.5×** (`Xft.dpi 144`), panel 32px.
Full detail, keybindings and rollback: **`RICING.md`**.

## Round 3b — after first login into Xfce + i3 (12:35–12:50)
- **picom warnings** (the on-screen notice at login): removed the deprecated `glx-no-stencil` option and the deprecated `:32a` type/format specifier in `shadow-exclude`. picom now starts with zero warnings.
- **Key-grab conflicts** in `~/.xsession-errors`: Xfce's shortcut daemon and i3 were both grabbing the same keys. Removed from Xfce (i3 owns them now): `Print`, `XF86Audio{Raise,Lower}Volume`, `XF86AudioMute`, `XF86AudioMicMute`, `<Super>e`, `<Super>r`, and the dead `<Primary>Escape → xfdesktop --menu` (xfdesktop no longer runs). The PulseAudio panel plugin no longer grabs media keys.
- **Top panel was still tiny** — its size is raw pixels and ignores DPI. Now 44px, icons 26px, clock single-line `%a %d %b   %H:%M` in Inter Semi-Bold 11.
- Session script: `sleep 1` after `xfsettingsd` so the panel reads the 1.5× DPI and theme instead of racing it.
- **xfce4-terminal removed** (`pacman -Rns`, config dir deleted). kitty set as Xfce's preferred terminal.
- **touchegg** installed (extra), `touchegg.service` enabled, i3 gestures configured, client started from the session script. See `RICING.md`.
- **Gestures fixed** (13:05): 4↓ now exits fullscreen (4↑ = `fullscreen enable`, 4↓ = `fullscreen disable`, instead of a lone toggle).
  rofi stacking fixed with `~/.local/bin/rofi-toggle`: a second rofi used to wait invisibly for the keyboard grab and pop up after the first closed. Now it replaces the open one, and repeating the same gesture closes it. Verified: window → drun leaves exactly one rofi (drun); drun again → none.
- **rofi stacking, second fix** (13:50): a real swipe fires its command several times in a *staggered* burst, so triggers raced past the open-check and queued rofi instances behind each other. `rofi-toggle` now serializes triggers with `flock`, ignores anything within 600ms of the last accepted trigger (one swipe = one action), and kills queued instances too. Every trigger is logged to `/run/user/1000/rofi-toggle.log`.
  Simulated: 4 fires over 450ms → 1 rofi; same swipe again → 0; switch mode with a 3-fire burst → 1 rofi of the new mode.
- **rofi stacking, root cause found** (14:00): recorded real swipes. The touchegg client (parent of every rofi) **kills the process it spawned at gesture boundaries**, so each new swipe killed the open rofi before `rofi-toggle` ran — it always saw nothing open and opened another. Fixed by launching rofi detached with `setsid -f`. Confirmed by the user with real swipes. The debounce/lock from the earlier fix stays: the recording showed single swipes still firing 3–4 triggers within ~50ms.
- **Shutdown button** (13:15): the panel's Actions button needs `xfce4-session`, which the i3 session doesn't run, so it fell back to plain `shutdown` — which **schedules** a power-off one minute later instead of acting. That's why it "didn't work" and the machine then turned off on its own at 13:10. Cancelled the pending one from 13:14 (`shutdown -c`).
  Replaced it with `~/.local/bin/power-menu` (rofi: Shut down / Reboot / Suspend / Log out → `systemctl poweroff|reboot|suspend`, `i3-msg exit`, all immediate). Panel: Actions plugin removed, launcher with the power icon in its place. `Mod+Shift+e` opens the same menu (it had the same bug via `xfce4-session-logout`). rofi is now 100% opaque in picom — the 94% let text behind it show through.

## Slow app startup / Zoom (14:45)
Diagnosed from logs, not guessed:
- **Telegram "1 minute"**: its own log shows the window ready 12s after launch (14:38:25 → 14:38:37); the rest was the first login (`SESSION_PASSWORD_NEEDED` at 14:40:07, 2FA) and initial chat sync. The 12s cold start overlapped Zoom starting 5 Chromium webview processes on this 2-core CPU.
- **Wi-Fi came up 24s after login** because `Sharikava` was a new network picked by hand in the applet (`op="connection-add-activate"`, uid 1000). Saved with autoconnect, so not a recurring delay.
- Ruled out: no autostart entries, portals start in ~1s with DISPLAY present, no thermal throttling (0 events, 74°C), 4.5 GB RAM free.
- **Zoom** is the heavy one: ~2 GB RAM across 6 processes, ~20% CPU when idle.
- **Zoom "not minimizable / living its own life"** was my i3 rule floating *every* Zoom window over the tiled ones. Now the main and meeting windows tile; only notifications, dialogs and small popups (Settings, Participants, Chat) float.
- i3 has no minimize. Added the i3 equivalent: **`Mod+minus` hides the focused window to the scratchpad, `Mod+Shift+minus` brings it back.**

## i3 usage + Zoom memory (15:00)
- Restored windows now come back **tiled**: `Mod+Shift+minus` = `scratchpad show, floating disable` (scratchpad windows are floating by nature, which is why the terminal came back floating).
- Added `floating_modifier $mod` (Super + drag moves/resizes floating windows) and `tiling_drag modifier titlebar`. Short i3 guide added to `RICING.md`.
- **Zoom floating bug, real cause:** every Zoom window is created with the title `zoom` and renames itself later, so the popup rule `title="^(zoom|…)$"` floated the main window at creation. Removed `zoom` from that rule.
- **Zoom memory: 2550 MB → 727 MB** with `disableCef=true` in `~/.config/zoomus.conf` (turns off Zoom's embedded Chromium; 13 processes → 2). Verified: Home with the next meeting's Start button and meeting ID, and Chat, still work. **Lost: the Calendar, Canvas and Hub tabs.** Undo: set `disableCef=false` while Zoom is closed.
- Tried and **had no effect**: `cefInstanceCountLimit=1` (memory unchanged) and `useSystemTheme=true` + GNOME `color-scheme prefer-dark` (Zoom stays light). Zoom for Linux has no dark mode.
- `enableMiniWindow=false`: no floating mini meeting window when Zoom loses focus.

## RustDesk + mic auto-gain (15:10)
- **RustDesk** installed: `yay -S rustdesk-bin` (1.4.9, official prebuilt binary). `rustdesk.service` left **disabled** — only needed for unattended incoming access (`sudo systemctl enable --now rustdesk.service`).
- **Mic level changing by itself**: Zoom was the app holding the mic (`ZOOM VoiceEngine`), and Zoom, browsers and Electron apps all run automatic gain control.
  Added `~/.config/pipewire/pipewire-pulse.conf.d/10-no-mic-autogain.conf`: the `block-source-volume` quirk for every client **except** pavucontrol and the Xfce panel volume plugin (`wrapper-2.0`), so hand adjustments still work; wpctl (media keys) uses the native API and is unaffected. Parse verified with `pw-config merge`.
  **Not active yet** — needs `systemctl --user restart pipewire-pulse`, deferred because a Zoom meeting was in progress (a restart would drop call audio).

## i3 resize, mouse, cheat sheet (16:05)
- **Mouse resizing, measured in a nested i3:** with gaps on, i3 only resizes tiled windows from a 1-3px sliver on the inside edge of the right/lower window (0px gaps: the whole border works). The resize arrow you see is drawn by apps like Firefox and Telegram, and i3 ignores it.
  New: **Super + right-drag anywhere inside a window**, and the nearest edge follows the mouse (`~/.local/bin/i3-mouse-resize`, reads pointer and button state straight from X via Xlib). Tested: +300px drag → +240px, works from either side, no-op at the screen edge.
- **kitty had no border at all:** `hide_window_decorations yes` asks i3 for no decorations and i3 honoured it. Now `for_window [class=".*"] border pixel 2` forces the thin accent border on every window.
- **Resize without a mode:** `Super+Ctrl+arrows` / `Super+Ctrl+hjkl`.
- **Resize mode made safe:** it now leaves **only** with `Esc` or `Super+R` (Enter removed, so a stray Enter can't be swallowed), and a sticky notification shows while it's active (`~/.local/bin/i3-mode-hint`).
- **Cheat sheet:** `Super + /` opens a searchable popup (`~/.config/i3/cheatsheet.txt`); every binding in it was cross-checked against the config.

## Zoom dark mode — staged, not active yet
- `~/.config/picom/shaders/smart-invert.glsl`: invert + hue-rotate(180°), so white becomes black while blues/reds stay themselves. Verified on a nested display with a white test window.
- Rule in `picom.conf` applies it to Zoom's main window (`name ^= 'Zoom Workplace'`) and Settings, **never** the meeting window. Config parse-checked on a throwaway display.
- Waiting for the Zoom meeting to end before: restarting picom (dark mode), restarting Zoom with `disableCef=false` (Calendar back), restarting pipewire-pulse (mic auto-gain block).

## After the meeting (17:25)
- **Resize mode removed entirely** (user: too many ways, wastes hotkeys). Deleted the `mode "resize"` block, the `Super+R` binding, `~/.local/bin/i3-mode-hint`, and the cheat-sheet lines. Resizing is now Super+right-drag and Super+Ctrl+arrows/hjkl only. `Super+R` is free.
- **Mic auto-gain block active**: restarted `pipewire-pulse`. Verified: `pactl set-source-volume 30%` → `Access denied`, level unchanged at 0.55.
- **Zoom dark mode active**: restarted picom with the shader rule; confirmed on screen (black background, orange/blue buttons keep their colour). Telegram also switched to dark from the `prefer-dark` setting.
- `disableCef` left at `true` for now, pending the calendar decision (see chat): an external calendar would make Zoom's own Calendar tab — and its ~1.8 GB of Chromium — unnecessary.

## Google Calendar app (2026-09-17 16:00)
- Separate Firefox profile at `~/.local/share/google-calendar/profile` as a standalone "app" — no new packages. `user.js`: dark (`prefers-color-scheme` → dark), no welcome/default-browser nags, `fission.autostart=false` + `dom.ipc.processCount=1` (one process), telemetry off. `userChrome.css`: no address/bookmarks bar; tab strip only when a second tab exists.
- `~/.local/bin/google-calendar` (focus if open, else launch with `--no-remote --class GoogleCalendar`), menu entry, **`Super+C`** in i3 and the cheat sheet. Verified window class `GoogleCalendar`, ~470 MB in 1 process before sign-in.
- picom: `100:class_g = 'GoogleCalendar'` — without it the window was partly see-through.
- Full walkthrough: `GOOGLE-CALENDAR.md`.
- Calendar profile: `dom.disable_open_during_load=false` (popup blocker off) — the Zoom add-on signs in via a popup. Guide updated: Zoom is chosen from the ▾ arrow in the full editor, not the quick box.

## i3-peek (2026-09-17 16:20)
- **Why Claude couldn't see other workspaces:** i3 unmaps windows on hidden workspaces, so X11 has no pixels for them; screenshots and the compositor can't reach them.
- `~/.local/bin/i3-peek --class <WM_CLASS> | --workspace <name> [-o file]`: waits until the user has been idle for 1.5s (read via XScreenSaver, no new package), switches to the workspace, captures with ffmpeg `x11grab`, switches back and restores focus to the exact window. Measured: 1.0s total, correct workspace and focus afterwards.
- Rejected: a Firefox remote-debugging port on the calendar profile (would let any local process drive the logged-in Google session).
