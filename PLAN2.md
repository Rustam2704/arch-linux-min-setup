# Plan 2 — post-reboot results and your new list (2026-09-16)

## Post-reboot verification

| Check | Result |
|---|---|
| Kernel | 6.18.52-1-lts, both DKMS drivers built for it |
| **Camera** | **Works** — `/dev/video0` present, `facetimehd` loaded, v4l reports "Apple Facetime HD" |
| **Wi-Fi region** | **`country UA: DFS-ETSI`** — correct, and 5 GHz/6 GHz channels are now unlocked |
| zswap | Off (`zswap.enabled=0` active), zram is the only swap |
| Services | mbpfan, thermald, tlp, time sync, rtkit all running |
| **Suspend** | **Still untested** — needs you to close the lid. `XHC1` and `LID0` are both still wake-enabled, so if it wakes by itself, that's the cause and the fix is in `CHANGELOG.md`. |

---

## Your new list

### 1. Remove the login screen
LightDM can log you straight in. On Arch this needs an `autologin` group to exist and your user to be in it, then two lines in `/etc/lightdm/lightdm.conf`:
```bash
sudo groupadd -r autologin; sudo gpasswd -a fanatic autologin
# in /etc/lightdm/lightdm.conf, section [Seat:*]:
autologin-user=fanatic
autologin-session=xfce
```
Trade-off: anyone who opens the lid is in your session. Your disk isn't encrypted anyway, so this changes very little in practice.

### 2. Remove the startup sound
The chime is played by Apple's firmware before Linux exists, but its volume lives in NVRAM, and that variable is writable from Linux. It's already present on your machine (`SystemAudioVolume-7c436110-...`).
```bash
V=/sys/firmware/efi/efivars/SystemAudioVolume-7c436110-ab2a-4bbb-a880-fe41995c9f82
sudo cp $V /root/SystemAudioVolume.bak        # so it can be restored
sudo chattr -i $V
printf '\x07\x00\x00\x00\x00' | sudo tee $V > /dev/null   # attrs + volume 0
sudo chattr +i $V
```
The first 4 bytes are the EFI variable attributes; the last byte is the volume. `0x00` silences it. An NVRAM reset (PRAM zap, battery fully drained) brings the chime back, and you'd just rerun this.

### 3. Turn off the Apple logo light
**Not possible in software, and there's no hardware switch.** On your model the logo is lit by the *same LED backlight as the screen* — literally the same light source, shining through the cut-out. It's only off when the display is off, and it dims when you dim the screen. The only real options are physical: a vinyl logo cover/sticker over it, or opening the lid assembly to block it (which risks the display).

### 4. Wi-Fi password and autoconnect
I looked at the actual profiles. Right now you have **two duplicate profiles for the same network**, and both do have a saved password and `autoconnect=yes`:
- `NOKIA-062A-5G` (created 00:50)
- `NOKIA-062A-5G 1` (created 03:08, the one you just made)

The original failure is in the logs: `no secrets: No agents were available for this request`. That happens when NetworkManager stores the password "for this user only" — it hands it to a keyring daemon, and **you have no keyring installed** (`gnome-keyring` is missing), so the password vanished and it asked again. The second profile was saved system-wide, which is why it works now.

Fix: delete the duplicate and pin the password to the system, so no keyring is involved:
```bash
sudo nmcli connection delete "NOKIA-062A-5G 1"
sudo nmcli connection modify "NOKIA-062A-5G" \
     wifi-sec.psk-flags 0 connection.autoconnect yes connection.autoconnect-priority 10
```
The autoconnect checkbox you couldn't find is in `nm-connection-editor` → your network → the **General** tab → "Connect automatically with priority". Optionally install `gnome-keyring` if you want per-user secrets for other apps later.

### 5. Claude's "Quick safety check" on startup
That's Claude Code's folder-trust prompt: *"Quick safety check: Is this a project you created or one you trust?"* It appears once per directory, because a folder can ship its own settings that run commands. It should be remembered after you answer, but your entry for `/home/fanatic` shows it was never recorded, so it keeps asking.

Fix — mark the folders you launch from as trusted in `~/.claude.json`:
```bash
# sets hasTrustDialogAccepted=true for /home/fanatic and your project dirs
```
I'd do this with a careful `jq` edit on a copy, then swap it in. If you launch Claude from new folders often, each new one will ask once — that's by design and there's no global off switch.

### 6. Remove Firefox, keep Developer Edition, freeze its version
```bash
sudo pacman -Rns firefox
```
Developer Edition on Arch doesn't update itself — pacman updates it. So "block updates" means telling pacman to skip it, in `/etc/pacman.conf`:
```
IgnorePkg = firefox-developer-edition
```
Belt and braces, to kill any in-app update attempt, `/usr/lib/firefox-developer-edition/distribution/policies.json`:
```json
{ "policies": { "DisableAppUpdate": true } }
```
Worth knowing: pinning means no security fixes for your main browser. `pacman -Sy firefox-developer-edition` overrides the pin whenever you want it.

### 7. Swap Fn and Control at a low level
Yes — the Apple keyboard driver has a built-in option, so it works everywhere including the console, before X starts:
```bash
echo 'options hid_apple swap_fn_leftctrl=1' | sudo tee /etc/modprobe.d/hid_apple.conf
sudo mkinitcpio -P     # the module loads from the initramfs, so it must be rebuilt
```
Related options in the same driver, for later: `swap_opt_cmd` (Alt ⇄ Cmd) and `iso_layout`. Your Caps plan is a separate layer — Caps→Ctrl or Caps→Escape is done with an XKB option (`setxkbmap -option ctrl:nocaps`, or permanently through `localectl`), and it stacks fine with the Fn/Ctrl swap.

### 8. Fix the function keys (volume, mute)
The keys *are* working at the hardware level — the keycodes exist and map to `XF86AudioMute`, `XF86AudioRaiseVolume`, and so on. **Nothing is listening to them**: your panel has no PulseAudio plugin (it's installed but not added), and no shortcuts are bound.

Two fixes, best done together:
1. Add the **PulseAudio plugin** to the panel — it handles the media keys itself and gives you a volume icon.
2. Bind them explicitly as a fallback, so they work even without the panel:
   ```bash
   XF86AudioRaiseVolume → wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%+
   XF86AudioLowerVolume → wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-
   XF86AudioMute        → wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle
   ```
Also: the driver is on `fnmode=3` (auto). If you'd rather have media keys work *without* holding Fn, set `fnmode=2` in the same `/etc/modprobe.d/hid_apple.conf` from item 7.

### 9. Remove the boot menu when there's only one option
`/boot/loader/loader.conf`: change `timeout 4` to `timeout 0`. systemd-boot then boots straight into Arch, and **holding Space during startup still brings the menu back** — so if you ever add a second entry, it's reachable. (systemd-boot has no "show only if more than one entry" mode; `timeout 0` plus the Space key is how that's done.)

### 10. The ~10 seconds before the boot menu
Measured: **firmware 30.5s**, loader 2.2s, kernel 2.5s, userspace 3.3s — so nearly all of your boot time is Apple's firmware, before Linux gets control at all.

This is a well-known Mac behavior: when the firmware has no *blessed* startup disk recorded in NVRAM, it scans for bootable devices — including network boot — and that scan is the delay. Your ESP already has the fallback path `/EFI/BOOT/BOOTX64.EFI`, which is what keeps it at 30s rather than failing outright.

Options, honestly ranked:
1. **Set the startup disk from macOS Recovery** (⌘R at boot, or Internet Recovery ⌘⌥R) → Startup Disk → pick the EFI volume. This writes the `efi-boot-device` NVRAM entry, which is the real fix. It works even with no macOS installed, though the EFI volume isn't always selectable.
2. **Write `efi-boot-device` from Linux** — the variable exists on your machine and is writable the same way as the chime one, but its value is an Apple-specific XML device path. Getting it wrong means a machine that hunts for a boot device on every start (recoverable by holding Option at boot, but annoying). I'd only try this if option 1 fails, and after backing up the current value.
3. **Accept it.** 30 seconds of firmware is typical for a 2013 Mac running anything but macOS.

### 11. Snapshot space
Right now: **7.2 GB total** for two snapshots (3.9 GB + 3.4 GB) out of 229 GB, with 199 GB free.

How it actually works: Timeshift's rsync mode **hardlinks unchanged files**, so a new snapshot only costs the files that changed since the last one. Your two are unusually far apart (one before and one after installing ~3 GB of apps), so they share less than daily snapshots normally would. Ongoing cost should be a few hundred MB per snapshot.

Controls, in `/etc/timeshift/timeshift.json` or the Timeshift GUI:
- **Retention** — currently 3 daily, 2 weekly, plus on-demand ones which are *never* auto-deleted. Lowering these is the biggest lever.
- **Delete manually:** `sudo timeshift --delete --snapshot '2026-09-16_02-45-29'`
- **Exclude more:** `/var/cache`, `/var/log`, `~/.cache` and `~/Downloads` are already excluded; adding `~/.local/share/Steam` etc. later matters if those get big.
- **Move them off the internal disk:** `--target /dev/sdX` on an external drive, which also makes them useful if the SSD dies (right now a dead SSD takes the snapshots with it).

My suggestion: keep the `clean-start` snapshot, drop `after-setup` once you're happy with the machine, and let the daily schedule handle the rest.

### 12. Ricing and desktop environment
The honest framing: **your bottleneck is the GPU and 8 GB of RAM, not the desktop.** Anything with heavy blur/animation will feel worse than Xfce does, and X11 still beats Wayland for Zoom and OBS screen capture on this hardware.

| Option | Ricing ceiling | Cost on this machine | Verdict |
|---|---|---|---|
| **Xfce (now)** | High — GTK/xfwm themes, panel layouts, conky, rofi, picom effects | Lowest, already stable | **Recommended base.** You've got the dark+sky-blue system already; the remaining ricing is panel layout, a launcher, and subtle compositor effects. |
| **i3 / bspwm (X11 tiling)** | Very high, and a real productivity win for coding | Very light; keeps X11 for Zoom/OBS | **Best next step if you want tiling.** Installs alongside Xfce — pick it at the login screen and switch back any time. |
| **Sway (Wayland tiling)** | Very high | Light, but screen sharing and Zoom go through XWayland | Good, but Wayland adds friction with your proprietary Wi-Fi driver era of hardware and with Zoom. |
| **KDE Plasma 6** | Highest with GUI tools, no config files needed | Heavy for 8 GB + HD 5000 | Only if you want point-and-click ricing more than speed. |
| **Hyprland** | Highest eye-candy | Animations and blur will drag on HD 5000; upstream breaks configs often | **Against your "stable" requirement.** Skip. |

Suggested path: rice Xfce first (panel, launcher, conky, wallpaper, cursor, picom), and **add i3 as a second session** to try tiling without giving up a working desktop. If tiling sticks, migrate the theme over — the GTK theme and fonts carry across unchanged.

---

## Suggested order
1. Quick wins: boot menu timeout, startup sound, function keys, Fn/Ctrl swap, Wi-Fi cleanup, Firefox removal + pin, autologin, Claude trust prompt.
2. Then: snapshot cleanup and retention.
3. Then: the firmware boot delay attempt (item 10, option 1).
4. Last: ricing, once you've decided Xfce vs. adding i3.

Items 3 (logo light) and 10 (firmware delay) are the only two where I can't promise a result.
