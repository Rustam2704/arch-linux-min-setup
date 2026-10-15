import datetime as dt
import io
from pathlib import Path
import sys
import threading
import urllib.parse
import unittest
from unittest.mock import Mock, patch

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

    def test_failed_series_truncation_deletes_new_series_and_surfaces_error(self):
        start = dt.datetime(2026, 9, 22, 10).astimezone()
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start, "end": start + dt.timedelta(hours=1),
                 "original_start": start.isoformat()}
        master = {"start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                  "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, path))
            if method == "GET":
                return master
            if method == "POST":
                return {"id": "new-series"}
            if method == "PATCH":
                raise api.ApiError("Truncation failed")
            return {}
        with patch.object(api, "google", google), self.assertRaisesRegex(api.ApiError, "Truncation failed"):
            api.change_occurrence(event, "following", summary="New title")
        self.assertEqual([method for method, _ in calls], ["GET", "POST", "PATCH", "DELETE"])
        self.assertTrue(calls[-1][1].endswith("/new-series"))

    def test_failed_series_cleanup_reports_duplicate(self):
        start = dt.datetime(2026, 9, 22, 10).astimezone()
        event = {"id": "occurrence", "recurring_id": "series", "all_day": False,
                 "start": start, "end": start + dt.timedelta(hours=1),
                 "original_start": start.isoformat()}
        master = {"start": {"dateTime": "2026-09-21T10:00:00+03:00"},
                  "recurrence": ["RRULE:FREQ=DAILY"]}
        def google(path, method="GET", body=None, **kwargs):
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
        with patch.object(api, "google", return_value={}) as google:
            api.update_event("event", summary="Renamed", start=start, end=end)
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
        with patch.object(api, "google", return_value={}) as google:
            api.update_event("event", start=self.day, end=self.day + dt.timedelta(days=1))
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"date": "2026-09-22", "dateTime": None, "timeZone": None})
        self.assertEqual(body["end"], {"date": "2026-09-23", "dateTime": None, "timeZone": None})

    def test_patch_switch_all_day_to_timed_clears_date(self):
        start = dt.datetime(2026, 9, 22, 10)
        with patch.object(api, "google", return_value={}) as google:
            api.update_event("event", start=start, end=start + dt.timedelta(hours=1))
        body = google.call_args.args[2]
        self.assertEqual(body["start"], {"dateTime": "2026-09-22T10:00:00", "timeZone": api.TZ, "date": None})
        self.assertEqual(body["end"], {"dateTime": "2026-09-22T11:00:00", "timeZone": api.TZ, "date": None})

    def test_patch_timed_move_clears_date(self):
        start = dt.datetime(2026, 9, 23, 9, 30)
        with patch.object(api, "google", return_value={}) as google:
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
        timed_master = {"start": {"dateTime": "2026-09-21T10:00:00"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        all_day_master = {"start": {"date": "2026-09-22"}, "recurrence": ["RRULE:FREQ=DAILY"]}
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
            with self.subTest(name), patch.object(api, "google", side_effect=[master, {}]) as google:
                api.change_occurrence(event, "all", start=start, end=end)
                body = google.call_args_list[1].args[2]
                self.assertEqual(body["start"], want_start)
                self.assertEqual(body["end"], want_end)
        # duration only: the master's end moves, its start is not sent
        with patch.object(api, "google", side_effect=[timed_master, {}]) as google:
            api.change_occurrence(timed, "all", start=timed["start"], end=timed["start"] + dt.timedelta(hours=2))
            body = google.call_args_list[1].args[2]
        self.assertEqual(body["end"], {"dateTime": "2026-09-21T12:00:00", "timeZone": api.TZ, "date": None})
        self.assertNotIn("start", body)

    def test_all_day_following_split_uses_exclusive_dates(self):
        start = self.day
        event = {"id": "occurrence", "recurring_id": "series", "all_day": True,
                 "start": start, "end": start + dt.timedelta(days=2),
                 "original_start": start.isoformat()}
        master = {"start": {"date": "2026-09-21"}, "recurrence": ["RRULE:FREQ=DAILY"]}
        calls = []
        def google(path, method="GET", body=None, **kwargs):
            calls.append((method, body))
            return master if method == "GET" else {"id": "new-series"}
        with patch.object(api, "google", google):
            api.change_occurrence(event, "following", summary="Renamed", start=start,
                                  end=start + dt.timedelta(days=2))
        self.assertEqual(calls[1][1]["start"], {"date": start.isoformat()})
        self.assertEqual(calls[1][1]["end"], {"date": (start + dt.timedelta(days=2)).isoformat()})
        self.assertEqual([method for method, _ in calls], ["GET", "POST", "PATCH"])

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
