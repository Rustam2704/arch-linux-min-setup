# Task: survey how KDE Plasma's KWin handles floating-window mechanics (X11)

## Goal
I maintain a small Windows-style floating window layer ("deskd") on top of the i3 window
manager. I want to borrow KWin's logic where it is better. Produce a factual reference of
how KWin (Plasma 6, X11 session) implements the behaviours listed below, with pointers to
the KWin source (file + function/class names) so each claim can be checked.

## Working root
`/home/fanatic/ai/claude/setup/research/kwin/` — write only here. You may `git clone --depth 1
https://invent.kde.org/plasma/kwin.git src` into this directory (and delete `src/` at the end)
and use web search / KDE docs / the KWin wiki / bug tracker.

## Topics (answer every one; say "not found" if you could not verify)
1. **Stacking of transients and modal dialogs**: how KWin keeps a transient (WM_TRANSIENT_FOR)
   above its main window; group transients (transient_for = root / window group);
   what happens when the user clicks the main window while a transient is open; how a
   frameless full-screen-size transient (e.g. an image viewer overlay) is stacked.
   Layers (`Layer` enum: Desktop, Below, Normal, Above, Notification, ActiveLayer/fullscreen,
   OnScreenDisplay…): which windows go where, and how fullscreen windows are layered when they
   lose focus.
2. **Focus stealing prevention**: levels, `_NET_WM_USER_TIME`, what happens on
   `_NET_ACTIVE_WINDOW` requests from applications (source indication 1 vs 2), demands attention.
3. **Focus after a window closes / minimizes**: which window gets focus (`FocusChain`,
   "focus under mouse" vs last used, transient's parent first?).
4. **Placement of new windows**: policies (Smart, Centered, Under mouse, Zero-cornered,
   Maximizing, Random, Cascade), default policy, how transients/dialogs are placed (centered on
   parent?), respect of program-specified position (USPosition/PPosition), keeping windows inside
   the work area, multi-monitor: on which screen a new window opens (active screen = mouse or
   focus?).
5. **Maximize / restore**: geometry restore memory (`geometryRestore`), maximize vertically /
   horizontally, behaviour of a maximized window when dragged by its title bar (unmaximize under
   the cursor: how the restored rect is positioned relative to the cursor — proportional offset?),
   double-click title bar action, `_NET_WM_STATE_MAXIMIZED_*` handling when the app itself
   requests maximize.
6. **Quick tiling / edge snapping**: electric border / screen-edge activation (distance, delay,
   the outline preview), half and quarter tiles, how quick-tile state is restored on drag-off,
   how a quick-tiled window behaves when the screen geometry changes, keyboard shortcuts
   (Meta+arrows sequence: e.g. Meta+Left twice → moves to the next screen?).
7. **Magnetic snapping during move/resize** ("Border snap zone", "Window snap zone",
   "Center snap zone", "only when overlapping"): default pixel values and algorithm
   (`Workspace::adjustWindowPosition`, `adjustWindowSize`).
8. **Interactive move/resize**: how move is driven (pointer grab, sync request
   `_NET_WM_SYNC_REQUEST` to avoid lag), whether geometry is applied at every motion event or
   throttled, "display content while moving/resizing", minimum visible area when moving
   off-screen (how much of the title bar must stay visible), Alt+drag / Meta+drag moves,
   right-button resize.
9. **Fullscreen windows**: `_NET_WM_STATE_FULLSCREEN`, layering when another window is
   activated, what happens to panels.
10. **Alt+Tab**: order (focus chain, most recent first), whether minimized windows are included,
    per-desktop, how a quick Alt+Tab (press-release) behaves, "show selected window" preview.
11. **Minimize / restore**: where minimized windows go, restoring focus/stacking.
12. **Multi-monitor**: moving windows between screens (keeps relative position? re-maximize?),
    what happens to windows on an unplugged screen.
13. **Window rules relevant to apps like Telegram Desktop** (frameless media viewer, call
    window), and any KWin special-casing of "splash", "utility", "dialog", "notification"
    window types.
14. Anything else KWin does to make floating windows feel good that a minimal i3-based layer
    would likely be missing (list concretely, with source pointers).

## Output
One file: `/home/fanatic/ai/claude/setup/research/kwin/kwin-mechanics.md`, in English,
section per topic above (numbered 1–14). Each section: short factual bullets, default
values, and `src/<path>:<function>` pointers. 4000–9000 words. No speculation presented as
fact: mark anything unverified with "(unverified)".

## Do not
- Do not touch anything outside the working root. Do not install packages.
- Do not leave the cloned `src/` directory behind.

## Final report (your last message)
- Path of the written file and its word count.
- The 10 KWin behaviours you think a minimal i3-based floating layer most likely lacks,
  one line each.
