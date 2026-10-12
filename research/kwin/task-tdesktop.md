# Task: how Telegram Desktop 7.2.x presents its media viewer window on Linux X11

## Goal
On my i3-based desktop, Telegram Desktop's image viewer (open a photo in a chat) sometimes
ends up *behind* the main Telegram window. Under KDE/Windows the viewer always stays over the
main window, and a click on the dimmed area closes it. I need the exact X11 window properties
and behaviour of the viewer, taken from the source, so I can make my window layer handle it.

## Working root
`/home/fanatic/ai/claude/setup/research/kwin/` — write only here. Clone the source
shallowly: `git clone --depth 1 https://github.com/telegramdesktop/tdesktop.git tdesktop`
and, if needed, `https://github.com/desktop-app/lib_ui.git` and
`https://github.com/desktop-app/lib_base.git` (these hold the window/platform code).
Delete the clones at the end.

## Questions (answer each, quoting the relevant code lines with file:line)
1. Which class implements the media viewer window (`Media::View::OverlayWidget` and its
   `_window`/`_widget`)? Which Qt window flags and attributes does it set on Linux X11
   (FramelessWindowHint, WindowStaysOnTopHint, Tool, Dialog, BypassWindowManagerHint,
   WA_TranslucentBackground…)? Resulting `_NET_WM_WINDOW_TYPE`?
2. Does it set a transient parent (`QWindow::setTransientParent`, WM_TRANSIENT_FOR) to the
   main window? Under which conditions?
3. Fullscreen vs windowed mode: default on Linux, the setting that switches it, how it requests
   fullscreen (`showFullScreen`, `_NET_WM_STATE_FULLSCREEN`), and how it sizes itself in
   windowed mode (and whether it sets a geometry covering the whole screen while not
   fullscreen).
4. What it does when it loses activation / focus (does it close, hide, lower, or re-activate?),
   and when the main window is activated while the viewer is open.
5. How a click on the dimmed area closes the viewer (is the dimmed area part of the viewer
   window itself?).
6. Any window-manager–specific code paths on Linux (checks for KWin, GNOME, "i3", tiling WMs,
   `Platform::IsX11`, `base::Platform::XCB`, `_NET_WM_STATE_ABOVE`, `_NET_ACTIVE_WINDOW`
   requests, `XCB` raise calls, `activateWindow()`/`raise()` sequences) in the viewer and in
   the main window activation code (`Window::Controller::activate`, `Core::App().activate...`,
   `PlatformSpecific` window activation).
7. The same questions 1, 2 and 4 for the **call window** (`Calls::Panel`) and for
   **pip (picture-in-picture) video** windows.

## Output
One file `/home/fanatic/ai/claude/setup/research/kwin/tdesktop-viewer.md`, English, sections
1–7, with code quotes and file:line references, plus a final "Implications for a window
manager" section (what WM behaviour the viewer relies on).

## Do not
- Do not run Telegram. Do not touch anything outside the working root. Do not leave clones.

## Final report (your last message)
Path of the file and a 5-line summary: window type, transient parent yes/no, fullscreen
default, what it relies on the WM to do, the most likely reason it can fall behind the main
window under i3.
