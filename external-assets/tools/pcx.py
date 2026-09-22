"""Minimal reader for Diablo's 8-bit PCX files: (width, height, indexes, palette).
Frames of a sprite list are stacked vertically (LoadPcxSpriteList in DevilutionX)."""
import struct


def read(path):
    data = open(path, "rb").read()
    x0, y0, x1, y1 = struct.unpack_from("<4H", data, 4)
    bpp, planes, bpl = data[3], data[65], struct.unpack_from("<H", data, 66)[0]
    assert bpp == 8 and planes == 1, (bpp, planes)
    width, height = x1 - x0 + 1, y1 - y0 + 1
    pal = data[-768:] if data[-769] == 0x0C else None
    palette = [tuple(pal[i:i + 3]) for i in range(0, 768, 3)] if pal else None
    out = bytearray(width * height)
    pos, i = 128, 0
    for row in range(height):
        col = 0
        while col < bpl:
            b = data[pos]; pos += 1
            if b >= 0xC0:
                n, b = b & 0x3F, data[pos]; pos += 1
            else:
                n = 1
            for _ in range(n):
                if col < width:
                    out[row * width + col] = b
                col += 1
    return width, height, bytes(out), palette


def frames(path, count):
    w, h, px, pal = read(path)
    fh = h // count
    return w, fh, [px[i * fh * w:(i + 1) * fh * w] for i in range(count)], pal


def to_png(path_out, w, h, px, pal, transparent=None, scale=1):
    import cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w * scale, h * scale)
    buf = surf.get_data(); stride = surf.get_stride()
    for y in range(h):
        for x in range(w):
            idx = px[y * w + x]
            if idx == transparent:
                continue
            r, g, b = pal[idx]
            for dy in range(scale):
                base = (y * scale + dy) * stride
                for dx in range(scale):
                    o = base + (x * scale + dx) * 4
                    buf[o:o + 4] = bytes((b, g, r, 255))
    surf.mark_dirty(); surf.write_to_png(path_out)
