#!/usr/bin/env python3
"""Open a file/URL under a mouse click, including hard-wrapped TUI text."""

import importlib.machinery
import importlib.util
import os
import unicodedata

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


def visible_lines(window):
    """The rows exactly as they are on screen now, scrollback position included.

    The mouse row counts from the top of what is shown, but plain as_text() is the live
    bottom screen: after scrolling back (a long Claude session) the click landed on an
    unrelated row and nothing opened. screen.visual_line(y) is kitty's own accessor for
    the displayed row y (it is what @first-line-on-screen uses)."""
    screen = window.screen
    return [str(screen.visual_line(y) or "") for y in range(screen.lines)]


def cell_width(ch):
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def token_at(row, x):
    """(start cell, end cell, text) of the run of non-space characters under cell x."""
    cells = []                                   # cell -> character index
    for i, ch in enumerate(row):
        cells.extend([i] * cell_width(ch))
    if not 0 <= x < len(cells) or row[cells[x]].isspace():
        return None
    i = j = cells[x]
    while i and not row[i - 1].isspace():
        i -= 1
    while j + 1 < len(row) and not row[j + 1].isspace():
        j += 1
    start = sum(cell_width(c) for c in row[:i])
    end = start + sum(cell_width(c) for c in row[i:j + 1])
    return start, end, row[i:j + 1]


def click_candidates(rows, y, x, columns):
    """The word under the click first. It is glued to the next or previous row only when
    it runs into the window edge - a path the terminal or a TUI wrapped. Whole-paragraph
    guesses come last: with a list of paths one per row, gluing the rows made every click
    open the first path of the list."""
    hit = token_at(rows[y], x) if 0 <= y < len(rows) else None
    if not hit:
        return []
    start, end, word = hit
    out = []
    if end >= columns - 1 and y + 1 < len(rows):            # runs off the right edge
        nxt = rows[y + 1].lstrip()
        if nxt:
            out.append(word + nxt.split()[0])
    if start <= 2 and y > 0:                                # starts at the left edge
        prev = rows[y - 1].rstrip()
        if prev and len(prev) >= columns - 2:
            out.append(prev.split()[-1] + word)
    out.append(word)
    return out


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

    lines = visible_lines(window)
    helper = load_open_path()
    cwd = window.cwd_of_child or os.path.expanduser("~")
    first = click_candidates(lines, pos["cell_y"], pos["cell_x"], window.screen.columns)
    for text in first + [t for t in text_around_click(lines, pos["cell_y"]) if t not in first]:
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
