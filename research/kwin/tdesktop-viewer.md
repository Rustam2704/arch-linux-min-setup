# Telegram Desktop 7.2.x media viewer on Linux X11

Source snapshot: `telegramdesktop/tdesktop` tag **v7.2.10** (`d81a5ac`, whose `core/version.h:25-27` says `7.2.10`, beta), with its pinned `lib_ui` commit `9763648` and `lib_base` commit `de35c7a`. Paths below are relative to the temporary source checkouts. Findings are static source analysis; Telegram was not run. X11 property names below describe the Qt/XCB protocol result or the absence of an application request, and are identified as such where Qt supplies the behavior.

## 1. Viewer class, window flags, attributes, X11 type

`Media::View::OverlayWidget` owns a separate `Ui::GL::Window`; `_window` is its top level `Ui::RpWindow`, `_body` is its content container, and `_widget` is the drawing surface inside that container:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:666-678
OverlayWidget::OverlayWidget()
: _wrap(std::make_unique<Ui::GL::Window>(Ui::GL::Window::Translucent::Yes))
, _window(_wrap->window())
, _helper(Platform::CreateOverlayWidgetHelper(_window.get(), [=](bool maximized) {
    toggleFullScreen(maximized);
}))
, _body(_wrap->widget())
...
, _surface(Ui::GL::CreateSurface(_body, chooseRenderer(_wrap->backend())))
, _widget(_surface->rpWidget())
```

`Ui::GL::Window` constructs `RpWindow` without a parent; the default helper marks it as a normal top level window. The default title helper applies `FramelessWindowHint` when its custom title is shown:

```cpp
// lib_ui/ui/gl/gl_window.cpp:60-65
std::unique_ptr<RpWindow> Window::createWindow(..., bool translucent) {
    _backend = chooseBackend(CheckCapabilities());
    return std::make_unique<RpWindow>(translucent);
}
// lib_ui/ui/platform/ui_platform_window.cpp:118-121, 332-334
BasicWindowHelper::BasicWindowHelper(not_null<RpWidget*> window)
: _window(window) {
    _window->setWindowFlag(Qt::Window);
}
window()->windowHandle()->setFlag(Qt::FramelessWindowHint, titleShown);
```

The viewer also explicitly enables transparency. Its sole explicit `Qt::Tool` assignment is **Mac only**:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:917-923, 1069-1070
if constexpr (Platform::IsMac()) {
    _window->setWindowFlags(Qt::FramelessWindowHint | Qt::Tool);
}
_window->setAttribute(Qt::WA_NoSystemBackground, true);
_window->setAttribute(Qt::WA_TranslucentBackground, true);
```

The `RpWindow` constructor also sets both background attributes for its translucent form (`lib_ui/ui/widgets/rp_window.cpp:26-34`). On Linux there is **no viewer request** for `Qt::Tool`, `Qt::Dialog`, `Qt::WindowStaysOnTopHint`, `Qt::X11BypassWindowManagerHint`/`BypassWindowManagerHint`, or an X11-specific window-type attribute. Therefore its expected `_NET_WM_WINDOW_TYPE` is **`_NET_WM_WINDOW_TYPE_NORMAL`**, supplied by Qt for `Qt::Window` (or equivalently treated as NORMAL if a WM sees no explicit type); it is not a dialog or utility window. `FramelessWindowHint` and translucency affect decoration/painting, not the normal type. This type mapping is an inference from the quoted flags and [Qt's window flag/X11 attribute documentation](https://doc.qt.io/qt-6/qt.html); Telegram does not write `_NET_WM_WINDOW_TYPE` itself.

## 2. Transient parent

The viewer does **not** call `QWindow::setTransientParent` or set `WM_TRANSIENT_FOR` to the main window, in fullscreen or windowed mode. It stores the opener only for later application navigation:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:4623-4625
if (const auto controller = request.controller()) {
    _openedFrom = base::make_weak(&controller->window());
}
```

That pointer is not passed to `_window`, whose construction has no parent (`lib_ui/ui/gl/gl_window.cpp:60-65`). The nearby Linux helper is only a default title-control helper (`tdesktop/Telegram/SourceFiles/platform/linux/overlay_widget_linux.h:12-18`). A possible Qt-generated `WM_TRANSIENT_FOR` pointing to Qt's **client leader** must not be mistaken for a main-window parent: `lib_ui/ui/platform/linux/ui_utility_linux.cpp:702-705` explicitly notes that `QXcbWindow::show()` rewrites the property “to the client leader by default.” The exact live X property can depend on the Qt build, but the application does not establish a main-window transient relation under any condition in this path.

## 3. Fullscreen, maximized, and windowed geometry

The saved viewer position's default is fullscreen (`maximized = 2`); `2` means fullscreen, `1` means maximized (on Linux), and `0` means a normal-sized window. `initFullScreen()` converts legacy/saved `1` to fullscreen only on Mac:

```cpp
// tdesktop/Telegram/SourceFiles/core/core_settings.h:1193
WindowPosition _mediaViewPosition = { .maximized = 2 };
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:1126-1141
switch (Core::App().settings().mediaViewPosition().maximized) {
case 2: _fullscreen = true; _windowed = false; break;
case 1: _fullscreen = Platform::IsMac(); _windowed = false; break;
}
```

The viewer's fullscreen control calls `toggleFullScreen`; toggling off selects normal windowed mode and persists that position via `savePosition()` (`media_view_overlay_widget.cpp:1159-1209, 3152-3170`). On each open it calls the Qt window-state API matching the selected mode:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:4961-4978
updateGeometry();
if (_windowed || Platform::IsMac()) {
    _window->showNormal();
} else if (_fullscreen) {
    _window->showFullScreen();
} else {
    _window->showMaximized();
}
...
activate();
```

On X11, Qt's `showFullScreen()` is the request that yields `_NET_WM_STATE_FULLSCREEN` for an EWMH WM; the viewer does not send that client message itself. It also sets its geometry to the whole *physical screen* when `_fullscreen` is true:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:1213-1227, 1250-1266
if (_fullscreen) {
    updateGeometryToScreen(inMove);
} else if (_windowed && _normalGeometryInited) {
    ...
    _window->setGeometry(geometry); // saved normal geometry
}
...
const auto available = screen->geometry();
_window->Ui::RpWidget::setGeometry(available);
```

Thus **windowed mode does not set screen-covering geometry**. It restores `_normalGeometry`, computed from the saved viewer rectangle or `DefaultPosition()` (`media_view_overlay_widget.cpp:242-259, 1143-1156`). Maximized mode uses `showMaximized()`, leaving the effective size to the WM.

## 4. Activation and loss of focus

Opening or explicitly activating the viewer raises it, asks Qt for activation, focuses its body, and sets the Qt active window:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:4510-4516
void OverlayWidget::activate() {
    _window->raise();
    _window->activateWindow();
    setFocus();
    QApplication::setActiveWindow(_window);
    setFocus();
}
```

Its window event filter handles move, resize, close, theme, context menu, and state changes (`media_view_overlay_widget.cpp:755-810`); it does **not** handle `WindowDeactivate` or `FocusOut` by closing, hiding, lowering, or reactivating. Losing focus alone leaves it open. The application event filter installed while the viewer is shown handles shortcuts and mouse activity inside this same viewer window (`media_view_overlay_widget.cpp:8696-8764`), not deactivation.

When a **main Telegram window** becomes active, the app reactivates the viewer only if the viewer is fullscreen, visible, not minimized, and on the same screen:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:4503-4507
return _fullscreen && !isHidden() && !isMinimized()
    && (_window->screen() == window->screen());
// tdesktop/Telegram/SourceFiles/core/application.cpp:1762-1764
if (_mediaView && _mediaView->takeFocusFrom(now->widget())) {
    _mediaView->activate();
}
```

**Windowed and maximized (`maximized = 1`) viewers do not get this automatic refocus.** This explains how the main window may become active above a still-open viewer in those modes. Even in fullscreen mode, this is an application-side reaction to a main-window activation event; the WM still decides whether to honor the raise/focus request.

## 5. Clicking the dimmed area

The dimmed area is painted **inside the viewer window** across its drawing surface; it is not a separate X11 dimmer window or the exposed main window. `_body` resize sets `_widget` to the same size (`media_view_overlay_widget.cpp:811-835`), and the renderer paints background before content:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:6393-6397
void OverlayWidget::paint(not_null<Renderer*> renderer) {
    renderer->paintBackground();
    if (contentShown()) { ... }
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_raster.cpp:77-88
const auto &bg = _owner->_fullScreenVideo
    ? st::mediaviewVideoBg : st::mediaviewBg;
for (const auto &rect : region) { _p->fillRect(rect, bg); }
```

The `_widget` mouse event filter calls `handleMousePress`/`handleMouseRelease` (`media_view_overlay_widget.cpp:843-853`). After an ordinary left press, release on empty background closes only if the viewer is **not windowed**, below its title controls, no drag or disqualifying action occurred, and no special selection/story/document-bubble case consumes the click:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp:8542-8568
} else if (_pressed) {
    if (_dragging) { ... }
    else if (!_windowed
        && position.y() > st::mediaviewTitleButton.height
        && (position - _lastAction).manhattanLength()
            >= st::mediaviewDeltaFromLastAction) {
        ...
        } else if (!_document || documentContentShown()
            || !documentBubbleShown() || !_docRect.contains(position)) {
            if (!_stories || _stories->closeByClickAt(position)) {
                close();
            }
        }
    }
}
```

`close()` hides the viewer (`media_view_overlay_widget.cpp:3137-3143`). A click on the main window when the viewer is behind it cannot reach this handler, so it cannot mimic the intended background-click dismissal.

## 6. WM-specific paths and main-window activation

The viewer and its Linux overlay helper contain no KWin, GNOME, i3, tiling-WM, `Platform::IsX11`, `_NET_WM_STATE_ABOVE`, `_NET_ACTIVE_WINDOW`, or direct XCB raising branch. They use Qt's `raise()`/`activateWindow()` sequence quoted in §4. The Linux helper simply returns `DefaultOverlayWidgetHelper` (`tdesktop/Telegram/SourceFiles/platform/linux/overlay_widget_linux.h:12-18`). Its ordinary minimize path sets `Qt::WindowMinimized` (`tdesktop/Telegram/SourceFiles/platform/platform_overlay_widget.cpp:194-196`). No viewer path sets always-on-top. The shared `lib_ui` helper does have X11 checks for custom frame margins: `WindowMarginsSupported()` tests WM support for `_GTK_FRAME_EXTENTS`, and `SetWindowMargins()` writes those extents (`lib_ui/ui/platform/linux/ui_utility_linux.cpp:716-739, 741-759`). That is decoration geometry, not viewer stacking or activation.

Main-window activation takes a different route:

```cpp
// tdesktop/Telegram/SourceFiles/window/window_controller.cpp:492-494
void Controller::activate() { _widget.activate(); }
// tdesktop/Telegram/SourceFiles/window/main_window.cpp:634-641
setWindowState(windowState() & ~Qt::WindowMinimized);
setVisible(true);
Platform::ActivateThisProcess();
raise();
activateWindow();
controller().updateIsActiveFocus();
```

On Linux, `Platform::ActivateThisProcess()` passes the active main window's XID to `base::Platform::ActivateThisProcessWindow` (`tdesktop/Telegram/SourceFiles/platform/linux/specific_linux.cpp:842-849`). On X11, that routine maps it, makes an XCB `XCB_STACK_MODE_ABOVE` restack request, then sends a root-window `_NET_ACTIVE_WINDOW` client message:

```cpp
// lib_base/base/platform/linux/base_process_linux.cpp:45-69, 77-85, 97-100
xcb_map_window_checked(connection, window);
uint32_t values[] = { XCB_STACK_MODE_ABOVE };
xcb_configure_window_checked(connection, window,
    XCB_CONFIG_WINDOW_STACK_MODE, values);
xev.type = activeWindowAtom; // "_NET_ACTIVE_WINDOW" at lines 35-37
xev.data.data32[0] = 1;     // application source
xcb_send_event_checked(connection, false, root,
    XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT
        | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY, ...);
```

This XCB path targets the **main** window, not the viewer. An unrelated X11-specific path in `platform/linux/main_window_linux.cpp:48-102` sends `_NET_WM_STATE_SKIP_TASKBAR` for tray behavior; it does not set the viewer above. `platform/linux/specific_linux.cpp:662-669` checks WM support only for skip-taskbar. There is no viewer-specific WM-name detection or X11 raise override in the inspected paths.

## 7. Call window and PiP

### Calls::Panel

`Calls::Panel` owns `Calls::Window`, which owns a default `Ui::GL::Window`/`Ui::RpWindow` (`tdesktop/Telegram/SourceFiles/calls/calls_panel.cpp:110-114`; `calls_window.h:101-103`). Like the viewer, that is a `Qt::Window` from the default `RpWindow` helper (`lib_ui/ui/gl/gl_window.cpp:32-40, 60-65`; `lib_ui/ui/platform/ui_platform_window.cpp:118-121`). It has a custom title that can set `FramelessWindowHint` (`lib_ui/ui/platform/ui_platform_window.cpp:332-334`). The panel itself sets `WA_OpaquePaintEvent` and `WA_NoSystemBackground`:

```cpp
// tdesktop/Telegram/SourceFiles/calls/calls_panel.cpp:281-285
void Panel::initWindow() {
    window()->setAttribute(Qt::WA_OpaquePaintEvent);
    window()->setAttribute(Qt::WA_NoSystemBackground);
    window()->setTitle(_user->name());
```

The shared default window helper **may also set `WA_TranslucentBackground`** when `WindowMarginsSupported()` is true (`lib_ui/ui/platform/ui_platform_window.cpp:312-315`). On X11, that depends on WM support for `_GTK_FRAME_EXTENTS` (`lib_ui/ui/platform/linux/ui_utility_linux.cpp:730-739`); the call panel does not set it unconditionally as the viewer does.

There is no `Tool`, `Dialog`, bypass-WM, or transient parent request to the main window in this call path. Its expected X11 type is **NORMAL**. It is **not always on top by default**; the user can pin it, which sets `WindowStaysOnTopHint` on its `QWindow`:

```cpp
// tdesktop/Telegram/SourceFiles/calls/calls_window.cpp:180-188
bool Window::pinnedOnTop() const {
    const auto handle = window()->windowHandle();
    return handle && (handle->flags() & Qt::WindowStaysOnTopHint);
}
void Window::setPinnedOnTop(bool pinned) {
    if (const auto handle = window()->windowHandle()) {
        handle->setFlag(Qt::WindowStaysOnTopHint, pinned);
    }
}
```

It shows, unminimizes, raises, activates, and focuses on `showAndActivate()` (`calls_panel.cpp:219-230`). The panel's event filter handles Close, KeyPress, WindowStateChange, Enter, and Leave, but no deactivation/focus-out action (`calls_panel.cpp:287-317`). Loss of activation neither closes nor automatically reactivates it; `handleClose()` may hang up or hide depending on call state (`calls_panel.cpp:1738-1755`). A pinned call window asks the WM for above-all behavior via Qt's top hint; an unpinned one does not.

### Picture-in-picture video

`Media::View::PipPanel` creates a parentless `Ui::RpWidget` and explicitly asks for a **Tool/utility** window above all windows. It also asks not to take focus and enables translucency:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_pip.cpp:339-360
PipPanel::PipPanel(QWidget *parent, ...)
: _window(std::make_unique<Ui::RpWidget>(nullptr))
, _parent(parent) { ... }
void PipPanel::init() {
    widget()->setWindowFlags(Qt::Tool
        | Qt::WindowStaysOnTopHint
        | Qt::FramelessWindowHint
        | Qt::NoDropShadowWindowHint
        | Qt::WindowDoesNotAcceptFocus);
    widget()->setAttribute(Qt::WA_ShowWithoutActivating);
    widget()->setAttribute(Qt::WA_MacAlwaysShowToolWindow);
    widget()->setAttribute(Qt::WA_NoSystemBackground);
    widget()->setAttribute(Qt::WA_TranslucentBackground);
```

Under Qt/X11, `Qt::Tool` yields `_NET_WM_WINDOW_TYPE_UTILITY` ([Qt documentation](https://doc.qt.io/qt-6/qt.html)); `WindowStaysOnTopHint` requests the above state. PiP explicitly removes Qt's `WM_TRANSIENT_FOR` X property when the window is shown/exposed, so it has **no main-window transient parent** and is intended to float independently:

```cpp
// tdesktop/Telegram/SourceFiles/media/view/media_view_pip.cpp:373-383
... | rpl::filter(rpl::mappers::_1) | rpl::on_next([=] {
    // Workaround Qt's forced transient parent.
    Ui::Platform::ClearTransientParent(widget());
}, rp()->lifetime());
// lib_ui/ui/platform/linux/ui_utility_linux.cpp:629-646
if (::Platform::IsX11()) {
    ... xcb_delete_property_checked(connection, widget->winId(),
        XCB_ATOM_WM_TRANSIENT_FOR);
}
```

On Linux, `IgnoreAllActivation()` and `InitOnTopPanel()` are empty hooks (`lib_ui/ui/platform/linux/ui_utility_linux.cpp:626-627`; `lib_ui/ui/platform/linux/ui_utility_linux.h:17-18`). PiP calls `show()` without an activation request (`media_view_pip.cpp:969-985`). Its event handler reacts to Close and mouse/leave events, not `WindowDeactivate`/`FocusOut` (`media_view_pip.cpp:992-1016`). Focus loss does not close, hide, lower, or re-activate it; `WindowDoesNotAcceptFocus` and `WA_ShowWithoutActivating` mean normal PiP use does not take focus in the first place.

## Implications for a window manager

The viewer relies on the WM to honor its normal window's initial `raise()` and activation request, and, when fullscreen, Qt's fullscreen request. It supplies **no persistent above state and no main-window transient relationship**, so normal stacking rules can later place the main Telegram window over it. Telegram repairs this only for a visible, unminimized **fullscreen** viewer on the **same screen** when a main window is activated (§4). A WM layer that wants the viewer to remain modal-looking should recognize the viewer as a distinct normal window (title set at `media_view_overlay_widget.cpp:914-915`), keep it above Telegram's main window while it is open, and preserve its full-window input region so background clicks reach the viewer's close handler. Do not apply PiP's utility/always-on-top handling to the viewer: the source asks for those flags only for PiP (§7).
