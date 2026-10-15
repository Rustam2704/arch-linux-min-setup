"""Render Telegram's badge state as genmon markup."""
import os

from sky_theme import THEME


def render(running, count):
    icons = os.path.expanduser("~/.local/share/panel-icons")
    if not running:
        icon, tip, text = "telegram-off.png", "Telegram is not running", ""
    elif count:
        icon = "telegram-accent.png"
        tip = f"Telegram: {count} unread"
        text = f'<span foreground="{THEME["light"]}" weight="bold">{count}</span>'
    else:
        icon, tip, text = "telegram.png", "Telegram: no unread messages", ""
    lines = ['<css>* { background-color: transparent; background-image: none; box-shadow: none; } '
             'button { padding: 0 2px 0 0; }</css>',
             f'<img>{os.path.join(icons, icon)}</img>']
    if text:
        lines.append(f'<txt>{text} </txt>')
    lines.append(f'<tool>{tip}</tool>')
    toggle = os.path.expanduser("~/.local/bin/telegram-toggle")
    lines.extend((f'<click>{toggle}</click>', f'<txtclick>{toggle}</txtclick>'))
    return "\n".join(lines) + "\n"
