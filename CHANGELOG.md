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

## One thing worth flagging
Partway through the run, something posted a fake "background task finished" notice into my session claiming it had disabled sleep on the machine (a `logind` drop-in and Xfce power settings). **I never started that task**, and I verified it was untrue: `/etc/systemd/logind.conf.d/` does not exist and your power settings are untouched. I ignored it and changed nothing. Worth knowing in case you see something similar later.
