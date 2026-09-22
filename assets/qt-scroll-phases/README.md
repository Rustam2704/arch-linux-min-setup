# Physical two-finger scroll phases for Qt on X11

This is a Qt 6 generic plugin, not a gesture-to-key daemon. It keeps the
application's own scrolling/navigation logic and supplies the missing
`ScrollBegin → ScrollUpdate → ScrollEnd` sequence. No application-name list,
arrow-key injection, input grabs, or new background service is involved.

## Why this fixes Telegram's native swipe handler

Telegram Desktop 7.2.8 already has two-finger media navigation. Its
[`SetupSwipeHandler`](https://github.com/telegramdesktop/tdesktop/blob/v7.2.8/Telegram/SourceFiles/ui/controls/swipe_handler.cpp#L367)
explicitly ignores `NoScrollPhase` and commits navigation on `ScrollEnd`.
The media viewer connects that handler to its own previous/next actions in
[`setupSwipeNavigation`](https://github.com/telegramdesktop/tdesktop/blob/v7.2.8/Telegram/SourceFiles/media/view/media_view_overlay_widget.cpp#L7489).
Qt 6.11.2's [XCB backend](https://github.com/qt/qtbase/blob/v6.11.2/src/plugins/platforms/xcb/qxcbconnection_xi2.cpp#L1360)
forwards scroll deltas without phases. The missing data is in the toolkit
integration, not in i3's workspace commands.

The plugin uses Qt's [generic plugin mechanism](https://doc.qt.io/qt-6/qgenericplugin.html).
It observes physical two-finger contact frames with libevdev, and associates
them with Qt touchpad events by device name and monotonic event timestamp.
Only udev-tagged touchpads are opened. The udev rule grants the active local
session access to those devices; keyboard devices are not opened.

One continuous contact sequence remains one gesture even if movement pauses.
The 25 ms release timer only drains trailing X events after physical contact
ends; it never substitutes inactivity for finger release. Rapid separate
gestures retain separate contact IDs. Motion values, modifiers, source and
natural-scroll direction are preserved. QPA delivery preserves normal widget
event propagation and logical HiDPI coordinates.

## Alternatives researched

* [Touchégg](https://github.com/JoseExposito/touchegg): installed stable 2.0.18,
  about 4,125 stars; repository last push 2025-06-14 when checked 2026-09-22.
  Its FAQ explicitly excludes two-finger browser navigation. Adding a pointer
  scroll recognizer to its daemon would detect the gesture, but sending keys
  still cannot choose the right action for a child widget. Retained for the
  existing three/four-finger desktop gestures.
* [Fusuma](https://github.com/iberianpig/fusuma): about 3,895 stars, repository
  last push 2026-07-10. It is maintained and extensible, but documented swipes
  start at three fingers. Its plugins do not restore application scroll phases.
* libinput already distinguishes finger scrolling and its end. Its
  [documentation](https://wayland.freedesktop.org/libinput/doc/latest/scrolling.html)
  assigns context-sensitive scroll behavior to the application. Replacing the
  recognizer or globally emulating arrows would work at the wrong layer here.

## Build and install

Dependencies on Arch: `qt6-base`, `libevdev`, `systemd-libs`, `cmake`,
`pkgconf`, and a C++ compiler (already installed on this machine).

```sh
bash assets/qt-scroll-phases/install.sh
```

The installer builds, tests, and writes through `lab/lab`, experiment
`27-native-two-finger-swipe`. It installs:

* `/usr/lib/qt6/plugins/generic/libqscrollphases.so`
* `/etc/udev/rules.d/70-qt-scroll-phases.rules`

The X11 session must export `QT_QPA_GENERIC_PLUGINS=scrollphases` before
starting applications. This has been added to `/usr/local/bin/xfce-i3-session`.
The current D-Bus/systemd activation environment has also been updated and
Telegram restarted with the variable. Applications launched by an already
running parent with the old environment need the variable explicitly, or the
next login. For a single launch:

```sh
QT_QPA_GENERIC_PLUGINS=scrollphases Telegram
```

The plugin uses Qt's private QPA delivery API. **Rebuild after a Qt update.**
A runtime version guard disables the plugin on a different Qt version instead
of using incompatible internals. Ordinary scrolling remains available when
the plugin is disabled or touchpad observation is unavailable.

## Scope and verification

This enables existing native swipe handlers in dynamically linked Qt 6 X11
applications. It does not invent navigation in applications without such a
handler, and does not extend GTK, Firefox, Electron, Qt 5, or sandboxed/static
Qt builds. No claim of a universal scroll-to-navigation fallback is made.

The rejected four-finger horizontal arrow bindings were removed from Touchégg.
Three-finger workspace/launcher gestures and four-finger maximize/restore
remain as before.

The regression harness checks one physical gesture despite a movement pause,
rapid consecutive gestures with delayed X delivery, mouse/native/unmonitored
events, horizontal and vertical scrolling over child widgets, switching from
touchpad to a mouse wheel, timestamp wrap, and a window closed mid-gesture.
It runs through Qt's real event and widget propagation path, offscreen.

Live checks on 2026-09-22 confirmed Qt identifies `bcm5974` as `TouchPad`,
the contact signal exists, and the plugin and `/dev/input/event15` descriptor
are loaded in the restarted Telegram process. On 2026-09-22 the user also confirmed a physical horizontal two-finger swipe
in Telegram's media viewer advances exactly one photo after finger release.

The release library is about 62 KiB. A sequential probe comparison measured
19,336 KiB PSS without it and 19,467 KiB with it (about +131 KiB in that run;
shared-library accounting varies). There is no additional persistent process.

## Disable/rebuild

For a one-off launch without the plugin, use `QT_QPA_GENERIC_PLUGINS= Telegram`
after quitting the running instance. For permanent removal, remove the session
export and activation environment, then remove the two installed files through
the lab workflow, reload udev rules, trigger the touchpad, and restart affected
applications. Do not roll back an older whole-file session backup after making
later session edits; see the existing lab rollback limitations in the review.
