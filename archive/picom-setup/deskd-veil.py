"""The panel veil from deskd (rounds 12-24): a 38 % black ARGB window over each panel
with a hole under the pointer. Needs a compositor to blend. Kept for reference."""

class PanelDim:
    """The panel sits under a thin dark veil, with a hole where the pointer is. That
    is how the volume icon behaves on its own - quiet until you point at it - and
    the only way to give every plugin the same behaviour: their drawings belong to
    the panel, and nothing outside it can repaint them brighter.

    One window per panel, click-through (empty input shape), so the panel keeps
    every click and the hole simply follows the pointer."""
    SHADE = 0.38

    def __init__(self, xs, geom):
        self.xs = xs
        self.geom = geom
        x, y, w, h = geom
        self.win = xs.window(xs.root, x, y, w, h, argb=True, override=True,
                             events=X.ExposureMask)
        try:
            shape.rectangles(self.win, shape.SO.Set, shape.SK.Input, 0, 0, 0, [])
        except Exception as e:                       # noqa: BLE001 - only the click-through
            log("panel veil is not click-through:", e)
        self.hole = None
        self.shown = True
        self.win.map()
        self.draw()

    def matches(self, geom):
        return self.geom == geom

    def set_visible(self, visible):
        """A window covering the screen (a photo, a video, anything full-screen) must
        not have our veil or anything else of ours on top of it."""
        if visible == self.shown:
            return
        self.shown = visible
        if visible:
            self.win.map()
            self.draw()
        else:
            self.win.unmap()

    def set_hole(self, hole):
        if hole != self.hole:
            self.hole = hole
            self.draw()

    def raise_above(self):
        self.win.configure(stack_mode=X.Above)

    def draw(self):
        x0, y0, w, h = self.geom
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, max(1, w), max(1, h))
        ctx = cairo.Context(surface)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.set_source_rgba(0, 0, 0, self.SHADE)
        ctx.paint()
        if self.hole:
            hx, hy, hw, hh = self.hole
            ctx.set_operator(cairo.OPERATOR_CLEAR)
            radius, inset = 7, 2
            x, y = hx - x0 + inset, hy - y0 + inset
            right, bottom = x + hw - 2 * inset, y + hh - 2 * inset
            ctx.new_sub_path()
            ctx.arc(right - radius, y + radius, radius, -1.5708, 0)
            ctx.arc(right - radius, bottom - radius, radius, 0, 1.5708)
            ctx.arc(x + radius, bottom - radius, radius, 1.5708, 3.1416)
            ctx.arc(x + radius, y + radius, radius, 3.1416, 4.7124)
            ctx.close_path()
            ctx.fill()
        self.xs.paint(self.win, surface, 32)




# --- the Deskd methods that drove it ---

    def watch_panel_items(self):
        """Follow the pointer across the panel and work out what it is over. Pointer
        events are not exclusive, so watching the panel's own window takes nothing
        away from it, and it is the only way to see the plugins that have no window
        of their own - the clock, the volume, the shutdown button."""
        self.panel_items = self.panel_regions()
        mask = X.PointerMotionMask | X.EnterWindowMask | X.LeaveWindowMask
        watch = []
        for frame, geom in self.dock_frames():
            watch += frame.query_tree().children
            veil = self.veils.get(frame.id)
            if veil is None or not veil.matches(geom):
                self.veils[frame.id] = PanelDim(self.xs, geom)
        watch += [win for win, _ in self.panel_wrappers()]
        for win in watch:
            try:
                win.change_attributes(event_mask=mask)
                self.panel_windows.add(win.id)
            except error.XError:
                pass
        self.raise_overlays()
        return True

    def raise_overlays(self):
        """Our own windows over the panel: the pentagram first, then the veil on top of
        it - the mark belongs to the panel and dims with it."""
        if self.ws_mark is not None and self.ws_mark.shown:
            self.fire_digits.raise_above()           # fire, then the star over it
            self.ws_mark.win.configure(stack_mode=X.Above)
        for veil in self.veils.values():
            veil.raise_above()

    def panel_regions(self):
        """[(x, y, w, h)] of everything the pointer can light up on the panel: the
        plugins that run in their own process, and the gaps between them, which is
        where the panel's own plugins sit. The workspace strip is left out - there
        the number under the pointer lights up on its own."""
        regions = []
        try:
            strips = {pid for pid, _ in self.strip_plugins()}
            for pid, out in self.strip_plugins():        # one number at a time
                view = self.strip_view(pid, out)
                if not view:
                    continue
                (_, gy, _, gh), items, bounds = view
                for (lo, hi), _ in zip(bounds, items):
                    regions.append((int(lo), gy, int(hi - lo), gh))
            for frame, (dx, dy, dw, dh) in self.dock_frames():
                boxes = []
                for win, pid in self.panel_wrappers():
                    g = win.get_geometry()
                    t = win.translate_coords(self.xs.root, 0, 0)
                    box = (-t.x, -t.y, g.width, g.height)
                    if not (dx <= box[0] < dx + dw):
                        continue
                    boxes.append((box, pid))
                boxes.sort(key=lambda b: b[0][0])
                regions += [box for box, pid in boxes if pid not in strips]
                edges = [dx] + [x for (x, _, w, _), _ in boxes for x in (x, x + w)] + [dx + dw]
                for left, right in zip(edges[::2], edges[1::2]):
                    width = right - left
                    if width < 24:
                        continue
                    # the last gap holds the clock and the square shutdown button
                    if width > dh * 1.6:
                        regions.append((left, dy, int(width - dh), dh))
                        regions.append((int(right - dh), dy, int(dh), dh))
                    else:
                        regions.append((left, dy, int(width), dh))
        except error.XError as e:
            log("panel regions failed:", e)
        return regions

    def panel_pointer(self, x, y):
        """Open the hole in the veil over whatever the pointer is on."""
        hole = None
        for rect in self.panel_items:
            rx, ry, rw, rh = rect
            if rx <= x < rx + rw and ry <= y < ry + rh:
                hole = rect
                break
        for veil in self.veils.values():
            veil.set_hole(hole)
        return None

