# Task: make the new CPU/RAM/SWAP panel plugins keep the old spacing

Your previous task (`task.md` here) split panel-sys into three genmon plugins (42 cpu, 63 ram, 64 swap)
fed by `sysqd`. It is applied and live. Compare (both are crops x=1300..2560, y=0..66 of the real panel):
- before: `/home/fanatic/ai/claude/setup/tools/sysicons/preview/panel_before.png` (one plugin; glyph icons)
- after:  `/home/fanatic/ai/claude/setup/tools/sysicons/preview/panel_after2.png`
In "after" the gaps ping-text → CPU icon, CPU number → RAM icon, RAM number → SWAP icon are much wider
than in "before" (measure them in pixels from the images: columns of non-background pixels); the
icon→number gap looks right. Also the icons look a bit bigger than the old glyphs — measure the old
glyph's ink height/width vs the new icon's and match them (same ink box as the old glyph).

Fix in the setup sources (`desktop/bin/panel-sys|panel-ram|panel-swap`, `desktop/share/sky-desktop/sysicons.py`,
`desktop/bin/sysqd`, genmon `<css>` paddings): the gaps between groups and to the neighbours must equal
the "before" values ±1 px, and with swap hidden no extra gap may remain. Use the SVG viewBox empty
strip and the genmon button css (`padding`/`margin`) as the project already does (ARCHITECTURE.md
"Панель Xfce": standard gap rules). Read what xfce4-panel adds between plugins (the panel's own
plugin spacing) — you can read the live xfconf (`xfconf-query -c xfce4-panel -lv`, read-only).

Verify: render the three plugins' output into an offscreen GTK test (or compute from the SVG + font
metrics) — and then the coordinator will restart the panel; give the coordinator the exact commands.
Do NOT restart the panel or services, do NOT `make apply`, no commit. `make test` must pass.
Final message (under 25 lines): measured gaps before/after-fix (expected), what changed, apply commands.
