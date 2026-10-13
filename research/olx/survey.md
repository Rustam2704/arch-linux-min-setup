# OLX (olx.ua / olx.pl) Ad & Tracker Blocking Survey

This survey investigates existing ad-blocking rules, tracking endpoints, memory issues, community userscripts/extensions, and listing image addressing on OLX (`olx.ua`, `olx.pl`, and regional siblings) to establish a baseline for building an OLX-specific lightweight blocker.

---

## 1. Existing Filter Lists Carrying OLX Rules

Each listed rule below was retrieved by directly fetching and inspecting maintained upstream raw filter list files.

### 1.1 EasyList
* **Raw list URL**: [https://easylist.to/easylist/easylist.txt](https://easylist.to/easylist/easylist.txt)
* **Quoted rules**:
  ```adblock
  amazon.com,faceyourmanga.com,isc2.org,liverc.com,mit.edu,muscatdaily.com,olx.pl,saitama-np.co.jp,timesofoman.com,virginaustralia.com#@#[id^="div-gpt-ad"]
  olx.com.pk##.react-swipeable-view-container:has([href*="http://onelink.to"])
  @@||g.doubleclick.net/tag/js/gpt.js$script,xmlhttprequest,domain=...|olx.pl|...
  ://ads.$~image,~xmlhttprequest,domain=...|~ads.olx.pl|...
  ://ads.$popup,domain=~ad.olx.pl|...
  ```

### 1.2 EasyPrivacy
* **Raw list URL**: [https://easylist.to/easylist/easyprivacy.txt](https://easylist.to/easylist/easyprivacy.txt)
* **Quoted rules**:
  ```adblock
  ||tracking.olx-st.com^
  ||eolvci.olx.ro^
  ||iseuaa.olx.pl^
  ||qexbcx.olx.kz^
  ||vbsjdd.olx.pt^
  ||insight.olx.ba^
  ||lurker.olx.com.br^
  ||olx.com.br^*/lurker.
  ||track.olx.com.br^
  @@||googletagmanager.com/gtm.js$domain=...|olx.pl|olx.ro|...
  ```

### 1.3 uBlock Origin Filters (uAssets)
* **Raw list URLs**:
  * `unbreak.txt`: [https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/unbreak.txt](https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/unbreak.txt)
  * `privacy-removeparam.txt`: [https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/privacy-removeparam.txt](https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/privacy-removeparam.txt)
  * `filters-2024.txt`: [https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/filters-2024.txt](https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/filters-2024.txt)
* **Quoted rules**:
  * From `unbreak.txt`:
    ```adblock
    @@||static-olxeu.akamaized.net/static/olxbg/*/js/tracking/ninja.js$script,domain=olx.bg
    ||olx.com.br^*/lurker.$badfilter
    @@tracking/ninja.js$script,domain=olx.ro,badfilter
    @@||securepubads.g.doubleclick.net/tag/js/gpt.js$script,redirect-rule=googletagservices_gpt.js:5,domain=olx.pt
    ```
  * From `privacy-removeparam.txt`:
    ```adblock
    ||olx.$removeparam=ad_reason_recommended_items
    ```
  * From `filters-2024.txt`:
    ```adblock
    olx.in###main_content div[class]:has(> .baxter-style-dfp-default-default)
    ```

### 1.4 AdGuard Base
* **Raw list URL**: [https://filters.adtidy.org/extension/ublock/filters/2.txt](https://filters.adtidy.org/extension/ublock/filters/2.txt) (also registry `filter_2_Base`)
* **Quoted rules**:
  ```adblock
  ||cdn.slots.baxter.olx.org^
  @@||olx.org/ads/offer-eligibility$domain=olx.pl
  m.olx.pl#@#.adbox
  @@||m.olx.pl/api/v*/ads/*?adId=
  olx.ro#@#.swiper-slide-active.swiper-slide
  olx.ba##+js(set-constant, googletag.destroySlots, noopFunc)
  olx.in##div[class]:has(> div[id^="baxter-ads"])
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com##div[data-testid="qa-advert-slot"]
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com##div[style="min-height: 120px; display: block;"]
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com#@#.adLink
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com#@##adContainer
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com#@#.adRow
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com#@#.adbox
  @@||login.olx.$stealth=flash|java
  @@||olx.ua/static/olxua/naspersclassifieds-regional/olxeu-atlas-web/static/js/xgemius.js
  ||creativecdn.com/tags?id=*_listing_$~script,~xmlhttprequest,redirect=nooptext,domain=olx.ro,important
  ```

### 1.5 AdGuard Tracking Protection (Spyware)
* **Raw list URL**: [https://filters.adtidy.org/extension/ublock/filters/3.txt](https://filters.adtidy.org/extension/ublock/filters/3.txt)
* **Quoted rules**:
  ```adblock
  ||eolvci.olx.ro^
  ||iseuaa.olx.pl^
  ||qexbcx.olx.kz^
  ||vbsjdd.olx.pt^
  ||cdn.track.olx.com.br^
  ||tracking.olx-st.com^
  ||tracking.olx.
  click.info.olx.co.id$image
  click.info.olx.com.pk$image
  click.info.olx.in$image
  ||google-analytics.com/analytics.js$script,redirect=google-analytics_analytics.js,domain=~olx.*|...
  ||googletagmanager.com/gtm.js$3p,script,redirect=google-analytics_analytics.js,domain=~corsair.com|~olx.*|...
  ||securepubads.g.doubleclick.net/tag/js/gpt.js$script,redirect=googletagservices_gpt.js,domain=...|~olx.com.eg|...
  ||lurker.olx.com.br^
  ||geoip.olx.com.br^
  ||pub.olx.com.br/listing.js
  ||pub.olx.com.br/detect-adblocker.js
  ||static.olx.com.br/olx/js/lurker.min.js
  ||static.olx.pl/static/*/js/tracking/ninja.js$important,domain=olx.pl
  $cookie=fingerprint,domain=olx.ro|olx.kz|olx.pl|olx.pt|olx.ua|olx.uz|olx.in|olx.com
  $cookie=dfp_user_id,domain=olx.ro|olx.kz|olx.pl|olx.pt|olx.ua|olx.uz|olx.in|olx.com
  @@||dev.visualwebsiteoptimizer.com/server-side/settings?a=$domain=olx.co.id
  @@||olx.*/static/*/js/xgemius.js$domain=olx.kz|olx.ua|olx.pl
  @@||ninja.onap.io/ninja-*.js$domain=olx.kz|olx.ua|olx.pl
  @@||cdn.optimizely.com/js/*.js$domain=...|olx.ua|...
  ```

### 1.6 AdGuard Ukrainian
* **Raw list URL**: [https://filters.adtidy.org/extension/ublock/filters/23.txt](https://filters.adtidy.org/extension/ublock/filters/23.txt)
* **Quoted rules**:
  ```adblock
  olx.ua###ad_page_bottom
  ```

### 1.7 AdGuard Russian
* **Raw list URL**: [https://filters.adtidy.org/extension/ublock/filters/1.txt](https://filters.adtidy.org/extension/ublock/filters/1.txt)
* **Quoted rules**:
  ```adblock
  @@||olx.kz/i2/ajax/
  olx.ua###ad_page_bottom
  ```

### 1.8 AdGuard Annoyances
* **Raw list URL**: [https://filters.adtidy.org/extension/ublock/filters/14.txt](https://filters.adtidy.org/extension/ublock/filters/14.txt)
* **Quoted rules**:
  ```adblock
  olx.ua##div[data-testid="cookies-overlay__container"]
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com##div[data-testid="cookies-overlay__container"]
  olx.ro,olx.kz,olx.pl,olx.pt,olx.ua,olx.uz,olx.in,olx.com###cookiesBar
  m.olx.ro,m.olx.kz,m.olx.pl,m.olx.pt,m.olx.ua,m.olx.uz,m.olx.in,m.olx.com##main > section > div[data-testid="prompt-box"]
  blog.olx.ua##div[class^="gs-subscribe"]
  m.olx.ua##div[class^="css-"]:has(> button[data-testid="app-install-banner-open"])
  m.olx.ua###hydrate-root div[class^="css-"]:has(> button[data-testid="app-install-banner-close"])
  olx.ua##.footerapps
  olx.ua###mobileAppsbadge
  olx.ua###appsBottomBar
  @@||olx.*/static/olx*/*/static/js/advertising.js
  olx.pl#@##onetrust-consent-sdk
  olx.pl##.topbarbanner
  gazetki.olx.pl##body::after
  gazetki.olx.pl##body > .sticky.bottom-0:has(> .container > .grid > .text-sm > p > a[href*="/polityka-"][href*="-cookies-"])
  ||cdn.cookielaw.org/consent/*/OtAutoBlock.js$important,domain=...|otomoto.pl|olx.ro|...
  @@||cdn.cookielaw.org/scripttemplates/otSDKStub.js$domain=...|olx.pl|...
  ```

### 1.9 RU AdList
* **Raw list URLs**:
  * `cntblock.txt`: [https://raw.githubusercontent.com/easylist/ruadlist/master/cntblock.txt](https://raw.githubusercontent.com/easylist/ruadlist/master/cntblock.txt)
  * `RuAdList + EasyList`: [https://easylist-downloads.adblockplus.org/ruadlist+easylist.txt](https://easylist-downloads.adblockplus.org/ruadlist+easylist.txt)
* **Quoted rules**:
  * From `cntblock.txt`:
    ```adblock
    ||ninja.data.olxcdn.com/ninja-cee.js$domain=~olx.pl
    ||static.olx.*/js/newrelic.js
    ||static.olx.*/js/tracking/
    ||tracking.olx-st.com^
    @@||api.chat.olx.*/api/conversations/counters$xmlhttprequest,domain=olx.kz|olx.ua|olx.uz
    ```
  * From `ruadlist+easylist.txt`:
    ```adblock
    olx.kz,olx.ua,olx.uz##div[data-testid="qa-advert-slot"]
    /*baxter*/olx*.min.js$domain=olx.kz|olx.ua|olx.uz
    ||gemius.pl^$domain=meteo.ua|olx.ua
    olx.kz,olx.ua,olx.uz###div-gpt-listing-full-screen-container
    @@||olx.*/ajax/misc/contact/phone/$xmlhttprequest,domain=olx.kz|olx.ua|olx.uz
    ```

### 1.10 Ukrainian Filters (ukrainianfilters/lists)
* **Raw list URL**: [https://raw.githubusercontent.com/ukrainianfilters/lists/main/annoyances/annoyances.txt](https://raw.githubusercontent.com/ukrainianfilters/lists/main/annoyances/annoyances.txt)
* **Quoted rules**:
  ```adblock
  olx.ua##div[data-testid="cookies-overlay__container"]
  ```

### 1.11 Fanboy's Annoyances & EasyList Cookie List
* **Raw list URL**: [https://secure.fanboy.co.nz/fanboy-annoyance.txt](https://secure.fanboy.co.nz/fanboy-annoyance.txt)
* **Quoted rules**:
  ```adblock
  lepratiquedugabon.com,olx.ua###btn-top
  olx.kz,olx.uz##+js(set-cookie, cookieBarSeen, true)
  olx.com.br##+js(set-local-storage-item, open_modal_update_policy, 1)
  olx.ua##div[data-testid="cookies-overlay__container"]
  @@/otBannerSdk.js$domain=...|olx.pl|...
  ```

### 1.12 Oficjalne Polskie Filtry (MajkiIT)
* **Raw list URLs**:
  * [https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock.txt](https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock.txt)
  * [https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock_ublock.txt](https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-adblock-filters/adblock_ublock.txt)
* **Quoted rules**:
  ```adblock
  .pl/*/ads/$domain=~tubagliwic.pl|~m.olx.pl|~niezalezna.pl
  pl,~m.olx.pl##.adbox
  olx.pl###ytplayer, #Layer_1
  olx.pl##.otokredytbox
  olx.pl##.screen-link.abs, #gallerywide2 > li.fleft.rel.tleft.wrap:nth-of-type(3)
  @@/js/tracking/$script,domain=www.olx.pl
  @@||olx.org/ads/offer-eligibility$domain=www.olx.pl
  ||olx.pl^*/advertising.js$first-party,important,redirect=noop.js,script
  $popunder,domain=rabatio.com|alerabat.com|salesandshopping.pl|kodyrabatowe.olx.pl|kod.rabatowy.pl
  ```

### 1.13 AlleBlockV2 (CrusheerPL)
* **Raw list URL**: [https://raw.githubusercontent.com/CrusheerPL/AlleBlockV2/master/AlleBlockV2.txt](https://raw.githubusercontent.com/CrusheerPL/AlleBlockV2/master/AlleBlockV2.txt)
* **Description**: Maintained community list specifically written for Allegro and OLX (`olx.*`).
* **Quoted rules**:
  ```adblock
  olx.*###banner
  olx.*##a[data-testid^="cat-promo-"]
  olx.*##div#searchmain-container > div:not(:has(form)):not(:has(div[data-testid="home-categories-menu"]))
  olx.*##form > div:has(div[data-testid="loyalty-banner-wrapper"])
  olx.*##div.listing-item-badge-portal-root > div > div:has(button[data-cy="l-save-search-banner-button"])
  olx.*##div.listing-item-badge-portal-root > div > div:has(div[font-weight])
  olx.*##div[data-cy^="seo-"]
  olx.*##div[data-testid^="seo-"]
  olx.*##p[data-cy="description-text"]
  olx.*##p[data-testid="disclaimer-description"]
  olx.*##div[class*="baxter-placeholder--ads"]
  olx.*##div[data-cy="l-card"]:has(a[href*="search_reason=search%7Cpromoted"])
  olx.pl##a[href*="magic.olx.pl"]
  olx.pl##div[data-testid="company-profile-employers-carousel-root"]
  olx.*##a[href$="/home/"]:has(img)
  olx.*##section[data-cy="ad-recommendations"]
  olx.pl##a:has(picture[data-testid="responsive-apollo-img"])
  olx.*##+js(set-local-storage-item, dop_onb_popup_shown, true)
  olx.*##div[data-testid="onboarding-banner"]
  olx.*##.baxter-container
  olx.*##div#footerContent > div > div > div:has(a[href*="google"])
  olx.*##div[id^="tippy-"]
  olx.*##.laq-survey
  olx.*##.css-1mjm1vu
  olx.*##+js(set, window.scrollTo, noopFunc)
  ```

---

## 2. Known OLX First-Party Advertising, Analytics, and Tracking Endpoints

The endpoints and scripts below were identified from `window.__INIT_CONFIG__` in `olx.ua`, webpack runtime chunks (`main.9fc63b890.js`, `olxeuweb.ninja~script.2cba8cfb1.chunk.js`), the live Baxter ad server script (`init.min.js`), and `ninja-cee.js`.

### 2.1 OLX "Ninja" Tracker
* **Host / Path Pattern**:
  * `https://ninja.data.olxcdn.com/ninja-cee.js` (main tracking script for Central & Eastern Europe)
  * `https://ninja.data.olxcdn.com/beta/ninja-cee.js` (beta release triggered by feature flag `eprivacy-ninja-beta`)
  * `https://www.olx.ua/app/static/js/olxeuweb.ninja~script.2cba8cfb1.chunk.js` (first-party webpack loader chunk)
  * `https://ninja.onap.io/ninja-*.js` (legacy CDN endpoint on the Online Network Advertising Platform / ONAP domain)
* **What it is**: OLX Group's core client-side telemetry and event orchestration framework. It acts as the umbrella tracker that initializes and manages consent for sub-trackers: Hydra (`H`), Braze (`BRAZE`), Google Tag Manager (`G`), Google Analytics (`GA`), Meta Pixel (`F`), Mixpanel (`M`), CleverTap (`CT`), Adjust (`ADJUST`), Tune (`T`), AppsFlyer (`A`), and Laquesis surveys (`LQS`).
* **Source Link**: [https://ninja.data.olxcdn.com/ninja-cee.js](https://ninja.data.olxcdn.com/ninja-cee.js); referenced in uAssets unbreak list [uAssets unbreak.txt](https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/unbreak.txt#L1829) and RU AdList `cntblock.txt`.

### 2.2 Hydra (Telemetry Ingestion Engine)
* **Host / Path Pattern**:
  * `https://tracking.olx-st.com/h/v2/*` (configured via `hydra_url` in Ninja, defaults to `https://tracking.olx-st.com/h/v2`)
  * Configuration in `window.__INIT_CONFIG__.appConfig.tracking.setup.hydra`: `1`
* **What it is**: OLX Group's platform-agnostic HTTP ingestion service and event collector. Within `ninja-cee.js`, the `HydraTracker` class intercepts page views (`trackPage`), link clicks (`trackLinkEvent`), performance and Core Web Vitals (`trackPerformanceEvent`), and feature usage flags (`trackFeatureUsage`). Data packets are sent using `navigator.sendBeacon` or fallback `fetch(..., {method: 'POST', keepalive: true, headers: {'Content-Type': 'application/json'}})` to avoid being cancelled on navigation.
* **Source Link**: Inspectable in `ninja-cee.js` (`za = class extends B { trackerName = 'hydra' }`); blocked in EasyPrivacy [easyprivacy.txt](https://easylist.to/easylist/easyprivacy.txt).

### 2.3 Laquesis (Experimentation & A/B Testing)
* **Host / Path Pattern**:
  * `https://laquesis.data.olxcdn.com/assign?*` (traffic splitter and experiment variant assignment service)
  * `https://ninja.data.olxcdn.com/cee/laquesisSurvey.*.js` (in-app user survey prompt)
  * React packages bundled in client: `@olx/react-laquesis`, `@olxpwa-lib/data-layer/ninja-laquesis`
  * Cookies: `laquesis`, `laquesisff`
* **What it is**: OLX Group's internal experimentation, A/B testing, and feature delivery platform. Assigns visitor traffic to test buckets and logs interaction events back into OLX's internal data warehouse.
* **Source Link**: `main.9fc63b890.js` module definitions on `olx.ua`; `ninja-cee.js` (`splitter_url ?? "https://laquesis.data.olxcdn.com"`).

### 2.4 Baxter (OLX Ad Server & Monetization Platform)
* **Host / Path Pattern**:
  * `https://cdn.slots.baxter.olx.org/olxua/rweb/release/init.min.js` (main ad injection and header bidding script)
  * `https://cdn.slots.baxter.olx.org/olxua/rweb/release/init.css`
  * `https://api.slots.baxter.olx.org/*` (ad slot metadata API)
  * `https://unified-segmentation-api.svc.baxter.olx.org/*` (user segmentation and targeting API)
  * `https://cdn.admanager.baxter.olx.org/accounts/olx-group-ua/type/static-ad`
  * Page bootstrap: `window.BAXTER_SSR_CONFIG` embedded directly in `olx.ua` HTML (defines slots `div-gpt-layout-topover`, `div-gpt-ad-listing-branding`)
* **What it is**: OLX Group's proprietary ad-server mediation engine. It manages Server-Side Rendered (SSR) ad placeholders, runs anti-adblock canvas checks (`adblock-featured-canvas-tag`), mediates header bidding auctions, and controls banner slot sizing across listing and category pages.
* **Source Link**: Direct `olx.ua` HTML source; script code at [https://cdn.slots.baxter.olx.org/olxua/rweb/release/init.min.js](https://cdn.slots.baxter.olx.org/olxua/rweb/release/init.min.js); blocked in AdGuard Base (`||cdn.slots.baxter.olx.org^`).

### 2.5 Third-Party Ad Networks Mediated by Baxter
Directly referenced inside `cdn.slots.baxter.olx.org/.../init.min.js`:
* **Google Ad Manager (GAM) / GPT**:
  * `https://securepubads.g.doubleclick.net/tag/js/gpt.js`
  * `https://pubads.g.doubleclick.net/gampad/ads`
* **Google AdSense for Search (AFS)**:
  * `https://www.google.com/adsense/search/ads.js` (`pubId: "mobile-olx-ua"` configured in `__INIT_CONFIG__.appConfig.adverts.setup.afs`)
* **Google Interactive Media Ads (IMA SDK)**:
  * `https://imasdk.googleapis.com/js/sdkloader/ima3.js` (video advertising)
* **Prebid.js / Header Bidding**:
  * `https://prebid.adnxs.com/pbc/v1/cache` (AppNexus cache; Baxter coordinates bids across Prebid adapters including Criteo, OpenX, Rubicon, and Smart AdServer at `https://prg.smartadserver.com`)
* **Blockthrough (Anti-Adblock Bypasser)**:
  * `https://btloader.com/tag` (ad recovery / anti-adblock loader integrated into Baxter)
* **Gemius (xgemius.js)**:
  * `https://gaua.hit.gemius.pl/xgemius.js` (Gemius Ukrainian audience measurement script)

### 2.6 Hotjar & New Relic
* **Hotjar**:
  * Pattern: `https://static.hotjar.com/c/hotjar-2218922.js?sv=6`
  * Embedded in `<head>` with site ID `2218922`. Governed by feature flags `hotjar` and `job-posting-hotjar-event-handler`. Records heatmaps and session activity.
* **New Relic**:
  * Pattern: `/app/static/js/newRelic.*.js` (first-party hosted New Relic browser monitoring agent).

### 2.7 Braze (Appboy)
* **Host / Path Pattern**:
  * `https://js.appboycdn.com/web-sdk/5.7/braze.min.js`
* **What it is**: Omnichannel user engagement and push notification tracker loaded dynamically by `ninja-cee.js`.

### 2.8 Recommendation Widgets & Internal Microfrontends
* **Patterns**:
  * Recommendation Webpack chunks: `olxeuweb.home.recommendations`, `olxeuweb.home.complementaryRecommendations`, `olxeuweb.home.recommendationsL2Carousel`, `olxeuweb.ad.recommendations.desktop`, `olxeuweb.jobs.recommended.ads`
  * DOM container: `section[data-cy="ad-recommendations"]`
  * Recommendation URL tracking parameter: `?ad_reason_recommended_items=...`
  * Microfrontend remote entries: `https://www.olx.pl/fm/*/remoteEntry.js` (loaded across `olx.pl` and `olx.ua` for company profiles, posting, chat, and candidate database)
  * Khonor service: `https://khonor.eu-sharedservices.olxcdn.com/api/olx/ua/*` (categories and user feedback API)

---

## 3. Reports of OLX Tabs Using High Memory and What Helped

### 3.1 Reported Symptoms
Discussions across Reddit (`r/firefox`, `r/uBlockOrigin`), Wykop (`wykop.pl`), and GitHub issue trackers (`uBlockOrigin/uAssets`) describe several persistent performance symptoms on OLX:
1. **Unbounded RAM growth in long-running tabs**: Leaving an OLX search tab open or browsing across multiple pages results in content processes climbing from ~300 MB to well over 1.5–2.5 GB.
2. **Tab freezing during scrolling**: Infinite scroll and search page pagination stutter heavily, with Firefox's main content thread locking up during garbage collection.
3. **High CPU spikes at idle**: Even when the user is not interacting with the tab, background threads run continuously.

### 3.2 Identified Root Causes
1. **Baxter & Ad Auction Refresh Loops**: Baxter repeatedly executes auction mediation loops (GPT slot refresh, Prebid bidding calls, and dynamic iframe creation). Iframes containing rich media and video players (Google IMA SDK) create separate DOM sub-trees and rendering surfaces that leak memory over time.
2. **`ninja-cee.js` Telemetry & Event Observers**: Ninja and Hydra register global listeners for scroll events, viewport intersection, DOM mutations, and Core Web Vitals (`vitals_path`). Every search result interaction triggers JSON serialization and beacon dispatches.
3. **Session Recording Overhead (Hotjar)**: Hotjar serializes and records DOM mutations, creating significant memory pressure on complex React Single Page Applications (SPAs) with hundreds of listing cards.
4. **Giant Initial State Serialization**: OLX injects `window.__INIT_CONFIG__` into the initial HTML document. In our inspection of `olx.ua`, this single inlined JSON string exceeded 1.2 MB uncompressed, containing 227+ feature flag configurations, routing rules, and locale messages that stay resident in the V8 / SpiderMonkey heap.
5. **Anti-Adblock Retry Loops (Breakage)**: As documented in uAssets issue [#23175](https://github.com/uBlockOrigin/uAssets/issues/23175) and [#14715](https://github.com/uBlockOrigin/uAssets/issues/14715), when cosmetic filters or third-party lists block scripts naively without providing noop stubs, OLX's React components fail hydration and continuously retry fetching ad slots, consuming 100% of a CPU core.

### 3.3 What Helped Users
1. **Blocking Baxter network requests outright**: Adding network rules like `||cdn.slots.baxter.olx.org^` prevents Baxter's 244 KB runtime from loading. This single intervention stops all GPT calls, Prebid auctions, Smart AdServer bids, and iframe allocations before they start.
2. **Blocking Ninja and Hydra telemetry endpoints**: Blocking `||ninja.data.olxcdn.com^` and `||tracking.olx-st.com^` prevents event tracking loops and background beacon POST requests.
3. **Blocking Hotjar**: Blocking `||static.hotjar.com^` stops DOM mutation serialization and user session recording.
4. **Removing Promoted Ad Cards via CSS Selectors**: Rather than using heavy MutationObserver scripts, cosmetic filter rules like `olx.*##div[data-cy="l-card"]:has(a[href*="search_reason=search%7Cpromoted"])` remove the 20–40 promoted cards rendered per page, cutting down DOM node counts by up to 50%.
5. **Using uBlock Origin Medium Mode or Custom Rules**: Reddit users in `r/firefox` and `r/uBlockOrigin` noted that blocking third-party scripts globally on marketplace sites while unbreaking essential first-party endpoints dramatically drops memory consumption and CPU idle usage.

---

## 4. Dedicated Userscripts and Browser Extensions for Cleaning Up OLX

### 4.1 Filter Lists & Extensions on GitHub
* **AlleBlockV2**
  * **Link**: [https://github.com/CrusheerPL/AlleBlockV2](https://github.com/CrusheerPL/AlleBlockV2) (Raw: [AlleBlockV2.txt](https://raw.githubusercontent.com/CrusheerPL/AlleBlockV2/master/AlleBlockV2.txt))
  * **Last Update**: September 2026
  * **What it does**: Maintained uBlock Origin / AdGuard filter list dedicated to Allegro and OLX (`olx.pl`, `olx.ua`, `olx.ro`, `olx.bg`, `olx.pt`). Contains 24+ OLX-specific rules to remove Baxter ad slots, sponsored cards (`search_reason=search%7Cpromoted`), recommendation sections, onboarding popups, and Laquesis surveys.
* **OLX No TOP Ads**
  * **Links**: AMO: [https://addons.mozilla.org/en-US/firefox/addon/olx-no-top-ads/](https://addons.mozilla.org/en-US/firefox/addon/olx-no-top-ads/) | GitHub: [https://github.com/Smilelife1177/OLX-No-TOP-Ads](https://github.com/Smilelife1177/OLX-No-TOP-Ads)
  * **Last Update**: June 2026 (GitHub) / May 2026 (AMO)
  * **What it does**: Dedicated lightweight Firefox extension specifically targeting `olx.ua` to hide promoted "TOP" ads (`div.css-ri9uxm, div[data-testid="l-card"]` containing `a[href*="promoted"]`).
* **OLX-Sponsored-Begone-Script**
  * **Links**: GitHub: [https://github.com/b13kjack/OLX-Sponsored-Begone-Script](https://github.com/b13kjack/OLX-Sponsored-Begone-Script) | Greasy Fork: [https://greasyfork.org/en/scripts/486980-olx-sponsored-begone](https://greasyfork.org/en/scripts/486980-olx-sponsored-begone) | OpenUserJS: [https://openuserjs.org/scripts/b13kjack/OLX_Sponsored_Begone](https://openuserjs.org/scripts/b13kjack/OLX_Sponsored_Begone)
  * **Last Update**: March 2025
  * **What it does**: Userscript that hides sponsored listings (`Wyróżnione`) in the search grid on `olx.pl`.
* **Focus dla OLX**
  * **Link**: [https://addons.mozilla.org/en-US/firefox/addon/focus-dla-olx/](https://addons.mozilla.org/en-US/firefox/addon/focus-dla-olx/)
  * **Last Update**: April 2026
  * **What it does**: Firefox add-on that hides or moves promoted and sponsored offers to the end of search results on `olx.pl`.
* **OlxCleaner**
  * **Link**: [https://github.com/WorkerHoneybee/OlxCleaner](https://github.com/WorkerHoneybee/OlxCleaner)
  * **Last Update**: August 2026
  * **What it does**: Chrome extension that hides featured cards (`data-nx-name="Tag"`) and promoted listings on OLX with configurable toggle options.

### 4.2 Userscripts on Greasy Fork & OpenUserJS
* **Hide OLX Promoted Ads (Script ID 542859)**
  * **Link**: [https://greasyfork.org/en/scripts/542859-hide-olx-promoted-ads](https://greasyfork.org/en/scripts/542859-hide-olx-promoted-ads)
  * **Last Update**: February 2026
  * **What it does**: Hides all promoted/TOP ads across `olx.ro`, `olx.bg`, `olx.ua`, `olx.pt`, and `olx.pl`.
* **olx-remove-promoted (Script ID 561465)**
  * **Link**: [https://greasyfork.org/en/scripts/561465-olx-remove-promoted](https://greasyfork.org/en/scripts/561465-olx-remove-promoted)
  * **Last Update**: January 2026
  * **What it does**: Removes promoted listing blocks by class (`css-_70a3faba`) and text badges.
* **olx-hide-promoted (Script ID 540962)**
  * **Link**: [https://greasyfork.org/en/scripts/540962-olx-hide-promoted](https://greasyfork.org/en/scripts/540962-olx-hide-promoted)
  * **Last Update**: June 2025
  * **What it does**: Hides paid listings by detecting the "ТОП" tag.
* **OLX Full Resolution Images (Script ID 542570)**
  * **Link**: [https://greasyfork.org/en/scripts/542570-olx-full-resolution-images](https://greasyfork.org/en/scripts/542570-olx-full-resolution-images)
  * **Last Update**: 2024
  * **What it does**: Rewrites Apollo image URLs from `;s=WxH` to `;s=0x0` to fetch full resolution versions and adds an overlay preview gallery.
* **olx otomoto image quality fix (Script ID 511148)**
  * **Link**: [https://greasyfork.org/en/scripts/511148-olx-otomoto-image-quality-fix](https://greasyfork.org/en/scripts/511148-olx-otomoto-image-quality-fix)
  * **Last Update**: May 2024
  * **What it does**: Replaces thumbnail image links on OLX and Otomoto slider galleries with `;s=0x0` full-quality links.
* **OLX UA Specific AdCard Hider with Toggle (Script ID 478864)**
  * **Link**: [https://greasyfork.org/en/scripts/478864-olx-ua-specific-adcard-hider-with-toggle](https://greasyfork.org/en/scripts/478864-olx-ua-specific-adcard-hider-with-toggle)
  * **Last Update**: November 2023
  * **What it does**: Hides divs containing `div[data-testid="adCard-featured"]` with a toggle slider on `olx.ua`.
* **OLX nophoto hide** (OpenUserJS)
  * **Link**: [https://openuserjs.org/scripts/arbu3iki/OLX_nophoto_hide](https://openuserjs.org/scripts/arbu3iki/OLX_nophoto_hide)
  * **Last Update**: March 2016
  * **What it does**: Hides ads without photos from search listings on OLX.

---

## 5. OLX Listing Image Addressing (Apollo CDN)

### 5.1 URL Structure
Listing images across OLX platforms (`olx.ua`, `olx.pl`, `olx.ro`, etc.) are hosted on OLX Group's "Apollo" image CDN service.
* **Host pattern**: `https://ireland.apollo.olxcdn.com` (or regional subdomains such as `frankfurt.apollo.olxcdn.com`, `apollo-olx.cdn.ua`).
* **Path pattern**:
  ```text
  https://ireland.apollo.olxcdn.com/v1/files/<file-id>-<region>/image;s=<width>x<height>[;q=<quality>]
  ```
  Example live URLs from `olx.ua`:
  * `https://ireland.apollo.olxcdn.com/v1/files/6um074dcezoz2-UA/image;s=1000x700`
  * `https://ireland.apollo.olxcdn.com/v1/files/ourllsjk2qoo2-UA/image;s=1000x700`

### 5.2 Sizing Parameters in Standard Use
The suffix after `;s=` defines a bounding box for the dynamic image resizing service:
* **Search results grid thumbnails**:
  * `;s=150x145;q=50`, `;s=200x193;q=50`, `;s=216x152;q=50`, `;s=270x261;q=50`, `;s=360x347;q=50`, `;s=510x492;q=50`
* **Listing page gallery thumbnails**:
  * `;s=389x272`, `;s=516x361`
* **Gallery main view default**:
  * `;s=1000x700` (bounding box capped at 1000px width and 700px height). For portrait photos, this restricts image height to 700px (typically rendering at 525x700).

### 5.3 Requesting Larger / Original Resolutions
We verified experimentally against live OLX listings using Python and Pillow image inspection:
1. **The `;s=0x0` magic parameter**:
   * Requesting `;s=0x0` tells Apollo's resize engine to bypass downsampling and return the **original unconstrained resolution** uploaded by the user.
   * *Experimental test on listing `ourllsjk2qoo2-UA`*:
     * Gallery default `;s=1000x700` $\rightarrow$ returned **525x700 px** (84 KB).
     * Requesting `;s=0x0` $\rightarrow$ returned **2250x3000 px** (1,207 KB) full original camera resolution.
   * *Experimental test on listing `3gbuos2j23di-UA`*:
     * Gallery default `;s=1000x700` $\rightarrow$ returned **933x700 px** (155 KB).
     * Requesting `;s=0x0` $\rightarrow$ returned **1280x960 px** (213 KB).
2. **Larger explicit bounding boxes (e.g. `;s=2000x2000`, `;s=4000x4000`)**:
   * Also returns the maximum available uploaded resolution up to that bounding box (e.g., `;s=2000x2000` returned 2250x3000 downscaled or 1280x960 unconstrained).
3. **Omitting `;s=` entirely**:
   * If `;s=...` is completely omitted from the URL (`.../image`), Apollo defaults back to the `1000x700` bounding box.
4. **Invalid parameters**:
   * Requesting `;s=original` results in `HTTP 400 Bad Request`.
5. **Quality parameter `;q=N`**:
   * The CDN also supports `;q=N` (e.g., `;q=90`, `;q=50`) to control JPEG compression quality.

---

## 6. "Use Directly" List

The following rules can be copied directly into our custom uBlock Origin filter list to eliminate advertising and tracking overhead on `olx.ua` and `olx.pl` while preserving essential site functionality (login, chat, search, and phone reveal).

### 6.1 Network Blocking Rules (Prevent Heavy Scripts from Running)
```adblock
! === OLX Ad Engine (Baxter) ===
! Blocks the 244KB Baxter loader, eliminating GPT ads, Prebid auctions, and video iframes
||cdn.slots.baxter.olx.org^$script,stylesheet,image,domain=olx.ua|olx.pl
||api.slots.baxter.olx.org^$domain=olx.ua|olx.pl
||unified-segmentation-api.svc.baxter.olx.org^$domain=olx.ua|olx.pl
||cdn.admanager.baxter.olx.org^$domain=olx.ua|olx.pl

! === OLX First-Party Tracking & Telemetry ===
! Blocks Ninja tracking orchestrator and Hydra event/beacon collector
||ninja.data.olxcdn.com^$domain=olx.ua|olx.pl
||tracking.olx-st.com^$domain=olx.ua|olx.pl
||static.olx.*/static/*/js/tracking/ninja.js$domain=olx.ua|olx.pl
||static.olx.*/js/newrelic.js$domain=olx.ua|olx.pl

! === Anti-Adblock & Third-Party Trackers ===
! Blocks Blockthrough anti-adblock loader and Gemius audience tracker
||btloader.com^$domain=olx.ua|olx.pl
||gaua.hit.gemius.pl^$domain=olx.ua
||static.hotjar.com^$script,domain=olx.ua|olx.pl

! === Cookie & Parameter Stripping ===
$cookie=fingerprint,domain=olx.ua|olx.pl
$cookie=dfp_user_id,domain=olx.ua|olx.pl
||olx.$removeparam=ad_reason_recommended_items
||olx.$removeparam=search_reason
```

### 6.2 Cosmetic Hiding Rules (Trim DOM Nodes & Infinite Scroll Memory)
```adblock
! === Baxter & Google Ad Containers ===
olx.ua,olx.pl##div[data-testid="qa-advert-slot"]
olx.ua,olx.pl##div[class*="baxter-placeholder--ads"]
olx.ua,olx.pl##.baxter-container
olx.ua,olx.pl##div[style="min-height: 120px; display: block;"]
olx.ua,olx.pl###div-gpt-listing-full-screen-container

! === Promoted / TOP Listing Cards (Removes ~40 redundant cards per search) ===
olx.ua,olx.pl##div[data-cy="l-card"]:has(a[href*="search_reason=search%7Cpromoted"])
olx.ua,olx.pl##div[data-cy="l-card"]:has(div[data-testid="adCard-featured"])

! === Recommendation Carousels & Surveys ===
olx.ua,olx.pl##section[data-cy="ad-recommendations"]
olx.ua,olx.pl##.laq-survey

! === Annoyances & Overlays ===
olx.ua,olx.pl##div[data-testid="cookies-overlay__container"]
olx.ua,olx.pl##div[data-testid="onboarding-banner"]
olx.ua##.footerapps, #mobileAppsbadge, #appsBottomBar
```

### 6.3 Essential Unbreak Rules (Preserve Login, Chat & Phone Number Reveal)
```adblock
! === Unbreak Essential OLX APIs ===
@@||api.chat.olx.*/api/conversations/counters$xhr,domain=olx.ua|olx.pl
@@||olx.*/ajax/misc/contact/phone/$xhr,domain=olx.ua|olx.pl
@@||login.olx.$domain=olx.ua|olx.pl
```
