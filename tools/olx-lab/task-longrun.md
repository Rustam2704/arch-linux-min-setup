# Task: what makes an OLX tab grow over an hour (olx-lab, phase 2)

## Goal
Phase 1 (`research/olx/measure.md`, `requests.json`) showed a fresh OLX search page takes only
~250 MB PSS whatever is blocked. The owner's 2 OLX tabs reach ~4 GB after hours of use. Find
which usage pattern grows the tab and whether our blocker list or the owner's extensions change
it. Reuse and extend your phase-1 tool `tools/olx-lab/olxlab.py`.

## Working root
`/home/fanatic/ai/claude/setup/tools/olx-lab/` (scripts, temp profiles in `./work/`).
Outputs: `/home/fanatic/ai/claude/setup/research/olx/longrun.md` (report) and
`/home/fanatic/ai/claude/setup/research/olx/longrun.json` (all samples).

## Same constraints as phase 1
One headless Firefox at a time, `systemd-run --user --scope -q -p MemoryMax=1300M
-p MemorySwapMax=0`; fresh temporary profiles under `./work/`; never touch the owner's Firefox,
profile or screen; anonymous only (no login, no chat, never contact sellers). If the scope is
OOM-killed, that is a result: record the time and the last sample, then go on to the next scenario.
Before each scenario check `MemAvailable` in /proc/meminfo; if it is below 900 MB wait (up to
10 min, polling every 30 s) and log the wait.

## Sampling (every scenario)
Every 30 s: PSS, USS and Swap of the content process hosting the OLX tab (`smaps_rollup`), the
sum over all content processes, DOM node count, `performance.getEntriesByType('resource').length`,
number of requests seen since the previous sample grouped by host. Also at start, at minute 20
and at the end: Firefox's own memory breakdown if you can get it (about:memory report via
chrome-context `Services.memreporter` / `ChromeUtils` — JS, DOM, images, other); if it cannot be
obtained, say so.

## Scenarios (each ~40 min: ~30 min of browsing, then 10 min idle; same seed URLs for all)
Search page: `https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/`.
- **S1 in-tab browsing (how a person uses it):** in one tab: on the results page click an ad card
  (a real click on the card link, same tab — OLX is a single-page app, so this is client-side
  navigation), wait 6 s, open the photo gallery and click "next" through up to 6 photos, close it,
  scroll the ad page to the bottom (similar/recommended ads load there), wait 4 s, go back with
  the browser Back, scroll the results a bit further, open the next ad. After the first page of
  results is used up, go to page 2, 3 ... by clicking the pager. ~25 ads total.
- **S2 hard navigation:** the same ad URLs in the same order, but every page is a full load
  (`driver.get(url)` for the ad and for the results page), same gallery/scroll actions.
- **S3 S1 + blocker:** S1 with the blocking list
  the OLX filters in `/home/fanatic/ai/claude/setup/desktop/system/usr/lib/firefox-developer-edition/distribution/policies.json` (3rdparty → uBlock0 → toOverwrite.filters) emulated: block requests matching
  its network rules (`||host^` = that host and its subdomains; `/path` = substring; `$domain=` =
  only when the page is that site; `@@` = exception), and inject its `##` cosmetic selectors as a
  `display:none !important` style. Also emulate the owner's uBlock medium mode as in phase-1
  variant B (all third-party scripts and frames blocked).
- **S4 S1 + owner's extensions:** S1 with uBlock-medium emulation (like S3 but without our list)
  plus the owner's Dark Reader and Violentmonkey installed as temporary add-ons from copies of
  `~/.config/mozilla/firefox/ay102hg5.dev-edition-default/extensions/addon@darkreader.org.xpi`
  and the Violentmonkey xpi (find which xpi in that folder is Violentmonkey by its manifest name;
  copy, never modify the originals). In Violentmonkey install
  `/home/fanatic/ai/claude/setup/assets/browser/light-images-hover.user.js` with its two
  `@exclude` lines for OLX **removed** (that is the version the owner runs now; do not edit the
  file in place — use a copy in `./work/`). Dark Reader with default settings (on for all sites).
  If installing userscripts into Violentmonkey automatically is not possible, inject the copy's
  code with `execute_script` after each navigation and say so.
- **S5 S4 with the OLX excludes:** Dark Reader on, light-images-hover not running on OLX
  (the shipped file as is), uBlock-medium emulation plus our list. This is the configuration the
  owner gets after our change.
Run order: S1, S2, S3, S4, S5.

## Also report
- For S1 vs S2: MB of growth per ad viewed; whether memory is released when the tab goes back
  to the results page; whether growth is in JS heap, DOM, images or other.
- Whether any scenario keeps growing during the 10-minute idle window, and which hosts were
  being contacted then.
- Anything in S3/S5 that broke on the page (photos, gallery, prices, "show phone" button present
  — do not click it, pagination).

## Do not
- No sudo, no system-wide installs, no edits outside the working root and the two output files.
- Do not change `assets/browser/*.txt` or `*.user.js` in place.
- No login, no contacting sellers, no more than one Firefox at once, no cap above 1300M.

## Final report (in `longrun.md`, English, and as your final message)
1. Method (how navigation, blocking, extensions were done; anything emulated or skipped).
2. Table per scenario: PSS at start / minute 10 / 20 / 30 / end of idle, peak, MB per ad, OOM yes/no.
3. Breakdown (JS/DOM/images/other) where obtained.
4. Idle-window activity per scenario.
5. Breakage found in S3/S5.
6. Your conclusion in 5 lines: what makes the tab grow, and what cut it.
