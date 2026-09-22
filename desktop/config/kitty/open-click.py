#!/usr/bin/env python3
"""Open a file/URL under a mouse click, including hard-wrapped TUI text."""

import importlib.machinery
import importlib.util
import os

from kitty.fast_data_types import click_mouse_url
from kittens.tui.handler import result_handler

OPEN_PATH = os.path.expanduser("~/.local/bin/open-path")


def load_open_path():
    loader = importlib.machinery.SourceFileLoader("panel_open_path", OPEN_PATH)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def text_around_click(lines, row):
    """Return the clicked hard-wrapped paragraph, then narrower fallbacks."""
    if not 0 <= row < len(lines):
        return []
    start = end = row
    while start and lines[start - 1].strip() and row - start < 3:
        start -= 1
    while end + 1 < len(lines) and lines[end + 1].strip() and end - row < 3:
        end += 1

    candidates = ["".join(line.strip() for line in lines[start:end + 1])]
    if row + 1 < len(lines):
        candidates.append(lines[row].strip() + lines[row + 1].strip())
    if row:
        candidates.append(lines[row - 1].strip() + lines[row].strip())
    candidates.append(lines[row].strip())
    return list(dict.fromkeys(text for text in candidates if text))


def main(args):
    pass


@result_handler(no_ui=True, type_of_input="screen")
def handle_result(args, screen_text, target_window_id, boss):
    window = boss.window_id_map.get(target_window_id)
    if window is None:
        return
    pos = window.current_mouse_position()
    if pos is None:
        return

    lines = window.as_text(add_wrap_markers=True).splitlines()
    helper = load_open_path()
    cwd = window.cwd_of_child or os.path.expanduser("~")
    for text in text_around_click(lines, pos["cell_y"]):
        path, line = helper.resolve(text, cwd=cwd)
        if path:
            helper.open_it(path, line)
            return
    # Preserve native OSC-8 handling when the target is stored behind display
    # text and therefore cannot be reconstructed from the visible rows.
    if click_mouse_url(window.os_window_id, window.tab_id, window.id):
        return
    row = pos["cell_y"]
    helper.complain(lines[row] if 0 <= row < len(lines) else "")
