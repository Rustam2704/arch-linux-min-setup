# Task: CPU / RAM / SWAP panel icons filled with the battery's segment rainbow

## What the owner asked (translated)
"CPU, RAM and swap icons: make them fill with the rainbow from our palette (the same as on the
battery) and also in segments. But inverted to the battery: the maximum fill must use the red
segment. The segments should shine through the icon (or find another cheap way). Swap and CPU fill
bottom-up; RAM fills left-to-right."

## Read first (project context — keep its decisions)
Setup project `/home/fanatic/ai/claude/setup`: ARCHITECTURE.md section "Панель Xfce" (gaps 15 px,
nothing may shift when a reading changes, genmon `<img>` rules, refresh via D-Bus `xfpanel.refresh`
not `xfce4-panel --plugin-event`, panel restart order `xfce4-panel -q` → xfconf → start via i3,
genmon font/period read only at plugin start), FEATURES.md panel section, CHANGELOG entries about
panel-sys / panel-battery / netqd / "Периоды опроса панели". Sources:
- `desktop/bin/panel-battery` — the battery SVG: 4 segments, colours top→bottom
  `THEME["light"]`, `THEME["success"]`, `THEME["warning"]`, `THEME["danger"]`, lit from the bottom,
  unlit `#23404a`; written to $XDG_RUNTIME_DIR only when changed; canvas 54x44, viewBox with a
  leading empty strip for the gap.
- `desktop/bin/panel-sys` — current CPU/RAM/SWAP genmon (one plugin, id 42, Python every 2 s ≈ 2.9 %
  of a core). Icons are Nerd Font glyphs from `desktop/share/sky-desktop/theme.json` "icons"
  (cpu, memory, swap) in `THEME["muted"]`, font "JetBrainsMono Nerd Font Propo"
  (`/usr/share/fonts/TTF/JetBrainsMonoNerdFontPropo-Regular.ttf`). Numbers: two digits CPU/RAM
  ("00" for 100), swap one digit in GB, red from 10 GB (10+ rolls to 0-6), swap hidden when < 64 MB
  used; colours of numbers by level; transparent-zero padding; tooltip text. KEEP all of that.
- `desktop/bin/netqd` — pattern for a daemon that writes panel files + SVG and calls
  `xfpanel.refresh(...)` only on change; genmon just `cat`s a file.
- `desktop/xfconf/xfce4-panel.xml` (plugin-42 and the plugin order), `desktop/share/deskd/panels.py`
  (`SKIP_ON_NARROW` has "panel-sys"; secondary-monitor panels are built from this), how services are
  declared (see `desktop/systemd/` or wherever `netqd`/`sky-stars` units live) and how `tools/desktop.py`
  installs files.

## Design (implement this)
1. **Icons:** for each of cpu / memory / swap take the glyph outline from the font (fontTools, pen →
   SVG path; do it at build/start time, not per frame) and use it as an SVG `clipPath`. Inside it draw
   4 segments with small gaps between them (so they read as segments, like the battery):
   - CPU and SWAP: horizontal bands, filled bottom→top; colours bottom→top `light`, `success`,
     `warning`, `danger` (inverted battery: full = red on top).
   - RAM: vertical bands, filled left→right, colours left→right the same order.
   - Lit segments = `max(1, ceil(pct/25))`; unlit segments in `THEME["muted"]` (today's icon colour),
     so an idle icon looks like today's.
   - SWAP level = used / SwapTotal. CPU = load since previous sample. RAM = the current mem_pct.
   - The glyph must fill the image height the way the battery does (genmon shows ~32 px); same canvas
     for every level so nothing shifts. Match the visual size of today's glyph icons in the panel.
   If clipping a glyph looks bad at panel size (thin strokes, unreadable), say so and propose the
   cheapest alternative, with preview images.
2. **Cheap updates:** a small daemon `sysqd` (Python, like netqd; or extend netqd only if clearly
   simpler — say which) samples every 2 s, writes per indicator a markup text file and an SVG into
   $XDG_RUNTIME_DIR **only when changed**, and calls `xfpanel.refresh(<plugin command>)` only then.
   Three genmon plugins: keep id 42 for CPU, add two new ids for RAM and SWAP right after it in the
   panel order; their commands just print the ready file (cheapest possible: e.g. `cat`, or a
   tiny `sh` one-liner printing `<img>` + the text file); update period long (60000 ms) since the
   daemon pushes. Systemd user unit for the daemon like the others, started in the session the same way.
   Update `SKIP_ON_NARROW` for the new commands.
3. **Spacing:** the gaps between CPU / RAM / SWAP groups and to the neighbours must stay what they are
   today (measure today's gaps on a screenshot crop of the real panel — read-only screenshot of :0's
   top 66 px is allowed; do not move anything). With swap hidden, no empty gap may remain.

## Previews (before integration)
Render PNGs at 4x of each icon at levels 1-4 (and 0 % CPU) on the panel background colour to
`/home/fanatic/ai/claude/setup/tools/sysicons/preview/`, plus one sheet `preview/sheet.png`
showing all of them side by side next to today's glyph and the battery icon (rsvg-convert or cairosvg).

## Integration
Edit sources in the setup project only (`desktop/...`, `packages.txt` if a new package is needed —
avoid new packages). Add/adjust tests if the project has relevant ones (`make test` must pass).
Do NOT run `make apply`, do NOT restart the panel or any live service, do NOT edit ~/.local or ~/.config,
do NOT commit. Never `pkill -f`/`pgrep -f`.

## Final message (English, under 40 lines)
Files changed/added, how the icon is built, the preview paths, measured CPU of the daemon over 60 s
(run it on a test copy writing into a temp dir with refresh disabled), the exact apply steps the
coordinator must run (panel restart order), risks.
