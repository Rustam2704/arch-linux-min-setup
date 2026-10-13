# Owner's Firefox state relevant to OLX (read-only inventory, 2026-10-13)

Profile: /home/fanatic/.config/mozilla/firefox/ay102hg5.dev-edition-default/ (Firefox Developer Edition). All sqlite/IDB files were copied to
/tmp/claude-1000/-home-fanatic/614f9629-afe8-4732-8a6d-898c41e15ffb/scratchpad/olx-state/ and read there. Nothing in the profile was modified.
Decoding: IDB keys are byte-shifted by +1; values are snappy blocks (own pure-Python decoder, scratchpad/snap.py + ex.py; no pip needed).
Note: uBO settings live in the `moz-extension+++45088fc6-...^userContextId=4294967295` IDB (browser.storage.local), not in the plain `moz-extension+++45088fc6-...` one (that one only holds uBO's own asset cache, an older state).

## 1. uBlock Origin (v1.75.0), uuid 45088fc6-40f9-465a-bd1d-d4cbfaa89521

Selected filter lists (`selectedFilterLists`): user-filters, ublock-filters, ublock-badware, ublock-privacy, ublock-unbreak, ublock-quick-fixes, easylist, easyprivacy, urlhaus-1, plowe-0.
(No regional/Ukrainian/Polish list, no annoyances list.)

Dynamic rules (`dynamicFilteringString`), exactly:
```
behind-the-scene * * noop
behind-the-scene * inline-script noop
behind-the-scene * 1p-script noop
behind-the-scene * 3p-script noop
behind-the-scene * 3p-frame noop
behind-the-scene * image noop
behind-the-scene * 3p noop
* * 3p-script block
* * 3p-frame block
www.youtube.com google.com * noop
www.youtube.com doubleclick.net * noop
```
=> "medium mode": all third-party scripts and third-party frames are blocked on every site, including OLX (except as allowed by static lists / noop). This is the most likely cause of OLX third-party breakage (e.g. login.olx.*, pay/payment widgets, image CDNs are not scripts, so images are unaffected).

Hostname switches (`hostnameSwitchesString`):
```
no-large-media: behind-the-scene false
no-csp-reports: * true
```

My filters (`user-filters`):
```
! Sep 28, 2026 https://www.edclub.com
www.edclub.com###adslot_results1
! Sep 29, 2026 https://www.edclub.com
www.edclub.com###adslot_results2 > .disable-ads-banner
```

Trusted sites / whitelist (`netWhitelist`):
```
127.0.0.1
chrome-extension-scheme
moz-extension-scheme
www.google.com.ua
```
Any rule mentioning olx: NONE (grepped decoded settings, user filters, dynamic rules, and the older IDB backup at ~/.cache/yt-lab/ublock-backup; zero "olx" hits outside compiled filter-list caches, which were not enumerated). OLX is neither whitelisted nor has a switch override; only the static lists and the medium-mode 3p-script/3p-frame block apply.
Other keys: importedLists empty; requestStats exist; backup copy has the same shape (older, 1462-byte cache registry).

## 2. OLX visits (places.sqlite, moz_places url LIKE '%olx.%')

Domain, summed visit_count, distinct URLs:
```
www.olx.ua            1550   952
www.olx.pl             268   190
help.olx.ua             18    14
m.olx.pl                13    11
login.olx.ua             6     6
payments.olx.com         5     5
login.olx.pl             5     5
techhub.olx.ua           4     2
pl-idp.login.olx.com     2     2
ua-idp.login.olx.com     2     2
```
(Plus google pages whose URL contains "olx.", ignore.) Main use: olx.ua (Kyiv), secondary olx.pl.
Recent URLs (removed from this file): ad pages in Kyiv and the account's message pages.
Pattern: logged-in account (myaccount/answers), browsing ad photo sliders (sliderIndex=N, isPreviewActive).

## 3. Violentmonkey ({aecec67f-0d10-4fa7-b7c7-609a2db280cf}, v2.49.0, uuid d4d825bb-f08d-4a8b-907e-559992498acc; extension active in extensions.json)

Four scripts in storage.local (all `config.enabled` = 1, removed = 0, installed from http://127.0.0.1:8899/ except Pinterest):
| id | name | @match | @run-at |
|---|---|---|---|
| 1 | Light images, full quality on hover (`light-images-hover`, setup-lab v0.2) | `*://*/*` | document-idle |
| 2 | YouTube: light thumbnails, full quality on hover (v0.2) | `*://*.youtube.com/*` | document-start |
| 3 | YouTube: drop video quality when the tab is hidden (v0.1) | `*://*.youtube.com/*` | document-idle |
| 4 | Pinterest - Enable Copy & Text Selection (v1.0) | `https://www.pinterest.com/*`, `https://*.pinterest.com/*` | document-start |

`light-images-hover`: ACTIVE and matches OLX (and every site). `@grant none`. Behaviour: for every `img[srcset]` with >=2 candidates it empties `srcset` and sets `src` to the smallest candidate (stores original in data-lih-*); restores full on `mouseover` (capture). Also swaps ytimg thumbnails. It runs a MutationObserver on `document.documentElement` (childList+subtree). Relevance to OLX: OLX gallery/slider images use srcset, so previews load in the smallest size until hovered; the observer fires on every DOM change in SPA pages. Possible cause of blurry/small ad photos (sliderIndex navigation) on olx.ua. Not an OLX-specific script; no script targets OLX explicitly.

## 4. Memory prefs (user.js and prefs.js agree)

user.js (line: pref):
```
4   image.mem.surfacecache.max_size_kb = 131072   // 128 MB
6   browser.sessionhistory.max_total_viewers = 2
58  browser.tabs.unloadOnLowMemory = true
59  browser.low_commit_space_threshold_mb = 1536
60  browser.tabs.min_inactive_duration_before_unload = 300000   (5 min)
63  fission.autostart = false
64  dom.ipc.processCount = 4
```
Not set anywhere (defaults): javascript.options.mem*, browser.cache.* (disk/memory cache), other image.mem.*. prefs.js carries the same values for these (no divergence).
Comments in user.js: "setup/lab experiment 01-memory", "memory relief (lab 59-memory-relief, 10.10.2026)".

## 5. Signatures and uBO uuid

- `xpinstall.signatures.required`: NOT present in prefs.js or user.js (grep for "xpinstall"/"signatures" empty). Dev Edition default applies (unsigned allowed by default there).
- `extensions.webextensions.uuids` entry: `"uBlock0@raymondhill.net":"45088fc6-40f9-465a-bd1d-d4cbfaa89521"` (moz-extension://45088fc6-40f9-465a-bd1d-d4cbfaa89521/). prefs.js also has `extensions.webextensions.ExtensionStorageIDB.migrated.uBlock0@raymondhill.net = true`.
