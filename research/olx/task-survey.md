# Task: survey of existing ad/tracker blocking for OLX (olx.ua)

## Goal
We are building an OLX-specific blocker (uBlock Origin filters and/or a tiny Firefox extension)
to cut memory use of OLX pages. First collect what already exists so we reuse it instead of
inventing. Web research only; no browser automation needed.

## Working root
`/home/fanatic/ai/claude/setup/research/olx/`. Write the result to
`/home/fanatic/ai/claude/setup/research/olx/survey.md`. Create no other files.

## Questions
1. Which maintained filter lists already carry OLX rules (`olx.ua`, `olx.pl`, `olx.*`):
   EasyList, EasyPrivacy, uBlock filters, AdGuard Base / Russian / Ukrainian, RU AdList,
   "Ukrainian filters" etc. Quote the actual OLX rules you find (network and cosmetic) with the
   list name and a link to the raw file. Fetch the raw list files and grep them for `olx`.
2. Known OLX first-party advertising/analytics/tracking endpoints and scripts: e.g. OLX "Ninja"
   tracker, Laquesis (A/B testing), Hydra, ad servers, Google Ad Manager / Prebid usage,
   Hotjar, Braze, recommendation widgets. For each: host/path pattern, what it is, source link.
3. Known reports of OLX tabs using lots of memory in Firefox/Chrome and what helped.
4. Userscripts or extensions dedicated to cleaning up OLX (Greasy Fork, OpenUserJS, GitHub):
   name, link, last update, what they do.
5. How OLX listing images are addressed (apollo / olxcdn URL with `;s=WxH`), what sizes exist,
   and whether a larger size than the gallery default can be requested.

## Do not
- Do not invent rules or hosts; every rule and host must come with the source you read it in.
  If you found nothing for a question, write "nothing found" and list where you looked.
- Do not edit any file except `survey.md`.

## Final report (`survey.md`, English, and as your final message)
One section per question, with quoted rules / patterns and source links. End with a short
"Use directly" list: rules you would copy into our list as-is.
