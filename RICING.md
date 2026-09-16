# Desktop: Xfce infrastructure + i3 (2026-09-16)

**Your next login goes straight into the new session** — no chooser, no password. LightDM autologs into `Xfce + i3`.
The plain **Xfce session is untouched** and still selectable if you ever want it back (see "If something's wrong").

## What runs
`/usr/local/bin/xfce-i3-session` starts, in this order:

| Piece | Why |
|---|---|
| `xrdb ~/.Xresources` | HiDPI: `Xft.dpi 144` (1.5×) and a 36px cursor |
| `xsetroot -solid '#000000'` | Full black background (no xfdesktop — one less process) |
| `xfsettingsd` | GTK theme, fonts, **your US/RU/UA layouts and Alt+Shift** |
| `xfce4-power-manager` | Battery, lid, brightness keys |
| `xfce4-panel` | Panel, systray, clock, volume, layout indicator |
| `Thunar --daemon`, `nm-applet` | File manager service, Wi-Fi tray |
| `picom` | Shadows, fade, light transparency |
| `dex -a -s ~/.config/autostart` | Your own autostart entries only |
| `exec i3` | Window manager |

It deliberately does **not** use `xfce4-session`: no session save/restore fighting i3 over window placement, and fewer moving parts.

## Keys (Mod = Super/Cmd)
| Key | Action |
|---|---|
| `Mod+Return` | kitty |
| `Mod+d` / `Mod+Shift+d` | rofi app launcher / run a command |
| `Mod+Tab` | rofi window switcher |
| `Mod+e` | Thunar |
| `Mod+q` | close window |
| `Mod+h/j/k/l` or arrows | move focus |
| `Mod+Shift+` same | move the window |
| `Mod+b` / `Mod+v` | split horizontal / vertical |
| `Mod+f` | fullscreen |
| `Mod+s` / `Mod+w` / `Mod+g` | stacking / tabbed / toggle split |
| `Mod+Shift+space` | float this window |
| `Mod+r` | resize mode (hjkl or arrows, Esc to exit) |
| `Mod+minus` / `Mod+Shift+minus` | "minimize" to the scratchpad / bring it back |
| `Mod+1…0` | workspace; `Mod+Shift+1…0` moves the window there |
| `Mod+Shift+c` / `Mod+Shift+r` | reload / restart i3 |
| `Mod+Shift+e` | power menu: shut down / reboot / suspend / log out (same as the ⏻ panel button) |
| `Print` | Flameshot |
| F-row | F1–F12 by default; hold Fn for volume, brightness and keyboard backlight |


## Using i3 — the essentials
**Mod = Super (the ⌘ key).** Windows don't overlap by default: each new window takes a share of the screen.

**Where the next window goes**
- `Mod+b` → next window opens **beside** the focused one; `Mod+v` → **below** it.
- `Mod+w` → **tabbed** (one window visible, tabs on top); `Mod+s` → **stacked**; `Mod+g` → back to side-by-side.

**Floating vs tiled**
- `Mod+Shift+space` — **float / un-float** the focused window. This is the one to use when a window ends up floating.
- `Mod+space` — switch focus between the floating windows and the tiled ones.
- `Mod + left-drag` moves a floating window; `Mod + right-drag` resizes it.
- Dialogs and small popups float by themselves; that's normal.

**Minimize** (i3 has no real minimize, this is its equivalent)
- `Mod+minus` — hide the window. `Mod+Shift+minus` — bring it back, **tiled** in the layout (repeat to bring back the next hidden one).
- Caveat: if nothing is hidden, `Mod+Shift+minus` un-floats the focused window instead.

**Moving around**
- `Mod+arrows` (or `h j k l`) focus; `Mod+Shift+arrows` move the window.
- `Mod+f` fullscreen. `Mod+r` resize mode → arrows → `Esc`.
- `Mod+1…0` workspace; `Mod+Shift+1…0` sends the window there. Or swipe 3 fingers ← →.

**Everything else:** `Mod+Return` terminal · `Mod+d` apps · `Mod+Tab` windows · `Mod+q` close · `Mod+Shift+e` power · `Mod+Shift+c` reload config.

## Look
- **Background `#000000`**, accent **`#0d8ecb`** (your sky-blue, darker and more saturated) everywhere: i3 borders, GTK selection, rofi, kitty cursor.
- **2px borders, 8px gaps, no titlebars.** A single window on a workspace gets no gaps and no border (`smart_gaps`, `hide_edge_borders smart`).
- **Interface at 1.5×** (`Xft.dpi 144`) — your screen is 2560×1600 on 13", so 96dpi was the reason buttons were hard to hit. Top panel is **44px** with 26px icons and a single-line clock (`Wed 16 Sep   12:38`) — panel height is in raw pixels, so it doesn't follow the DPI setting on its own.
- Fonts: **Inter** for UI, **JetBrains Mono Nerd Font** for code. Iosevka Nerd is installed too — swap it in kitty with one line if you prefer the narrower one.

## picom — deliberately conservative for HD 5000
`glx` backend, vsync on, shadows, 60ms fades, 6px rounded corners, kitty at 92%/88% opacity, rofi 94%.
**No blur** — it's the one effect that would actually hurt on this GPU. Fullscreen windows bypass the compositor entirely (`unredir-if-possible`), so video and games are unaffected.

## Config files
```
~/.config/i3/config          ~/.config/picom/picom.conf
~/.config/rofi/config.rasi   ~/.config/rofi/sky.rasi      ~/.config/kitty/kitty.conf
~/.Xresources                /usr/local/bin/xfce-i3-session   /usr/share/xsessions/xfce-i3.desktop
```

## Tested before you saw it
Ran the whole session in a nested X server (Xephyr) rather than on your live desktop. That caught three things:
1. **`xsetroot` wasn't installed** — the black background would have silently failed at login. Installed.
2. **picom was starting twice** (session script *and* i3's `exec`). Removed from i3's config.
3. **rofi rendered cream-colored rows** — rofi loads its default theme *after* `config.rasi`, so the theme now lives in `sky.rasi` and is pulled in with `@theme`. Verified dark afterwards.

Also killed a stuck root-owned `xfce4-panel -r` that the theme installer left behind.

## If something's wrong at login
- **Ctrl+Alt+F2** gets you a text console; log in there.
- To go back to plain Xfce: `sudo sed -i 's/^autologin-session=.*/autologin-session=xfce/' /etc/lightdm/lightdm.conf`
- To get the session picker back: comment out `autologin-user` in `/etc/lightdm/lightdm.conf`.
- i3 config syntax check: `i3 -C -c ~/.config/i3/config`

## Gestures (touchegg)
| Gesture | Action |
|---|---|
| 3 fingers ← / → | next / previous workspace |
| 3 fingers ↑ | window switcher (rofi) — swipe ↑ again to close |
| 3 fingers ↓ | app launcher (rofi) — swipe ↓ again to close |
| 4 fingers ↑ | fullscreen on |
| 4 fingers ↓ | fullscreen off (back to the tiled layout) |

Only one rofi exists at a time: `~/.local/bin/rofi-toggle <mode>` closes an open rofi of the same mode, or replaces one of a different mode. `Mod+d`, `Mod+Shift+d` and `Mod+Tab` go through the same wrapper, so keys and gestures behave identically.

Daemon: `touchegg.service` (system). Client: started by the session script. Config: `~/.config/touchegg/touchegg.conf`.

## Terminal
**kitty only** — xfce4-terminal is uninstalled. kitty is the Xfce preferred terminal (`~/.config/xfce4/helpers.rc`), so the dock launcher and `Ctrl+Alt+T` open it too.
In kitty, **Shift+Enter inserts a newline** in Claude Code instead of sending.

## Not doing, for now
- **polybar** — your call: keep the Xfce panel.
