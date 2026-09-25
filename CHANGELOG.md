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

## Zoom option in Google Calendar — fixed by Claude, no user steps (17:10)
- `i3-peek` moved to **`~/ai/claude/tools/i3-peek`** (symlinked into `~/.local/bin`), extended with `--do "<xdotool args>"` (repeatable), `--settle`, `--no-capture`; restores the pointer position. Saved as the default way to view/operate windows in any project.
- Diagnosis, all through i3-peek while the user kept working: the full editor showed only "Add Google Meet video conferencing" with no dropdown; the Zoom add-on panel showed it **installed and signed in** (account, personal meeting link, today's meetings). Cause: Calendar loads conferencing providers at page load and the add-on was installed after that.
- Fix: reload (`F5`). Editor now shows **"Add video conferencing ▾" → Google Meet / Add-ons: Zoom Meeting**. Editor closed without saving; calendar returned to its previous view (sidebar collapsed again after one mis-click toggled it).
- The Firefox debugging port was not needed and was not opened.

## Память, панель, календарь (2026-09-18)
Все изменения — через песочницу `lab/` (журнал + `lab rollback all`), снапшот
Timeshift `before-lab-experiments` снят до начала.

- **Память:** zram → zswap + своп-файл 16 ГБ на SSD; Firefox запускается в systemd-области
  с мягким лимитом 4 ГБ (`firefox-mem` меняет лимит на лету, без «Save»); потолок кэша
  распакованных картинок 128 МБ. Проверено: Firefox держится на потолке, лишнее уходит на SSD.
- **Браузер:** три скрипта в Violentmonkey — мелкие картинки с полным качеством по наведению,
  превью YouTube в уменьшённом размере (крупные больше не запрашиваются вообще),
  падение качества видео при уходе с вкладки (звук остаётся).
- **Панель:** одна сверху, одна строка, без дублей. Свои индикаторы (genmon):
  батарея («заряжена» вместо 97%), Telegram со счётчиком, CPU/RAM/SWAP, сеть, погода
  с кэшем (живёт без интернета), рабочие области 1…5, которые не исчезают.
  Кнопки переключают на открытое окно (Ctrl/Shift — новое). Часы `#48daf9`.
- **OSD:** своё окно поверх всего — громкость видна поверх полноэкранного видео,
  бейдж смены раскладки рядом с индикатором.
- **Календарь:** свой мини-календарь вместо веб-версии Google (месяц, создание,
  правка, перенос, Zoom). Google подключён, приложение **In production** (иначе доступ
  отзывался бы каждые 7 дней); Zoom — Server-to-Server приложение с правами на создание,
  изменение и удаление встреч. Проверено сквозным тестом.

Требования пользователя — `REQUIREMENTS.md`, детали и откат — `lab/README.md`,
работа с календарём — `~/.local/share/mini-calendar/ИНСТРУКЦИЯ.md`.

## План 3, ночь на 18.09 (06:10–06:55) — окна как в Windows, клавиатура, память, light-year
Всё через `lab/` (эксперименты 06–12), подробности и откат — `lab/README.md`, план — `PLAN3.md`.
Весь интерфейс — на английском.

- **OSD** переписан: окно фиксированной ширины (больше не дёргается), непрозрачность 90%,
  любое изменение громкости снимает mute, шкала 0–100% (выше 100% — оранжевым),
  демон сам меняет громкость и яркость (без shell и `wpctl` на каждое нажатие).
- **Раскладки EN / RU / UA:** `Alt+Shift` — EN ⇄ RU (из UA — в EN), `Ctrl+Shift` — UA
  (повтор — назад). Срабатывает при отпускании, как в Windows: `Ctrl+Shift+V/C/T` не мешает.
  Опция xkb `grp:alt_shift_toggle` снята (xfconf + localectl). В xfconf ключ `XkbOptions/Group`
  задан **пустой строкой**: если его удалить, xfsettingsd при переприменении подставляет
  свой default `grp:alt_shift_toggle` (это случилось один раз ночью, найдено финальной проверкой). Индикатор в панели — `EN/RU/UA`,
  обновляется мгновенно, клик — EN ⇄ RU. Проверено: `RU EN UA EN EN UA EN EN` на наборе нажатий.
- **Панель:** батарея при полном заряде — `100%`; индикаторы обновлялись раз в 30 с —
  теперь сеть 1 с, CPU/RAM 2 с, Telegram 3 с, батарея 10 с, погода 60 с; числа фиксированной
  ширины (соседи не прыгают). Мёртвые `genmon-*.rc` удалены (настройки genmon живут в xfconf).
- **Сеть:** вместо трафика — задержка сейчас · медиана за 10 с, отдельно до роутера и до
  интернета, вердикт «Wi-Fi / провайдер» в подсказке. Левый клик — меню, тест скорости только
  оттуда (Cloudflare, curl). Служба `netqd` (8 МБ).
- **Клавиши:** `Super+Shift+S` скриншот, `Super+R` выполнить (вместо `Super+Shift+D`),
  `Ctrl+Shift+Esc` — btop, `Alt+Tab` — фокус по окнам области, фокус на `J K L ;`,
  `Super+стрелки` — как в Windows. Шпаргалка `Super+/` переписана.
- **Sublime** — редактор по умолчанию для 38 текстовых типов, Mousepad удалён.
- **Firefox:** служба `firefox-memd` заранее уводит холодную память в своп до цели 2 ГБ
  (MGLRU выбирает старые вкладки), отступает, если страницы сразу возвращаются;
  потолок 4 ГБ не тронут; при долгом упоре в потолок — одно уведомление раз в 10 мин.
  `firefox-mem target 2G`, `firefox-mem early on|off`.
- **light-year** (бывший mini-calendar): родное окно GTK3 без браузера, один процесс,
  **42 МБ PSS**; иконка sky-shoe; `Super+C`. Старый сервер и окно в Firefox убраны.
- **Меню под «яблоком»** (`deskd-favorites`): автозапуск избранного при входе, «Launch all now»,
  иконки с включением/исключением, правый клик — рабочая область программы, «+».
  Конфиг `~/.config/deskd/apps.conf` → правила `assign` в `~/.config/i3/generated/apps.conf`.
- **deskd** — помощник окон (22 МБ, ~0.1% CPU): шапки у всех окон с цветными кнопками
  🟡🟢🔴 справа; растягивание за промежуток между окнами и за край плавающего; правый клик
  по шапке — плитка ⇄ плавающее; правое перетаскивание — к верху = развернуть (панель видна),
  к краю = половина экрана плиткой, на цифру в панели = на ту область; развернуть/вернуть
  на точное место; свернуть; кнопки самих приложений (Telegram) тоже работают; клики по цифрам
  в панели; RustDesk в фокусе — все клавиши уходят в удалённую машину.
  Проверено во вложенном i3 (Xephyr) и вживую.
- **Экраны:** у каждого свои области 1…9 (`Super+N` — на экране с фокусом); при отключении
  области экрана переходят на ноутбук (6, 7, …), при подключении любого монитора — на него.
  Раскладка мониторов запоминается сама (autorandr + deskd: новый набор — рядом справа,
  изменение раскладки — сохраняется). Уведомления и авто-профили XFCE для экранов выключены.
  Логика отключения/подключения проверена на подменённом i3; живьём с отключением ещё не пробовалось.
- Telegram переключён на системную рамку окна; Firefox — `browser.tabs.inTitlebar=0`
  (вступит в силу после перезапуска Firefox).
- `osd` и `deskd` запускает i3 (им нужен X), а не systemd при входе — иначе после перезагрузки
  они бы не поднялись.

## Раунд 4 (19.09) — перетаскивание, панели на каждом экране, повторяющиеся события
Эксперимент `lab` **13-round4**; обзор всего — `REVIEW.md`.

- **Один движок перетаскивания за шапку** (`drag_*` в deskd) для обеих кнопок:
  левая по плитке — перестановка плиток с голубым превью (сторона соседа / центр = обмен),
  левая по плавающему — перемещение, правая — вытянуть окно; везде верх = развернуть,
  бок = половина, цифра в панели = на область. **Двойной клик** по шапке — развернуть/вернуть.
- **Вернуть на место** теперь через пустую заглушку i3: раскладка и размеры восстанавливаются
  точно (раньше ломалось, если соседом был контейнер — i3 схлопывал его вместе с меткой).
- **Firefox (плавающий):** окно, ставшее плавающим, всегда вписывается в рабочую область —
  шапка больше не уходит под панель.
- **Скриншоты:** `Super+Shift+S` — область, `Print` — экран; в буфер + `~/Pictures/Screenshots`
  (`snip`, maim + slop; Flameshot отвязан — у него проблемы с двумя мониторами разного размера).
- **Панель на каждом экране** (`panels.py`): области этого экрана, его окна, часы; создаётся и
  убирается при подключении/отключении. Проверено на живом xfconf (с отсутствующим HDMI-2).
- Цифры областей в 2 раза шире; текст полосы, зоны клика и цели перетаскивания строит одна функция.
- Кнопки в шапке в 1.5 раза больше.
- Telegram: вторая иконка (трей) скрыта, значок в панели больше не обрезан (шрифт Nerd «Propo»).
- «Яблоко» — снова обычное меню XFCE; **Favorites** — третий пункт, открывается у курсора.
  Меню избранного больше не «зависает»: захват мыши повторяется, пока кнопка, открывшая меню,
  ещё зажата.
- **light-year:** повторяющиеся события — «This event / This and following / All events» при
  правке, переносе и удалении. Проверено на настоящем календаре тестовой серией (удалена).
- Процессы-зомби от вызовов обновления панели (osd-daemon, deskd) — устранены.

## Раунд 5 (20.09) — терминал, автозапуск, календарь
Эксперимент `lab` **14-round5**.

- **Правый клик в терминале больше не вставляет.** Проверено опытом: сам kitty по правому
  клику не вставляет — вставлял Claude Code, он перехватывает мышь. Теперь kitty не передаёт
  правый клик приложению, средняя кнопка тоже не вставляет, вставка — `Ctrl+V`.
- **Клики по путям (kitty):** путь считается одним словом, **Ctrl+клик** открывает его
  (папку — в Thunar, `файл:строка` — в Sublime на нужной строке), **средняя кнопка** —
  меню «Open / Show in file manager / Copy path» (`open-path`). Обычный левый клик
  по-прежнему выделяет текст.
- **Автозапуск избранного:** Firefox открывался не на своей области, потому что у него два
  написания класса окна (`firefox-…` и `Firefox-…`), а правила сравнивали регистр —
  теперь правила регистронезависимые `(?i)`. Telegram не стартовал: `gtk-launch` идёт через
  D-Bus и в самом начале сессии молча падал. Теперь команда берётся прямо из ярлыка и
  запускается через i3, с паузой 1.5 с между программами и логом `~/.cache/deskd-favorites.log`.
- **Новые окна браузера** (`popup_apps` в `apps.conf`): второе окно открывается там, где уже
  есть окно этой программы, и плавающим (окна входа Google). Кнопка на панели с Ctrl/Shift
  сообщает deskd, что окно нужно открыть на текущей области.
- **Панель:** индикатор сети пропадал, если при загрузке ещё не было сети (`ping` завершался
  и не перезапускался) — теперь netqd следит за процессами. Клик по значку Telegram работает
  как клик по значку в трее: показать окно, повторный клик — свернуть.
- **light-year:**
  - месяц рисуется по реальному числу недель (обычно 5, 6 — только когда нужно);
  - редактируемое событие подсвечено жёлтым, при создании на дне появляется жёлтый блок;
  - время — список с шагом 15 минут: можно выбрать мышью или напечатать (`9` → `09:00`,
    `1130` → `11:30`), Enter берёт первый подходящий вариант;
  - длительность сохраняется: сдвинул начало — конец едет следом; поменял конец — это новая длительность;
  - дата открывает мини-календарь: выбранный день тёмным кругом, сегодня бледнее, прошлое приглушено, под курсором подсветка;
  - прошедшие дни в месяце бледнее; текст события отодвинут от цветной полоски;
  - фон понедельника, среды и пятницы +5% белого, субботы и воскресенья +5% красного;
  - свайп двумя пальцами влево и вправо меняет месяц (год переключается корректно),
    соседние месяцы подгружаются заранее, поэтому свайп показывает их сразу.

## Раунд 6 (20.09) — панель крупнее, значок Telegram, список времени в календаре
Эксперимент `lab` **16-round6**.

- **light-year, фон колонок:** цвет в фоне уменьшен с 5% до 2% (понедельник/среда/пятница —
  белого, суббота/воскресенье — красного), включая «чужие» дни соседних месяцев.
- **light-year, поле времени переписано.** Вместо выпадающего списка GTK — обычное поле
  без стрелки: клик открывает список времён **под полем** (своё окно, поэтому список
  никогда не перекрывает само поле и не обрезается диалогом), текущее время события выделено
  и список сразу прокручен к нему. Прокрутка — полосой справа или двумя пальцами.
  Диалог модальный и держит GTK-grab, поэтому у списка свой grab, а клавиши пробрасываются
  обратно в поле — иначе клики проваливались в диалог под списком.
- **light-year, ввод времени:** двоеточие рисуется само. `123` → `12:3` прямо во время ввода,
  `1234` → `12:34`. Если первая цифра 3–9 (или 25–29), час однозначный и дальше сразу минуты:
  `345` → `3:45` при вводе и `03:45` после Enter или клика в сторону. Курсор после каждой
  подстановки уходит в конец — иначе следующая цифра попадала перед двоеточием (`3:54`).
- **Верхняя панель в 1.5 раза больше:** высота 44 → 66, значки 32 → 48, шрифт плагинов
  `Inter 10` → `Inter 15`. Важно: genmon читает шрифт только при старте плагина, поэтому
  менять его нужно при остановленной панели (`xfce4-panel -q`, правка, запуск).
  Часы (режим LCD) рисуют цифры фиксированной высотой 24 px независимо от размера панели —
  это ограничение плагина, а не настройка.
- **Значок Telegram — настоящий.** `setup/assets/make-telegram-icons.py` делает из иконки
  самого Telegram три PNG в `~/.local/share/panel-icons/`: обычную, в цвете акцента
  (непрочитанные) и полупрозрачную (не запущен). Панель показывает их через `<img>` genmon.
  Между значком и `ping` добавлен прозрачный разделитель (plugin-56).
- **Свой значок Telegram в трее выключен** в самом Telegram (Settings → Advanced →
  System integration → Show tray icon), поэтому из панели пропала и стрелка со скрытыми
  значками. «When window closed» переключено на **Close to taskbar**: окно остаётся, и
  счётчик непрочитанных по-прежнему читается из его заголовка.
- **Медиана пинга** теперь 75% размера моментальной цифры и 80% яркости её цвета.
- **Терминал на панели** запускается через `app-focus-or-launch`, как браузер: клик —
  переключение на открытое окно, **Shift+клик** — новое окно на текущей области. Подписи
  ярлыков панели переведены на английский.
  - Ctrl+клик по кнопке панели использовать нельзя: xfce4-panel сам перехватывает его и
    открывает своё меню элемента (Properties / Move / Remove), до ярлыка клик не доходит.
  - Заодно починена проверка модификатора: `query_pointer()` в нынешнем python-xlib
    отдаёт поле `mask`, а не `state`, поэтому Ctrl/Shift не замечались вообще и кнопки
    панели всегда только переключали фокус.
- **Копирование в терминале:** выделение копируется сразу в буфер обмена
  (`copy_on_select clipboard`), а `Ctrl+C` копирует выделенное и снимает выделение; если
  ничего не выделено — это обычное прерывание процесса (`copy_and_clear_or_interrupt`).
  В программах, которые сами читают мышь (Claude Code, codex), выделять нужно с Shift —
  так устроен kitty. `Ctrl+Shift+C` и `Ctrl+Shift+V` остаются.
- **Открытие путей:** `open-path` понимает markdown-ссылку `[имя](путь)`, `file://`,
  путь относительно домашней папки, и, если открыть нечего, показывает уведомление вместо
  тишины. Добавлены `Ctrl+Shift+O` (открыть выделенное) и `Ctrl+Shift+Alt+O` (меню) —
  для путей, которые перенесены на две строки или содержат пробелы.
- **Плавающее окно над панелью.** Панель — dock, и i3 (а иногда и сама панель) ставит её
  выше плавающих окон: клик по заголовку окна попадал в панель. deskd теперь поднимает
  рамку плавающего окна над панелью и повторяет это по ConfigureNotify самой панели
  (с ограничителем: не больше 8 раз за 2 с, чтобы не устроить войну за стек).

## Рабочий процесс (20.09) — одна история чатов Claude Code

Claude Code хранит расшифровки (и файлы памяти) в `~/.claude/projects/<путь рабочего
каталога через дефисы>`, поэтому `/resume`, запущенный из `~/ai/claude/setup`, не видел
ни одной из сессий, начатых из `/home/fanatic` — история выглядела пропавшей.

- **Общее хранилище.** Настоящий каталог остался один — `-home-fanatic` (там все 10 сессий
  и 12 файлов памяти). Остальные — символические ссылки на него:
  `-home-fanatic-ai-claude`, `-home-fanatic-ai-claude-setup`, `-home-fanatic-ai-claude-tools`,
  `-home-fanatic--local-share-deskd`, `-home-fanatic--claude`. Что Claude Code ходит по
  таким ссылкам и на чтение, и на запись, проверено одноразовой сессией до правки настоящих
  каталогов.
- **`~/.local/bin/claude-projects-link`** создаёт такую ссылку для текущего каталога, если
  это `$HOME` или что-то внутри `~/ai/claude`. Каталог, в котором уже есть своя история,
  не трогается. Пути настраиваются переменными `CLAUDE_STORE_DIR` и `CLAUDE_STORE_SCOPE`.
- **Обёртка в `~/.bashrc`** — функция `claude()`, вызывающая этот скрипт перед запуском
  (по образцу соседней функции `codex()`), поэтому новые подпроекты попадают в общее
  хранилище сами. `command claude` запускает клиент в обход обёртки.

Откат: `lab/lab rollback 18-claude-sessions`.

## Раунд 7 (20.09) — панель задач как в Windows, свой значок сети, календарь
Эксперимент `lab` **17-round7**.

- **Панель задач — `xfce4-docklike-plugin`** (официальный репозиторий) вместо штатного
  tasklist: один ряд, по одному значку на программу, закреплённые (kitty, Firefox, Thunar)
  сами держат свои окна, как в Windows. Отдельные кнопки-ярлыки из панели убраны —
  значок программы теперь один.
  - Клик — показать/свернуть окна, **Shift+клик — новое окно** (одинаково для всех программ,
    проверено на kitty, Firefox и Thunar), правый клик — список действий программы.
  - **Средняя кнопка по умолчанию закрывала все окна программы** — так у меня закрылось
    окно терминала вместе с сеансом Claude. Переставлено на «Launch new instance»
    (`/plugins/plugin-57/middleButtonBehavior = 1`).
- **Значок Wi-Fi рисуем сами.** У nm-applet значок в трее — XEmbed, и xfce4-panel не
  масштабирует его дальше 22 px. Теперь `netqd` показывает сам канал (дуги Wi-Fi по уровню
  сигнала, кабель, телефон) шрифтом панели, а `net-menu` получил список сетей: известная
  подключается сразу, новая спрашивает пароль, плюс «Other network…» (nmtui) и
  «Network settings…» (nm-connection-editor). `nm-applet` выключен через
  `~/.config/autostart/nm-applet.desktop` (`Hidden=true`).
- **Значок Telegram — монохромный**, как был в трее (`org.telegram.desktop-symbolic.svg`),
  и загорается цветом акцента при непрочитанных; не запущен — приглушён.
- **Часы** переведены с режима LCD (фиксированные 24 px) на цифровые шрифтом
  **DSEG7 Classic 18** — те же семисегментные цифры, но 36 px, в полтора раза крупнее.
- **Отступы в панели**: между словом и числом (`ping`, `CPU`, `RAM`, медиана) — половина
  пробела вместо целого (`<span size="50%">`).
- **Цифры областей сдвинуты влево** (`STRIP_TAIL`, genmon центрирует строку), чтобы «5» не
  прижималась к разделителю.
- **Важно: deskd измерял полосу областей шрифтом `Inter 10`**, а панель уже рисовала
  `Inter 15` — поэтому зоны клика и цели перетаскивания стояли не под цифрами. Шрифт
  теперь читается из xfconf того же genmon-плагина.
- **Бросок окна на панель мимо области** больше не оставляет окно уменьшенным: если отпустить
  над панелью, но не на цифре, окно возвращается туда, откуда его взяли.
- **Переменные сеанса Claude больше не протекают в приложения.** Панель, перезапущенная
  из-под Claude, раздавала детям `CLAUDE_CODE_CHILD_SESSION=1`, и запущенный в таком окне
  `claude` считал себя вложенным — запись транскрипта выключалась. Панель перезапущена
  через i3 (чистое окружение), а обёртка `claude()` в `~/.bashrc` снимает эти переменные,
  если среди родителей нет настоящего процесса `claude`.
- **light-year:**
  - дата из мини-календаря наконец применяется: попап сделан модальным, иначе клик
    проваливался сквозь него в модальный диалог (та же причина, что у списка времени);
  - клик по полю времени очищает его под новый ввод, Escape или пустой ввод возвращают
    прежнее значение;
  - **Enter больше не сохраняет событие**: у полей убран `activates_default`, поэтому окно
    редактирования закрывается и спрашивает «this / following / all» только по кнопке Save.

## Раунд 8 (20.09) — мелкая правка панели, часы пожирнее, прокрутка месяцев
Эксперимент `lab` **18-round8**.

- **Средняя кнопка в docklike — «Do Nothing»** (`middleButtonBehavior = 2`): закрывать все
  окна программы случайным нажатием слишком легко.
- **Транскрипт чатов включён навсегда:** обёртка `claude()` в `~/.bashrc` теперь снимает
  `CLAUDE_CODE_CHILD_SESSION` всегда, без проверок; остальные переменные сеанса снимаются,
  только если среди родителей нет настоящего `claude`.
- **Отступы в панели — настоящая причина** была не в пробеле, а в выравнивании: `pad()`
  добавлял цифровые пробелы **перед** числом, поэтому «ping ␣␣16». Теперь место под лишние
  разряды резервируется **справа** от числа и половинной ширины (`value()` в `netqd` и
  `panel-sys`), так что слово и число стоят рядом, а полоса всё так же не скачет.
- **Значок Wi-Fi** увеличен до 140% — вровень с иконкой Telegram.
- **Значок «яблоко»** крупнее: `icon-size` панели 48 → 60 (44×53 px вместо 34×40);
  заодно подросли значки в панели задач.
- **Разделитель отодвинут от Telegram** — два прозрачных разделителя (плагины 58 и 59).
- **Часы — `DSEG7 Classic Bold 18`**: те же 36 px, но штрихи толще и зазоры между сегментами
  заметнее, как на старых семисегментных часах. (Есть ещё наклонный вариант
  `DSEG7 Classic Bold Italic` — если захочется совсем «будильниковый» вид.)
- **Кнопка области 5** снова такой же ширины, как остальные: в `measure()` правый край
  последнего сегмента брался от конца всей строки, вместе с добавленным отступом.
- **Прокрутка месяцев в календаре**: один месяц на один жест. Остаток свайпа, который уже
  перелистнул месяц, отбрасывается до тех пор, пока пальцы не оторвут от тачпада
  (событие `is_stop`), и смена направления обнуляет накопленное — поэтому обратный свайп
  больше не пролистывает ещё раз в старую сторону.

### Память deskd — проверено, утечки нет (20.09)
После первого перетаскивания RSS deskd растёт с ~38 до ~88 МБ и не возвращается. Разбор
`/proc/<pid>/smaps_rollup` показал: своей (анонимной) памяти там всего ~27 МБ, остальные
~61 МБ — общие страницы шрифтов и библиотек отрисовки (fontconfig, freetype, pango, cairo),
которые подгружаются при первой отрисовке целей и делятся с панелью и остальными GTK-программами.
`tracemalloc` за то же перетаскивание насчитал меньше 1 МБ питоновских объектов.
Попутно убраны две настоящие расточительности в перетаскивании:
- цели на панели перерисовывались на **каждый** опрос мыши (новая cairo-поверхность
  каждый раз) — теперь только когда меняется подсвеченная область, и на одной поверхности;
- `tile_zone` на каждый опрос тянул всё дерево i3 (и не использовал его) и список областей —
  дерево больше не запрашивается, список областей кэшируется на полсекунды.

## 21.09 — сочетания kitty на русской и украинской раскладке
Эксперимент `lab` **15-kitty-layout-shortcuts** (сделан сессией Codex, проверен здесь).

- **Причина.** В kitty буква в `map` — это символ *текущей* раскладки, а не позиция клавиши.
  Поэтому `map ctrl+v paste_from_clipboard` срабатывал только на EN: на RU та же клавиша даёт
  `Ctrl+м`, правило не совпадало, и kitty отдавала событие программе.
- **Почему в Claude Code вставка всё-таки работала, а в Codex нет.** Несработавшее сочетание
  kitty передаёт приложению по своему протоколу клавиатуры, где кроме символа указан
  `alternate_key` (буква с латинской раскладки). Claude Code его читает и понимает, что это
  `Ctrl+V`; TUI Codex — нет. То есть это не «общая беда kitty», а разница обработчиков поверх
  неполной привязки.
- **Исправление:** ко всем `map` добавлено `--allow-fallback=shifted,ascii` — kitty сверяет
  сочетание ещё и с латинской раскладкой.
- **Проверка (здесь, во вложенном X):** kitty запущена с `--debug-keyboard`, физическая клавиша
  нажималась через XTEST (не `xdotool key ctrl+v` — тот подменяет keycode и проверяет не то).
  На us, ru и ua в логе видно `alternate_key: 118 (v)` / `99 (c)` и
  `matched action: paste_from_clipboard` / `copy_and_clear_or_interrupt`. Работает везде.
- Уже открытым окнам конфиг перечитан (`kill -SIGUSR1`); kitty и сама следит за файлом
  (`kitten __watch_conf__` рядом с каждым окном).

## Раунд 9 (21.09) — цифровая панель и перенесённые ссылки
Эксперимент `lab` **19-panel-polish**.

- **Часы:** `DSEG7 Classic Bold Italic 18` — высота осталась 36 px, но теперь это
  наклонный «будильниковый» вариант.
- **Сетка цифр:** ping всегда занимает три табличные ячейки, CPU/RAM — две;
  начальных нулей нет. При ping ≥ 1000 показывается `000`, при CPU/RAM ≥ 100 —
  `00`. Ширина и интервалы больше не скачут при смене разряда.
- **Батарея:** свой вертикальный LCD-корпус с четырьмя сегментами в духе
  телефонов 2000–2010-х; зарядка показана молнией. SVG лежат в
  `assets/panel/battery/`, без нового демона и памяти.
- **Звук:** свой лёгкий `Sky-Dark-Icons`, наследующий `Papirus-Dark`; переопределены
  только четыре значка громкости. Сам динамик ~90% прежнего размера, дуг 1/2/3
  по уровню; неактивные дуги остаются едва видными.
- **Раскладки:** к исходному `#48daf9` подмешано 5%: EN синего (`#44cff9`),
  RU коричневого (`#4bd3ee`), UA жёлтого (`#51dced`).
- **Ctrl+клик по перенесённому пути:** у Codex TUI это не soft-wrap kitty, а две отдельно
  нарисованные строки. Поэтому `open-click.py` берёт координату клика и соседние
  строки экрана, склеивает Markdown-цель и передаёт её в общий `open-path`.
  Нативные OSC-8/URL ссылки остались. Живой Ctrl+клик по двухстрочной ссылке
  открыл точный `messaging-analysis-statistics.md` в Sublime.
- Панель проверена живым снимком; Python/shell и все SVG прошли синтаксическую
  проверку. Конфиг перечитан всеми открытыми kitty.

## Раунд 10 (21.09) — панель: цифры, значки, цвета
Эксперименты `lab` **20-panel-corrections** (сессия Codex, доведено здесь) и **21-panel-finish**.

- **Цифры больше не дёргаются.** Ячейка теперь прижата влево: число и знак `%` стоят слева,
  а справа добирается невидимый ноль (`alpha="1"`), который держит ширину. Раньше
  добивка стояла *слева*, поэтому при переходе на сотни число уезжало вправо. Сотни
  больше не отменяются (`00` вместо `100` убрано), ping свыше 999 мс показывается как `999`.
- **`ping` и `ms` вровень с `CPU`.** Причина была не в шрифте: значок Wi-Fi выводился тегом
  `<img>` **внутри** `<txt>`, genmon рисовал его дважды и сдвигал подпись вниз. Костыль
  `rise="2pt"` убран, картинка вынесена в собственный тег, как у батареи и Telegram.
- **Значок Wi-Fi.** Восемь делений вместо четырёх, в середине — уровень в дБм. Панель
  отдаёт значку ~32 px по высоте, и восемь дуг поверх трёх цифр в этом размере читаются
  как каша, поэтому середина веера — сплошная площадка: горит вместе с веером (цифры на
  ней чёрные), при слабом сигнале остаётся тёмной (цифры цвета значка). Холст 56×35 без
  полей — иначе genmon ужимает рисунок и цифры пропадают.
- **Динамик.** Дуги зелёная/жёлтая/красная (цвета кнопок в шапках окон), рупор полый с
  тонкой окантовкой. Почему раньше было серым: GTK для имён `*-symbolic` подставляет
  `rect,circle,path { fill: <цвет темы> !important }`. Теперь у каждой фигуры свой
  `style="fill:none!important;stroke:…!important"` — inline-стиль с `!important` перебивает
  подстановку, и цвета доживают до панели.
- **Раскладки.** Подмешивание 5% было незаметно; теперь у каждого языка свой цвет:
  EN — акцент `#48daf9`, RU — коричневый `#c98a55`, UA — жёлтый `#ffd447`. Подчёркивание
  убрано, OSD показывает те же цвета.
- **Батарея.** Молния видна, пока ноутбук в сети (а не только при `Charging`), значок
  отдаётся панели в 44 px вместо 30 — вровень с остальными.
- **Погода.** Эмодзи не растёт до размера соседей: при 350% строка становится выше панели.
  Значки заменены на погодные глифы шрифта панели (`nf-weather-*`, 170%) — те же ~30 px,
  что у Wi-Fi и батареи, и в одном стиле с остальными.
- Всё проверялось во вложенном X (Xephyr + макет строки панели), экран пользователя не занимался.

## Раунд 11 (21.09) — цифры по правому краю, батарея, пентаграмма, всплывашки
Эксперимент `lab` **22-panel-round11**.

- **Цифры.** Вернул то, что и просили с самого начала: ячейка ровно на нужное число
  разрядов (CPU/RAM — два, ping — три), число прижато к правому краю ячейки, добивка —
  невидимые нули. Перекатывание `00` и `000` восстановлено (это было указание, а не выдумка).
  Расстояние между CPU, RAM и SWAP вернулось к прежнему.
- **Значок Wi-Fi — снова сплошной веер**, как был, только деления мельче: восемь вместо
  четырёх, тонкие чёрные риски между ними. Уровень в дБм написан поперёк широкой части
  веера: чёрным по засвеченной части, цветом значка — по тёмной (инверсия). На линиях-дугах
  текст был нечитаем, на сплошном фоне читается.
- **Батарея.** Один рисунок на все состояния, генерируется самим `panel-battery` в
  `$XDG_RUNTIME_DIR` (семь SVG-файлов удалены). Корпус и деления не двигаются никогда —
  при зарядке рядом появляется только молния. Деления сверху вниз зелёное, зелёное, жёлтое,
  красное (цвета кнопок окон) и гаснут по мере разряда. Слева у значка своя пустота в
  viewBox — тот же отступ от разделителя, что у погоды; у Telegram такой же отступ впечатан
  в PNG. Подпись `100%` придвинута к значку.
- **Подсветка под курсором.** genmon-плагины — это event box, GTK никогда не переводит их
  в `:hover`, поэтому ни тема, ни `<css>` самого genmon ничего не дают (проверено).
  deskd подписывается на Enter/Leave у окон плагинов и рисует поверх полупрозрачную
  плашку; окно имеет пустую input-форму (`XShape`), поэтому клики проходят насквозь.
  У областей подсветка своя — подсвечивается одна цифра под курсором, а не вся полоса.
- **Активная область — перевёрнутая пентаграмма** вместо подчёркивания: тонкая линия
  цвета акцента в отдельном прозрачном окне над панелью (в подпись её не нарисовать).
- **Раскладки.** EN синий `#3b7ddd`, RU тёмно-коричневый `#8f5b2e`, UA жёлтый `#ffd447`.
  Код набран моноширинным шрифтом: в пропорциональном EN/RU/UA занимали 27/28/29 px, и при
  каждой смене языка вся левая часть панели дёргалась.
- **Всплывающие меню поверх окон.** Календарь часов открывался под окнами: мы поднимаем
  плавающие окна над панелью, а её меню — это override-redirect окна рядом с ней. Теперь
  deskd по `MapNotify` поднимает чужие override-redirect окна наверх.
- **Погода — снова эмодзи**, растянутое до предела: экран 144 dpi, поэтому 160% от шрифта
  панели — это 42 px рисунка (больше значков Wi-Fi и батареи), а `line_height="0.6"` ужимает
  строку эмодзи, которая иначе выше панели и обрезает рисунок.

## Раунд 12 (21.09) — слои, подсветка панели, пентаграмма
Эксперимент `lab` **23-panel-round12**.

- **Панель снова всегда сверху.** Подъём плавающих окон над панелью (раунд 6) убран целиком —
  из-за него панель уходила вниз, а календарь часов и уведомления открывались под окнами.
  Вместо этого окно при перетаскивании **не может** заехать под панель: `deskd` держит его
  в рабочей области, поэтому брошенное на панель окно встаёт вплотную под ней, в ближайшей
  к точке броска позиции. Рабочая область и высота окна берутся один раз в начале
  перетаскивания — на каждом кадре дерево i3 больше не запрашивается.
- **Чужие всплывающие окна** (меню, уведомления, календарь часов) `deskd` поднимает наверх
  по `MapNotify`.
- **Подсветка под курсором — для всего.** Вместо Enter/Leave у окон плагинов `deskd` следит
  за указателем на самой панели: внешние плагины он знает по их окнам, а часы, громкость и
  выключение окна не имеют — их места вычисляются как промежутки между внешними плагинами
  (последний промежуток делится на часы и квадратную кнопку выключения). Плашка теперь
  белая полупрозрачная, поэтому под ней светлеют и значок, и текст.
- **Пентаграмма** оранжевая (`#f4811e` — оранжевая полоса яблока в углу), центрирована по
  рисунку, а не по описанной окружности (у звезды остриём вниз низ длиннее верха), и
  переезжает на новую область сразу по событию i3, не дожидаясь перерисовки полосы.
- **Батарея:** опрос раз в 2 с вместо 10 с, подпись в ячейке на три разряда с прижатием
  вправо — при 100% → 99% и при смене режима ничего больше не дёргается.
- **Раскладка:** шрифт 17 вместо 14 (моноширинный, чтобы ширина не менялась).

## Раунд 13 (21.09) — притушенная панель, точные границы, мгновенная батарея
Эксперимент `lab` **24-panel-round13**.

- **Подписи короче:** `p 46 · 21` (без `ms`), `C 11`, `R 70`, `S 3` — буква и число,
  своп в целых гигабайтах.
- **Панель притушена, под курсором — полная яркость.** Вместо подсветки-плашки deskd
  держит над панелью тонкую тёмную вуаль (26→38% чёрного) с «дыркой» там, где указатель.
  Так ведёт себя значок громкости, и теперь так же ведут себя все значки и подписи, включая
  часы и кнопку выключения, которые своих окон не имеют. Вуаль кликов не ловит (пустая
  input-форма), одно окно на панель, перерисовывается только при смене места.
- **Подсветка больше не пропадает через раз:** указатель отслеживается и на окне панели, и
  на окнах внешних плагинов, а `LeaveNotify` с `NotifyInferior` (курсор ушёл в дочернее окно)
  больше не гасит подсветку.
- **Границы цифр областей были смещены.** deskd мерил полосу Pango без табличных цифр, а
  панель рисует с ними: «1» уже остальных, и дальше по строке накапливался сдвиг. Теперь
  измерение идёт с `tnum=1` — расчётные центры совпали с нарисованными цифрами до пикселя,
  а значит встали на место и зоны клика, и цели перетаскивания, и пентаграмма.
- **Пентаграмма крупнее** — цифра помещается во внутренний пятиугольник — и ставится по
  чернильному центру цифры, а не по ячейке.
- **Батарея реагирует мгновенно:** deskd подписан на `PropertiesChanged` UPower и обновляет
  индикатор в тот же момент (плагин по-прежнему опрашивается раз в 2 с как запасной путь).
  Уведомления xfce4-power-manager выключены — состояние видно по значку.

## Раунд 14 (21.09) — слои поверх полноэкранного, пентаграмма за цифрой, календарь
Эксперимент `lab` **25-panel-round14**.

- **Чужая подсветка на пинге убрана.** genmon делает плагин кнопкой, только если у него есть
  команда клика, — поэтому тема рисовала свою рамку на сети, Telegram, раскладке и областях,
  а на батарее, ЦПУ и погоде нет. Каждый индикатор теперь отдаёт
  `<css>* { background-color: transparent; … }</css>`, и остаётся только вуаль.
- **Полноэкранное окно ничем не перекрывается.** Вуаль и пентаграмма прячутся, пока на экране
  есть окно во весь экран (просмотр фото в Telegram, видео, игра), и возвращаются после.
- **Пентаграмма за цифрой:** окно нельзя положить под панель (она непрозрачна), поэтому звезда
  вырезается по форме цифры — читается как будто цифра поверх звезды.
- **Свайп двумя пальцами = стрелки** в Telegram: X отдаёт горизонтальный свайп кнопками 6 и 7,
  их никто не слушает. Пока такое окно в фокусе, deskd перехватывает эти кнопки и шлёт
  `Left`/`Right`. Проверено во вложенном X: приложение получило `^[[D`.
  Список программ — `SWIPE_ARROW_CLASSES` в `deskd.py`.
- **Календарь: всегда шесть недель** (у месяца бывает и пять, и шесть — от этого прыгала вся
  сетка), и у заголовка фиксированная ширина, поэтому `‹`, `›` и `Today` не двигаются при
  смене месяца. Проверено на трёх месяцах подряд во вложенном X.
- **Правило на будущее:** элементы интерфейса при смене состояния не двигаются — меняется
  содержимое или подсветка, но не положение. Как в сегментных часах.

## Раунд 15 (21.09) — жест перелистывания и цвет батареи
Эксперимент `lab` **26-swipe-and-battery**.

- **Перехват свайпа у Telegram убран из deskd целиком** (grab кнопок 6/7 и подделка стрелок).
  Он пролистывал по десятку фотографий за свайп и требовал списка классов окон.
- **Перелистывание теперь на четырёх пальцах влево/вправо** (touchegg → `xdotool key Right/Left`,
  `repeat=false`, `on=begin`): одно нажатие на жест, работает в любой программе, никаких
  правил на каждую.
  - Почему не два пальца: libinput считает движение двумя пальцами прокруткой и свайпом его
    не отдаёт (touchegg двухпальцевые свайпы не поддерживает), а главное — X не сообщает
    посреднику, обработала ли программа событие 6/7. Поэтому «сначала прокрутка, а если
    не сработала — стрелка» принципиально не сделать. Глобально превращать 6/7 в стрелки
    нельзя: в терминале это правка командной строки, в редакторе — прыжок курсора.
  - Ту же задачу параллельно решал Codex (`gpt-5.6-sol`, high): вывод совпал — два пальца
    оставить прокруткой, перелистывание повесить на свободный жест четырьмя пальцами.
    Его уточнение (`on=end` вместо `on=begin`) не взято: у остальных жестов здесь `begin`,
    и так отзывчивее.
- **Верхний сегмент батареи** теперь цвета акцента (`#48daf9`), дальше зелёный, жёлтый, красный.

## Раунд 16 (22.09) — восстановление нативных двухпальцевых жестов Qt/X11

Эксперимент `lab`: **27-native-two-finger-swipe**. Продолжена остановившаяся
сессия Claude; её последнее исследование не внесло изменений после раунда 15.

- Проверены upstream-документация Touchégg/Fusuma и исходники установленной
  версии Telegram 7.2.8 и Qt 6.11.2. Telegram уже реализует двухпальцевую
  навигацию, но игнорирует события `NoScrollPhase`, которые посылает Qt/XCB.
  Утверждение раунда 15 о невозможности двухпальцевого перелистывания было
  слишком широким: восстановление протокола внутри toolkit решает конкретную
  проблему без глобальной подмены прокрутки стрелками.
- Добавлен исходный код плагина, сборка, установщик и регрессионные проверки в
  `assets/qt-scroll-phases/`. Плагин использует штатный механизм Qt generic
  plugins, libevdev для границ касания и QPA для доставки событий виджетам.
  Пауза с пальцами на поверхности не завершает жест; отпускание завершает.
  Сохраняются исходные дельты, модификаторы и направление. Нет списка классов
  приложений, поддельных клавиш, захвата ввода или отдельного демона.
- Udev предоставляет активному локальному сеансу доступ только к устройствам
  с `ID_INPUT_TOUCHPAD=1`; клавиатуры плагин не открывает.
- Удалены обе горизонтальные привязки на четыре пальца из Touchégg.
  Трёхпальцевые команды областей/rofi и четырёхпальцевый разворот сохранены.
- Экспорт плагина добавлен в `xfce-i3-session`, обновлено окружение активации
  D-Bus/systemd, Telegram штатно перезапущен. Проверены загрузка `.so`,
  дескриптор `/dev/input/event15`, класс устройства `TouchPad`, XML Touchégg
  и синтаксис session script.
- Автотесты покрывают длительный жест с паузой, быстрые последовательные
  жесты, задержку X-событий, мышь/неподдержанный ввод, прокрутку над дочерними
  виджетами, переход на мышь, переполнение времени и закрытие окна.
  Пользователь подтвердил на реальном тачпаде: горизонтальный свайп двумя
  пальцами в просмотрщике Telegram перелистывает ровно одну фотографию после
  отпускания пальцев (22.09).
- Измеренная разница PSS маленького Qt probe: около +131 КиБ; библиотека
  около 62 КиБ. Это один сравнительный замер, не универсальная оценка.
- Ограничения: только динамические Qt 6 X11 приложения с собственной
  поддержкой свайпов; не GTK/Firefox/Electron. После обновления Qt требуется
  пересборка, при несовпадении версии плагин отключается. Уже работающие
  родительские процессы сохраняют старое окружение до следующего входа.

Исходники upstream, сравнение вариантов и команды обслуживания:
[README плагина](assets/qt-scroll-phases/README.md).

## Раунд 17 (22.09) — фиксы по ревью 22.09

Эксперимент `lab`: **30-review-fixes**. Основание — `REVIEW-2026-09-22.md`
(пункты 4.2–4.5 и раздел 5); решение пользователя: «делай фиксы все свои».

- **Фокус после разворота** (Super+F и жест четырьмя пальцами вверх): `deskd.maximize()`
  в конце явно даёт фокус развёрнутому окну. Причина потери — `remember(placeholder=True)`
  делает `open`, а i3 отдаёт фокус новому пустому контейнеру.
- **Окно события больше не уходит под календарь.** `deskd.raise_focused()` (раунд Codex
  «активное окно наверх») поднимал окно и над его собственным модальным диалогом; i3 к тому
  же заново выставляет свой порядок (активное плавающее окно сверху) при каждой смене фокуса.
  Теперь deskd на каждой области проверяет все пары `WM_TRANSIENT_FOR` и поднимает диалог над
  владельцем только когда он реально ниже — без лишних `ConfigureWindow`, иначе получалась
  петля `ConfigureNotify → refresh`. Проверено пробным GTK-окном с модальным диалогом:
  порядок верный и после клика по родителю, и после ухода фокуса в другое окно.
- **deskd не делает полный refresh на события `window::title` / `window::urgent`** —
  они ничего не двигают, а спиннер в заголовке kitty (Claude Code) обновлял заголовок каждые
  100 мс и держал deskd на 3–10 % ядра. В простое теперь ≈0 (1 тик за 11 с).
- **Хук `ConfigureNotify → refresh`** не срабатывает, пока deskd сам тянет или растягивает
  окно (`drag_end` обновляет один раз).
- **Календарь сохраняет только по Save.** Убрана автозапись Codex (`queue`/`flush` через
  650 мс) в диалоге события — вернулось правило раунда 8. Cancel/Esc отбрасывают черновик.
- **«Сегодня» в календаре часов** — акцентная плашка (`calendar:selected` в
  `~/.config/gtk-3.0/gtk.css`, теперь объявлен в `desktop/config/gtk-3.0/`). GTK читает
  этот файл только при старте, поэтому панель перезапущена (`xfce4-panel -r`).
- **`nm-applet` больше не стартует** — строка убрана из `/usr/local/bin/xfce-i3-session`
  (автозапуск `Hidden=true` его не касался).
- **`VISUAL=sky-edit` только для Codex**: убран `env VISUAL` из `kitty.conf`, переменная
  задаётся в обёртке `codex()` в `~/.bashrc`. `git commit` и всё, что уважает `$VISUAL`,
  снова открывают консольный редактор.
- `tools/desktop.py apply` берёт имя эксперимента из `LAB_EXPERIMENT` (по умолчанию
  `desktop-apply`) вместо зашитого `29-desktop-polish`.

## Раунд 18 (22.09) — фон-звёзды как настоящие обои

Эксперимент `lab`: **31-sky-stars**. Запрос: «сделай рисованием в корневое окно… без
пересчёта рандомного — зациклить 30 сек анимацию заранее просчитанную (типа видео)…
не рендерить, если весь экран закрыт окнами».

- **`sky-stars` переписан без GTK** (`desktop/bin/sky-stars`: python-xlib, цикл `select()`
  по сокетам X и i3). Память 23 МБ RSS вместо 25 МиБ PSS + GTK.
- **Не корневое окно, а override-redirect окно типа `DESKTOP` в самом низу стека** — это
  отклонение от формулировки запроса, и вот почему: под picom само корневое окно не видно
  вообще, композитор показывает свою копию корневого pixmap и перечитывает её только при смене
  свойства `_XROOTPMAP_ID`, то есть каждый кадр обходился бы полноэкранной перекомпозицией.
  У окна же есть точный damage: picom перерисовывает только изменившиеся квадратики звёзд.
  i3 override-redirect окна не трогает — ни рамки, ни заголовка, на всех областях.
- **30-секундный цикл просчитан один раз при старте** (120 кадров по 250 мс): для каждого
  кадра — список звёзд, у которых сменилась ступень яркости (12 ступеней). В цикле кадра нет
  ни тригонометрии, ни случайных чисел. Периоды мерцания привязаны к делителям 30 с
  (3,75–7,5 с вместо 4–7 с), поэтому стык цикла бесшовный.
- **Кадр — до 25 запросов `PolyFillRectangle`** с заранее упакованными прямоугольниками
  (свой класс запроса через `rq.Binary`; штатная упаковка python-xlib по одному
  прямоугольнику стоила больше, чем всё остальное). Звёзды крупнее: ядро 4 px и ореол 6 px,
  пик яркости 75 % от `foreground` темы; сетка 20×28 px, 1456 звёзд на 2560×1600.
- **Под окнами не рисуется.** Перекрытие считается по дереву i3 (док-панель и все окна
  видимых областей — плитки, плавающие, полноэкранные) и пересчитывается по событиям i3
  (со слиянием 100 мс). Форма окна (XShape Bounding) = незакрытая часть экрана, так что под
  окнами слоя нет и композитору нечего смешивать. Когда открытых звёзд нет — процесс спит до
  события i3. Раскрытые звёзды дорисовываются до текущей ступени.
- Замеры на живой системе: худший случай (все звёзды открыты, `SKY_STARS_ALWAYS=1`) — 0,6 %
  ядра у `sky-stars`, разница у picom/Xorg в пределах шума (чередующийся A/B, 6 раундов);
  при закрытом экране — 0. Было: 8,8 % ядра постоянно.
- `starfield.py` влит в `sky-stars`; `i3ipc.py` переехал из `deskd/` в общую библиотеку
  `~/.local/share/sky-desktop/` (`subscribe()`/`decode()` для сырого сокета, `Subscription`
  для GLib; GLib импортируется лениво). `deskd` импортирует его оттуда.
- `lab/lab remove <эксп> <путь>` — удаление файла с бэкапом, откат восстанавливает.

## Раунд 19 (22.09) — проект как законченный продукт

Эксперимент `lab`: **32-project-structure**. Запрос: «чтобы проект был уже законченным
продуктом, чтобы была система стиля и прочие правильные архитектурные вещи, а не хаос как
сейчас. Старьё и мусор удалить и сделать добавление фиксов удобным и организованным».

- **Три документа вместо четырнадцати.** `README.md` (что это, структура, команды, как
  добавить фикс, система стиля, правила, машина), `ARCHITECTURE.md` (сессия, службы, deskd,
  панель, фон, OSD, сеть, календарь, терминал/жесты/клавиши, принятые решения),
  `MAINTENANCE.md` (ежедневное, что перезапускать, восстановление на чистой машине, особенности
  этой машины, если сломалось, известные хвосты). `CHANGELOG.md` остаётся историей,
  `lab/README.md` сокращён до описания журнала. Удалены `PLAN*.md`, `REQUIREMENTS.md`,
  `REVIEW*.md` (три), `RICING.md`, `FINDINGS.md`, `BOOT-DELAY.md`, `GOOGLE-CALENDAR.md`,
  `STATUS.md`, `STATE.md` — их живое содержание перенесено, остальное есть в истории git.
- **Дерево `desktop/` — полный источник истины.** Добавлены `home/` (→ `~`, `.Xresources`)
  и `system/` (→ `/`, через sudo: `xfce-i3-session`, `xfce-i3.desktop`), бинарные файлы
  (иконки light-year и Telegram копируются как есть) и всё, что стояло в системе, но не было
  объявлено: `touchegg.conf`, `rofi/sky.rasi`, шейдер picom, `cheatsheet.txt`,
  `deskd/apps.conf`, `firefox-memd.service`, меню Xfce, `mimeapps.list`, ярлыки `.desktop`.
  70 файлов, `make status` — 0 расхождений.
- **Система стиля.** `theme.json` — единственное место цветов и шрифтов: добавлены `text`,
  `dim`, `highlight`, `layouts` (EN/RU/UA), `mono_font`. Конфиги и shell пишут токены
  `@COLOUR_X@` / `@RGB_X@` / `@HEX_X@` / `@FONT@`, Python читает `THEME`, CSS внутри Python
  идёт через `sky_theme.css()` с теми же токенами. Скрытая подмена литералов по таблице
  `PALETTE` из `tools/desktop.py` убрана; `make check` теперь **отказывает** источнику, где
  цвет темы написан литералом. Переведены: i3, kitty, picom, rofi, touchegg, gtk.css,
  `panel-layout`, `panel-battery`, `panel-sys`, `osd-daemon`, `deskd` (полоса областей),
  `deskd-favorites`, `light-year` (`app.py`, `api.py`), `netqd` (цвета маски SVG — `black`/`white`).
  Побочные унификации: urgent в rofi/i3/kitty `color1` = `danger` (#ff5f57), «выше 100 %» в
  OSD = `warning`, амбер батареи = `warning`.
- **Рабочий процесс фикса** — `make check` → `make diff` → `make apply EXP=NN-name`
  (тест + установка через журнал) → перезапуск по таблице в MAINTENANCE → CHANGELOG.
  `make packages` сверяет `packages.txt` (48 пакетов, все стоят), `make rollback EXP=…`.
- **Мусор удалён.** Из репозитория: `tools/panel.py` (одноразовая миграция, выполнена),
  `tools/session.py` (никем не использовался), `lab/revert-i3-config.py`, `assets/light-year.png`
  (612 КБ, иконки объявлены), `logs/`, `lab/__pycache__`, 205 `.bak` из индекса git
  (`lab/backups/` теперь в `.gitignore`, на диске остаются для отката); `lab/browser/` →
  `assets/browser/`. Из системы: старый веб-календарь (`google-calendar` скрипт, ярлык,
  профиль Firefox), правило picom для него, `~/.config/autostart/nm-applet.desktop`,
  `kitty.conf.bak-links`, семь `rc`-файлов и каталог плагинов, которых давно нет на панели,
  `~/.local/share/Mousepad`, пустой `xfce4-lab-launchers`, `ИНСТРУКЦИЯ.md` календаря
  (содержание — в ARCHITECTURE/MAINTENANCE).
- `~/.codex/AGENTS.md`: указатель на новые документы и правило «через `desktop/` +
  `make apply`, не правкой установленных копий».

## Раунд 20 (22.09) — реакция панели, размер значков, меню Wi-Fi

Эксперимент `lab`: **33-panel-reactions**.

- **Батарея реагирует на кабель сразу.** Сигнал UPower доходил до deskd вовремя (проверено:
  `PropertiesChanged` идут), но скрипт судил о зарядке по `BAT0/status`, который на этом Mac
  меняется через несколько секунд после кабеля. Теперь `plugged` берётся из
  `/sys/class/power_supply/ADP1/online` — он переключается мгновенно.
- **Громкость без задержки.** OSD делал три вызова `wpctl` по 44 мс до показа. Теперь `pactl`
  (19 мс), значение кэшируется, OSD показывается **до** применения, потом два вызова на шаг.
- **Иконки CPU и RAM вернулись** — символы приватной области Unicode потерялись при
  переписывании `theme.json` в раунде 19 (моя ошибка), восстановлены.
- **Единый размер значков.** Трей (`plugin-6`) получил `icon-size = 36` — Zoom стал как
  Telegram и веер Wi-Fi (~36 px видимой высоты при значке 60). Индикатор записи микрофона
  у плагина звука брал `microphone-sensitivity-*-symbolic` из Papirus на весь холст; в тему
  `Sky-Dark-Icons` добавлены четыре своих значка микрофона с той же высотой рисунка, что у
  динамика (14–50 на холсте 64). Сама тема значков переехала из `assets/panel/` в
  `desktop/share/icons/` (теперь она объявлена и рендерится с токенами цветов).
- **Меню Wi-Fi при пустом списке само сканирует.** Раньше без кэша NetworkManager (после
  включения радио или сна) показывалось «No cached networks · click Refresh». Теперь при
  включённом радио и пустом списке — «Scanning…», запуск `nmcli dev wifi rescan` и опрос
  списка раз в секунду до 10 с; включение переключателя ведёт туда же. Фоновое сканирование
  по-прежнему выключено — сканирует только клик пользователя.
- **Меню Wi-Fi не появлялось вообще** (обнаружено после жалобы пользователя): `net-menu`
  запускается панелью, а не из клика в окне GTK, поэтому `popup_at_pointer(None)` не имел
  события-триггера и молча ничего не показывал. Теперь меню ставится у указателя явно
  (`popup_at_rect` от корневого окна, как в `power-menu`). Добавлены крупные строки
  «Turn Wi-Fi on» (видна, пока радио выключено; включает и сразу сканирует) и «Refresh
  networks»; обе не закрывают меню — список заполняется на месте. Проверено на вложенном X
  с подменённым `nmcli` (радио выключено → включение → список) и на реальном экране.

## Раунд 21 (22.09) — зарядка, отступ, обновление Wi-Fi, RustDesk, кнопка Save

Эксперимент `lab`: **34-fixes**.

- **Батарея при подключении кабеля.** Подписка на UPower заменена событиями udev
  (`GUdev`, подсистема `power_supply`) — это самый ранний сигнал, который есть в системе:
  ядро шлёт его в момент, когда меняется `ADP1/online`. Отключение и так стало быстрым после
  раунда 20; подключение по UPower запаздывало. `refresh_plugin` больше не опрашивает xfconf на
  каждое событие — номер плагина запоминается после первого запроса.
- **Отступ после значка свопа** равен отступу перед погодой: у `panel-sys` появился такой же
  пробел справа, какой у погоды слева.
- **Refresh в меню Wi-Fi показывает все сети.** Раньше после `nmcli dev wifi rescan` список
  опрашивался и первый непустой ответ (только текущая сеть) принимался за результат. Теперь
  обновление — блокирующий `nmcli dev wifi list --rescan yes` в потоке: nmcli ждёт конца
  сканирования и отдаёт полный список (28 сетей за 4,6 с при проверке); в меню на это время
  «Scanning…».
- **RustDesk: окно переносится на другие области.** В режиме i3 `passthrough` (все клавиши
  уходят на удалённую машину) добавлены `Super+Shift+1…0` — те же `nop deskd move N`, что и в
  обычном режиме.
- **Кнопка Save вернулась в окно события.** С автосохранением Codex убрал её для существующих
  событий; в раунде 17 автосохранение было снято, а кнопка не восстановлена — правку было
  нечем записать. Теперь Delete · Cancel · Save (для нового события — Create). Проверено
  на виртуальном дисплее.
- **Вспышка «+N more» при открытии/закрытии окна события.** Сетка месяца перестраивается
  вокруг диалога, и новые ячейки на один кадр показывали все события и кнопку «More», пока не
  придёт первое размещение (`size-allocate` → пересчёт через 20 мс). Теперь `DayEvents`
  помнит высоту ячейки на классе (все ячейки одинаковы) и раскладывает строки сразу при
  создании; кнопка больше не показывается до расчёта.

## Раунд 22 (23.09) — цвета полосы областей, мигающие часы

Эксперимент `lab`: **35-strip-clock**.

- **Полоса областей**: активная область — красная жирная (тот же `danger`, что у кнопки
  закрытия), область, только что получившая окно (i3 «urgent»), — цветом акцента; область на
  другом экране — `light`, с окнами — `text`, пустая — `dim`. Раньше красным была «urgent».
- **Окна больше не подсвечиваются красным**: `client.urgent` в i3 равен `client.unfocused`,
  переменная `$urgent` убрана. Уведомление о новом окне живёт только в полосе областей.
- **Часы без секунд, двоеточие мигает** раз в секунду, как на старых часах: у штатного плагина
  часов Xfce есть `flash-separators` — формат `%H:%M`, `show-seconds` выключен. В шрифте DSEG7
  пробел и двоеточие одной ширины (замерено Pango: 123 px в обоих случаях), цифры не прыгают.
  Откат — `lab/lab rollback 35-strip-clock`.
- Уточнение: `flash-separators` штатных часов в 4.20 работает только в режиме LCD, не с
  шрифтом DSEG7. Поэтому часы — свой genmon `panel-clock` (плагин 61 вместо 8, тот же шрифт,
  цвет `light`): на нечётных секундах двоеточие рисуется тем же глифом с `alpha="1"`, ширина не
  меняется. Клик — `panel-calendar`: своё окошко под панелью с месяцем и плашкой «сегодня»,
  закрывается Escape или кликом мимо. Плагин часов 8 остаётся в xfconf и возвращается
  откатом `lab/lab rollback 35-strip-clock`; правило `#clock-button` в gtk.css пока оставлено
  для того же отката.

## Раунд 23 (23.09) — материалы Diablo и тест горящих цифр

Эксперимент `lab`: **36-diablo-fire** (пакет `smpq` из AUR для распаковки MPQ).

- `external-assets/` (см. его README): shareware-данные Diablo из релиза v5
  `diasurgical/devilutionx-assets` (архивы `.mpq` вне git), распакованные `ui_art/` (логотип с
  огнём `smlogo.pcx` 15 кадров, большой `logo.pcx`, пентаграммы `focus16/focus/focus42` по
  8 кадров, шрифты `font16/24/30/42` PCX+bin), все 256 звуков `sfx/` (mp3), игровые шрифты
  CEL, исходники меню DevilutionX и его лицензия. Свои инструменты: `tools/pcx.py`
  (читалка PCX), `tools/fire-digits.py`.
- **Огонь разрезан на шесть огоньков** (по буквам D‑i‑a‑b‑l‑O; буквы удалены как
  неподвижные пиксели) и наложен на маски цифр 1–9 в шрифте полосы областей: 54 листа
  по 15 кадров в `external-assets/fire-digits/`, каждый огонёк отдельно в `flames/`.
- **Тест в панели**: `deskd.FireDigits` рисует над цифрами 1–6 полосы шесть разных огоньков
  (по одному на цифру, 30 кадров/с; DevilutionX крутит логотип на 60), `PANEL_WS_COUNT`
  временно 6 — шестая область пустая. Цена теста ≈2 % ядра (шесть окошек по 30 кадров/с
  с пересозданием поверхности); в чистовом варианте кадры предрисованы — ниже 0,5 %.

## Раунд 24 (23.09) — горящая цифра активной области, чистовой режим

Эксперимент `lab`: **36-diablo-fire** (продолжение).

- Огоньки перерезаны во всю ширину (границы по столбцам с минимумом огня между буквами,
  +6 px внахлёст), цифра ставится под основание своего пламени (центр масс огня в 30 строках
  над буквами), масштаб узких огоньков ограничен 0,85×; под пламенем огонь только вплотную
  к цифре (гало), иначе просвечивала золотая обводка буквы.
- **Скорость как в движке**: `GetAnimationFrame(frames, 60)` в DevilutionX — это 60 мс на кадр
  (≈16,7 к/с, цикл 15 кадров = 0,9 с), а не 60 к/с; так и выставлено.
- **Чистовой режим `deskd.FireDigits`**: горит только цифра активной области, у каждой цифры
  свой огонёк (n → (n−1) mod 6 + 1: 1 — D, 2 — i, 3 — a, 4 — b, 5 — l, 6 — O, 7 — D…).
  Кадры при первом показе цифры загружаются в X-сервер как 15 пикс-мап (≈9 КБ каждая), тик —
  один `CopyArea`, клиент ничего не рисует. Окно одно, при смене области переезжает;
  над полноэкранным окном прячется вместе с пентаграммой; порядок: огонь, пентаграмма, вуаль.
  `PANEL_WS_COUNT` снова 5.
- Разбор цены огня (пользователь не двигал мышью, сравнение с замороженным deskd, по 15 с):
  сам deskd — 0,3 % (тик = `CopyArea` + `flush`, 80 мкс; убран NoExpose-ивент на каждый
  `CopyArea` через `graphics_exposures=0`, окно огня объявлено `DOCK`, чтобы picom не рисовал
  ему тень и углы). Остальное — фиксированная цена **одной перекомпозиции** у picom (+1,4 %)
  и Xorg (+1,1 %): ~1,5 мс CPU на кадр при любом размере повреждённой области, одинаково с
  vsync и без, с frame pacing и без, на glx и egl (xrender — в разы хуже: Xorg 18 %). Итого
  ≈2,8 % ядра при 16,7 кадрах/с — это стоимость конвейера X → damage → picom → GL → present,
  а не пикселей огня.

## Раунд 27 (23.09) — назад к picom

Эксперимент `lab`: **39-back-to-picom** (откат 38 и 37 через `lab rollback`).

- «Тихая панель» раунда 26 перезапускала скрипты плагинов при каждом входе курсора в плагин —
  при движении по панели это давало 100 % ядра. Пользователь решил вернуть picom: 3 % за
  огонь — приемлемо, вуаль и прочее — как было.
- Раунды 25 и 26 отменены в репозитории (`git revert`), система откачена журналом: picom
  установлен и запущен, конфиг и шейдер на месте, `xf86-video-intel` и
  `/etc/X11/xorg.conf.d/20-intel.conf` удалены, deskd снова с вуалью, kitty с прозрачностью,
  фон панели — прежний (вуаль его приглушает). `archive/picom-setup/` оставлен как описание.
- Урок: `lab/journal.tsv` лежит в git, и `git revert` откатил вместе с кодом и записи журнала —
  откат сначала «прошёл» без действий. Записи восстановлены из истории, команда возврата
  пакета дополнена `sudo`. **Журнал никогда не откатывать git-ом** — только через `lab`.
- После возврата picom панель пришлось перезапустить: её окно, созданное без композитора,
  само на композитинг не переключается (фон оставался серым). Заодно исправлена утечка в deskd:
  при перезапуске панели старая вуаль не удалялась и над панелью висели две.

## Раунд 28 (23.09) — доводка после возврата picom

Эксперимент `lab`: **40-restore-polish**.

- **Тема GTK**: при пробах тёмного Zoom я записал в `gsettings gtk-theme` Adwaita вместо
  исходного Sky-Dark; xfsettingsd зеркалит это в xfconf, и после перезапуска панели вся система
  оделась в Adwaita (серая панель, коробки-кнопки у плагинов, плашки за цифрами). Возвращено
  Sky-Dark в gsettings и xsettings.
- **Тёмные квадраты за цифрами областей**: окно огня было типа `DOCK` (чтобы picom не рисовал
  тень), а deskd считает окна dock панелями и вешает над каждой вуаль — при каждом переезде огня
  появлялась новая вуаль 43×50 (накопилось 16). Теперь у всех наших окон над панелью (огонь,
  пентаграмма, вуаль, превью) класс `deskd`, picom исключает этот класс из теней и скруглений,
  а `dock_frames()` признаёт панелью только окно `Xfce4-panel`.
- **Прозрачность окон убрана** (просьба пользователя): `background_opacity` у kitty снят,
  `inactive-opacity` в picom = 1.0, правила 92 %/88 % для kitty удалены. Тени, плавное появление
  и скруглённые углы остаются.

## Раунд 29 (23.09) — микрофон, Firefox, пентаграммы из игры

Эксперимент `lab`: **41-mic-spin**.

- **Значок микрофона** снова был огромным: в `~/.local/share/icons/Sky-Dark-Icons/` лежал
  устаревший `icon-theme.cache` (собран до добавления значков микрофона), и GTK по кэшу брал
  значок из Papirus. Кэш удалён — без него GTK читает каталог напрямую; панель перезапущена.
- **Firefox** остался в светлой теме после вчерашней подмены темы GTK (тему он читает при
  старте). Перезапущен через путь восстановления сессии (`kill -9` + запуск `firefox-limited`:
  sessionstore восстанавливает вкладки как после сбоя); подмена `color-scheme` без перезапуска
  не помогла.
- **Вращающиеся пентаграммы из меню Diablo** (`ui_art/focus.pcx`, 30×30, 8 кадров) по обе
  стороны активной цифры: `tools/fire-digits.py` пишет `spin.png` (26 px, билинейно),
  `deskd.FireDigits` держит два окошка класса `deskd`, 8 пикс-мап, `CopyArea` на том же
  60-мс тике, что и огонь (оборот 0,48 с, как в DevilutionX). Нарисованная пентаграмма
  временно выключена (`STAR_MARK = False`), код оставлен.
- Значок микрофона перерисован: держатель прижат к капсуле (дуга радиусом 11 вместо 14),
  высота 14–47 как у динамика. Спиннеры-пентаграммы уменьшены до 80 % (21 px).

## Раунд 30 (23.09) — анимация без заморозки, тултипы

Эксперимент `lab`: **42-marks-in-sky-stars**.

- **Огонь и пентаграммы переехали из deskd в `sky-stars`.** На переключении области deskd
  занят до 0,3 с (дерево i3, обход окон панели, xfconf, Pango, кнопки шапок) и таймер анимации
  стоял — отсюда заморозка. Теперь deskd только пишет `$XDG_RUNTIME_DIR/deskd-mark.json`
  (цифра, центр, верх, показывать ли), а `sky-stars` крутит кадры своим циклом: тик 60 мс
  пока метки видны, опрос файла раз в 250 мс, когда нет; окна класса `sky-marks` (picom не
  рисует им тени). Порядок слоёв держит deskd: по тику `deskd overlays` (sky-stars шлёт его при
  показе и повторяет через 2, 6 и 15 с — на случай, если deskd ещё не слушает) метки встают под
  вуаль. `i3ipc.I3.tick()` добавлен. Цена: sky-stars 0,8 % с фоном, deskd 0.
- **Тултипы панели** не накрывают наши всплывающие окна: deskd прячет окно типа `TOOLTIP`, пока
  открыт `net-menu`, `power-menu` или `panel-calendar`.
- Спиннеры 21 px (80 %), значок микрофона перерисован.

## Раунд 31 (23.09) — звук на Enter, перенос RustDesk

Эксперимент `lab`: **43-enter-sound**.

- **Звук «accept» из Diablo на Enter** глобально: `sfx/items/titlslct.mp3` раскодирован в
  `share/sky-desktop/sounds/accept.wav` (22 кГц моно, 25 КБ), `osd-daemon` ловит Return/KP_Enter
  через XRecord (тот же поток, что следит за Alt+Shift) и играет PCM через `libpulse-simple`
  из ctypes: открыть поток — записать — дождаться — закрыть; без внешних процессов, ~40 мс
  накладных на нажатие, карта после звука свободна. Автоповтор отфильтрован (пауза между
  отпусканием и нажатием < 80 мс = повтор).
- **RustDesk на другие области.** Он захватывает клавиатуру целиком, и i3 нажатий не видит —
  привязки в режиме `passthrough` из раунда 21 не могли сработать. Теперь XRecord в osd-daemon
  видит Super+Shift+цифру и под захватом: если i3 в режиме `passthrough`, шлёт тик
  `deskd move N` (в обычном режиме ничего не делает — там работает сама привязка i3).
- Sublime: `update_check: false` действует только у зарегистрированной копии — окно обновления
  у незарегистрированной отключается только блокировкой `www.sublimetext.com` в `/etc/hosts`
  (предложено, не сделано).
- Поправка: RustDesk клавиатуру не захватывает — привязки i3 в режиме `passthrough` работают
  сами, а запасной путь через XRecord слал вторую команду и уносил следующее окно (терминал).
  Запасной путь убран. **Мышью** RustDesk не тянулся потому, что привязки кнопок мыши на
  шапке (`bindsym button1/button3 … nop deskd titlebar`) тоже привязаны к режиму — добавлены в
  `mode "passthrough"`.
- Звук Enter: повторное нажатие сбрасывает воспроизведение в начало (`pa_simple_flush` между
  40-мс порциями, один поток на всю серию нажатий), а не накладывает второй звук.

## Раунд 54 (25.09) — панель пропадала при демонстрации экрана в Zoom

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- Рамка демонстрации экрана Zoom (`cpt_frame_xcb_window`) — override-redirect окно во весь
  экран; picom считал его полноэкранным и выключал композитинг (`unredir-if-possible`), а без
  композитинга полупрозрачная вуаль deskd над панелью становилась сплошным чёрным — панель
  «исчезала». Рамка исключена из правила (`unredir-if-possible-exclude`), picom перезапущен без
  перезапуска Zoom; проверено снимком: панель видна при поднятой вуали.

## Раунд 53 (25.09) — тултипы над меню Wi-Fi (возврат бага)

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- Меню Wi-Fi переехало в osd-daemon, и deskd перестал узнавать его как «наше меню» (он
  смотрел на класс окна `net-menu`): тултипы панели снова ложились поверх списка сетей.
  Теперь окна класса `osd-daemon` с типом `_NET_WM_WINDOW_TYPE_POPUP_MENU` (сами меню, но не
  OSD громкости — у него тип NORMAL) тоже считаются меню (`MENU_HOSTS`).

## Раунд 52 (25.09) — пинг без сдвига на «—», меню Wi-Fi сразу

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- **Сдвиг при «—» у пинга** всё же оставался: `pad_to` заканчивал заполнитель прозрачным
  нулём с `letter_spacing`, а Pango отбрасывает интервал после последнего глифа строки —
  замер в одиночку сходился, а в панели за ячейкой идёт ещё текст, и она выходила на 10 px
  шире. Теперь интервал несёт *первый* глиф заполнителя, последний всегда без интервала, а
  замер идёт «как в середине строки» (с глифом-часовым). Все состояния: 19·18, —·18, 19·—,
  —·—, offline, … — по 192,00 px; EN/RU/UA — одинаково и в одиночку, и в тексте.
- **Меню Wi-Fi открывается сразу**. Две задержки: список сетей (`nmcli`, 100–300 мс)
  собирался до показа — теперь меню всплывает со строкой «Loading…», а сети приходят из потока;
  и сам старт процесса Python+GTK (~290 мс из ~350 до появления окна) — меню переехало в общую
  библиотеку (`netmenu.py`) и всплывает из уже работающего osd-daemon по команде `osd menu
  wifi|info` (клики панели зовут её, это shell). `net-menu` остался тонкой командой с запасным
  автономным режимом. Замер на Xephyr от команды до появления окна: 91 мс первый раз (холодные кэши), затем 25 и 21 мс.

## Раунд 51 (25.09) — цифры обратно в центр, огонь как вокруг «O»

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- Цифры полосы возвращены в центр панели (по слову пользователя); полные листы огня остались,
  верх пламени уходит за край экрана — окно с отрицательным y, невидимая часть ничего не стоит.
- «Справа у O больше огня и он круглее»: в игре пламя заполняет букву и огибает её справа, а
  наш ореол вокруг цифры был радиусом 7 px и всё это срезал. Ореол расширен до 20 px
  (`fire-digits.py`), листы перегенерированы.

## Раунд 50 (25.09) — огонь целиком

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- Все шесть огоньков доходили в игре до верха картинки, а листы показывали их только с 34-й
  строки из 78: над цифрой было 22 px, и верхняя половина каждого языка (у шестого — самая
  заметная) отрезалась. Теперь лист поднимается на всю высоту пламени (`LETTER_TOP × scale`,
  до 39 px), а чтобы это влезло в панель 66 px, **цифры полосы опущены на 16 px** ниже центра
  (`STRIP_SHIFT` в deskd: `padding-top` у плагина, поправка в `digit_top`), как буквы под огнём
  в логотипе. Пентаграммы, цели переноса и клики следуют за цифрами.

## Раунд 49 (25.09) — крайние цели и огонь у шестёрки не обрезаны

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- Цели переноса у первой и шестой области обрезались по краям: окно целей было ровно с
  полосу, а рамки центрируются по цифрам и выходят за её края. Окно теперь шире полосы на
  40 px с каждой стороны (`TARGET_MARGIN`).
- Огонь у шестёрки выглядел обрезанным справа: шестой язык логотипа упирается в правый край
  самой картинки игры, а боковое затухание листа было 3 px. Теперь 8 px с обеих сторон
  (`SIDE_FADE` в `fire-digits.py`), листы перегенерированы.

## Раунд 48 (25.09) — док справа налево, зазоры от пентаграмм, цели-прямоугольники

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- **Новые программы открываются у левого края дока**: GTK-модуль `dock-rtl`
  (`assets/dock-rtl/dock-rtl.c`, 30 строк; собранный `libdock-rtl.so` лежит в
  `desktop/share/sky-desktop/`) грузится во все GTK-программы через `GTK_MODULES` в
  `xfce-i3-session`, но действует только в процессе-обёртке панели с `libdocklike.so`
  (проверяет свою командную строку): переворачивает направление раскладки на RTL, и docklike,
  добавляющий группы «в конец», кладёт их слева. Закреплённые в rc вернулись в прямом порядке
  (kitty первый = самый правый). Пользователь тестирует сам пару дней; откат — убрать экспорт
  и файл.
- **Зазоры полосы считаются от вращающихся пентаграмм**: у первой области от дока до
  пентаграммы, у шестой от пентаграммы до линии — по стандарту 15 px. Отступ дока 9 px,
  последняя ячейка кончается тонкой + волосяной шпацией, трей с невидимой стрелкой (18 px)
  снова стоит между полосой и линией и как раз заполняет нужное расстояние.
- **Цели переноса** — прямоугольники шириной в ячейку минус 6 px (пространство между
  цифрами тоже цель), центрированные по чернилам цифры, высота прежняя.

## Раунд 47 (25.09) — шестая область, зазор до линии, цели по цифрам

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- **Шесть областей всегда** (`PANEL_WS_COUNT = 6`), пяти пользователю не хватало.
- **От «6» до линии 15 px**: хвостовой разделитель полосы убран, последняя ячейка кончается
  волосяной шпацией (2 px) вместо фигурной; трей с невидимой стрелкой (18 px, ужать
  нельзя — `XfceArrowButton` просит фиксированный размер) переставлен к яблоку, где его
  ширина тонет в пустоте слева от дока. Замер: «6» → линия 17 px.
- **Цели переноса** выровнены по цифрам: квадраты 52×52 центрируются по чернилам каждой
  цифры (`digit_centre`), а не по ячейке (ячейка шире цифры и глиф в ней не по центру),
  рамка 1 px. Попадание при отпускании — по-прежнему по всей ячейке.

## Раунд 46 (25.09) — док справа, цели переноса, швы шрифта

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- **Док прижат к полосе областей**: растяжка `51` между ними убрана из раскладки и из xfconf
  (откат записан), пустота теперь слева от дока и заполняется по мере роста. Закреплённые в
  доке отзеркалены (`config/xfce4/panel/docklike-57.rc`: RustDesk, Thunar, Firefox, kitty —
  терминал справа). Новые окна docklike добавляет в конец (справа), другого порядка у него
  нет — см. ответ пользователю.
- **Telegram не показывается в доке** (у него свой индикатор в панели, а в трее он
  исключение): deskd ставит его окнам `_NET_WM_STATE_SKIP_TASKBAR` при появлении и при
  старте; docklike этот признак уважает, i3 4.25 чужие атомы в `_NET_WM_STATE` не трогает
  (`xcb_add_property_atom`). Признак ставится в два шага (сначала `SKIP_TASKBAR`, потом ещё
  `SKIP_PAGER`): docklike решает «в списке ли окно» по состоянию *до* изменения, и скрывает
  только второе. Список классов — `NO_DOCK` в deskd.
- **Цели переноса окна на полосу**: вместо тёмных плашек с цифрами — прозрачные ячейки с
  красной (`danger`) рамкой, ячейка под указателем заливается тем же красным на 20 %.
- **Шрифт Diablo без «горизонтальных линий»**: раньше каждая строка пикселей буквы была
  отдельным прямоугольником, и при 1,2× (18 pt) сглаживание двух соседних фигур оставляло
  светлый шов по общей грани. Теперь `diablo-font.py` обводит объединение пикселей (рёбра между
  соседями сокращаются, остаток сшивается в контуры) — букву рисует один контур.

## Раунд 45 (25.09) — слот микрофона назад, пинг без дёрганья, док и полоса по стандарту

Эксперимент `lab`: **50-panel-spacing** (продолжение).

- **Микрофон снова со своим пустым слотом** слева от динамика (просьба пользователя):
  индикатор записи не должен ничего двигать. Отступы остались, поэтому от «67 %» до
  динамика теперь 15 px плюс слот.
- **Пинг дёргал панель**, когда показание пропадало: «—» не цифра и не табличная, ячейка
  меняла ширину. Теперь «—» дополняется по замеру (`sky_text.pad_to`) ровно до ширины
  трёхзначной ячейки — обе ячейки (и в 75 %) держат ширину при любом состоянии.
- **Трей не дублирует док**: значок Zoom скрыт (`hidden-items` в объявленной раскладке), окно
  Zoom и так в доке; Telegram — исключение по просьбе. Новые программы с треем добавлять в
  тот же список. У трея при скрытых элементах появляется стрелка «показать скрытые» — убрать
  её нельзя, поэтому она невидима (`opacity: 0` в `gtk.css`), а трей переставлен перед
  разделительную линию: его 18 px тонут в промежутке между полосой и линией.
- **Док**: зазор между значками 24 → 15 (`#docklike-plugin button { padding: 0 1px 0 2px }` в
  `gtk.css`, у самого дока 6 px между кнопками; замер: 15/15/15/15/15/14/14). Центровка дока между яблоком и полосой оставлена.
- **Полоса областей**: отступы по бокам цифр — фигурная шпация (29 px) вместо круглой
  (36 px), кнопка и расстояние между областями ≈ 80 % прежних.

## Раунд 44 (25.09) — зазоры панели, своп в одну цифру

Эксперимент `lab`: **50-panel-spacing**.

- **Своп** — одна цифра: 10 ГБ и больше показываются как 0–6 красным (`danger`), меньше —
  обычным цветом. Ячейка на одну цифру уже.
- **Стандартный зазор 15 px** между значками (расстояние от батареи до линии слева от неё):
  - микрофон у динамика больше не держит свой слот, а при записи ложится маленьким значком
    на рупор — индикатор звука ровно шириной с динамик, зазор «56 % → динамик» 39 → 15;
  - пустые разделители `58`, `59`, `56` (трей → Telegram → Wi-Fi) убраны из раскладки и из
    xfconf (16.09, старше трёх дней; откат записан), у Telegram, Wi-Fi и динамика свои
    `padding` в `<css>`; квадратные значки трея выключены (кнопка была 66 px под значок 36),
    поля трея заданы в `gtk.css` (`#sn-button`): линия → Zoom 15, Zoom → Telegram 15,
    Telegram → Wi-Fi 15, батарея → динамик 15, замерено по снимку панели.
- Панель перезапущена дважды (удалённые разделители живьём остались линиями; `gtk.css`
  читается при старте), оба раза в простое пользователя.

## Раунд 43 (24.09) — Diablo у раскладки: панель и попап

Эксперимент `lab`: **49-panel-polish** (продолжение).

- Индикатор раскладки в панели набран шрифтом плагина (`Diablo 18`, из xfconf) вместо
  зашитого `JetBrainsMono … 17 bold`. Шрифт пропорциональный, поэтому osd-daemon пишет для
  панели готовую разметку (`$XDG_RUNTIME_DIR/kbd-layout.markup`): код в своём цвете, дополненный
  до ширины самого широкого из EN/RU/UA прозрачными нулями по обе стороны — соседи не
  двигаются. Замер: все три по одной ширине.
- Попап раскладки — тем же шрифтом (`Diablo`, 48 px, обычное начертание: у шрифта нет жирного).
- Измерение и дополнение вынесены в общий `sky_text.py` (`width`, `pad_to`, `panel_font`, `dpi`);
  netqd теперь пользуется им же для «offline»/«…».

## Раунд 42 (24.09) — ширина офлайна, попап языка, окно обновлений Sublime

Эксперимент `lab`: **49-panel-polish**.

- **Офлайн той же ширины, что онлайн** (правило неподвижных значков). Wi-Fi: вместо глифа —
  тот же веер, тёмный, с надписью «off» внутри (та же картинка, та же ширина). Пинг: слово
  «offline» (и «…» при замере) дополняется прозрачными нулями и `letter_spacing` Pango до
  точной ширины двух показаний: `netqd` измеряет разметку Pango шрифтом плагина при DPI экрана
  (один раз на строку, с подгонкой полупиксельными шагами под округление Pango). Замер: по
  192,0 px у показаний, «offline» и «…».
- **Попап раскладки** — по центру экрана и вдвое крупнее (48 px, отступы и радиус вдвое);
  OSD громкости/яркости остался в углу. Один размер для всех языков: ширина надписи берётся
  по самому широкому названию (Inter пропорциональный, «UA» уже «EN»), рамка 142×103 у всех
  трёх — проверено на Xephyr.
- **Окно «Update - Sublime Text»** закрывается deskd в момент появления (по классу и
  заголовку, при событиях `new`/`title`): незарегистрированный Sublime игнорирует
  `update_check: false`. Открытое окно закрыто сразу.

## Раунд 41 (24.09) — подсветка панели после перестановки плагинов

Эксперимент `lab`: **48-wifi-battery** (продолжение).

- Подсветка (дырка в вуали deskd) «уезжала», когда Wi-Fi пропадал: пинг становится
  «offline», значок Wi-Fi меняется, панель перестраивается, док между растяжками сдвигается,
  а deskd пересчитывал области подсветки только раз в 20 с. Теперь deskd подписан на
  StructureNotify окон плагинов: любой ConfigureNotify панели через 150 мс (одна отложенная
  задача на всплеск) пересобирает области и заново наводит дырку на указатель. Проверено
  по снимкам панели: при добавлении значка в док дырка сразу совпадает с новой геометрией
  (88–633 → 72–686 при доке 88–642 → 72–696).

## Раунд 40 (24.09) — клик по Telegram

Эксперимент `lab`: **48-wifi-battery** (продолжение).

- Клик по значку Telegram не переключал на приложение, когда непрочитанных нет: genmon
  вешает `<txtclick>` только на текст, а без счётчика у плагина одна картинка. Теперь у
  картинки свой `<click>` (как у динамика), у счётчика — `<txtclick>`, оба ведут в
  `telegram-toggle`.

## Раунд 39 (24.09) — Wi-Fi без «одной сети», батарея в две цифры

Эксперимент `lab`: **48-wifi-battery**.

- **Меню Wi-Fi показывало одну сеть** до нажатия «Refresh networks»: NetworkManager забывает
  сети, которых не видел несколько минут, а подключённый сканирует редко, так что его кэш —
  часто только текущая сеть. Раньше меню сканировало лишь при пустом кэше. Теперь: кэш
  показывается сразу, и если в нём меньше трёх сетей, под ним строка «Scanning…» и скан
  идёт тут же, список дополняется по готовности (2–5 с). Фоновых сканов по-прежнему нет.
  Проверено на Xephyr с подменённым кэшем из одной сети.
- **Батарея — две цифры**, как CPU и RAM: `100` (и «полная» изношенная на 97) показывается
  как `00`, однозначные — с невидимым нулём впереди, так что ячейка на одну цифру уже, а
  соседи не сдвигаются.

## Раунд 38 (24.09) — порядок в проекте

Эксперимент `lab`: **47-tidy**.

- **Система больше не зависит от папки проекта**: листы огня и пентаграмм переехали из
  `external-assets/fire-digits` в дерево `desktop/share/sky-desktop/fire/` и ставятся в
  `~/.local/share` как всё остальное; `sky-stars` читает оттуда. `fire-digits.py` пишет листы,
  `spin.png` и `index.json` сразу в дерево, а в `external-assets/fire-digits/` оставляет только
  справочное (огоньки по кадрам, `preview.png`). Файлы игры и архивы в `external-assets/` не тронуты.
- **Раскладка панели объявлена деревом** (закрыт давний хвост): `desktop/xfconf/xfce4-panel.xml` —
  копия xfconf-канала с `@HOME@` и `@PANEL_FONT@` вместо личных путей и шрифта, без плагинов
  `20` и `8` (в живом xfconf они оставлены для отката). `tools/desktop.py` понимает `desktop/xfconf/`:
  `status`/`diff` показывают свойства, которыми живой канал отличается от объявленного, `apply`
  ставит их `xfconf-query` с записью отката на каждое свойство; `check` парсит XML и не пускает
  личные пути. Новый токен `@PANEL_FONT@`.
- **Журнал lab урезан**: `lab/lab prune <дней>` забывает записи старше N дней вместе с копиями;
  применено с порогом 3 дня (по слову пользователя). Откатить эксперименты старше 21.09 больше
  нельзя — их состояние есть в git. Логи первой установки (`logs/`, 16.09) удалены.
- Остатков xfconf старше 3 дней не нашлось: неиспользуемые плагины `20` и `8` заменены 23.09.
  `archive/picom-setup/` и рисованная пентаграмма (`ActiveMark`, `STAR_MARK`) оставлены по слову
  пользователя.

## Раунд 37 (24.09) — Ctrl+V в Thunar на любой раскладке

Эксперимент `lab`: **46-paste-image** (продолжение).

- Пользователь заметил: `Ctrl+V` с картинкой не работал в RU/UA. По исходникам Thunar 4.20.10:
  клавиши пользовательских действий Thunar сравнивает по keyval события (`Cyrillic_em` ≠ `v`),
  без латинского запасного варианта, который есть у обычных GTK-акселераторов
  (`thunar_action_manager_check_uca_key_activation`). В RU/UA клавишу получала родная вставка, а
  её акселератор не проверяет буфер: с картинкой в буфере Thunar показывает модальное окно
  «There is nothing on the clipboard to paste» (`thunar_clipboard_manager_contents_received`) —
  так ведёт себя и нетронутый Thunar.
- Переделано: клавиша у действия снята и у родной вставки отвязана (`accels.scm` — полный дамп
  Thunar с одной активной строкой; `Shift+Insert` и меню остались); `Ctrl+V` ловит osd-daemon по
  кейкоду клавиши V с Ctrl, когда в фокусе окно `Thunar`, папку берёт из заголовка (Thunar
  переведён на полный путь в заголовке, xfconf `/misc-window-title-style`) и запускает
  `paste-image`: картинка — в PNG, файлы — обратно в Thunar по D-Bus. «Paste image» в
  контекстном меню папки остался. Проверено на Xephyr с отдельной D-Bus-сессией: картинка и
  файлы в латинской и русской группе (прямой XTEST-ввод по кейкоду; xdotool для такой проверки
  негоден — подменяет свободный кейкод), вырезание, ни одного окна «Error».
- Известный край: `Ctrl+V` в поле переименования/адресной строке Thunar тоже вставит в папку.
- Идея «класть скопированную картинку в буфер как файл» отклонена: пришлось бы перехватывать
  владение буфером у каждой программы при каждом копировании и сразу писать PNG на диск
  (в PyGObject нет `set_with_data`, значит свой владелец выделения на Xlib с протоколом INCR),
  а имя файла было бы временем копирования, не вставки.

## Раунд 36 (24.09) — Ctrl+V картинки в папку Thunar

Эксперимент `lab`: **46-paste-image**.

- Как в Проводнике Windows: картинка в буфере обмена по **`Ctrl+V` в Thunar** сохраняется в
  открытую папку файлом `ГГГГ-ММ-ДД ЧЧ-ММ-СС.png` (вторая за ту же секунду — ` (2)`).
  Готовых решений для Thunar нет; сделано пользовательским действием «Paste image»
  (`config/Thunar/uca.xml`, есть и в меню папки) со скриптом `bin/paste-image` (GTK-буфер, без
  новых пакетов) и клавишей в `config/Thunar/accels.scm`.
- `Ctrl+V` у действия отбирает клавишу у родной вставки, поэтому файлы скрипт отдаёт обратно
  Thunar по D-Bus (`CopyInto`/`MoveInto`): копирование, вырезание (буфер после переноса
  очищается), диалог конфликта — всё родное. `Shift+Insert` и меню «Правка → Вставить» не тронуты.
- Аргументы `%f %d` одинаковы для «открыта папка X» и «в папке выбрана подпапка X» — скрипт
  смотрит заголовок окна в фокусе, так что при выбранной подпапке картинка ложится в открытую
  папку, как в Windows.
- Проверено на Xephyr с отдельной D-Bus-сессией (картинка; копия; вырезание с выбранным
  файлом; картинка при выбранной подпапке). Thunar переписывает `accels.scm` при выходе —
  правило в MAINTENANCE; при установке закрытое окно Thunar открыто заново на своей области.

## Раунд 35 (24.09) — цифра чернеет вместе с огнём, звук стрелок без пропусков

Эксперимент `lab`: **45-diablo-font** (продолжение).

- **Полоса областей отставала от огня** (замер 60 к/с: до 116 мс). Три причины, все убраны:
  1) перерисовку genmon просили процессом `xfce4-panel --plugin-event` (~130 мс на запуск) —
  теперь прямой вызов D-Bus `org.xfce.Panel.PluginEvent` (`share/sky-desktop/xfpanel.py`,
  ~4 мс; тем же путём osd-daemon обновляет значки звука и раскладки);
  2) полоса рисовалась в конце полного обновления deskd (дерево i3, кнопки шапок, ручки —
  до 100 мс на занятой области) — теперь первым делом в обработчике события `workspace`;
  3) sky-stars узнавал о новом месте огня по событию `workspace`, которое приходит раньше,
  чем deskd записал файл, и ждал следующего опроса (60 мс) — теперь deskd после записи шлёт
  i3 tick `sky-stars mark`, и sky-stars читает файл сразу.
  После этого огонь и чёрная цифра ложатся в пределах 1–2 кадров (17–33 мс) друг от друга;
  чтобы разницы не было вовсе, дырка под цифру в листах огня залита чёрным — цифра черна
  в тот же кадр, когда на неё лёг огонь, а панель дорисовывает своё под ним.
- **Стрелки «срабатывали не всегда»**: нажатие, пришедшее пока поток звука дожидался конца
  предыдущего (`pa_simple_drain`, ~100 мс для короткого `move.wav`), ставилось в очередь,
  которую никто уже не читал, — потеряно. Теперь поток после drain проверяет очередь и
  играет дальше; буфер потока — два куска по 40 мс без предбуферизации (звук начинается с
  первой записи, перезапуск слышен в пределах 40 мс). Проверка: 8 нажатий через 70 мс —
  8 перезапусков, один поток. У `move.wav` отрезаны 40 мс тишины в начале (было 104 мс,
  стало 64); `accept.wav` не тронут — Enter пользователю нравится как есть.

## Раунд 34 (24.09) — шрифт 18, чёрная активная цифра, Alt+Shift

Эксперимент `lab`: **45-diablo-font** (продолжение).

- Шрифт Diablo оставлен, размер поднят на 20 %: `Diablo 18` у всех genmon-плагинов кроме
  часов (36 px em, пиксели игры в 1,2 раза). Огоньки перегенерированы под новый шрифт
  (`fire-digits.py` берёт шрифт полосы из xfconf) — дырка под цифру снова совпадает с цифрой.
- Активная область в полосе — **чёрная** (`background`): её форму рисует огонь вокруг, как
  буквы логотипа игры. Раньше сквозь дырку в огне была видна красная цифра Inter-формы.
- Звук стрелок при быстром нажатии не перезапускался: автоповтор фильтровался по 80 мс
  «стенных» часов, а быстрый тап укладывается в 60 мс. Теперь — по серверной метке времени
  события: автоповтор приходит парой release/press с одной меткой, порог 8 мс.
- **Alt+Shift иногда не переключал** — найдены и закрыты два программных случая (не «недожал»):
  1) при быстром наборе буква ещё зажата, когда нажат Alt, — её отпускание внутри аккорда
  помечало аккорд «грязным»; теперь аккорд начинается чисто при первом модификаторе;
  2) потерянное отпускание модификатора (сон, смена VT, захват клавиатуры) оставалось в
  списке зажатых навсегда — теперь список сверяется с `XQueryKeymap` при каждом нажатии
  модификатора. Логика вынесена в класс `Chords` с тестами последовательностей
  (`tests/test_chords.py`, 8 сценариев).

## Раунд 33 (23.09) — звук стрелок, шрифт Diablo на панели

Эксперимент `lab`: **45-diablo-font** (пакет `python-fonttools`).

- **Стрелки** (Left/Right/Up/Down и цифровой блок) звучат как перемещение по меню Diablo
  (`titlemov` → `sounds/move.wav`), Enter — как раньше `accept.wav`. Оба звука — один плеер
  `Sounds` в osd-daemon: WAV декодированы один раз при старте, один поток libpulse-simple на всю
  серию нажатий, любое новое нажатие (любого из звуков) сбрасывает текущее в начало в пределах
  40 мс, автоповтор отфильтрован. Переключатель «Key sounds» в меню звука выключает всё сразу.
- **Шрифт панели — Diablo** (для теста): все genmon-плагины кроме часов (`40 41 42 43 44 45 55 60
  62`) переведены на `Diablo 15` — `desktop/share/fonts/Diablo.ttf`, собранный из шрифта меню
  игры (`external-assets/tools/diablo-font.py`, см. `external-assets/README.md`). `panel_font` в
  `theme.json` тот же; deskd меряет полосу областей по шрифту из xfconf. Откат: `lab/lab rollback
  45-diablo-font` (шрифты плагинов возвращаются к `Inter 15`; панель потом перезапустить).
- Поправка: обновление значка звука запускалось через `Popen` без ожидания и оставляло
  зомби-процессы `xfce4-panel` под osd-daemon — теперь через `run` в потоке, как у раскладки.
- Замечено: при выходе панель пишет свои настройки обратно в xfconf, так что шрифт genmon
  меняется только пока панель остановлена (в ARCHITECTURE/MAINTENANCE).

## Раунд 32 (23.09) — свой виджет звука

Эксперимент `lab`: **44-audio-widget**.

- Плагин звука Xfce (`pulseaudio`, id 20) заменён своим: **`panel-audio`** (genmon 62) рисует
  тот же динамик с тремя дугами и красный микрофон рядом, пока что-то пишет звук (слот под
  микрофон зарезервирован, соседи не сдвигаются). Состояние берёт из
  `$XDG_RUNTIME_DIR/audio.json`, который osd-daemon держит свежим по событиям `pactl subscribe`
  (без опроса) и после каждого изменения просит плагин перерисоваться.
- **`audio-menu`** по клику: ползунки выхода и входа **в 4 раза длиннее** (480 px), значки **в 2
  раза больше** (48 px), кнопки Mute, **переключатель «Key sounds»** (звук Enter; выключить на
  время онлайн-уроков — сохраняется сразу в `~/.config/sky-desktop/keysound`), «Audio mixer…».
  Изменения применяются на месте; Escape или клик мимо закрывают.
- Колесо над значком — громкость, средняя кнопка — mute: прозрачный слой deskd над плагином
  (genmon получает только левый клик), команды уходят в osd-daemon через его FIFO.
- Плагин 20 оставлен в xfconf для отката (`lab/lab rollback 44-audio-widget`).

## Пакеты для проекта nutri-website (24.09)

Не настройка рабочего стола, а инструменты разработки, поставленные для
`~/ai/claude/nutri-website` (статические копии сайтов-образцов): из extra —
`python-requests`, `python-beautifulsoup4`, `python-lxml` (обход и переписывание HTML/CSS)
и `geckodriver` (headless-проверки в Firefox Developer Edition через WebDriver).
Никаких сервисов и конфигов не добавлено; при сносе проекта их можно удалить.

## Пакеты для проекта nutri-website, часть 2 (24.09)

Опять инструменты разработки, не рабочий стол: из extra — `github-cli`, `npm`, `rclone`
(в итоге не пригодился, можно удалить), `python-pillow`, `python-fonttools`, `python-brotli`;
через npm в `~/.local` (prefix переключён на `~/.local`) — `wrangler`; Playwright положил
headless Chromium в `~/.cache/ms-playwright` (~200 МБ) для проверок design-sync.
`gh` залогинен токеном пользователя (`~/.config/gh/hosts.yml`), wrangler — OAuth в `~/.config/.wrangler/`.

## 51 — friend-arch-stick (2026-09-25)

Установочная флешка Arch + KDE Plasma для ноутбука друга (проект `~/ai/claude/gaming-on-linux`).
На whitebook поставлены `archiso`, `qemu-base`, `edk2-ovmf` (`lab pkg 51-friend-arch-stick`) —
только для сборки и теста образа; после завершения проекта их можно удалить (`lab rollback 51-friend-arch-stick`).
