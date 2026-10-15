# Task C-lightyear: clear the other time field in PATCH bodies

Project `/home/fanatic/ai/claude/setup`, file `desktop/share/light-year/api.py`, tests in
`tests/test_calendar.py`.

Problem: Google Calendar `events.patch` merges nested objects. When an existing timed event is switched
to all-day, `update_event()` (api.py ~347, via `_event_times()` ~300) sends
`"start": {"date": "..."}` — Google keeps the old `dateTime` next to it and answers 400; the opposite
switch (all-day → timed) leaves the old `date`. Background:
`/home/fanatic/ai/claude/setup/research/light-year-2026-10-15/api-facts.md`, finding F5 (read it).

Fix:
- Every **PATCH** body that sets `start`/`end` must clear the other representation explicitly:
  `{"date": "...", "dateTime": None, "timeZone": None}` for all-day and
  `{"dateTime": "...", "timeZone": TZ, "date": None}` for timed. Find all PATCH paths that set
  start/end (`grep -n '"PATCH"' api.py`; ~357, ~513-534) and apply it there. POST (insert) bodies stay
  as they are. Keep the change minimal, one helper if it avoids repetition, same code style.
- Do not touch the Zoom calls, recurrence logic or anything else.
- Add unit tests to `tests/test_calendar.py` (follow the existing mocking style there) that check the
  PATCH body for both switches (timed → all-day, all-day → timed) and for a plain timed move.
- Run `python3 -m unittest tests.test_calendar -v` and `make test`; both must pass.
- Do not run `make apply`, do not touch the real calendar or network, do not commit.

Final message (English, under 25 lines): the diff summary (file:line), test results.
