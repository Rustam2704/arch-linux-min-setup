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

# 1. show() rebuilds the grid only when month, today or events differ
events = [dict(id=f"s{i}", start=start + dt.timedelta(hours=i), end=start + dt.timedelta(hours=i, minutes=30),
               all_day=False, summary=f"Show {i}", description="", zoom="") for i in range(3)]
window.show(list(events))
first = list(window.grid.get_children())
assert first
window.show([dict(e) for e in events])
assert len(first) == len(window.grid.get_children()) and all(a is b for a, b in zip(first, window.grid.get_children())), \
    "equal events must not rebuild the grid"
window.show(events[:2])
second = list(window.grid.get_children())
assert all(not any(a is b for b in first) for a in second), "changed events must rebuild the grid"
window.show(events[:2])
assert all(a is b for a, b in zip(second, window.grid.get_children())), "same events again must not rebuild"
window.show(list(events))
settle()

# 2. mark_editing: the "editing" class and the placeholder chip, no rebuild
cells = list(window.grid.get_children())
window.editing_id = "s0"
assert window.chips_of["s0"]
window.mark_editing(True)
assert all(c.get_style_context().has_class("editing") for c in window.chips_of["s0"])
assert not window.chips_of["s1"][0].get_style_context().has_class("editing")
window.mark_editing(False)
assert not any(c.get_style_context().has_class("editing") for c in window.chips_of["s0"])
assert all(a is b for a, b in zip(cells, window.grid.get_children())), "mark_editing must not rebuild the grid"
window.editing_id = None
pend = today + dt.timedelta(days=1) if (today + dt.timedelta(days=1)).month == window.cursor.month else today - dt.timedelta(days=1)
assert pend in window.areas
before = len(window.areas[pend].chips)
window.pending_day = pend
window.mark_editing(True)
assert len(window.areas[pend].chips) == before + 1
assert window.placeholder_chip in window.areas[pend].chips
assert window.placeholder_chip.get_style_context().has_class("editing")
window.mark_editing(False)
assert len(window.areas[pend].chips) == before
assert window.placeholder_chip is None and window.placeholder_area is None
window.pending_day = None
assert all(a is b for a, b in zip(cells, window.grid.get_children())), "placeholder must not rebuild the grid"

# 3. add_chip / remove_chip keep the "+N more" logic right
many = [dict(id=f"m{i}", start=start + dt.timedelta(minutes=15*i), end=start + dt.timedelta(minutes=15*i+15),
             all_day=False, summary=f"Many {i}", description="", zoom="") for i in range(20)]
window.show(many)
settle()
area = window.areas[today]
assert area.more.get_visible() and area.more.get_label().startswith("+"), "20 chips overflow"
for chip in list(area.chips)[2:]:
    area.remove_chip(chip)
settle()
assert len(area.chips) == 2 and not area.more.get_visible(), "two chips fit, no more button"
for i in range(20):
    area.add_chip(window.placeholder())
settle()
assert len(area.chips) == 22 and area.more.get_visible() and area.more.get_label().startswith("+"), "added chips overflow"
assert 0 < sum(c.get_visible() for c in area.chips) < 22
window.show([])
settle()

# 4. EventDialog end note and end date for long, overnight and short events
friday = today + dt.timedelta(days=(4 - today.weekday()) % 7)
long_ev = dict(id="L", start=dt.datetime.combine(friday, dt.time(10)).astimezone(),
               end=dt.datetime.combine(friday + dt.timedelta(days=2), dt.time(12)).astimezone(),
               all_day=False, summary="Long", description="", zoom="")
dlg = app.EventDialog(window, friday, long_ev)
settle()
_, s_, e_, _ = dlg.values()
assert (s_, e_) == (long_ev["start"].replace(tzinfo=None), long_ev["end"].replace(tzinfo=None)), (s_, e_)
assert dlg.end_note.get_text().startswith("Ends"), dlg.end_note.get_text()
dlg.end.set_time("09:00")
dlg._end_moved("09:00")
_, s_, e_, _ = dlg.values()
assert e_ == dt.datetime.combine(friday + dt.timedelta(days=2), dt.time(9)), e_
assert s_ == dt.datetime.combine(friday, dt.time(10)), s_
dlg.destroy()
night = dict(long_ev, id="N", start=dt.datetime.combine(friday, dt.time(23)).astimezone(),
             end=dt.datetime.combine(friday + dt.timedelta(days=1), dt.time(1)).astimezone())
dlg = app.EventDialog(window, friday, night)
_, s_, e_, _ = dlg.values()
assert e_ == dt.datetime.combine(friday + dt.timedelta(days=1), dt.time(1)), e_
assert dlg.end_note.get_text().startswith("Ends")
dlg.destroy()
short = dict(long_ev, id="S", start=dt.datetime.combine(friday, dt.time(10)).astimezone(),
             end=dt.datetime.combine(friday, dt.time(11)).astimezone())
dlg = app.EventDialog(window, friday, short)
assert dlg.end_note.get_text() == "\u00a0", repr(dlg.end_note.get_text())
dlg.destroy()

# 5. Undo button follows the history (nothing may reach the network)
with patch.object(app.api, "release_meeting", lambda *a, **k: None), patch.object(app, "run_async", lambda w, d: None):
    window.history.clear()
    window.update_undo()
    assert not window.undo_btn.get_sensitive()
    window.remember(app.api.Change("created \u201cX\u201d"))
    assert window.undo_btn.get_sensitive()
    assert "created" in window.undo_btn.get_tooltip_text(), window.undo_btn.get_tooltip_text()
    window.history.clear()
    window.update_undo()
    assert not window.undo_btn.get_sensitive()

# 6. A long status message never widens the window's minimum width
window.set_status("", False)
settle()
width = window.get_preferred_width()
window.set_status("x" * 3000, True)
settle()
assert window.get_preferred_width() == width, (width, window.get_preferred_width())
assert window.status.get_style_context().has_class("error")
window.set_status("")

# 7. keyboard helper exists (a real key test needs a real keyboard)
assert callable(app.physical_key_name)

window.destroy()
print("GTK smoke: recurrence, overflow, expand/collapse, scrolling, resize, five-event capacity, show/mark_editing, chips, dialog end, undo and status passed")
