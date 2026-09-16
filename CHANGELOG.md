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
