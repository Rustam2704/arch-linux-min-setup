# The 30-second firmware delay — diagnosis and options

## Measurement
```
Startup finished in 30.498s (firmware) + 2.162s (loader) + 2.480s (kernel) + 3.312s (userspace)
```
Linux boots in about 8 seconds. **The other 30 seconds are Apple's firmware, before any bootloader runs.**

## Cause — found it

Your Mac's NVRAM still believes it should boot **a macOS install that no longer exists**. From `efibootmgr -v`:

```
BootCurrent: 0000            <- what actually booted (the fallback path; no such entry is stored)
BootOrder:   0080            <- what the firmware tries FIRST
Boot0080* Mac OS X   ...Sata(0,0,0)/HD(2,GPT,8e5e3e3d-…)/VenMedia(…)/\601E3FB0-…\System\Library\CoreServices\boot.efi
Boot0081* Mac OS X   ...\4555B31A-…\System\Library\CoreServices\boot.efi
Boot0082*            ...\601E3FB0-…\System\Library\CoreServices\boot.efi
BootFFFF*            ...\System\Library\CoreServices\boot.efi
```

And Apple's own startup-disk variable, `efi-boot-device`, agrees:

```xml
<array><dict><key>IOMatch</key><dict>…<key>UUID</key><string>E7C37FCE-4476-461C-9A94-2050A2E6B6D4</string></dict>
<key>BLLastBSDName</key><string>disk1s2</string></dict>
<dict><key>IOEFIDevicePathType</key><string>MediaFilePath</string>
<key>Path</key><string>\601E3FB0-…\System\Library\CoreServices\boot.efi</string></dict></array>
```

Those entries point at a CoreStorage/HFS+ macOS volume — partition GUID `8e5e3e3d-…`, "disk1s2". Your disk today is just `sda1` (1 GB EFI) + `sda2` (ext4). That volume was wiped when Arch was installed, but **nothing cleaned up NVRAM**.

So every cold boot goes: try `Boot0080` → not there → keep searching (including other buses and network boot) → time out → finally fall back to the generic path `\EFI\BOOT\BOOTX64.EFI` on your ESP, which is systemd-boot. There is no Boot entry for systemd-boot at all — it is only ever reached as the last-resort fallback.

This matches the documented behavior: Intel Macs store boot targets in NVRAM, and when the firmware tries to load a nonexistent target it waits before giving up and scanning for other loaders.

## Options

### A. Add a real boot entry for systemd-boot and reorder (recommended first step)
```bash
sudo efibootmgr -c -d /dev/sda -p 1 -l '\EFI\systemd\systemd-bootx64.efi' -L "Arch Linux"
sudo efibootmgr -o 0000,0080          # new entry first (use the number it prints)
```
- **Risk: very low.** The fallback `\EFI\BOOT\BOOTX64.EFI` stays exactly where it is, so even if the firmware ignores the new entry, the machine boots as it does today.
- **Expected gain: partial.** Someone who did exactly this on an Intel Mac went from ~30s to ~22s — the firmware still burns time on the dead entry before reaching the new one.
- Undo: `sudo efibootmgr -b 0000 -B` and set the order back.

### B. Delete the four dead macOS entries as well
```bash
sudo efibootmgr -b 0080 -B; sudo efibootmgr -b 0081 -B; sudo efibootmgr -b 0082 -B
```
- **Risk: low, with a caveat.** These point to a volume that no longer exists, so nothing usable is lost. Apple firmware sometimes recreates entries; if the machine ends up with no valid entry at all, it still finds the fallback path, and holding **Option** at power-on always gives you the manual boot picker.
- **Expected gain: this is where the real saving should be**, since it removes what the firmware is waiting on. Doing A and B together is the highest-value low-risk combination.
- Undo: not directly — but the entries are worthless (they point at a deleted volume), and a NVRAM reset (⌘⌥P+R at power-on) restores factory defaults.

### C. Rewrite Apple's own `efi-boot-device` variable
This is what macOS's "Startup Disk" preference writes, and Apple's firmware trusts it over the standard UEFI variables. It is an Apple-specific XML blob plus a matching binary device path in `efi-boot-device-data`, and it must describe your ESP and `\EFI\systemd\systemd-bootx64.efi` exactly.
- **Risk: medium.** A malformed value means the firmware hunts for a boot device on every start. Recoverable by holding Option at boot, or a NVRAM reset, but it's the fiddliest option.
- I'd only do this if A+B don't help, and I'd back up both variables first.

### D. macOS Recovery → Startup Disk
Hold ⌘R (or ⌘⌥R for Internet Recovery) at power-on, then Startup Disk → pick "EFI Boot" → restart. This writes both the UEFI entries and Apple's variables the official way.
- **Risk: none to the installed system.** It's the cleanest fix when it works.
- **Caveat:** with no macOS on the disk, Recovery has to come over the network (slow, needs Wi-Fi at the firmware level), and the EFI volume isn't always offered in the Startup Disk list.

### E. One cheap experiment, independent of the above
```bash
sudo efibootmgr -t 0      # firmware boot-manager timeout, currently 5 seconds
```
Apple's firmware may ignore it, but it costs nothing to try and is undone with `-t 5`.

### F. Do nothing
30 seconds of firmware is normal for a 2013 Mac running anything but macOS. It costs you only on a cold boot — suspend/resume is unaffected.

## My recommendation
Do **A + B together** (add the Arch entry, delete the three dead Mac OS X entries), and E while we're there. Low risk, reversible in the ways described, and it targets exactly what the firmware is stalling on. If that gets it under ~10 seconds, stop there. If it barely moves, the remaining time is the firmware's device scan and only C or D can touch it.

## Sources
- `efibootmgr -v` and `/sys/firmware/efi/efivars/efi-boot-device-*` on this machine, 2026-09-16
- [Fixing a Long EFI Boot Delay on an Intel Mac Pro Running FreeBSD](https://eldapper.wordpress.com/2025/11/30/fixing-a-long-efi-boot-delay-on-an-intel-mac-pro-running-freebsd/) — stale `Boot0080* Mac OS X` entry, 30s → 22s after adding an entry and reordering
- [Arch forums: MacBook Pro waits 30 seconds white screen before GRUB](https://bbs.archlinux.org/viewtopic.php?id=138915) — the fallback `\EFI\BOOT\BOOTX64.EFI` path behavior
- [rEFInd documentation: Mac boot delays](https://www.rodsbooks.com/refind/installing.html) — blessing, `--shortform`, ESP vs HFS+, "true causes remain mysterious"
- [joevt: macOS nvram boot variables and EFI device paths](https://gist.github.com/joevt/477fe842d16095c2bfd839e2ab4794ff) — `efi-boot-device` XML/`-data` format
