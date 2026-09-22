"""Astra's deterministic sparkle field, adapted from OpenAI Codex (Apache-2.0).

Source: codex-rs/tui/src/bottom_pane/chat_composer/sparkle_field.rs.
The hash, density, phase, exponent, brightness threshold and 150 ms cadence
are unchanged. The desktop uses a black background and does not fade after 15 s.
"""
import math

FRAME_MS = 150
DOTS = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3))


def field(columns, rows):
    for y in range(rows):
        for x in range(columns):
            h = y * 65537 + x
            h = ((h ^ (h >> 16)) * 0x45d9f3b) & ((1 << 64) - 1)
            h = ((h ^ (h >> 16)) * 0x45d9f3b) & ((1 << 64) - 1)
            h ^= h >> 16
            if h % 5 == 0:
                yield x, y, h


def brightness(h, elapsed):
    phase = (elapsed / (4.0 + (h % 31) / 10.0) + (h % 997) / 997.0) % 1.0
    value = math.sin(phase * math.pi) ** 12 * 0.55
    return value if value >= 0.04 else 0.0
