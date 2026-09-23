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
import os
from pathlib import Path

THEME = json.loads(Path(__file__).with_name("theme.json").read_text())
GAP = '<span size="50%"> </span>'

# The panel is quiet: every indicator draws itself at QUIET brightness unless the
# pointer is on it. deskd watches the pointer and writes the name of the plugin
# script under it to HOT_FILE, then asks that plugin (and the previous one) to
# redraw. This replaced the compositor-era veil: no compositor, no blending.
RUN = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
HOT_FILE = os.path.join(RUN, "panel-hot")
QUIET = 0.62


def hot():
    """The panel script the pointer is on ("" when none)."""
    try:
        with open(HOT_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def quiet(name):
    return hot() != name


def shade(colour, factor=QUIET):
    """A hex colour at a share of its brightness (what a black veil did)."""
    c = colour.lstrip("#")
    return "#" + "".join(f"{int(int(c[i:i + 2], 16) * factor):02x}" for i in (0, 2, 4))


def wrap(name, markup):
    """Pango markup for a plugin's text: dimmed unless the plugin is under the pointer."""
    return markup if not quiet(name) else f'<span alpha="{int(QUIET * 100)}%">{markup}</span>'


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
