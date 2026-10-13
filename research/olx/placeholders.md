# OLX grey photo placeholders: lab result (2026-10-13)

URL: https://www.olx.ua/uk/elektronika/telefony-i-aksesuary/q-iphone/ (anonymous, headless Firefox Developer Edition, 1280x1000).
Script: `tools/olx-lab/work/policy-test/lab.py` (raw data `lab-v0.json`, `lab-v1.json`, `lab-v2.json`, `lab-v2fast.json`; screenshots `v0.png`, `v1.png`, `v2.png`, `*-rescroll.png`, `v2fast-0.png`, `v2fast-30.png`).
Each variant used a fresh profile copy. Owner's uBlock = read-only copy of the xpi and both storage dirs.
- V0: uBlock not installed at all (plain profile, plain binary).
- V1: owner's uBlock as is, plain `/usr/lib/firefox-developer-edition/firefox` (no policy). My filters had no OLX lines.
- V2: owner's uBlock + our policies.json in a copy of the browser (My filters showed the OLX lines on the 2nd start).
Method: load, wait 10 s, scroll 400 px / 700 ms to the bottom, sample at +5/+15/+30 s, scroll to top and down again, +5 s, recount.

## Cards with a loaded photo (naturalWidth > 0) / total cards

| Variant | after load, no scroll | bottom +5 s | +15 s | +30 s | after re-scroll |
|---|---|---|---|---|---|
| V0 no uBlock | 5/51 | 51/51 | 51/51 | 51/51 | 51/51 |
| V1 owner's uBlock | 5/51 | 51/51 | 51/51 | 51/51 | 51/51 |
| V2 uBlock + policy | 5/51 | 51/51 | 51/51 | 51/51 | 51/51 |
| V2 fast scroll (14 x ~600 px / 0.8 s, then no scrolling) | - | 51/51 (+0 s: 50/51) | 51/51 | 51/51 | - |

All 51 Apollo image requests returned HTTP 200 in every variant. Page height 9.8-10.2k px, 51 cards.

## Cards that stay placeholders

None, in any variant. So the V0 URL / fate comparison is empty: no card was a placeholder in V1/V2 and loaded in V0.
(Same-listing check: 37 of 51 hrefs repeat between V0 and V1/V2, the rest are new results; all of V0's 37 photo URLs were requested in V1/V2 too.)

## What the grey boxes are

Every card starts with `<img src="/app/static/media/no_thumbnail.*.svg">` (OLX's own grey placeholder; 46 of 51 cards at load). OLX's React code swaps in the Apollo photo
only when the card scrolls into the viewport. It is not an adblock block, not a failed request: the real photo is simply never requested before the card is near the viewport.
The earlier `search.png` showed "Запчастини iphone 6s", "Чохол Pitaka...", "перехідник..." grey because that run scrolled 14 steps, took the screenshot at once, and stopped mid-page;
the cards in view were still mid-swap. In the fast-scroll rerun the last entered card ("Iphone 16 pro 256gb") was grey at +0 s and loaded by +5 s without any further scrolling.

## uBlock logger (V1, V2): blocked requests and cosmetic hits

Blocked (all `* * 3p-script block`, the owner's global dynamic rule, none relate to photos): `js.appboycdn.com/web-sdk/5.6/service-worker.js`, `ninja.data.olxcdn.com/ninja-cee.js`,
`js-agent.newrelic.com/nr-spa-1.249.0.min.js` (x2), `cdn.slots.baxter.olx.org/olxua/rweb/release/init.min.js` (x2), `static.hotjar.com/c/hotjar-2218922.js`.
Cosmetic/scriptlet: `##+js(prevent-clipboard-write, ...)` x2, `##div[id^="div-gpt-"]...`, `##[id^="div-gpt-ad"]...` (uBlock filters - Ads). V2 adds `##div[data-testid="qa-advert-slot"]` (our policy line).
Nothing on `apollo.olxcdn.com`, no OLX `/app/static` chunk blocked. In V2 Baxter `init.css` was also blocked (CORS error). uBlock's own list update fetch (`ublock-quick-fixes` patch) also appears.

## Console errors

- V0 (17 entries): CSP media-src block on a data:video, `[Ninja] GtmTracker` / `BrazeTracker` init errors, cookies rejected for invalid domain (`_tt_enable_cookie`, `cto_bundle`, `sa-user-id`).
- V1 (48 entries) / V2 (50): CORS-blocked `baxter .../init.min.js` (V2 also `init.css`), CORS-blocked `newrelic nr-spa-1.249.0.min.js` and its sha512 integrity mismatch. No chunk-load error, no Apollo image error.
- Network: V0 935 requests (ads load), V1 183, V2 190; no `fetch_error` events in any variant.

## Screenshots

`v0.png`/`v1.png`/`v2.png` (bottom at +30 s) show only the footer, SEO links and cookie banner, no cards. The photo area is visible in `v2fast-0.png` (photos loaded, bottom card grey) and `v2fast-30.png`.

## Conclusion

The lab does not reproduce permanent placeholders with the owner's uBlock, with or without our policy. The grey boxes are OLX's lazy-load placeholders, replaced on viewport entry.
Not tested (cannot be copied into a headless lab): the owner's live Firefox state (other extensions such as Violentmonkey were checked earlier with no effect, see images.md), prefs such as
resistFingerprinting or `dom.IntersectionObserver`, hardware acceleration or a slow link. Next step if the owner still sees it: ask for `about:support` extensions/prefs list and a console
log from their own browser on this page.
