#!/usr/bin/env python3
"""light-year — a small month calendar for Google Calendar, with Zoom meetings.

A native GTK3 window, no browser engine: month grid, create, edit, drag an event
to another day, delete, Zoom link on request, Reload. One process; closing the
window ends it. Launching it again just brings the open window forward.

Keys: ← → month · T today · F5 / Ctrl+R reload · Esc close a dialog
"""
import calendar
import datetime as dt
import os
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import gi  # noqa: E402
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

import api  # noqa: E402
from widgets import RecurrencePicker, DayEvents
sys.path.insert(0, os.path.expanduser("~/.local/share/sky-desktop"))
from sky_theme import gtk_css

APP_ID = "space.fanatic.lightyear"
ACCENT = "#48daf9"
REFRESH_MS = 5 * 60 * 1000

CSS = """
window, .ly { background-color: #0a0e11; color: #dfe8ee; }
.ly * { font-family: Inter; }
.ly-bar { padding: 10px 16px; border-bottom: 1px solid #1e262c; }
.ly-title { font-size: 17pt; font-weight: 600; }
.ly-status { color: #5b6b76; font-size: 9.5pt; }
.ly-status.error { color: #e05561; }
.ly button { background: #12171a; color: #dfe8ee; border: 1px solid #1e262c; border-radius: 8px;
             padding: 4px 12px; box-shadow: none; text-shadow: none; -gtk-icon-shadow: none; }
.ly button:hover { border-color: ACCENT; background: #12171a; }
.ly button.primary { background: ACCENT; color: #05222c; border-color: ACCENT; font-weight: 600; }
.ly button.danger:hover { border-color: #e05561; color: #e05561; }
.ly-weekday { color: #5b6b76; font-size: 8.5pt; padding: 6px 8px 4px 8px; }
.ly-grid { background-color: #1e262c; margin: 0 16px 16px 16px; }
/* columns: Mon/Wed/Fri get 2% white, Saturday and Sunday 2% red */
.ly-day { background-color: #0a0e11; padding: 4px 6px; }
.ly-day.tint { background-color: #0f1316; }
.ly-day.weekend { background-color: #0f0e11; }
.ly-day.other { background-color: #080b0d; }
.ly-day.other.tint { background-color: #0b0e10; }
.ly-day.other.weekend { background-color: #0b0b0d; }
.ly-day.past label { opacity: 0.55; }          /* days gone by are paler */
.ly-day.drop { background-color: #0f1d24; }
.ly-num { color: #5b6b76; font-size: 9.5pt; padding: 0 6px; border-radius: 6px; }
.ly-day.today .ly-num { background-color: ACCENT; color: #05222c; font-weight: 600; }
.ly-chip { background-color: rgba(72, 218, 249, 0.16); border-left: 3px solid ACCENT;
           border-radius: 5px; padding: 2px 5px; margin-top: 3px; }
/* the event being edited (and the placeholder for a new one) stands out in yellow */
.ly-chip.editing { background-color: rgba(255, 209, 102, 0.30); border-left-color: #ffd166; }
.ly-chip.editing label, .ly-chip.editing .time { color: #ffd166; }
.ly-chip:hover { background-color: rgba(72, 218, 249, 0.28); }
.ly-chip label { font-size: 9pt; }
.ly-chip .time { color: ACCENT; font-size: 8.5pt; }
.ly-more { color: #5b6b76; font-size: 8.5pt; padding: 2px 5px; }
.ly entry, .ly textview, .ly textview text { background-color: #0a0e11; color: #dfe8ee;
             border: 1px solid #1e262c; border-radius: 8px; }
.ly entry:focus { border-color: ACCENT; }
.ly-label { color: #5b6b76; font-size: 9pt; }
.ly-error { color: #e05561; font-size: 9pt; }
/* the mini calendar behind the date field */
.mini { padding: 8px; }
.mini button.mini-day { padding: 0; min-width: 32px; min-height: 28px; border: none;
                        background: none; border-radius: 14px; color: #dfe8ee; font-size: 9.5pt; }
.mini button.mini-day:hover { background-color: rgba(72, 218, 249, 0.22); border: none; }
.mini button.mini-day.other { color: #39434a; }
.mini button.mini-day.past { color: #5b6b76; }
.mini button.mini-day.today { background-color: rgba(72, 218, 249, 0.16); color: ACCENT; }
.mini button.mini-day.selected { background-color: #0d8ecb; color: #04212c; font-weight: 700; }
.mini-head { font-weight: 600; font-size: 10pt; }
/* drop-down lists live in their own windows and would be white otherwise */
window.popup, window.background.popup, .ly combobox window { background-color: #0a0e11; }
treeview.view, menu, popover { background-color: #0a0e11; color: #dfe8ee; }
treeview.view:hover, menu menuitem:hover { background-color: rgba(72, 218, 249, 0.22); }
treeview.view:selected, menu menuitem:selected { background-color: #0d8ecb; color: #04212c; }
menu menuitem { color: #dfe8ee; padding: 3px 8px; }
scrollbar { background-color: #0a0e11; }
/* the list of times below a time field */
.ly-times, .ly-times list { background-color: #0a0e11; }
.ly-times row { padding: 3px 10px; color: #dfe8ee; }
.ly-times row:hover { background-color: rgba(72, 218, 249, 0.22); }
.ly-times row:selected { background-color: #0d8ecb; color: #04212c; font-weight: 600; }
.ly-times-frame { background-color: #0a0e11; border: 1px solid #1e262c; }
.mini-weekday { color: #5b6b76; font-size: 8pt; }
""".replace("ACCENT", ACCENT)
CSS = gtk_css(CSS) + "\n.ly button:checked { background: #0d8ecb; color: #000000; }\n.ly button.ly-more { padding: 0 5px; min-height: 0; border: none; font-size: 8.5pt; }"


def run_async(work, done):
    """Run work() in a thread, hand (result, error) to done() on the GTK thread."""
    def target():
        try:
            res, err = work(), None
        except Exception as e:               # noqa: BLE001 - every failure is shown
            res, err = None, str(e)
        GLib.idle_add(lambda: done(res, err) and False)
    threading.Thread(target=target, daemon=True).start()


def month_grid(year, month):
    """Six weeks, always, starting on the Monday on or before the 1st. Some months
    need six and some only five, but a grid that changes height moves every row
    under it - the month should change, not the shape of the window."""
    first = dt.date(year, month, 1)
    start = first - dt.timedelta(days=first.weekday())
    return [start + dt.timedelta(days=i) for i in range(6 * 7)]


TIMES = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]


def normalize_time(text):
    """What the user typed -> "HH:MM", the way the list would complete it:
    "9" -> 09:00, "15" -> 15:00, "9:3"/"930"/"9.30" -> 09:30. None if unreadable."""
    t = text.strip().replace(".", ":").replace(",", ":").replace(" ", "")
    if not t:
        return None
    if ":" in t:
        h, _, m = t.partition(":")
        m = m or "0"
    elif len(t) <= 2:
        h, m = t, "0"
    else:
        h, m = t[:-2], t[-2:]
    if not (h.isdigit() and m.isdigit()):
        return None
    h, m = int(h), int(m) * 10 if len(m) == 1 else int(m)
    if h > 23 or m > 59:
        return None
    return f"{h:02d}:{m:02d}"


def type_time(text):
    """How the digits typed so far should read, colon drawn in: "123" -> "12:3".
    A first digit of 3-9 (or 25..29) can only be a one-digit hour, so the rest is
    minutes at once: "345" -> "3:45"."""
    d = "".join(c for c in text if c.isdigit())[:4]
    if not d:
        return ""
    two_digit_hour = d[0] in "012" and not (d[0] == "2" and len(d) > 1 and d[1] > "3")
    if two_digit_hour:
        return f"{d[:2]}:{d[2:4]}" if len(d) > 2 else d
    return f"{d[0]}:{d[1:3]}" if len(d) > 1 else d[0]


class TimeField(Gtk.Entry):
    """A time in 15-minute steps. Clicking the field drops the list of times below it
    (its own window, so it always opens downwards and never covers the field), with
    the event's own time picked out; the list scrolls by the bar on its right or with
    two fingers. Typing works as well: the colon is drawn for you, so "345" reads as
    3:45 while typing and settles as 03:45."""
    LIST_HEIGHT = 280

    def __init__(self, value, on_change=None):
        super().__init__(width_chars=7)          # Enter settles the time, it does not save
        self.on_change = on_change
        self._editing = False
        self._value = ""
        self._restore = None        # the time to put back when nothing is typed
        self._watching = None
        self.popup = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.popup.set_type_hint(Gdk.WindowTypeHint.COMBO)
        self.popup.get_style_context().add_class("ly")
        frame = Gtk.Frame(shadow_type=Gtk.ShadowType.IN)
        frame.get_style_context().add_class("ly-times-frame")
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           vscrollbar_policy=Gtk.PolicyType.ALWAYS)
        self.scroller.set_overlay_scrolling(False)      # a real bar on the right
        self.scroller.set_kinetic_scrolling(True)       # two fingers, as everywhere else
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        self.list.get_style_context().add_class("ly-times")
        self.rows = {}
        for t in TIMES:
            row = Gtk.ListBoxRow()
            row.time = t
            row.add(Gtk.Label(label=t, xalign=0))
            self.rows[t] = row
            self.list.add(row)
        self.list.connect("row-activated", self._picked)
        self.popup.connect("button-press-event", self._popup_press)
        self.popup.connect("key-press-event", self._popup_key)
        self.scroller.add(self.list)
        frame.add(self.scroller)
        self.popup.add(frame)
        self.set_time(value)
        self.connect("changed", self._typed)
        self.connect("button-press-event", self._pressed)
        self.connect("key-press-event", self._key)
        self.connect("activate", self._settle)
        self.connect("focus-out-event", self._settle)
        self.connect("destroy", lambda *_: self.popup.destroy())
        self.connect("hierarchy-changed", self._watch_toplevel)

    # --- the list -------------------------------------------------------------
    def _watch_toplevel(self, *_):
        """Close the list when the dialog itself is clicked elsewhere or loses focus."""
        top = self.get_toplevel()
        if not isinstance(top, Gtk.Window) or top is self._watching:
            return
        self._watching = top
        top.connect("configure-event", lambda *_: (self.close(), False)[1])
        top.connect("delete-event", lambda *_: (self.close(), False)[1])

    def _pressed(self, *_):
        """A click starts a fresh entry: the field empties, and the time that was in
        it comes back if nothing is typed (or Escape is pressed)."""
        if not self.popup.get_visible():
            self._restore = self._value
            self._editing = True
            self.set_text("")
            self._editing = False
        GLib.idle_add(self.open)
        return False

    def open(self):
        if self.popup.get_visible():
            return False
        top = self.get_toplevel()
        if not isinstance(top, Gtk.Window) or not top.get_window():
            return False
        alloc = self.get_allocation()
        ox, oy = top.get_window().get_origin()[1:]
        wx, wy = self.translate_coordinates(top, 0, 0) or (0, 0)
        self.popup.set_transient_for(top)
        self.popup.set_size_request(max(alloc.width, 110), self.LIST_HEIGHT)
        self.popup.move(ox + wx, oy + wy + alloc.height + 2)
        row = self.rows.get(self._nearest())
        if row:
            self.list.select_row(row)
        self.popup.show_all()
        # the dialog is modal and holds a GTK grab, so without one of our own every
        # click would fall through the list into the dialog underneath
        self.popup.grab_add()
        GLib.idle_add(self._scroll_to_selected)
        return False

    def close(self):
        if self.popup.get_visible():
            self.popup.grab_remove()
            self.popup.hide()

    def _popup_press(self, _w, event):
        """With the grab in place, clicks anywhere arrive here; the ones that miss
        the list close it."""
        win = self.popup.get_window()
        if win:
            ox, oy = win.get_origin()[1:]
            if (ox <= event.x_root < ox + self.popup.get_allocated_width()
                    and oy <= event.y_root < oy + self.popup.get_allocated_height()):
                return False
        self.close()
        return True

    def _popup_key(self, _w, event):
        """Typing keeps going into the field, which still holds the keyboard focus."""
        top = self.get_toplevel()
        return top.propagate_key_event(event) if isinstance(top, Gtk.Window) else False

    def _nearest(self):
        """The list entry the field is closest to right now."""
        fixed = normalize_time(self.get_text()) or self._value or TIMES[0]
        if fixed in self.rows:
            return fixed
        h, m = (int(x) for x in fixed.split(":"))
        return f"{h:02d}:{m // 15 * 15:02d}"

    def _scroll_to_selected(self):
        row = self.list.get_selected_row()
        adj = self.scroller.get_vadjustment()
        if row is None or adj is None:
            return False
        y = row.get_allocation().y
        adj.set_value(max(0, min(y, adj.get_upper() - adj.get_page_size())))
        return False

    def _picked(self, _list, row):
        self.close()
        self._restore = None
        self._editing = True                 # set_time would move _value first, and
        self.set_text(row.time)              # then the change would look like none
        self._editing = False
        self._announce(row.time)

    # --- typing ---------------------------------------------------------------
    def _key(self, _w, event):
        if event.keyval == Gdk.KEY_Escape:
            if self._restore:                 # give up on this entry, keep the old time
                self.set_time(self._restore)
                self._restore = None
            if self.popup.get_visible():
                self.close()
                return True
        return False

    def _typed(self, *_):
        if self._editing:
            return
        text = self.get_text()
        shown = type_time(text)
        if shown != text:
            self._editing = True
            self.set_text(shown)
            self._editing = False
            # after this handler: GTK puts the cursor where the raw character went,
            # which is behind the colon we just drew
            GLib.idle_add(lambda: (self.set_position(-1), False)[1])
        row = self.rows.get(self._nearest())
        if row:
            self.list.select_row(row)
            if self.popup.get_visible():
                GLib.idle_add(self._scroll_to_selected)

    def set_time(self, value):
        self._value = value if isinstance(value, str) else value.strftime("%H:%M")
        self._editing = True
        self.set_text(self._value)
        self._editing = False

    def get_time(self):
        return normalize_time(self.get_text())

    def _settle(self, *_):
        """Enter, or the focus leaving: pad what was typed out to HH:MM. An empty
        field means the click was a false start, so the old time comes back."""
        fixed = normalize_time(self.get_text()) or self._restore
        self._restore = None
        if fixed and fixed != self.get_text():
            self._editing = True
            self.set_text(fixed)
            self._editing = False
        self.close()
        if fixed:
            self._announce(fixed)
        return False

    def _announce(self, fixed):
        if fixed != self._value:
            self._value = fixed
            if self.on_change:
                self.on_change(fixed)


class MiniCalendar(Gtk.Box):
    """The month behind a date field: the chosen day in a dark circle, today in a pale
    one, days gone by dimmer, and the day under the pointer highlighted."""
    def __init__(self, day, on_pick):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.get_style_context().add_class("mini")
        self.selected = day
        self.shown = day.replace(day=1)
        self.on_pick = on_pick
        head = Gtk.Box(spacing=4)
        self.title = Gtk.Label(xalign=0)
        self.title.get_style_context().add_class("mini-head")
        prev, nxt = Gtk.Button(label="‹"), Gtk.Button(label="›")
        prev.connect("clicked", lambda *_: self.shift(-1))
        nxt.connect("clicked", lambda *_: self.shift(1))
        head.pack_start(self.title, True, True, 4)
        head.pack_start(prev, False, False, 0)
        head.pack_start(nxt, False, False, 0)
        self.pack_start(head, False, False, 0)
        self.grid = Gtk.Grid(column_homogeneous=True, row_spacing=1, column_spacing=1)
        self.pack_start(self.grid, True, True, 0)
        self.draw()

    def shift(self, months):
        m = self.shown.month - 1 + months
        self.shown = dt.date(self.shown.year + m // 12, m % 12 + 1, 1)
        self.draw()

    def draw(self):
        self.title.set_text(f"{calendar.month_name[self.shown.month]} {self.shown.year}")
        for child in self.grid.get_children():
            self.grid.remove(child)
        for i, name in enumerate(["M", "T", "W", "T", "F", "S", "S"]):
            l = Gtk.Label(label=name)
            l.get_style_context().add_class("mini-weekday")
            self.grid.attach(l, i, 0, 1, 1)
        today = dt.date.today()
        for i, day in enumerate(month_grid(self.shown.year, self.shown.month)):
            b = Gtk.Button(label=str(day.day))
            ctx = b.get_style_context()
            ctx.add_class("mini-day")
            if day.month != self.shown.month:
                ctx.add_class("other")
            if day < today:
                ctx.add_class("past")
            if day == today:
                ctx.add_class("today")
            if day == self.selected:
                ctx.add_class("selected")
            b.connect("clicked", lambda _b, d=day: self.on_pick(d))
            self.grid.attach(b, i % 7, i // 7 + 1, 1, 1)
        self.grid.show_all()


class DateField(Gtk.Entry):
    """Click it and the mini calendar drops down; typing still works."""
    def __init__(self, day, on_change=None):
        # no activates_default: Enter belongs to the field, and only the Save button
        # closes the dialog (a recurring event asks "this / following / all" there)
        super().__init__(text=day.isoformat(), width_chars=12)
        self.on_change = on_change
        self.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "pan-down-symbolic")
        # modal: the dialog itself holds a GTK grab, and without one of its own the
        # mini calendar would never see a click - it would fall through to the dialog
        self.popover = Gtk.Popover(relative_to=self, modal=True)
        self.popover.get_style_context().add_class("ly")
        self.mini = MiniCalendar(day, self._picked)
        self.popover.add(self.mini)
        self.mini.show_all()
        self.connect("icon-press", lambda *_: self.open())
        self.connect("button-press-event", self._pressed)
        self.connect("focus-out-event", lambda *_: (self.popover.popdown(), False)[1])
        self.connect("activate", lambda *_: self.popover.popdown())

    def _pressed(self, *_):
        GLib.idle_add(self.open)
        return False

    def open(self):
        day = self.get_date()
        if day:
            self.mini.selected = day
            self.mini.shown = day.replace(day=1)
            self.mini.draw()
        self.popover.popup()
        return False

    def _picked(self, day):
        self.set_text(day.isoformat())
        self.popover.popdown()
        if self.on_change:
            self.on_change(day)

    def get_date(self):
        try:
            return dt.date.fromisoformat(self.get_text().strip())
        except ValueError:
            return None


def ask_scope(parent, verb):
    """Recurring event: which occurrences? Returns "this", "following", "all" or None."""
    dlg = Gtk.Dialog(title=f"{verb} recurring event", transient_for=parent, modal=True)
    dlg.get_style_context().add_class("ly")
    box = dlg.get_content_area()
    box.set_spacing(8)
    box.set_border_width(16)
    choices = [("this", "This event"), ("following", "This and following events"), ("all", "All events")]
    first = None
    buttons = {}
    for key, label in choices:
        b = Gtk.RadioButton.new_with_label_from_widget(first, label)
        first = first or b
        buttons[key] = b
        box.pack_start(b, False, False, 0)
    dlg.add_button("Cancel", Gtk.ResponseType.CANCEL)
    ok = dlg.add_button(verb, Gtk.ResponseType.OK)
    ok.get_style_context().add_class("danger" if verb == "Delete" else "primary")
    dlg.set_default_response(Gtk.ResponseType.OK)
    dlg.show_all()
    resp = dlg.run()
    scope = next((k for k, b in buttons.items() if b.get_active()), "this")
    dlg.destroy()
    return scope if resp == Gtk.ResponseType.OK else None


class EventDialog(Gtk.Dialog):
    def __init__(self, parent, day, event=None, zoom_available=False):
        super().__init__(title="Edit event" if event else "New event", transient_for=parent, modal=True)
        self.get_style_context().add_class("ly")
        self.event = event
        self.set_default_size(560, -1)
        box = self.get_content_area()
        box.set_spacing(4)
        box.set_border_width(16)

        def label(text):
            l = Gtk.Label(label=text, xalign=0)
            l.get_style_context().add_class("ly-label")
            box.pack_start(l, False, False, 0)

        start = event["start"] if event and not event["all_day"] else dt.datetime.combine(day, dt.time(10))
        end = event["end"] if event and not event["all_day"] else start + dt.timedelta(hours=1)

        label("Title")
        self.title = Gtk.Entry(text=event["summary"] if event else "")
        box.pack_start(self.title, False, False, 0)

        row = Gtk.Box(spacing=10)
        self.duration = end - start          # moving the start keeps the length
        self.date = DateField(start.date())
        self.start = TimeField(start, on_change=self._start_moved)
        self.end = TimeField(end, on_change=self._end_moved)
        for caption, widget in (("Date", self.date), ("Start", self.start), ("End", self.end)):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            l = Gtk.Label(label=caption, xalign=0)
            l.get_style_context().add_class("ly-label")
            col.pack_start(l, False, False, 0)
            col.pack_start(widget, False, False, 0)
            row.pack_start(col, widget is self.date, True, 0)
        box.pack_start(row, False, False, 6)


        label("Repeat")
        self.repeat = RecurrencePicker(start.date(), (event or {}).get("recurrence", []))
        box.pack_start(self.repeat, False, False, 4)

        label("Notes")
        self.notes = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=8, right_margin=8,
                                  top_margin=6, bottom_margin=6)
        self.notes.get_buffer().set_text(event["description"] if event else "")
        self.notes.set_size_request(-1, 90)
        box.pack_start(self.notes, True, True, 0)

        self.zoom = Gtk.CheckButton(label="Zoom meeting")
        if not event and zoom_available:
            box.pack_start(self.zoom, False, False, 8)
        if event and event.get("zoom"):
            join = Gtk.Button(label="Join Zoom meeting")
            join.connect("clicked", lambda *_: subprocess.Popen(["xdg-open", event["zoom"]]))
            box.pack_start(join, False, False, 8)

        self.error = Gtk.Label(xalign=0)
        self.error.get_style_context().add_class("ly-error")
        box.pack_start(self.error, False, False, 0)

        if event:
            delete = self.add_button("Delete", 2)
            delete.get_style_context().add_class("danger")
        self.add_button("Close" if event else "Cancel", Gtk.ResponseType.CANCEL)
        if not event:
            create = self.add_button("Create", Gtk.ResponseType.OK)
            create.get_style_context().add_class("primary")
            self.set_default_response(Gtk.ResponseType.OK)
        self.scope = Gtk.ComboBoxText()
        for key, caption in (("this", "This event"), ("following", "This and following events"), ("all", "All events")):
            self.scope.append(key, caption)
        self.scope.set_active_id("this")
        if event and event.get("recurring_id"):
            label("Apply changes to")
            box.pack_start(self.scope, False, False, 4)
        self.show_all()

    def _start_moved(self, value):
        """Start moved: the end follows, so the event keeps its length."""
        start = normalize_time(value)
        if not start:
            return
        h, m = (int(x) for x in start.split(":"))
        new_end = (dt.datetime(2000, 1, 1, h, m) + self.duration).strftime("%H:%M")
        if new_end != self.end.get_time():
            self.end.set_time(new_end)

    def _end_moved(self, value):
        """End moved by hand: that is the new length."""
        start, end = self.start.get_time(), normalize_time(value)
        if not (start and end):
            return
        a = dt.datetime.strptime(start, "%H:%M")
        b = dt.datetime.strptime(end, "%H:%M")
        if b <= a:
            b += dt.timedelta(days=1)
        self.duration = b - a

    def values(self):
        """(summary, start, end, notes) or raises ValueError with a readable message."""
        day = self.date.get_date()
        if day is None:
            raise ValueError("Date must look like 2026-09-18")
        start, end = self.start.get_time(), self.end.get_time()
        if not (start and end):
            raise ValueError("Times must look like 09:30 (9 becomes 09:00)")
        s = dt.datetime.combine(day, dt.time.fromisoformat(start))
        e = dt.datetime.combine(day, dt.time.fromisoformat(end))
        if e <= s:
            e += dt.timedelta(days=1)          # ends after midnight
        buf = self.notes.get_buffer()
        notes = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        return self.title.get_text().strip(), s, e, notes


class Window(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="light-year")
        self.set_default_size(1500, 1050)
        self.set_icon_name("light-year")
        self.get_style_context().add_class("ly")
        self.cursor = dt.date.today().replace(day=1)
        self.events = []
        self.state = {}
        self.loading = 0
        self.expanded_days = set()
        self.months = {}            # (year, month) -> events, so a swipe shows at once
        self.editing_id = None      # event open in the dialog: drawn in yellow
        self.pending_day = None     # day a new event is being created on
        self.swipe = 0.0
        self.swipe_lock = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.get_style_context().add_class("ly")
        self.add(root)

        bar = Gtk.Box(spacing=8)
        bar.get_style_context().add_class("ly-bar")
        self.title_label = Gtk.Label(xalign=0)
        self.title_label.get_style_context().add_class("ly-title")
        # wide enough for the longest month name, so the buttons beside it never
        # shift when the month changes
        self.title_label.set_width_chars(len("September 2026") + 1)
        self.title_label.set_max_width_chars(len("September 2026") + 1)
        bar.pack_start(self.title_label, False, False, 6)
        for text, tip, cb in (("‹", "Previous month (←)", lambda *_: self.shift(-1)),
                              ("›", "Next month (→)", lambda *_: self.shift(1)),
                              ("Today", "Today (T)", lambda *_: self.go_today())):
            b = Gtk.Button(label=text, tooltip_text=tip)
            b.connect("clicked", cb)
            bar.pack_start(b, False, False, 0)
        self.status = Gtk.Label(xalign=1)
        self.status.get_style_context().add_class("ly-status")
        self.connect_btn = Gtk.Button(label="Connect Google")
        self.connect_btn.connect("clicked", self.sign_in)
        reload_btn = Gtk.Button(label="↻  Reload", tooltip_text="Reload (F5)")
        reload_btn.connect("clicked", lambda *_: self.load(force=True))
        bar.pack_end(reload_btn, False, False, 0)
        bar.pack_end(self.connect_btn, False, False, 0)
        bar.pack_end(self.status, True, True, 8)
        root.pack_start(bar, False, False, 0)

        head = Gtk.Grid(column_homogeneous=True, margin_start=16, margin_end=16)
        for i, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            l = Gtk.Label(label=name.upper(), xalign=0)
            l.get_style_context().add_class("ly-weekday")
            head.attach(l, i, 0, 1, 1)
        root.pack_start(head, False, False, 0)

        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True,
                             row_spacing=1, column_spacing=1)
        self.grid.get_style_context().add_class("ly-grid")
        root.pack_start(self.grid, True, True, 0)

        self.connect("key-press-event", self.on_key)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.connect("scroll-event", self.on_scroll)
        root.show_all()
        self.connect_btn.hide()
        self.draw()
        self.refresh_state()
        GLib.timeout_add(REFRESH_MS, lambda: (self.load(force=True), True)[1])

    # ------------------------------------------------------------ data
    def set_status(self, text, error=False):
        self.status.set_text(text)
        ctx = self.status.get_style_context()
        (ctx.add_class if error else ctx.remove_class)("error")

    def refresh_state(self):
        self.state = api.state()
        self.connect_btn.set_visible(not self.state["google"])
        if not self.state["google_configured"]:
            self.set_status(f"Google credentials missing: {api.CREDENTIALS}", True)
        elif not self.state["google"]:
            self.set_status("Not connected to Google")
        else:
            self.load()

    @staticmethod
    def key_of(day):
        return (day.year, day.month)

    @staticmethod
    def month_of(key, offset=0):
        m = key[1] - 1 + offset
        return (key[0] + m // 12, m % 12 + 1)

    def fetch(self, key, done):
        days = month_grid(*key)
        run_async(lambda: api.list_events(days[0], days[-1] + dt.timedelta(days=1)), done)

    def load(self, force=False):
        """Show the month: from the cache at once when it is there, then refresh it
        and quietly fetch the neighbouring months, so a swipe has nothing to wait for."""
        if not self.state.get("google"):
            return
        key = self.key_of(self.cursor)
        cached = self.months.get(key)
        if cached is not None:
            self.events = cached
            self.draw()
            if not force:
                self.prefetch(key)
                return
        self.loading += 1
        token = self.loading
        if cached is None:
            self.set_status("Loading…")

        def done(events, err):
            if token != self.loading:
                return                        # a newer load already started
            if err:
                self.set_status(err, True)
            else:
                self.months[key] = events
                self.events = events
                self.set_status("Google · Zoom" if self.state.get("zoom") else "Google")
            self.draw()
            self.prefetch(key)
        self.fetch(key, done)

    def prefetch(self, key):
        for offset in (1, -1):
            side = self.month_of(key, offset)
            if side not in self.months:
                self.fetch(side, lambda events, err, k=side: self.months.__setitem__(k, events)
                           if not err else None)
                return                        # one at a time: the next one follows later

    def mutate(self, work):
        self.set_status("Saving…")

        def done(res, err):
            if err:
                self.set_status(err, True)
            else:
                self.months.clear()           # the change can land in any month
            self.load(force=True)
        run_async(work, done)

    # ------------------------------------------------------------ drawing
    def draw(self):
        self.title_label.set_text(f"{calendar.month_name[self.cursor.month]} {self.cursor.year}")
        for child in self.grid.get_children():
            self.grid.remove(child)
        today = dt.date.today()
        by_day = {}
        for e in self.events:
            day = e["start"].date() if not e["all_day"] else e["start"]
            by_day.setdefault(day, []).append(e)

        for i, day in enumerate(month_grid(self.cursor.year, self.cursor.month)):
            cell = Gtk.EventBox()
            ctx = cell.get_style_context()
            ctx.add_class("ly-day")
            if day.weekday() in (0, 2, 4):          # Mon, Wed, Fri
                ctx.add_class("tint")
            elif day.weekday() in (5, 6):           # Saturday, Sunday
                ctx.add_class("weekend")
            if day < today:
                ctx.add_class("past")
            if day.month != self.cursor.month:
                ctx.add_class("other")
            if day == today:
                ctx.add_class("today")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            num = Gtk.Label(label=str(day.day), halign=Gtk.Align.START)
            num.get_style_context().add_class("ly-num")
            box.pack_start(num, False, False, 0)
            events = by_day.get(day, [])
            chips = [self.chip(e) for e in events]
            if self.pending_day == day:
                chips.append(self.placeholder())
            area = DayEvents(chips, day in self.expanded_days,
                             lambda expanded, d=day: self.expanded_days.add(d) if expanded else self.expanded_days.discard(d))
            box.pack_start(area, True, True, 0)
            cell.add(box)
            cell.connect("button-press-event", lambda w, ev, d=day: self.on_day_click(ev, d))
            cell.drag_dest_set(Gtk.DestDefaults.ALL, [Gtk.TargetEntry.new("light-year/event", Gtk.TargetFlags.SAME_APP, 0)],
                               Gdk.DragAction.MOVE)
            cell.connect("drag-data-received", lambda w, c, x, y, data, info, t, d=day: self.drop(data.get_text(), d))
            cell.connect("drag-motion", lambda w, *a: w.get_style_context().add_class("drop") or False)
            cell.connect("drag-leave", lambda w, *a: w.get_style_context().remove_class("drop"))
            self.grid.attach(cell, i % 7, i // 7, 1, 1)
        self.grid.show_all()

    @staticmethod
    def describe(e):
        when = "all day" if e["all_day"] else f"{e['start']:%H:%M}–{e['end']:%H:%M}"
        return f"{when}  {e['summary']}" + ("  (Zoom)" if e.get("zoom") else "")

    def placeholder(self):
        """The yellow block standing in for the event being created."""
        eb = Gtk.EventBox()
        eb.get_style_context().add_class("ly-chip")
        eb.get_style_context().add_class("editing")
        eb.add(Gtk.Label(label="New event…", xalign=0, ellipsize=3, margin_start=8))
        return eb

    def chip(self, e):
        eb = Gtk.EventBox()
        eb.get_style_context().add_class("ly-chip")
        if e["id"] == self.editing_id:
            eb.get_style_context().add_class("editing")
        # an event box ignores CSS padding, so the gap from the coloured bar is a margin
        row = Gtk.Box(spacing=6, margin_start=8, margin_end=4)
        if not e["all_day"]:
            # the time never shrinks; only the title is ellipsized in a narrow cell
            t = Gtk.Label(label=f"{e['start']:%H:%M}", xalign=0, width_chars=5, single_line_mode=True)
            t.get_style_context().add_class("time")
            row.pack_start(t, False, False, 0)
        name = Gtk.Label(label=e["summary"] + ("  · zoom" if e.get("zoom") else ""), xalign=0,
                         ellipsize=3, max_width_chars=1)      # Pango.EllipsizeMode.END
        row.pack_start(name, True, True, 0)
        eb.add(row)
        eb.set_tooltip_text(self.describe(e))
        eb.connect("button-release-event", lambda w, ev: self.edit(e) or True)
        eb.connect("button-press-event", lambda *a: True)        # not a click on the day
        if not e["all_day"]:
            eb.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                               [Gtk.TargetEntry.new("light-year/event", Gtk.TargetFlags.SAME_APP, 0)],
                               Gdk.DragAction.MOVE)
            eb.connect("drag-data-get", lambda w, c, data, info, t: data.set_text(e["id"], -1))
        return eb

    # ------------------------------------------------------------ actions
    def shift(self, months):
        m = self.cursor.month - 1 + months
        self.cursor = dt.date(self.cursor.year + m // 12, m % 12 + 1, 1)   # December -> January
        self.events = self.months.get(self.key_of(self.cursor), [])
        self.draw()
        self.load()

    def on_scroll(self, w, ev):
        """Two fingers left or right: the next or the previous month - one month per
        swipe. What is left of a swipe that has already turned the page is dropped
        until the fingers come off, so swiping back does not repeat the last step
        first."""
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            if getattr(ev, "is_stop", False):        # fingers lifted
                self.swipe, self.swipe_lock = 0.0, False
                return True
            ok, dx, dy = ev.get_scroll_deltas()
            if not ok or abs(dx) <= abs(dy):
                return False
            step = dx
        elif ev.direction == Gdk.ScrollDirection.LEFT:
            step = -3.0
        elif ev.direction == Gdk.ScrollDirection.RIGHT:
            step = 3.0
        else:
            return False
        if self.swipe_lock:
            # the tail of the swipe that just turned the month must not add up to
            # one more month once the lock is over
            self.swipe = 0.0
            return True
        if step * self.swipe < 0:            # turned around: start counting afresh
            self.swipe = 0.0
        self.swipe += step
        if abs(self.swipe) >= 2.5:
            self.shift(1 if self.swipe > 0 else -1)
            self.swipe = 0.0
            self.swipe_lock = True
            # a wheel sends no "fingers off" event, so the lock also times out
            GLib.timeout_add(600, lambda: (setattr(self, "swipe_lock", False), False)[1])
        return True

    def go_today(self):
        self.cursor = dt.date.today().replace(day=1)
        self.events = self.months.get(self.key_of(self.cursor), [])
        self.draw()
        self.load()

    def on_key(self, w, ev):
        key, ctrl = Gdk.keyval_name(ev.keyval), ev.state & Gdk.ModifierType.CONTROL_MASK
        if key == "Left":
            self.shift(-1)
        elif key == "Right":
            self.shift(1)
        elif key in ("t", "T"):
            self.go_today()
        elif key == "F5" or (ctrl and key in ("r", "R")):
            self.load(force=True)
        else:
            return False
        return True

    def on_day_click(self, ev, day):
        if ev.button == 1 and ev.type == Gdk.EventType.BUTTON_PRESS and self.state.get("google"):
            self.open_dialog(day, None)
        return True

    def edit(self, e):
        day = e["start"] if e["all_day"] else e["start"].date()
        if e.get("recurring_id"):
            self.set_status("Loading recurrence…")
            def done(rules, err):
                if err:
                    self.set_status(err, True)
                    return
                self.set_status("")
                self.open_dialog(day, dict(e, recurrence=rules))
            run_async(lambda: api.get_recurrence(e), done)
        else:
            self.open_dialog(day, e)

    def open_dialog(self, day, event):
        self.editing_id = event["id"] if event else None
        self.pending_day = None if event else day
        self.draw()
        dlg = EventDialog(self, day, event, zoom_available=self.state.get("zoom"))
        timer = None
        busy = False
        closing = False
        saved_values = dlg.values() if event else None
        saved_rules = list((event or {}).get("recurrence", []))

        def flush(close=False):
            nonlocal timer, busy, closing, saved_values, saved_rules, event
            if timer is not None:
                GLib.source_remove(timer)
                timer = None
            closing = closing or close
            if busy:
                return False
            try:
                values = dlg.values()
                rules = dlg.repeat.values(values[1].date())
                if not values[0]:
                    raise ValueError("Enter an event title")
            except ValueError as err:
                dlg.error.set_text(str(err))
                closing = False
                return False
            if values == saved_values and rules == saved_rules:
                if closing:
                    dlg.response(3)
                return False
            scope = dlg.scope.get_active_id() if event.get("recurring_id") else "this"
            changed_rules = rules if rules != saved_rules else None
            if changed_rules is not None and event.get("recurring_id") and scope == "this":
                dlg.scope.set_active_id("following")
                scope = "following"
            busy = True
            dlg.get_content_area().set_sensitive(False)
            dlg.get_action_area().set_sensitive(False)
            dlg.error.set_text("Saving…")
            def done(result, err):
                nonlocal busy, closing, saved_values, saved_rules, event
                busy = False
                dlg.get_content_area().set_sensitive(True)
                dlg.get_action_area().set_sensitive(True)
                if err:
                    dlg.error.set_text(err + " · Edit a field to retry")
                    closing = False
                    return
                saved_values, saved_rules = values, rules
                summary, start, end, notes = values
                updated = dict(event, summary=summary, start=start.astimezone(), end=end.astimezone(),
                               description=notes, recurrence=rules)
                if scope == "following" or not event.get("recurring_id"):
                    updated.update(id=result["id"], recurring_id=result["id"] if rules else None,
                                   original_start=start.astimezone().isoformat())
                event = updated
                # The split is now a series of its own; subsequent edits use its master.
                if scope == "following":
                    dlg.scope.set_active_id("all")
                dlg.repeat.dirty = False
                dlg.repeat.original = list(rules)
                self.months.clear()
                self.load(force=True)
                dlg.error.set_text("Saved")
                if closing:
                    dlg.response(3)
            run_async(lambda: api.change_occurrence(event, scope, *values, recurrence=changed_rules), done)
            return False

        def queue(*_):
            nonlocal timer
            if busy:
                return
            if timer is not None:
                GLib.source_remove(timer)
            # Text fields are debounced; controls persist as soon as their change settles.
            timer = GLib.timeout_add(650, flush)

        if event:
            for field in (dlg.title, dlg.date, dlg.start, dlg.end):
                field.connect("changed", queue)
            dlg.notes.get_buffer().connect("changed", queue)
            dlg.repeat.changed = lambda: flush()
        while True:
            resp = dlg.run()
            if resp == 3:
                break
            if busy:
                closing = True
                continue
            if resp == 2 and event:
                if timer is not None:
                    GLib.source_remove(timer)
                    timer = None
                scope = ask_scope(dlg, "Delete") if event.get("recurring_id") else "this"
                if scope is None:
                    continue
                self.mutate(lambda e=event, sc=scope: api.delete_occurrence(e, sc))
                break
            if event:
                closing = True
                flush(close=True)
                if not busy and closing:
                    break
                continue
            if resp != Gtk.ResponseType.OK:
                break
            try:
                values = dlg.values()
                rules = dlg.repeat.values(values[1].date())
                if not values[0]:
                    raise ValueError("Enter an event title")
            except ValueError as err:
                dlg.error.set_text(str(err))
                continue
            with_zoom = dlg.zoom.get_active()
            # Keep the draft open on API failure; never discard a user's input.
            dlg.set_sensitive(False)
            def created(result, err):
                dlg.set_sensitive(True)
                if err:
                    dlg.error.set_text(err)
                else:
                    self.months.clear()
                    self.load(force=True)
                    dlg.response(3)
            run_async(lambda: api.create_event(*values, with_zoom, rules), created)
        if timer is not None:
            GLib.source_remove(timer)
        dlg.destroy()
        self.editing_id = self.pending_day = None
        self.draw()

    def drop(self, event_id, day):
        e = next((x for x in self.events if x["id"] == event_id), None)
        if not e or e["all_day"]:
            return
        start = dt.datetime.combine(day, e["start"].time().replace(tzinfo=None))
        end = start + (e["end"] - e["start"])
        # ask after the drag has fully finished (a dialog inside the drop handler breaks it)
        GLib.idle_add(self.finish_drop, e, start, end)

    def finish_drop(self, e, start, end):
        scope = "this"
        if e.get("recurring_id"):
            scope = ask_scope(self, "Move")
            if scope is None:
                return False
        original = dict(e)
        e["start"], e["end"] = start.astimezone(), end.astimezone()    # show it moved right away
        self.draw()
        self.mutate(lambda: api.change_occurrence(original, scope, start=start, end=end))
        return False

    def sign_in(self, *_):
        self.set_status("Finish the sign-in in the browser…")
        api.google_sign_in(lambda err: GLib.idle_add(self.signed_in, err))

    def signed_in(self, err):
        if err:
            self.set_status(err, True)
        else:
            self.refresh_state()
        return False


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        if not self.window:
            self.window = Window(self)
        self.window.present_with_time(Gtk.get_current_event_time() or 0)


if __name__ == "__main__":
    GLib.set_prgname("light-year")
    Gdk.set_program_class("light-year")
    sys.exit(App().run(sys.argv))
