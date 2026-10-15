# Fix task B2: light-year calendar (audit `research/audit-2026-10-15/b-daemons.md`, B15–B19, B26 calendar part)
Rules: `tools/audit/fix-common.md`. Files you may edit: `desktop/share/light-year/*`, `desktop/bin/light-year`,
`tests/test_calendar.py` (and a new `tests/test_lightyear_*.py` if useful).
Fix B15 (all-day events stay all-day on edit), B16 (multi-day and overnight events drawn on every day
they cover, all-day end exclusive), B17 (mutation errors stay visible; failed drag restores the event),
B18 (delete the Zoom meeting if the Google event creation fails), B19 (OAuth callback: check path and a
random state; keep serving until a valid callback or timeout). B26: add the missing mock test for
"series split: create succeeds, truncating the old series fails" and verify cleanup + error surfacing.
No live Google/Zoom calls: mocks only.
