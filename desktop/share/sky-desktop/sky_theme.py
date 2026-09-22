"""Shared palette, spacing and panel markup. No GTK import in panel readers."""
import json
from pathlib import Path

THEME = json.loads(Path(__file__).with_name("theme.json").read_text())
GAP = '<span size="50%"> </span>'


def icon(name):
    return (f'<span font_family="JetBrainsMono Nerd Font Propo" foreground="{THEME["muted"]}">'
            f'{THEME["icons"][name]}</span>')


def rgb(name):
    colour = THEME[name].lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def gtk_css(css):
    """Map the existing GTK styles onto the shared palette."""
    for old, key in {"#0a0e11": "background", "#dfe8ee": "foreground",
                     "#12171a": "surface", "#5b6b76": "muted", "#1e262c": "border",
                     "#48daf9": "light", "#0d8ecb": "accent", "#e05561": "danger"}.items():
        css = css.replace(old, THEME[key])
    return css.replace("font-family: Inter", "font-family: " + THEME["font"])
