#!/usr/bin/env python3
"""Two panel icons out of Telegram's own one, with GdkPixbuf (no extra packages).

    make-telegram-icons.py <out-dir> [size]

telegram.png        — Telegram's icon, scaled to the panel's icon size.
telegram-accent.png — the same shape in the desktop accent colour, for unread
                      messages: the blue disc becomes accent, the white plane
                      stays white, and every shade in between is blended, so the
                      edges keep their smoothness.
telegram-off.png    — the plain icon at 45% opacity, for "Telegram is not running".
"""
import os
import sys

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

SOURCE = "/usr/share/icons/hicolor/128x128/apps/org.telegram.desktop.png"
ACCENT = (0x48, 0xda, 0xf9)


def luma(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def tint(pixbuf, accent):
    """Blue -> accent, white stays white, alpha untouched."""
    out = pixbuf.copy()
    data = bytearray(out.get_pixels())
    rowstride, channels = out.get_rowstride(), out.get_n_channels()
    lo, hi = 140.0, 255.0                      # luma of Telegram blue, luma of white
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            o = y * rowstride + x * channels
            if channels == 4 and data[o + 3] == 0:
                continue
            t = min(1.0, max(0.0, (luma(data[o], data[o + 1], data[o + 2]) - lo) / (hi - lo)))
            for i in range(3):
                data[o + i] = int(round(accent[i] + (255 - accent[i]) * t))
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), out.get_colorspace(), out.get_has_alpha(),
        out.get_bits_per_sample(), out.get_width(), out.get_height(), rowstride)


def fade(pixbuf, alpha):
    """The same icon, dimmer: for an app that is not running."""
    out = pixbuf.add_alpha(False, 0, 0, 0)
    data = bytearray(out.get_pixels())
    rowstride, channels = out.get_rowstride(), out.get_n_channels()
    for y in range(out.get_height()):
        for x in range(out.get_width()):
            o = y * rowstride + x * channels + 3
            data[o] = int(data[o] * alpha)
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(data)), out.get_colorspace(), out.get_has_alpha(),
        out.get_bits_per_sample(), out.get_width(), out.get_height(), rowstride)


def main():
    out_dir = sys.argv[1]
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 48
    os.makedirs(out_dir, exist_ok=True)
    plain = GdkPixbuf.Pixbuf.new_from_file_at_size(SOURCE, size, size)
    plain.savev(os.path.join(out_dir, "telegram.png"), "png", [], [])
    tint(plain, ACCENT).savev(os.path.join(out_dir, "telegram-accent.png"), "png", [], [])
    fade(plain, 0.45).savev(os.path.join(out_dir, "telegram-off.png"), "png", [], [])
    print(f"wrote telegram.png, telegram-accent.png and telegram-off.png ({size}px) to {out_dir}")


if __name__ == "__main__":
    from gi.repository import GLib  # noqa: E402  (only needed when rebuilding pixels)
    main()
