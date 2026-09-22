"""Synthetic UI only: no credentials, no real calendar API, no desktop interaction."""
import datetime as dt
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "desktop/share/sky-desktop"), str(ROOT / "desktop/share/light-year")]
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk
import app
from widgets import DayEvents, RecurrencePicker


def settle():
    end = time.monotonic() + .15
    loops = 0
    while time.monotonic() < end:
        if Gtk.events_pending():
            Gtk.main_iteration_do(False)
            loops += 1
        else:
            time.sleep(.002)
    assert loops < 3000, "layout is continuously reallocating"


provider = Gtk.CssProvider()
provider.load_from_data(app.CSS.encode())
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
with patch.object(app.Window, "refresh_state", lambda self: None):
    window = app.Window(None)
today = dt.date.today()
start = dt.datetime.combine(today, dt.time(9)).astimezone()
window.events = [dict(id=str(i), start=start + dt.timedelta(minutes=15*i),
                      end=start + dt.timedelta(minutes=15*i+15), all_day=False,
                      summary=f"Synthetic meeting {i+1}", description="", zoom="") for i in range(20)]
window.draw()
window.show_all()
settle()
area = next(cell.get_child().get_children()[-1] for cell in window.grid.get_children()
            if cell.get_child().get_children()[-1].chips)
assert isinstance(area, DayEvents)
assert area.more.get_visible()
assert 0 < sum(c.get_visible() for c in area.chips) < 20
area.more.clicked()
settle()
assert all(c.get_visible() for c in area.chips)
assert area.scroll.get_vadjustment().get_upper() > area.scroll.get_vadjustment().get_page_size()
area.more.clicked()
settle()
count = sum(c.get_visible() for c in area.chips)
window.resize(1600, 1600)
settle()
assert sum(c.get_visible() for c in area.chips) > count
window.events = window.events[:5]
window.draw()
settle()
area = next(cell.get_child().get_children()[-1] for cell in window.grid.get_children()
            if cell.get_child().get_children()[-1].chips)
assert all(c.get_visible() for c in area.chips), "five events should fit in a large cell"
assert not area.more.get_visible()
dialog = app.EventDialog(window, today)
settle()
repeat = dialog.repeat
assert repeat.days == {today.weekday()}
repeat.choose("custom")
assert repeat.week.get_visible()
repeat.day_buttons[(today.weekday()+1) % 7].set_active(True)
assert len(repeat.days) == 2
assert "BYDAY=" in repeat.values(today)[0]
repeat.choose("monthly")
assert not repeat.week.get_visible()
assert repeat.values(today) == ["RRULE:FREQ=MONTHLY"]
assert dialog.get_widget_for_response(Gtk.ResponseType.OK).get_label() == "Create"
dialog.destroy()
window.destroy()
print("GTK smoke: recurrence, overflow, expand/collapse, scrolling, resize and five-event capacity passed")
