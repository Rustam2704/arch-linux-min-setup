import datetime as dt
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import urllib.parse
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop/share/light-year"))
import api
import recurrence


class FakeGoogle:
    """Route local responses by method and path, while recording request order."""
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, path, method="GET", data=None, params=None, etag=None):
        self.calls.append((method, path, data, params, etag))
        response = self.routes[(method, path)]
        return response(data, params, etag) if callable(response) else response


class CalendarTests(unittest.TestCase):
    day = dt.date(2026, 9, 22)

    @staticmethod
    def timed_master(rule="RRULE:FREQ=DAILY"):
        return {"id": "series", "summary": "Lesson", "etag": "old",
                "start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                "end": {"dateTime": "2026-09-21T11:00:00+03:00"},
                "recurrence": [rule]}

    @staticmethod
    def timed_occurrence():
        start = dt.datetime.fromisoformat("2026-09-22T10:00:00+03:00")
        return {"id": "series_20260922", "recurring_id": "series", "all_day": False,
                "start": start, "end": start + dt.timedelta(hours=1),
                "original_start": start.isoformat()}

    def test_concurrent_token_writes_are_atomic_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tokens.json")
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i: api.write_json(path, {"google": {"token": str(i)}}), range(80)))
            with open(path) as f:
                self.assertIn(json.load(f)["google"]["token"], {str(i) for i in range(80)})
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(os.listdir(directory), ["tokens.json"])

    def test_invalid_grant_clears_google_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "tokens.json")
            api.write_json(path, {"google": {"refresh_token": "old"}, "zoom": {"access_token": "keep"}})
            with patch.object(api, "TOKENS", path), \
                 patch.object(api, "credentials", return_value={"google": {"client_id": "id"}}), \
                 patch.object(api, "request", side_effect=api.ApiError('400: {"error":"invalid_grant"}')):
                with self.assertRaisesRegex(api.ApiError, "Google sign-in expired - press Connect Google"):
                    api.google_token()
            self.assertEqual(api.read_json(path), {"zoom": {"access_token": "keep"}})

    def test_day_events_reuses_more_label(self):
        from widgets import DayEvents
        chip = Mock()
        chip.get_preferred_height.return_value = (1, 10)
        more = Mock()
        more.get_preferred_height.return_value = (1, 10)
        more.get_label.return_value = "+3 more"
        area = Mock(chips=[chip] * 3, expanded=False, row_height=1, more_height=1, more=more)
        DayEvents.layout(area, 1)
        more.set_label.assert_not_called()

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
        with patch.object(api, "google", return_value={"id": "created", "etag": "v1"}) as google:
            change = api.create_event("Test", start, start + dt.timedelta(hours=1), recurrence=rules)
            self.assertIsInstance(change, api.Change)
            self.assertEqual(change.steps, [("DELETE", "created", None, "v1")])
            self.assertEqual(google.call_args.args[2]["recurrence"], rules)
            self.assertEqual(google.call_args.args[2]["start"]["timeZone"], api.TZ)
            with self.assertRaises(ValueError):
                api.change_occurrence({"recurring_id": "series"}, "this", recurrence=rules)

    def test_failed_series_split_does_not_truncate_original(self):
        start = dt.datetime(2026, 9, 22, 10)
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start.astimezone(), "end": (start + dt.timedelta(hours=1)).astimezone(),
                 "original_start": start.astimezone().isoformat()}
        master = {"id": "series", "summary": "Test", "start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                  "end": {"dateTime": "2026-09-21T11:00:00+03:00"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, body))
            if path.endswith("/instances"):
                return {"items": []}
            if method == "POST":
                raise RuntimeError("API unavailable")
            return master
        with patch.object(api, "google", google), self.assertRaises(RuntimeError):
            api.change_occurrence(event, "following", summary="New title")
        self.assertEqual([method for method, _ in calls], ["GET", "GET", "POST"])

    def test_failed_series_truncation_deletes_new_series_and_surfaces_error(self):
        start = dt.datetime(2026, 9, 22, 10).astimezone()
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start, "end": start + dt.timedelta(hours=1),
                 "original_start": start.isoformat()}
        master = {"id": "series", "summary": "Test", "start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                  "end": {"dateTime": "2026-09-21T11:00:00+03:00"},
                  "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, path))
            if path.endswith("/instances"):
                return {"items": []}
            if method == "GET":
                return master
            if method == "POST":
                return {"id": "new-series"}
            if method == "PATCH":
                raise api.ApiError("Truncation failed")
            return {}
        with patch.object(api, "google", google), self.assertRaisesRegex(api.ApiError, "Truncation failed"):
            api.change_occurrence(event, "following", summary="New title")
        self.assertEqual([method for method, _ in calls], ["GET", "GET", "POST", "PATCH", "DELETE"])
        self.assertTrue(calls[-1][1].endswith("/new-series"))

    def test_failed_series_cleanup_reports_duplicate(self):
        start = dt.datetime(2026, 9, 22, 10).astimezone()
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start, "end": start + dt.timedelta(hours=1),
                 "original_start": start.isoformat()}
        master = {"id": "series", "summary": "Test", "start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                  "end": {"dateTime": "2026-09-21T11:00:00+03:00"},
                  "recurrence": ["RRULE:FREQ=DAILY"]}
        def google(path, method="GET", body=None, **kwargs):
            if path.endswith("/instances"):
                return {"items": []}
            if method == "GET":
                return master
            if method == "POST":
                return {"id": "new-series"}
            raise api.ApiError("Unavailable")
        with patch.object(api, "google", google), self.assertRaisesRegex(api.ApiError, "duplicate series may remain: new-series"):
            api.change_occurrence(event, "following", summary="New title")

    def test_all_day_update_and_visible_days(self):
        start = self.day
        end = start + dt.timedelta(days=3)
        before = {"id": "event", "summary": "Old", "start": {"date": start.isoformat()},
                  "end": {"date": end.isoformat()}}
        with patch.object(api, "google", side_effect=[before, {**before, "summary": "Renamed"}]) as google:
            change = api.update_event("event", summary="Renamed", start=start, end=end)
        self.assertIsInstance(change, api.Change)
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"date": start.isoformat(), "dateTime": None, "timeZone": None})
        self.assertEqual(body["end"], {"date": end.isoformat(), "dateTime": None, "timeZone": None})
        event = {"start": start, "end": end, "all_day": True}
        self.assertEqual(list(api.event_days(event, start, end)),
                         [start, start + dt.timedelta(days=1), start + dt.timedelta(days=2)])
        timed = {"start": dt.datetime(2026, 9, 22, 23, 30).astimezone(),
                 "end": dt.datetime(2026, 9, 24).astimezone(), "all_day": False}
        self.assertEqual(list(api.event_days(timed, start, end)),
                         [start, start + dt.timedelta(days=1)])

    def test_patch_switch_timed_to_all_day_clears_datetime(self):
        before = {"id": "event", "start": {"dateTime": "2026-09-22T10:00:00+03:00"},
                  "end": {"dateTime": "2026-09-22T11:00:00+03:00"}}
        with patch.object(api, "google", side_effect=[before, before]) as google:
            api.update_event("event", start=self.day, end=self.day + dt.timedelta(days=1))
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"date": "2026-09-22", "dateTime": None, "timeZone": None})
        self.assertEqual(body["end"], {"date": "2026-09-23", "dateTime": None, "timeZone": None})

    def test_patch_switch_all_day_to_timed_clears_date(self):
        start = dt.datetime(2026, 9, 22, 10)
        before = {"id": "event", "start": {"date": "2026-09-22"}, "end": {"date": "2026-09-23"}}
        with patch.object(api, "google", side_effect=[before, before]) as google:
            api.update_event("event", start=start, end=start + dt.timedelta(hours=1))
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"dateTime": "2026-09-22T10:00:00", "timeZone": api.TZ, "date": None})
        self.assertEqual(body["end"], {"dateTime": "2026-09-22T11:00:00", "timeZone": api.TZ, "date": None})

    def test_patch_timed_move_clears_date(self):
        start = dt.datetime(2026, 9, 23, 9, 30)
        before = {"id": "event", "start": {"dateTime": "2026-09-22T10:00:00+03:00"},
                  "end": {"dateTime": "2026-09-22T11:00:00+03:00"}}
        with patch.object(api, "google", side_effect=[before, before]) as google:
            api.update_event("event", start=start, end=start + dt.timedelta(minutes=45))
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"dateTime": "2026-09-23T09:30:00", "timeZone": api.TZ, "date": None})
        self.assertEqual(body["end"], {"dateTime": "2026-09-23T10:15:00", "timeZone": api.TZ, "date": None})

    def test_series_patch_clears_other_time_kind(self):
        timed = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": dt.datetime(2026, 9, 22, 10), "end": dt.datetime(2026, 9, 22, 11),
                 "original_start": "2026-09-22T10:00:00"}
        all_day = {"id": "occurrence", "recurring_id": "series", "all_day": True,
                   "start": self.day, "end": self.day + dt.timedelta(days=1),
                   "original_start": self.day.isoformat()}
        timed_master = {"id": "series", "summary": "Test", "start": {"dateTime": "2026-09-21T10:00:00"},
                        "end": {"dateTime": "2026-09-21T11:00:00"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        all_day_master = {"id": "series", "summary": "Test", "start": {"date": "2026-09-22"},
                          "end": {"date": "2026-09-23"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        cases = (
            ("timed move", timed, timed_master, dt.datetime(2026, 9, 23, 11), dt.datetime(2026, 9, 23, 12),
             {"dateTime": "2026-09-22T11:00:00", "timeZone": api.TZ, "date": None},
             {"dateTime": "2026-09-22T12:00:00", "timeZone": api.TZ, "date": None}),
            ("timed to all-day", timed, timed_master, dt.date(2026, 9, 23), dt.date(2026, 9, 24),
             {"date": "2026-09-22", "dateTime": None, "timeZone": None},
             {"date": "2026-09-23", "dateTime": None, "timeZone": None}),
            ("all-day to timed", all_day, all_day_master, dt.datetime(2026, 9, 23, 10), dt.datetime(2026, 9, 23, 11),
             {"dateTime": "2026-09-23T10:00:00", "timeZone": api.TZ, "date": None},
             {"dateTime": "2026-09-23T11:00:00", "timeZone": api.TZ, "date": None}),
        )
        for name, event, master, start, end, want_start, want_end in cases:
            with self.subTest(name), patch.object(api, "google") as google:
                google.side_effect = lambda path, method="GET", body=None, **kwargs: (
                    {"items": []} if path.endswith("/instances") else master)
                api.change_occurrence(event, "all", start=start, end=end)
                body = next(call.args[2] for call in google.call_args_list if len(call.args) > 2)
                self.assertEqual(body["start"], want_start)
                self.assertEqual(body["end"], want_end)
        # duration only: the master's end moves, its start is not sent
        with patch.object(api, "google") as google:
            google.side_effect = lambda path, method="GET", body=None, **kwargs: (
                {"items": []} if path.endswith("/instances") else timed_master)
            api.change_occurrence(timed, "all", start=timed["start"], end=timed["start"] + dt.timedelta(hours=2))
            body = next(call.args[2] for call in google.call_args_list if len(call.args) > 2)
        self.assertEqual(body["end"], {"dateTime": "2026-09-21T12:00:00", "timeZone": api.TZ, "date": None})
        self.assertNotIn("start", body)

    def test_all_day_following_split_uses_exclusive_dates(self):
        start = self.day
        event = {"id": "occurrence", "recurring_id": "series", "all_day": True,
                 "start": start, "end": start + dt.timedelta(days=2),
                 "original_start": start.isoformat()}
        master = {"id": "series", "summary": "Test", "start": {"date": "2026-09-21"},
                  "end": {"date": "2026-09-23"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, body))
            if path.endswith("/instances"):
                return {"items": []}
            return master if method == "GET" else {"id": "new-series"}
        with patch.object(api, "google", google):
            api.change_occurrence(event, "following", summary="Renamed", start=start,
                                  end=start + dt.timedelta(days=2))
        self.assertEqual(calls[2][1]["start"], {"date": start.isoformat()})
        self.assertEqual(calls[2][1]["end"], {"date": (start + dt.timedelta(days=2)).isoformat()})
        self.assertEqual([method for method, _ in calls], ["GET", "GET", "POST", "PATCH", "GET"])

    def test_failed_google_create_deletes_zoom_meeting(self):
        start = dt.datetime(2026, 9, 22, 10)
        def google(*args):
            raise api.ApiError("Google failed")
        with patch.object(api, "google", google), patch.object(api, "zoom", return_value={"id": 42, "join_url": "https://zoom.us/j/42"}) as zoom:
            with self.assertRaisesRegex(api.ApiError, "Google failed"):
                api.create_event("Call", start, start + dt.timedelta(hours=1), with_zoom=True)
        self.assertEqual(zoom.call_args.args, ("/meetings/42", "DELETE"))

    def test_failed_zoom_cleanup_is_visible(self):
        start = dt.datetime(2026, 9, 22, 10)
        def zoom(path, method, body=None):
            if method == "POST":
                return {"id": 42, "join_url": "https://zoom.us/j/42"}
            raise api.ApiError("Zoom cleanup failed")
        with patch.object(api, "google", side_effect=api.ApiError("Google failed")), patch.object(api, "zoom", zoom):
            with self.assertRaisesRegex(api.ApiError, "Google failed.*Zoom meeting 42.*Zoom cleanup failed"):
                api.create_event("Call", start, start + dt.timedelta(hours=1), with_zoom=True)

    def test_all_time_change_reapplies_exceptions_and_undoes_in_order(self):
        master = self.timed_master()
        moved_start = {"dateTime": "2026-09-25T15:00:00+03:00"}
        moved_end = {"dateTime": "2026-09-25T16:00:00+03:00"}
        exceptions = [
            {"id": "old-cancelled", "status": "cancelled",
             "originalStartTime": {"dateTime": "2026-09-22T10:00:00+03:00"}},
            {"id": "old-moved", "originalStartTime": {"dateTime": "2026-09-23T10:00:00+03:00"},
             "start": moved_start, "end": moved_end},
        ]
        phase = [0]
        def patch_master(body, params, etag):
            phase[0] += 1
            return {**master, "start": body["start"], "end": body["end"], "etag": "edited"}
        def instances(body, params, etag):
            if params.get("showDeleted"):
                return {"items": exceptions}
            prefix = "new" if phase[0] == 1 else "old"
            return {"items": [{"id": f"{prefix}-{day}",
                              "originalStartTime": {"dateTime": f"2026-09-{day}T10:00:00+03:00"}}
                             for day in (22, 23)]}
        base = "/calendars/primary/events/series"
        fake = FakeGoogle({("GET", base): lambda *_: {**master, "etag": "edited"} if phase[0] else master,
                           ("PATCH", base): patch_master,
                           ("GET", base + "/instances"): instances,
                           ("DELETE", "/calendars/primary/events/new-22"): {},
                           ("PATCH", "/calendars/primary/events/new-23"): {},
                           ("DELETE", "/calendars/primary/events/old-22"): {},
                           ("PATCH", "/calendars/primary/events/old-23"): {}})
        with patch.object(api, "google", fake):
            change = api.change_occurrence(self.timed_occurrence(), "all",
                                           start=dt.datetime(2026, 9, 22, 11),
                                           end=dt.datetime(2026, 9, 22, 12))
            self.assertEqual([s[0] for s in change.steps], ["REAPPLY", "PATCH"])
            self.assertEqual(change.steps[1][2]["start"]["dateTime"], master["start"]["dateTime"])
            self.assertIn(("DELETE", "/calendars/primary/events/new-22"),
                          [(m, p) for m, p, *_ in fake.calls])
            moved = next(data for method, path, data, *_ in fake.calls
                         if method == "PATCH" and path.endswith("/new-23"))
            self.assertEqual((moved["start"]["dateTime"], moved["end"]["dateTime"]),
                             (moved_start["dateTime"], moved_end["dateTime"]))
            before_undo = len(fake.calls)
            api.revert(change)
        undo = [(method, path) for method, path, *_ in fake.calls[before_undo:]
                if method != "GET"]
        self.assertEqual(undo, [("PATCH", base), ("DELETE", "/calendars/primary/events/old-22"),
                                ("PATCH", "/calendars/primary/events/old-23")])

    def test_following_split_copies_fields_reapplies_then_trims(self):
        master = {**self.timed_master("RRULE:FREQ=DAILY;UNTIL=20260930T070000Z"),
                  "attendees": [{"email": "guest@example.test"}],
                  "reminders": {"useDefault": False, "overrides": []},
                  "extendedProperties": {"private": {"zoomMeetingId": "42"}}, "colorId": "7"}
        base = "/calendars/primary/events/series"
        new = "/calendars/primary/events/new-series"
        cancelled = {"id": "old-23", "status": "cancelled",
                     "originalStartTime": {"dateTime": "2026-09-23T10:00:00+03:00"}}
        fake = FakeGoogle({("GET", base): master,
                           ("GET", base + "/instances"): lambda _, params, __: {"items": [cancelled]}
                           if params.get("showDeleted") else {"items": []},
                           ("POST", "/calendars/primary/events"): {"id": "new-series"},
                           ("GET", new + "/instances"): {"items": [{"id": "new-23",
                               "originalStartTime": cancelled["originalStartTime"]}]},
                           ("DELETE", "/calendars/primary/events/new-23"): {},
                           ("PATCH", base): {"etag": "trimmed"},
                           ("GET", new): {"etag": "new-etag"}})
        with patch.object(api, "google", fake):
            change = api.change_occurrence(self.timed_occurrence(), "following", summary="Renamed")
        post = next(data for method, _, data, *_ in fake.calls if method == "POST")
        self.assertEqual({k: post[k] for k in ("attendees", "reminders", "extendedProperties", "colorId")},
                         {k: master[k] for k in ("attendees", "reminders", "extendedProperties", "colorId")})
        actions = [(method, path) for method, path, *_ in fake.calls]
        self.assertLess(actions.index(("POST", "/calendars/primary/events")),
                        actions.index(("DELETE", "/calendars/primary/events/new-23")))
        self.assertLess(actions.index(("DELETE", "/calendars/primary/events/new-23")),
                        actions.index(("PATCH", base)))
        self.assertEqual([s[0] for s in change.steps], ["REAPPLY", "PATCH", "DELETE"])

    def test_following_trim_failure_deletes_new_series_after_reapply(self):
        master = self.timed_master("RRULE:FREQ=DAILY;UNTIL=20260930T070000Z")
        base = "/calendars/primary/events/series"
        new = "/calendars/primary/events/new-series"
        cancelled = {"id": "old-23", "status": "cancelled",
                     "originalStartTime": {"dateTime": "2026-09-23T10:00:00+03:00"}}
        fake = FakeGoogle({("GET", base): master,
                           ("GET", base + "/instances"): {"items": [cancelled]},
                           ("POST", "/calendars/primary/events"): {"id": "new-series"},
                           ("GET", new + "/instances"): {"items": [{"id": "new-23",
                               "originalStartTime": cancelled["originalStartTime"]}]},
                           ("DELETE", "/calendars/primary/events/new-23"): {},
                           ("PATCH", base): lambda *_: (_ for _ in ()).throw(api.ApiError("trim failed")),
                           ("DELETE", new): {}})
        with patch.object(api, "google", fake), self.assertRaisesRegex(api.ApiError, "trim failed"):
            api.change_occurrence(self.timed_occurrence(), "following")
        self.assertEqual([(m, p) for m, p, *_ in fake.calls if m != "GET"][-3:],
                         [("DELETE", "/calendars/primary/events/new-23"), ("PATCH", base), ("DELETE", new)])

    def test_following_count_until_includes_shifted_last_start(self):
        master = self.timed_master("RRULE:FREQ=DAILY;COUNT=3")
        base = "/calendars/primary/events/series"
        originals = [{"originalStartTime": {"dateTime": f"2026-09-{day}T10:00:00+03:00"}}
                     for day in (21, 22, 23)]
        fake = FakeGoogle({("GET", base): master,
                           ("GET", base + "/instances"): lambda _, params, __: {
                               "items": [] if params.get("showDeleted") else originals},
                           ("POST", "/calendars/primary/events"): {"id": "new-series"},
                           ("PATCH", base): {"etag": "trimmed"},
                           ("GET", "/calendars/primary/events/new-series"): {"etag": "new"}})
        with patch.object(api, "google", fake):
            api.change_occurrence(self.timed_occurrence(), "following",
                                  start=dt.datetime(2026, 9, 22, 11), end=dt.datetime(2026, 9, 22, 12))
        post = next(data for method, _, data, *_ in fake.calls if method == "POST")
        until = api._rrule_parts(post["recurrence"][0])[1]["UNTIL"]
        self.assertGreaterEqual(dt.datetime.strptime(until, "%Y%m%dT%H%M%SZ"),
                                dt.datetime(2026, 9, 23, 8))
        self.assertNotIn("COUNT", post["recurrence"][0])

    def test_following_all_day_until_is_date_only(self):
        master = {"id": "series", "summary": "Holiday", "start": {"date": "2026-09-21"},
                  "end": {"date": "2026-09-22"}, "recurrence": ["RRULE:FREQ=DAILY;UNTIL=20260930"]}
        event = {"id": "series_20260922", "recurring_id": "series", "all_day": True,
                 "start": self.day, "end": self.day + dt.timedelta(days=1),
                 "original_start": self.day.isoformat()}
        base = "/calendars/primary/events/series"
        fake = FakeGoogle({("GET", base): master,
                           ("GET", base + "/instances"): {"items": []},
                           ("POST", "/calendars/primary/events"): {"id": "new-series"},
                           ("PATCH", base): {"etag": "trimmed"},
                           ("GET", "/calendars/primary/events/new-series"): {"etag": "new"}})
        with patch.object(api, "google", fake):
            api.change_occurrence(event, "following", start=self.day + dt.timedelta(days=1),
                                  end=self.day + dt.timedelta(days=2))
        post = next(data for method, _, data, *_ in fake.calls if method == "POST")
        until = api._rrule_parts(post["recurrence"][0])[1]["UNTIL"]
        self.assertEqual(until, "20261001")

    def test_delete_occurrence_keeps_shared_zoom_meeting(self):
        event = {**self.timed_occurrence(), "extendedProperties": {"private": {"zoomMeetingId": "42"}}}
        path = "/calendars/primary/events/series_20260922"
        before = {"id": event["id"], "summary": "Lesson", "recurringEventId": "series",
                  "extendedProperties": event["extendedProperties"]}
        fake = FakeGoogle({("GET", path): before, ("DELETE", path): {}})
        with patch.object(api, "google", fake), patch.object(api, "zoom") as zoom:
            change = api.delete_occurrence(event, "this")
        self.assertEqual(change.meetings, [])
        self.assertEqual(change.steps, [("PATCH", event["id"], {"status": "confirmed"}, None)])
        zoom.assert_not_called()

    def test_delete_one_off_defers_zoom_release_until_unreferenced(self):
        path = "/calendars/primary/events/one"
        listing = "/calendars/primary/events"
        before = {"id": "one", "summary": "Call",
                  "extendedProperties": {"private": {"zoomMeetingId": "42"}}}
        fake = FakeGoogle({("GET", path): before, ("DELETE", path): {},
                           ("GET", listing): {"items": [{"id": "other"}]}})
        with patch.object(api, "google", fake), patch.object(api, "zoom") as zoom:
            change = api.delete_event("one")
            self.assertEqual(change.meetings, ["42"])
            zoom.assert_not_called()
            api.release_meeting("42")
        zoom.assert_not_called()
        self.assertEqual(fake.calls[-1][3]["privateExtendedProperty"], "zoomMeetingId=42")

    def test_move_occurrence_does_not_follow_zoom_but_one_off_does(self):
        old = {"id": "series_20260922", "summary": "Lesson", "recurringEventId": "series",
               "start": {"dateTime": "2026-09-22T10:00:00+03:00"},
               "end": {"dateTime": "2026-09-22T11:00:00+03:00"},
               "extendedProperties": {"private": {"zoomMeetingId": "42"}}}
        new = {**old, "start": {"dateTime": "2026-09-22T12:00:00+03:00"},
               "end": {"dateTime": "2026-09-22T13:00:00+03:00"}, "etag": "updated"}
        start, end = dt.datetime(2026, 9, 22, 12), dt.datetime(2026, 9, 22, 13)
        with patch.object(api, "google", side_effect=[old, new, {k: v for k, v in old.items()
                if k != "recurringEventId"}, {k: v for k, v in new.items() if k != "recurringEventId"}]), \
             patch.object(api, "zoom") as zoom:
            occurrence = api.change_occurrence(self.timed_occurrence(), "this", start=start, end=end)
            zoom.assert_not_called()
            one_off = api.update_event("one", start=start, end=end)
        self.assertIsInstance(occurrence, api.Change)
        self.assertIsInstance(one_off, api.Change)
        zoom.assert_called_once()
        self.assertEqual(zoom.call_args.args[:2], ("/meetings/42", "PATCH"))

    def test_revert_runs_steps_last_first_and_reports_stale_etag(self):
        change = api.Change("edited")
        change.inverse("DELETE", "first", None, "e1")
        change.inverse("PATCH", "second", {"summary": "old"}, "e2")
        fake = FakeGoogle({("DELETE", "/calendars/primary/events/first"): {},
                           ("PATCH", "/calendars/primary/events/second"): {}})
        with patch.object(api, "google", fake):
            api.revert(change)
        self.assertEqual([(m, p, etag) for m, p, _, _, etag in fake.calls],
                         [("PATCH", "/calendars/primary/events/second", "e2"),
                          ("DELETE", "/calendars/primary/events/first", "e1")])
        with patch.object(api, "google", side_effect=api.ApiError("412 Precondition Failed")):
            with self.assertRaises(api.ApiError) as error:
                api.revert(change)
        self.assertTrue(str(error.exception).startswith("Not undone"))

    def test_change_loosen_drops_series_and_occurrence_etags_only(self):
        change = api.Change("edited")
        change.inverse("PATCH", "series", {}, "master-etag")
        change.inverse("DELETE", "series_20260922", None, "instance-etag")
        change.inverse("PATCH", "other", {}, "other-etag")
        change.inverse("REAPPLY", "series", [])
        change.loosen({"series"})
        self.assertEqual([step[3] for step in change.steps[:3]], [None, None, "other-etag"])
        self.assertEqual(change.steps[3], ("REAPPLY", "series", []))

    def test_google_sends_if_match_for_etag(self):
        with patch.object(api, "google_token", return_value="token"), \
             patch.object(api, "request", return_value={}) as request:
            api.google("/calendars/primary/events/one", "PATCH", {"summary": "New"}, etag="etag-1")
        self.assertEqual(request.call_args.args[3]["If-Match"], "etag-1")

    def test_oauth_ignores_wrong_path_and_state(self):
        opened = []
        handled = []
        finished = threading.Event()
        outcomes = []

        class Server:
            def __init__(self, address, handler):
                self.handler = handler
                self.timeout = None

            def handle_request(self):
                auth = urllib.parse.parse_qs(urllib.parse.urlparse(opened[0]).query)
                state = auth["state"][0]
                path = ("/unrelated?code=bad&state=" + state,
                        "/oauth2callback?code=bad&state=wrong",
                        "/oauth2callback?state=" + state,
                        "/oauth2callback?code=good&state=" + state)[len(handled)]
                request = self.handler.__new__(self.handler)
                request.path = path
                request.wfile = io.BytesIO()
                request.send_error = Mock()
                request.send_response = Mock()
                request.send_header = Mock()
                request.end_headers = Mock()
                request.do_GET()
                handled.append(request)

            def server_close(self):
                pass

        def popen(args, **kwargs):
            opened.append(args[1])
        def done(error):
            outcomes.append(error)
            finished.set()
        with patch.object(api, "credentials", return_value={"google": {"client_id": "client", "client_secret": "secret"}}), \
             patch.object(api.http.server, "HTTPServer", Server), patch.object(api.subprocess, "Popen", popen), \
             patch.object(api, "request", return_value={"refresh_token": "refresh", "access_token": "access"}) as token_request, \
             patch.object(api, "tokens", return_value={}), patch.object(api, "write_json"):
            api.google_sign_in(done)
            self.assertTrue(finished.wait(2))
        self.assertEqual(outcomes, [None])
        self.assertEqual(len(handled), 4)
        self.assertTrue(all(item.send_error.called for item in handled[:3]))
        self.assertEqual(token_request.call_args.args[2]["code"], "good")


if __name__ == "__main__":
    unittest.main()
