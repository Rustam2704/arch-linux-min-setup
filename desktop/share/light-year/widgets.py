"""Small GTK controls used by the month view and event editor."""
import calendar
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk
import recurrence


class RecurrencePicker(Gtk.Box):
    def __init__(self, day, rules=(), changed=lambda: None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.day, self.original, self.changed = day, list(rules), changed
        self.mode, self.days = recurrence.describe(rules, day)
        self.dirty = False
        self.buttons = {}
        row = Gtk.Box(spacing=6)
        self.pack_start(row, False, False, 0)
        for mode, label in (("none", "None"), ("weekly", "Weekly"), ("daily", "Daily")):
            b = Gtk.ToggleButton(label=label)
            b.connect("clicked", lambda _, m=mode: self.choose(m))
            row.pack_start(b, False, False, 0)
            self.buttons[mode] = b
        self.more = Gtk.MenuButton(label="More ▾")
        row.pack_start(self.more, False, False, 0)
        pop = Gtk.Popover(relative_to=self.more)
        pop.get_style_context().add_class("ly")
        options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=10)
        for mode, label in (("custom", "Custom days ▸"), ("monthly", "Monthly"), ("yearly", "Yearly")):
            b = Gtk.ToggleButton(label=label)
            b.connect("clicked", lambda _, m=mode: self.choose(m))
            options.pack_start(b, False, False, 0)
            self.buttons[mode] = b
            if mode == "custom":
                self.week = Gtk.Box(spacing=3)
                self.week.set_no_show_all(True)
                self.day_buttons = []
                for i in range(7):
                    toggle = Gtk.ToggleButton(label=calendar.day_abbr[i])
                    toggle.set_tooltip_text(calendar.day_name[i])
                    toggle.set_active(i in self.days)
                    toggle.connect("toggled", self.toggle_day, i)
                    self.week.pack_start(toggle, False, False, 0)
                    toggle.show()
                    self.day_buttons.append(toggle)
                options.pack_start(self.week, False, False, 0)
        pop.add(options)
        options.show_all()
        self.more.set_popover(pop)
        self.note = Gtk.Label(xalign=0, wrap=True)
        self.note.get_style_context().add_class("ly-label")
        self.pack_start(self.note, False, False, 0)
        self.render()

    def render(self):
        self.rendering = True
        for mode, button in self.buttons.items():
            button.set_active(mode == self.mode)
        self.rendering = False
        self.week.set_visible(self.mode == "custom")
        labels = {"custom": "Custom days", "monthly": "Monthly", "yearly": "Yearly", "existing": "Existing rule"}
        self.more.set_label(labels.get(self.mode, "More") + " ▾")
        self.note.set_text("Existing recurrence is preserved until you choose another option." if self.mode == "existing"
                           else "Repeats on " + ", ".join(calendar.day_abbr[i] for i in sorted(self.days)) if self.mode == "custom"
                           else "Monthly and yearly repeats skip dates that do not exist." if self.mode in ("monthly", "yearly") else "")

    def choose(self, mode):
        if getattr(self, "rendering", False):
            return
        self.mode, self.dirty = mode, True
        self.render()
        self.changed()

    def toggle_day(self, button, i):
        if button.get_active():
            self.days.add(i)
        else:
            self.days.discard(i)
        self.dirty = True
        self.render()
        self.changed()

    def values(self, day):
        return recurrence.rule(self.mode, day, self.days) if self.dirty else self.original


class DayEvents(Gtk.Box):
    """The viewport never dictates the grid's minimum height. Allocation does."""
    def __init__(self, chips, expanded=False, on_expand=lambda value: None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.chips, self.expanded, self.on_expand = chips, expanded, on_expand
        self.pending = None
        self.row_height = self.more_height = 1
        self.scroll = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_min_content_height(0)
        self.scroll.set_propagate_natural_height(False)
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for chip in chips:
            self.rows.pack_start(chip, False, False, 0)
            chip.show_all()
            chip.set_no_show_all(True)
            chip.show()
        self.scroll.add(self.rows)
        self.pack_start(self.scroll, True, True, 0)
        self.more = Gtk.Button(label="More")
        self.more.get_style_context().add_class("ly-more")
        self.more.set_no_show_all(True)
        self.more.connect("clicked", self.toggle)
        self.pack_start(self.more, False, False, 0)
        self.more.show()
        self.connect("size-allocate", self.allocated)
        self.connect("destroy", self.destroyed)
        self.scroll.connect("scroll-event", self.scrolled)

    def scrolled(self, widget, event):
        # Stop vertical wheel/touchpad events reaching the month navigator.
        direction = event.direction
        dy = event.get_scroll_deltas()[2] if direction == Gdk.ScrollDirection.SMOOTH else (
            1 if direction == Gdk.ScrollDirection.DOWN else -1 if direction == Gdk.ScrollDirection.UP else 0)
        if not dy:
            return False
        if not self.expanded and any(not c.get_visible() for c in self.chips):
            self.toggle()
        adj = self.scroll.get_vadjustment()
        adj.set_value(max(adj.get_lower(), min(adj.get_upper() - adj.get_page_size(), adj.get_value() + dy * 30)))
        return True

    def toggle(self, *_):
        self.expanded = not self.expanded
        self.on_expand(self.expanded)
        self.reflow()

    def allocated(self, *_):
        if self.pending is None:
            self.pending = GLib.timeout_add(20, self.reflow)

    def destroyed(self, *_):
        if self.pending is not None:
            GLib.source_remove(self.pending)
            self.pending = None

    def reflow(self):
        self.pending = None
        if not self.chips:
            self.more.hide()
            return False
        self.row_height = max(self.row_height, *(c.get_preferred_height()[1] for c in self.chips))
        row = self.row_height
        height = self.get_allocated_height()
        self.more_height = max(self.more_height, self.more.get_preferred_height()[1])
        more_height = self.more_height
        count = recurrence.capacity(height, row, more_height, len(self.chips))
        overflow = count < len(self.chips)
        for i, chip in enumerate(self.chips):
            chip.set_visible(self.expanded or i < count)
        self.more.set_label("Show less" if self.expanded else f"+{len(self.chips) - count} more")
        self.more.set_visible(overflow)
        return False
