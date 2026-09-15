# System scan — whitebook (2026-09-16)

**Machine:** MacBook Pro 11,1 (Retina 13", Late 2013) · i5-4278U Haswell · 8 GB RAM · Apple 256 GB SATA SSD
**OS:** Arch Linux · kernel `linux-lts` 6.18.51 · systemd-boot · Xfce 4.20 on Xorg · LightDM · NetworkManager · PipeWire

## Critical / broken
| # | Area | Finding |
|---|------|---------|
| 1 | Packages | `/var/lib/pacman/sync` is empty (no `core`/`extra` databases), so pacman can't see updates. **12 updates pending**, including kernel 6.18.52, linux-firmware, and tzdata. |
| 2 | Wi-Fi (BCM4360) | Uses proprietary `broadcom-wl-dkms`. It's unmaintained and throws kernel WARNs at boot ("Unpatched return thunk" and a field-spanning memcpy in `wl_cfg80211_hybrid.c`). It also taints the kernel and weakens Spectre mitigations. |
| 3 | Camera | FaceTime HD camera (14e4:1570) has **no driver**, so there's no `/dev/video*`. |
| 4 | Clock | NTP is inactive and the clock isn't synchronized (`systemd-timesyncd` is disabled). |

## Missing drivers / firmware / system components
| # | Finding |
|---|---------|
| 5 | `wireless-regdb` is missing (kernel: `regulatory.db` load failed), so Wi-Fi runs on the world regulatory domain with limited channels and power. |
| 6 | No fan-control daemon (`mbpfan`). `applesmc` is loaded, but the fan stays on SMC defaults. |
| 7 | `rtkit` is missing, so PipeWire and WirePlumber can't get realtime priority (repeated journal errors). |
| 8 | `vulkan-intel` is missing, so there's no Vulkan driver for Haswell. VA-API via `libva-intel-driver` is present and is the correct driver. |
| 9 | Tumbler thumbnail plugins are missing libraries: poppler-glib, ffmpegthumbnailer, libgsf, libgepub, libopenraw. |
| 10 | zswap is enabled **and** zram swap is active. That double-compresses and is not recommended. |

## Configuration gaps
| # | Finding |
|---|---------|
| 11 | Firewall: `ufw` is installed but inactive. |
| 12 | Mirrors: the list is unsorted (AU, AL and AR mirrors near the top while you're in Kyiv), and `reflector.timer` is disabled. |
| 13 | pacman: no AUR helper, `Color` is off, no package cache cleanup (`pacman-contrib`/paccache is missing). |
| 14 | No system snapshots or backups on ext4 (no timeshift, snapper or similar). |
| 15 | Both `iwd` and `wpa_supplicant` are installed; NetworkManager uses wpa_supplicant, so iwd is unused. |
| 16 | No hibernation (swap is zram only), and TLP runs on stock config. |

## Software (dev / AI tooling)
| # | Finding |
|---|---------|
| 17 | Present: git, python 3.14, gcc 16, Claude Code 2.1.273, Codex CLI 0.154.0. |
| 18 | Missing: node/npm/bun, uv/pipx/pip, docker/podman, gh, go, rust, neovim, tmux, zsh/fish, ollama, VS Code. |

## Hardware health (informational)
| Item | Status |
|------|--------|
| Battery | **68% of design capacity** (48.9 of 71.8 Wh), 1201 cycles. Worn. |
| SSD | SMART PASSED, 0 reallocated or pending sectors, 14,170 power-on hours. Healthy. |
| Thermals | CPU 53 °C at idle, fan 1300 RPM. OK. |
| Firmware | Apple EFI 478.0.0.0.0 (2023-01). Updatable only through macOS; fwupd doesn't support it. |
| CPU microcode | 0x26 (latest for Haswell-ULT). OK. |
| Works fine | Bluetooth (BCM20702), keyboard backlight (`smc::kbd_backlight`), trackpad (bcm5974), audio (CS4208), Thunderbolt 2, TRIM (`fstrim.timer`). |
