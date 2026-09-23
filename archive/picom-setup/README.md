# Как было с picom (раунды 1–24, до 23.09.2026)

Сохранено из истории git (последний коммит с picom — `17c12c8`; удалён в `06e3514`).

| Файл | Что это |
|---|---|
| `picom.conf` | конфиг: glx, vsync, use-damage, тени (radius 14, без панели/рамок i3/dock/desktop), fade 60 мс, `inactive-opacity 0.96`, kitty 92 %/88 %, углы 6 px (без dock/desktop/рамок i3), `unredir-if-possible`, шейдер инверсии для окон Zoom |
| `shaders/smart-invert.glsl` | шейдер, делавший светлый Zoom тёмным |
| `deskd-veil.py` | класс `PanelDim` и методы deskd: чёрная вуаль 38 % над панелью с «дыркой» под курсором (панель приглушена, ярко только то, на что указываешь), слежение за указателем над окнами плагинов |
| `session-line.txt`, `kitty-line.txt`, `osd-line.txt` | строки, которые были в сессии (`picom --config … &`), в kitty (`background_opacity 0.92`) и в OSD (`set_opacity(0.90)`) |

Чем заменено: без композитора — `TearFree` драйвера intel вместо vsync; формы XShape у наших
окон над панелью вместо альфы; «тихая панель» (каждый плагин рисует себя приглушённым, если
курсор не на нём; deskd пишет имя плагина под курсором в `$XDG_RUNTIME_DIR/panel-hot`) вместо вуали.

Вернуть picom: `pacman -S picom`, положить `picom.conf` и `shaders/` в `~/.config/picom/`,
вернуть строку в `xfce-i3-session`, убрать `/etc/X11/xorg.conf.d/20-intel.conf`; в deskd
формы XShape тогда лишние, но безвредные.
