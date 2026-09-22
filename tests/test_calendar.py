import datetime as dt
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop/share/light-year"))
import api
import recurrence


class CalendarTests(unittest.TestCase):
    day = dt.date(2026, 9, 22)

    def test_recurrence_roundtrip(self):
        for mode in ("none", "daily", "weekly", "monthly", "yearly", "custom"):
            with self.subTest(mode=mode):
                rules = recurrence.rule(mode, self.day, {1, 3})
                self.assertEqual(recurrence.describe(rules, self.day)[0], mode)
        self.assertEqual(recurrence.rule("custom", self.day, {1, 3}), ["RRULE:FREQ=WEEKLY;BYDAY=TU,TH"])
        with self.assertRaises(ValueError):
            recurrence.rule("custom", self.day, set())

    def test_preserve_advanced_recurrence(self):
        for rules in (["RRULE:FREQ=WEEKLY;COUNT=10"], ["RRULE:FREQ=MONTHLY;BYDAY=-1FR"],
                      ["RRULE:FREQ=YEARLY", "EXDATE:20260922T100000Z"]):
            self.assertEqual(recurrence.describe(rules, self.day)[0], "existing")

    def test_day_capacity(self):
        self.assertEqual(recurrence.capacity(150, 30, 20, 5), 5)
        self.assertEqual(recurrence.capacity(149, 30, 20, 5), 4)
        self.assertEqual(recurrence.capacity(150, 30, 20, 20), 4)
        self.assertEqual(recurrence.capacity(10, 30, 20, 20), 0)

    def test_event_pagination(self):
        event = {"id": "a", "start": {"dateTime": "2026-09-22T10:00:00+03:00"},
                 "end": {"dateTime": "2026-09-22T11:00:00+03:00"}}
        calls = []
        def google(path, **kwargs):
            calls.append(dict(kwargs["params"]))
            return {"items": [event], **({"nextPageToken": "next"} if len(calls) == 1 else {})}
        with patch.object(api, "google", google):
            self.assertEqual(len(api.list_events(self.day, self.day + dt.timedelta(days=1))), 2)
        self.assertEqual(calls[1]["pageToken"], "next")

    def test_create_repeat_and_change_single_occurrence_guard(self):
        start = dt.datetime(2026, 9, 22, 10)
        rules = recurrence.rule("daily", self.day)
        with patch.object(api, "google", return_value={}) as google:
            api.create_event("Test", start, start + dt.timedelta(hours=1), recurrence=rules)
            self.assertEqual(google.call_args.args[2]["recurrence"], rules)
            self.assertEqual(google.call_args.args[2]["start"]["timeZone"], api.TZ)
            with self.assertRaises(ValueError):
                api.change_occurrence({"recurring_id": "series"}, "this", recurrence=rules)

    def test_failed_series_split_does_not_truncate_original(self):
        start = dt.datetime(2026, 9, 22, 10)
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start.astimezone(), "end": (start + dt.timedelta(hours=1)).astimezone(),
                 "original_start": start.astimezone().isoformat()}
        master = {"start": {"dateTime": "2026-09-21T10:00:00+03:00"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, body))
            if method == "POST":
                raise RuntimeError("API unavailable")
            return master
        with patch.object(api, "google", google), self.assertRaises(RuntimeError):
            api.change_occurrence(event, "following", summary="New title")
        self.assertEqual([method for method, _ in calls], ["GET", "POST"])


if __name__ == "__main__":
    unittest.main()
