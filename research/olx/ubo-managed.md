# uBlock Origin 1.75.0: Firefox managed policy (3rdparty) behaviour

Source: `uBlock0@raymondhill.net.xpi` (version 1.75.0, from manifest.json), unpacked to
`/tmp/claude-1000/-home-fanatic/614f9629-afe8-4732-8a6d-898c41e15ffb/scratchpad/ubo-src/`.
Line numbers refer to that unpacked copy. The schema is `managed_storage.json`.

## 1. Which managed keys are honored

Keys read through `vAPI.adminStorage` (`js/vapi-background.js:1449`), which wraps `webext.storage.managed`:

- `adminSettings` (JSON string or object): read at `js/storage.js:1392-1404`. Sub-keys honored:
  `assetsBootstrapLocation` (1417-1422), `userSettings` (1424-1433, only names already in `µb.userSettings`),
  `selectedFilterLists` (1453-1456, only if `toOverwrite.filterLists` is absent), `whitelist` / `netWhitelist` (1465-1471),
  `dynamicFilteringString` (1473), `urlFilteringString` (1478), `hostnameSwitchesString` (1483), `userFilters` (1495-1496).
- `userSettings` (`[name, value]` pairs): `js/storage.js:173` and `179-190`. Applied as defaults, not as locks.
- `advancedSettings` (`[name, value]` pairs), `disableDashboard`, `disabledPopupPanelParts`: `js/storage.js:233-276`.
  `disableDashboard` sets `µb.noDashboard` (259). Popup parts map to bits `globalStats`, `basicTools`, `extraTools`, `overviewPane` (261-266).
- `toAdd.trustedSiteDirectives`: read at `js/start.js:394`, appended to the whitelist at `js/start.js:197-204`.
- `toOverwrite.filters` (1493-1507), `toOverwrite.filterLists` (1438-1456), `toOverwrite.trustedSiteDirectives` (1458-1464).

```js
// js/storage.js:1458-1464
if (
    Array.isArray(toOverwrite.trustedSiteDirectives) &&
    toOverwrite.trustedSiteDirectives.length !== 0
) {
    µb.netWhitelistDefault = toOverwrite.trustedSiteDirectives.slice();
    bin.netWhitelist = toOverwrite.trustedSiteDirectives.slice();
```

Caveats found in the code:
- Caching: `js/vapi-background.js:1446-1448` says admin changes need an extra restart. The cache is `cachedManagedStorage` (1463, 1470-1474).
- `js/storage.js:286` reads `Object.hasOwn(hsAdmin, name)`. `name` is not declared in `loadHiddenSettings`, so this check does not test the intended key.

## 2. `toOverwrite.filters` ("My filters")

Applied on every startup, but only written when the text differs from the stored user filters. Startup awaits `restoreAdminSettings` every launch (`js/start.js:386-387`).

```js
// js/storage.js:1492-1507
let userFiltersAfter;
if ( Array.isArray(toOverwrite.filters) ) {
    userFiltersAfter = toOverwrite.filters.join('\n').trim();
} else if ( typeof data.userFilters === 'string' ) {
    userFiltersAfter = data.userFilters.trim();
}
if ( typeof userFiltersAfter === 'string' ) {
    const bin = await vAPI.storage.get(this.userFiltersPath);
    const userFiltersBefore = bin && bin[this.userFiltersPath] || '';
    if ( userFiltersAfter !== userFiltersBefore ) {
```

- Full replacement, not a merge: the joined text overwrites the stored content through `saveUserFilters` (`js/storage.js:581-587`, `io.put(this.userFiltersPath, content)`). An empty array (`[]`) passes `Array.isArray` and clears the user filters.
- The user can still edit My filters in the dashboard. Dashboard saves call `µb.saveUserFilters` (`js/messaging.js:1124`, `1466`). No lock or read-only check was found.
- Edits do not survive a restart when the admin value is set. On the next launch the admin text differs from the edited text, so it is overwritten again (`js/storage.js:1501-1505`). Edits persist only when no `toOverwrite.filters` / `adminSettings.userFilters` is present.

## 3. `toOverwrite.filterLists`

Yes, it replaces the whole selection, not a merge. A non-empty array is stored verbatim as `selectedFilterLists`.

```js
// js/storage.js:1438-1456
if (
    Array.isArray(toOverwrite.filterLists) &&
    toOverwrite.filterLists.length !== 0
) {
    const importedLists = [];
    for ( const list of toOverwrite.filterLists ) {
        if ( /^[a-z-]+:\/\//.test(list) === false ) { continue; }
        importedLists.push(list);
    }
    if ( importedLists.length !== 0 ) {
        bin.importedLists = importedLists;
        bin.externalLists = importedLists.join('\n');
    }
    bin.selectedFilterLists = toOverwrite.filterLists;
    binNotEmpty = true;
```

- Custom URLs are accepted when they match `^[a-z-]+://` (`js/storage.js:1444`). They are also stored as `importedLists` (1447-1449). Other entries are kept as-is in `selectedFilterLists`, with no validation.
- The write happens on every startup: `if ( binNotEmpty ) { vAPI.storage.set(bin); }` (`js/storage.js:1488-1490`). `loadSelectedFilterLists` then reads the stored value (`js/storage.js:453-458`). Startup awaits `restoreAdminSettings` before that (`js/start.js:387`, `413`).

## 4. `file://` custom lists

Not blocked by uBO's own code. The URL passes the admin regex (`js/storage.js:1444`) and the custom-list regex (`js/storage.js:569`, `/^[a-z-]+:\/\/\S+/`). Remote fetch treats any `scheme://` path as external (`js/assets.js:34`, `331-332`) and fetches it with XHR (`js/assets.js:311`).

```js
// js/assets.js:307-321
// Be ready for thrown exceptions:
// I am pretty sure it used to work, but now using a URL such as
// `file:///` on Chromium 40 results in an exception being thrown.
try {
    xhr.open('get', url, true);
    ...
    xhr.send();
} catch {
    onErrorEvent.call(xhr);
}
```

- Whether Firefox lets the extension XHR a `file://` URL is not determinable from this source. The manifest grants `file://*/*` only in `content_scripts` (`manifest.json:67`) and has no `host_permissions` entry for it. Access also depends on the user's file-access setting in Firefox.
- A `file://` list is not trusted by default. `trustedListPrefixes` is `'ublock-'` (`js/background.js:87`), and `file:///` prefixes are only trusted if added there (`js/storage.js:426`).

## 5. Format of managed filters and the `user-filters` list

- Format: each array item is one line. The array is joined with `\n` and trimmed (`js/storage.js:1494`). No `!#` prefix is needed or checked by the managed-filters path.
- Auto-add: no. Overwriting `filters` only writes the content (`js/storage.js:1493-1507`) and does not touch `selectedFilterLists`. If `toOverwrite.filterLists` is set, `user-filters` is selected only if that array contains `user-filters`. No code found re-adds it. The only other selection touch is `userFiltersAreEnabled` (`js/storage.js:680-682`), which only reads it. Without managed `filterLists`, `user-filters` is in the first-launch default (`js/storage.js:687`).
