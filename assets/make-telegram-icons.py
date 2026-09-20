#!/usr/bin/env python3
"""Panel icons for Telegram, from Telegram's own monochrome tray icon.

    make-telegram-icons.py <out-dir> [size]

The source is the symbolic (one-colour) icon Telegram ships for the tray, so the
panel keeps the look the tray icon had. Three states, all the same shape:

telegram.png        — quiet: the pale text colour of the panel
telegram-accent.png — unread messages: the icon lights up in the accent colour
telegram-off.png    — Telegram is not running: dimmed

GdkPixbuf does the work (it is already there for GTK), so nothing extra gets
installed for three small images.
"""
import os
import sys

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib  # noqa: E402

SOURCE = "/usr/share/icons/hicolor/symbolic/apps/org.telegram.desktop-symbolic.svg"
COLOURS = {"telegram.png": (0xc6, 0xd0, 0xd9),          # the panel's own text colour
           "telegram-accent.png": (0x48, 0xda, 0xf9),   # accent: unread messages
           "telegram-off.png": (0x5b, 0x6b, 0x76)}      # dim: not running


def paint(pixbuf, colour):
    """Repaint the glyph in one colour, keeping every pixel's transparency."""
    out = pixbuf.add_alpha(False, 0, 0, 0)
    data = bytearray(out.get_pixels())
    rowstride, channels = out.get_rowstride(), out.get_n_channels()
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            o = y * rowstride + x * channels
            data[o], data[o + 1], data[o + 2] = colour
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), out.get_colorspace(), out.get_has_alpha(),
        out.get_bits_per_sample(), out.get_width(), out.get_height(), rowstride)


def main():
    out_dir = sys.argv[1]
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 48
    os.makedirs(out_dir, exist_ok=True)
    glyph = GdkPixbuf.Pixbuf.new_from_file_at_size(SOURCE, size, size)
    for name, colour in COLOURS.items():
        paint(glyph, colour).savev(os.path.join(out_dir, name), "png", [], [])
    print(f"wrote {', '.join(COLOURS)} ({size}px) to {out_dir}")


if __name__ == "__main__":
    main()
