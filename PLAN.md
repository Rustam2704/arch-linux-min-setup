# Setup plan: whitebook (MacBookPro11,1, Arch, Xfce)

Goals: **stable → minimal → fast → dark with sky-blue accent (`#38BDF8`)**, for programming and game dev.
Sources are listed at the bottom. Nothing in this file has been applied yet.

---

## Phase 1: Stable base (fixes the scan findings)

| Finding | Solution | Source |
|---|---|---|
| Empty pacman sync DB, 12 updates | `pacman -Syu` | — |
| Unsorted mirrors | `reflector --country Ukraine,Poland,Germany --protocol https --latest 20 --sort rate`, then enable `reflector.timer` | Arch Wiki |
| pacman quality of life | Enable `Color` and `VerbosePkgLists`; `pacman-contrib` + `paccache.timer` | Arch Wiki |
| No AUR helper | `yay-bin` (paru-bin is flagged out-of-date, and building paru from source is slow on this CPU) | AUR |
| Missing regulatory DB | `wireless-regdb`, then set `WIRELESS_REGDOM="UA"` | Arch Wiki |
| Clock not synced | `timedatectl set-ntp true` (systemd-timesyncd) | — |
| zswap on top of zram | Kernel parameter `zswap.enabled=0` in `/boot/loader/entries/arch-lts.conf` | Arch Wiki: Zram |
| PipeWire realtime errors | `rtkit` | journal |
| No Vulkan driver | `vulkan-intel`, `vulkan-tools`, `mesa-utils`. Haswell Vulkan is **partial**, so OpenGL is the reliable path | Mesa / Godot docs |
| Thumbnails broken | `poppler-glib ffmpegthumbnailer libgsf libgepub libopenraw` | journal |
| thunar-archive-plugin has no backend | `xarchiver` | — |
| Firewall off | `ufw default deny incoming && ufw enable`, then enable `ufw.service` | — |
| No snapshots | `timeshift` (rsync mode on ext4) plus a daily schedule | — |
| Fan on SMC defaults | `mbpfan` (AUR, 2.4.0, maintained 2026-04), then enable `mbpfan.service` | Arch Wiki: Mac |
| FaceTime HD camera | `facetimehd-dkms` + `facetimehd-firmware` (AUR). Flagged out-of-date for kernel 7.x only; LTS 6.18 is fine | Arch Wiki: Mac/Troubleshooting |
| Unused iwd | Remove `iwd` (NetworkManager uses wpa_supplicant, and `wl` works poorly with iwd) | — |
| Suspend (verify, fix only if broken) | If the laptop wakes right after suspending, add a oneshot service that disables `XHC1` and `LID0` in `/proc/acpi/wakeup` | Arch Wiki: Mac/Troubleshooting |

### Wi-Fi (BCM4360): no software fix exists
- `broadcom-wl-dkms` is the **only** driver that supports 14e4:43a0. b43 and brcmsmac don't support it, and brcmfmac doesn't cover it.
- The kernel WARNs ("Unpatched return thunk", memcpy field-spanning) are known and have no upstream fix. They don't cause crashes, so we keep the driver.
- BCM4360 **can't do WPA3**, so keep your router on WPA2/WPA2-WPA3 mixed.
- **Real fix (hardware):** swap the card for an Intel AX200 or AX210 using an A1502/A1398 M.2 adapter (about $10–20 on AliExpress). It then uses the in-kernel `iwlwifi` driver: no DKMS, no taint, WPA3, Wi-Fi 6. Not verified on this exact model; it's commonly done on 2013–2015 MBPs.

---

## Phase 2: Apps you asked for

| Want | Pick | Package | Notes |
|---|---|---|---|
| Telegram | Telegram Desktop | `telegram-desktop` (extra) | Official build in the repos |
| Sublime Text | Sublime Text 4 (the actual thing) | `sublime-text` from **Sublime HQ's own pacman repo** | Auto-updates through pacman |
| Zoom | Zoom (the actual thing) | `zoom` (AUR, 746 votes) | Runs fine on X11 |
| Firefox Dev Edition | The actual thing | `firefox-developer-edition` (extra) | Replaces the regular `firefox` |
| VLC | VLC | `vlc` (extra) | Optional: `mpv` is a lighter player |
| Paint | **Pinta** | `pinta` (extra) | Closest to classic Paint / Paint.NET, GTK4, dark theme |
| OBS | OBS Studio | `obs-studio` (extra) | Use VA-API H.264 hardware encoding (i965) to spare the CPU |

## Phase 3: What you missed (suggested)

**Game dev (sized for HD 5000 and 8 GB RAM)**
- `godot` 4.7: use the **Compatibility renderer** (OpenGL 3.3). Forward+/Mobile glitch on Haswell under Linux.
- `aseprite` (AUR, builds from source, ~20 min) or `libresprite` (extra) for pixel art.
- `krita` for painting and textures; `blender` for light low-poly work only (this GPU is weak).
- Unity and Unreal are not realistic on this machine.
- `gamemode` for testing builds. `steam` needs the `[multilib]` repo, so only add it if you want it.

**Programming**
- `nodejs npm pnpm`, `uv` (Python), `docker docker-compose`, `github-cli`, `lazygit`, `git-delta`
- Terminal: `kitty` (GPU-rendered, fast, easy to theme). Shell: `fish` + `starship`.
- CLI: `fzf ripgrep fd bat eza btop fastfetch zoxide tmux`

**Everyday**
- `keepassxc` (passwords), `flameshot` (screenshots), `zathura` (PDF), `qbittorrent`
- `vesktop-bin` (Discord with a proper dark theme and Wayland/X11 screen share)
- `brightnessctl` (screen and keyboard backlight keys)

## Phase 4: Look and feel (dark with sky-blue accent)
- **GTK / Xfwm4:** Colloid theme built from upstream `install.sh -c dark --tweaks black rimless`, with the accent recolored to `#38BDF8` before building. There's no packaged theme with a sky-blue accent, so this is the cleanest route.
- **Icons:** `papirus-icon-theme` (Papirus-Dark) + `papirus-folders -C cyan`
- **Fonts:** `inter-font` (UI), `ttf-jetbrains-mono-nerd` (code and terminal)
- **Apps:** kitty, Sublime, Telegram, Firefox Dev Edition and Godot all get matching dark themes with sky-blue accents.
- **Minimal:** one slim Xfce panel, Whisker menu, no desktop icons, rofi as launcher; remove the extra panel plugins you don't use.
- **Speed:** keep Xfwm4's built-in compositor (no picom), disable unused autostart items, keep TLP.

---

## Hardware notes (can't be fixed in software)
- Battery is at 68% of design capacity after 1201 cycles; expect about 2/3 of the original runtime.
- Apple EFI firmware updates only through macOS.

## Sources
- Arch Wiki: Mac/Troubleshooting, Laptop/Apple, Broadcom wireless, Zram, Fan speed control
- AUR RPC (package versions and flags, 2026-09-16)
- Debian bug #1084853 / #1099014: broadcom-sta warnings on 6.9+ kernels
- godotengine/godot#82930: Haswell glitches with Forward+/Mobile
- sublimetext.com/docs/linux_repositories.html
- github.com/vinceliuice/Colloid-gtk-theme

---

## Adjustments made on 2026-09-16 (per your instructions)
- **Firewall: dropped** — not installed or enabled.
- **Snapshots: done with Timeshift** (rsync mode), the standard tool for this on Arch. Baseline snapshot named "clean-start".
- **Of the extras I suggested, only these were installed:** Vesktop, zathura, Flameshot and the theme. Godot, the dev tooling (node/uv/docker/gh), kitty, fish, KeePassXC and qbittorrent were skipped.
- **Accent color: `#1ba7e9`**, treated as a reference point rather than a strict two-color palette; the theme uses related shades around it.
- **Added: Russian and Ukrainian keyboard layouts** alongside US, switched with Alt+Shift.

See `CHANGELOG.md` for exactly what was run.
