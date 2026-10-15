"""Calendar UI regressions; run under xvfb-run for a GTK display."""
import datetime as dt
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "desktop/share/sky-desktop"), str(ROOT / "desktop/share/light-year")]
if os.environ.get("LIGHTYEAR_TEST_DISPLAY"):
    import app


@unittest.skipUnless(os.environ.get("LIGHTYEAR_TEST_DISPLAY"), "requires a test GTK display")
class LightYearUiTests(unittest.TestCase):
    def setUp(self):
        with patch.object(app.Window, "refresh_state", lambda self: None):
            self.window = app.Window(None)
        self.window.state = {"google": True, "zoom": False}

    def tearDown(self):
        self.window.destroy()

    def test_edit_all_day_keeps_exclusive_date_end(self):
        day = dt.date(2026, 9, 22)
        event = {"id": "all-day", "summary": "Holiday", "start": day,
                 "end": day + dt.timedelta(days=3), "all_day": True, "description": ""}
        dialog = app.EventDialog(self.window, day, event)
        dialog.title.set_text("Renamed")
        self.assertEqual(dialog.values(),
                         ("Renamed", day, day + dt.timedelta(days=3), ""))
        self.assertFalse(dialog.start.get_sensitive())
        dialog.destroy()

    def test_failed_drag_restores_position_and_keeps_error_through_reload(self):
        start = dt.datetime(2026, 9, 22, 10).astimezone()
        event = {"id": "event", "summary": "Meeting", "start": start,
                 "end": start + dt.timedelta(hours=1), "all_day": False,
                 "description": "", "zoom": ""}
        self.window.events = [event]
        self.window.cursor = start.date().replace(day=1)
        def async_error(work, done):
            try:
                done(work(), None)
            except Exception as error:
                done(None, str(error))
        with patch.object(app, "run_async", async_error), \
             patch.object(app.api, "change_occurrence", side_effect=app.api.ApiError("Move failed")), \
             patch.object(self.window, "fetch", lambda key, done: done([event], None)):
            self.window.finish_drop(event, start + dt.timedelta(days=1),
                                    start + dt.timedelta(days=1, hours=1))
            self.assertEqual(event["start"], start)
            self.assertEqual(self.window.status.get_text(), "Move failed")
            self.window.load(force=True)
            self.assertEqual(self.window.status.get_text(), "Move failed")
            self.window.clear_mutation_error()
            self.window.load(force=True)
            self.assertEqual(self.window.status.get_text(), "Google")
