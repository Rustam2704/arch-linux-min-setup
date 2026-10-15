# Research E: inspiration and ready-made alternatives (web)
Read `/home/fanatic/ai/claude/setup/tools/audit/common.md` for the context (you do not need to read code
in depth; skim FEATURES.md and ARCHITECTURE.md to know what exists).
Output: `/home/fanatic/ai/claude/setup/research/audit-2026-10-15/e-research.md`.
The owner prefers existing, maintained tools over home-made ones, wants a minimal, fast, dark desktop
with a sky-blue accent (#1ba7e9), Windows-like window handling on i3 (all floating), and cares about
RAM/CPU on an 8 GB, 2-core MacBookPro11,1. Research the web (2024–2026 sources preferred, give links) and
report, per area, what exists, how it compares with our home-made piece, and concrete ideas worth
stealing — each with expected benefit, cost, and risk:
1. Windows-like stacking on top of i3/X11: projects similar to deskd (snap/quarter tiling helpers,
   window buttons, Alt+Tab MRU switchers like `alttab` (sagb), `rofi`, `skippy-xd`), or WMs that give this
   natively at low cost (e.g. xfwm4 + i3-like keys, Openbox, fluxbox, JWM, IceWM, herbstluftwm floating,
   "leftwm"), and whether staying on i3 is still the best base.
2. Panels/indicators with push updates instead of polling: xfce4-panel genmon alternatives
   (i3blocks with signals, i3status-rust, polybar IPC hooks, eww with deflisten, yambar), and the
   cost (RAM/CPU) of each; tricks to make genmon cheaper.
3. Compositing on old Intel: picom vs xcompmgr vs no compositor + TearFree in 2026; picom's
   `--backend xrender/glx/egl`, `unredir`, damage tracking; fork projects (picom-ftlabs etc.).
4. MacBookPro11,1 on Linux in 2025–2026: fan control (mbpfan, macfanctld) — recommended settings for
   lower temps; thermald; powersave; suspend/resume reliability (wl, XHC1/LID0 wakeup, facetimehd,
   bcm5974 "Invalid fake finger state" log spam fixes), backlight, Broadcom Wi-Fi alternatives (brcmfmac
   vs wl for BCM4360), battery calibration.
5. Memory on 8 GB with heavy browser use: zram vs zswap vs swap on SSD, `systemd-oomd`/earlyoom/nohang,
   Firefox memory settings, MGLRU, `vm.swappiness` advice for desktop in 2025–2026.
6. Animated wallpapers / starfields that are cheap on X11 (xwinwrap, xsnow, glslwallpaper, etc.) vs
   our sky-stars approach.
7. Anything else you find in good "i3 / X11 ricing for low-end hardware" write-ups that we do not do yet.
End with a ranked "Top 10 ideas for this machine" (benefit, effort, risk, link).
