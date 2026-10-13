# Task: with the owner's uBlock Origin, OLX listing photos do not load — find the rule

## Goal
In the owner's Firefox, on www.olx.ua, photos (search results and ad galleries) do not load; with
uBlock Origin disabled for the site they do. In phase 1 your BiDi emulation of "3p scripts and
frames blocked" loaded photos fine, so the cause is something else in the real uBlock: a static
filter, a cosmetic/scriptlet filter, or the dynamic rules. Reproduce it with the owner's real uBlock
and name the exact filter(s) / rule(s) responsible.

## Working root
`/home/fanatic/ai/claude/setup/tools/olx-lab/` (reuse `olxlab.py`, venv, `./work/`).
Report: `/home/fanatic/ai/claude/setup/research/olx/images.md`.

## How to reproduce the owner's uBlock exactly
- Fresh temp profile in `./work/ubo-profile/`. Install uBlock from a COPY of
  `~/.config/mozilla/firefox/ay102hg5.dev-edition-default/extensions/uBlock0@raymondhill.net.xpi`
  (Selenium `install_addon(path, temporary=True)` or put it in the temp profile's `extensions/`).
- Give it the owner's storage: in the owner's profile, uBlock's uuid is
  `45088fc6-40f9-465a-bd1d-d4cbfaa89521` (`extensions.webextensions.uuids` in prefs.js). Copy (rsync,
  read-only on the source) the folders
  `storage/default/moz-extension+++45088fc6-40f9-465a-bd1d-d4cbfaa89521^userContextId=4294967295/`
  and `storage/default/moz-extension+++45088fc6-40f9-465a-bd1d-d4cbfaa89521/` into the temp
  profile, and set `extensions.webextensions.uuids` in the temp profile's user.js so uBlock gets the
  same uuid. If that mapping does not take, fall back to: let uBlock start clean, then in its
  dashboard (moz-extension://<uuid>/dashboard.html) select the owner's lists — user-filters,
  ublock-filters, ublock-badware, ublock-privacy, ublock-unbreak, ublock-quick-fixes, easylist,
  easyprivacy, urlhaus-1, plowe-0 — wait for them to update, and put these into "My rules" and
  commit: `* * 3p-script block`, `* * 3p-frame block`,
  `www.youtube.com google.com * noop`, `www.youtube.com doubleclick.net * noop`.
  Say which way worked.
- Owner's Firefox is running; copying its storage while it runs is acceptable (read only).

## Steps
1. With that uBlock, open `https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/` and one
   ad page from it. Record: do photos render (`img.complete && naturalWidth>0` on the listing
   photos, and screenshot the page to `./work/shot-ubo.png`), which image URLs are requested and
   their status, and the console errors.
2. Open uBlock's logger (`moz-extension://<uuid>/logger-ui.html`, in a second tab, before loading
   OLX) and capture every blocked / modified / cosmetic / scriptlet entry for olx.ua. Save them in
   the report.
3. Bisect to the cause: disable groups and retest — dynamic rules off (no 3p-script/3p-frame block);
   each filter list off in turn; cosmetic filtering off; then narrow to the single filter. Confirm
   by re-enabling only that filter.
4. Check also: do photos render with uBlock on, if the page is only waiting for scroll/lazy-load
   (scroll slowly through the page)?
5. Find the minimal fix that keeps ads and trackers blocked: e.g. an `@@` exception, a
   `#@#` cosmetic exception, a `#@#+js()` scriptlet exception, or a `www.olx.ua <host> * noop`
   dynamic rule. Verify photos render with the fix and that Baxter/GPT ad scripts stay blocked.
   Then also test the fix together with our list `/home/fanatic/ai/claude/setup/assets/browser/ublock-olx.txt`
   (paste its lines into My filters in the lab uBlock) — photos must render, ads stay off.

## Constraints
One headless Firefox at a time inside
`systemd-run --user --scope -q -p MemoryMax=1300M -p MemorySwapMax=0`. Check MemAvailable first
(wait while below 900 MB). Anonymous, no login, no contacting sellers. Never write into the owner's
profile, never touch the owner's Firefox or screen. Keep it short: no long idle measurements.
Quit Firefox and geckodriver when done (kill by PID, never `pkill -f` with a pattern).

## Final report (images.md, English, and as your final message)
1. How uBlock was reproduced (storage copy or dashboard) and whether photos failed like the owner's.
2. The logger entries for olx.ua (blocked/modified/cosmetic/scriptlet).
3. The responsible filter(s)/rule(s), exact text and list name, and how you confirmed it.
4. The minimal fix, exact lines, and the verification (photos ok, ad scripts still blocked).
