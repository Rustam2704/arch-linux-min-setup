"""Shared style: the palette, fonts and panel markup from theme.json.

Python consumers read THEME directly. Text that goes to GTK (CSS), Pango or a
shell script uses the same tokens as the config files in the desktop tree:

    @COLOUR_ACCENT@     -> #0d8ecb            (any string key; nested keys join with _)
    @RGB_LIGHT@         -> 72, 218, 249       (for rgba(@RGB_LIGHT@, 0.2))
    @HEX_ACCENT@        -> 0d8ecb             (colours without the hash, e.g. touchegg)
    @FONT@              -> Inter

No GTK import here: the panel readers must stay small.
"""
import json
from pathlib import Path

THEME = json.loads(Path(__file__).with_name("theme.json").read_text())
GAP = '<span size="50%"> </span>'


def _flat(d, prefix=""):
    for key, value in d.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            yield from _flat(value, prefix + key + "_")
        else:
            yield prefix + key, value


def rgb(name):
    colour = THEME[name].lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def tokens():
    """Every replacement the tree renderer and css() agree on."""
    out = {"@FONT@": THEME["font"], "@MONO_FONT@": THEME["mono_font"]}
    for key, value in _flat(THEME):
        if isinstance(value, str) and value.startswith("#") and len(value) == 7:
            k = key.upper()
            out[f"@COLOUR_{k}@"] = value
            out[f"@HEX_{k}@"] = value[1:]
            out[f"@RGB_{k}@"] = ", ".join(str(int(value[i:i + 2], 16)) for i in (1, 3, 5))
    return out


def css(text):
    """Fill the style tokens in a CSS (or any) string."""
    for token, value in tokens().items():
        text = text.replace(token, value)
    return text


def icon(name):
    return (f'<span font_family="{THEME["mono_font"]} Propo" foreground="{THEME["muted"]}">'
            f'{THEME["icons"][name]}</span>')
