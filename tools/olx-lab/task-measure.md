# Task: measure what makes OLX pages heavy in Firefox (olx-lab)

## Goal
The owner keeps 2 OLX pages (search results / an ad page) open in Firefox and they grow to ~4 GB.
We are going to write an OLX-specific blocker. Before that we need hard numbers: which scripts and
requests an OLX page loads, which of them are ads/trackers, and how much memory each group costs.
Images of the listings must stay in full quality, so images are never a block candidate; still
measure them.

## Working root
`/home/fanatic/ai/claude/setup/tools/olx-lab/` — put every file you create here (scripts, venv,
temp profiles under `./work/`). Final report goes to
`/home/fanatic/ai/claude/setup/research/olx/measure.md`, raw data to
`/home/fanatic/ai/claude/setup/research/olx/requests.json`.

## Machine constraints (important)
- 8 GB RAM laptop, the owner's Firefox is running and already uses ~5.4 GB, swap is 12 GB used.
  Run **one** browser at a time, **headless**, inside a memory-capped scope:
  `systemd-run --user --scope -q -p MemoryMax=1300M -p MemorySwapMax=0 <cmd>`.
  If the scope gets OOM-killed, report it and lower the page count rather than raising the cap.
- Never touch the owner's running Firefox, its profile `~/.config/mozilla/firefox/*`, or the screen
  (`DISPLAY=:0`). Use a fresh temporary profile under `./work/`.
- Binary: `/usr/lib/firefox-developer-edition/firefox`, driver `/usr/bin/geckodriver`. Selenium is
  not installed system-wide: `python3 -m venv ./venv && ./venv/bin/pip install selenium`.
- Anonymous browsing only: no login, never click "write to seller", "call", buy, or anything that
  sends data to sellers. Read-only page views and scrolling.

## Pages
Site: `https://www.olx.ua` (Ukrainian OLX). Use
1. a search results page, e.g. `https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/`
2. one ad page opened from that result list (first non-promoted ad).
Record the exact URLs you used.

## What to measure
For each page, in each variant below, run once (repeat a variant only if numbers look noisy):
- **Request inventory**: every request (URL, host, first-/third-party relative to olx.ua,
  resource type, transfer size, decoded size). Use WebDriver BiDi network events or the page's
  `performance.getEntriesByType('resource')` plus navigation entry — your choice, say which.
  Group by host and by type; list every script URL with its decoded size.
- **Memory**: after load + 20 s settle, then after scrolling to the bottom of the page slowly
  (results page: through all results; ad page: through the "similar ads"/recommendation feed
  until it stops growing or 40 scroll steps), then after 3 minutes idle. At each point record the
  content process's PSS/USS from `/proc/<pid>/smaps_rollup` (find the content process hosting the
  tab: the `-isForBrowser` child that grew), and DOM node count
  (`document.getElementsByTagName('*').length`). If you can get Firefox's own breakdown
  (about:memory report via `Services.memreporter` in chrome context, or
  `ChromeUtils.requestProcInfo`), add JS / DOM / images totals; if not, say so and move on.
- **Idle activity**: count requests fired during the 3-minute idle window, grouped by host —
  timers that keep loading ads or beacons are what grows memory over hours.

## Variants (block with BiDi `network.addIntercept` + `failRequest`, or a tiny local
WebExtension with blocking webRequest — your choice, say which)
- A. nothing blocked.
- B. "uBlock medium mode" emulation: all third-party scripts and third-party frames blocked
  (this is what the owner's uBlock does now).
- C. B plus every first-party (olx.ua / olxcdn.com / olx-owned host) request you classify as
  advertising, analytics, tracking, A/B testing or recommendation ads. Image requests of listings
  (`*.olxcdn.com` / apollo image URLs) stay unblocked. List exactly what C blocks.
For C, also check the page still works: listing titles, prices, photos and the gallery on the ad
page render; the "show phone"/chat button is present (do not click it).

## Also find out
- How listing photos are addressed (URL pattern, the size parameter, e.g. `;s=WxH`), and the
  largest size the gallery requests. Download one image at the largest size you can find with
  curl and report its pixel size, so we know what "full quality" is.

## Do not
- Do not install anything system-wide, do not use sudo, do not edit files outside the working
  root and the two output files.
- Do not run more than one Firefox at once, do not raise the memory cap above 1300M.
- Do not log in, do not contact sellers.

## Final report (in `measure.md`, English, and as your final message)
1. Pages and URLs used, method used for requests and for memory.
2. Table per page × variant: requests, scripts count, script bytes, image bytes, PSS after load /
   after scroll / after idle, DOM nodes, idle requests.
3. Top 30 hosts/URLs by script bytes for variant B (what survives the owner's current uBlock),
   each classified: core-site / ads / analytics / tracking / A-B testing / recommendations /
   chat / unknown.
4. Exact blocking list used in C, and what (if anything) broke.
5. Image URL pattern and the full-quality size.
6. Anything surprising (service workers, websockets, polling, memory that keeps growing idle).
