# Обслуживание и восстановление

## Ежедневное

```bash
make status                         # система совпадает с деревом? (норма: 0 files differ)
lab/lab status                      # что применено, по экспериментам
systemctl --user status deskd osd netqd sky-stars
journalctl --user -u deskd -n 50    # логи любой службы
firefox-mem                         # потолок Firefox, цель, сколько в свопе
deskd-ctl maximize-on|maximize-off  # то же, что жесты 4 пальцами
i3-peek --workspace 3 -o /tmp/shot.png     # посмотреть область, не переключаясь
```

## Что перезапускать после `make apply`

| Изменён файл | Действие |
|---|---|
| `config/i3/config` | `i3 -C -c ~/.config/i3/config && i3-msg reload` |
| `share/deskd/*`, `share/sky-desktop/*` | `systemctl --user restart deskd` (и `osd`, `sky-stars`, если менялась тема) |
| `bin/osd-daemon`, `share/sky-desktop/netmenu.py` | `systemctl --user restart osd` |
| `bin/netqd` | `systemctl --user restart netqd` |
| `bin/sky-stars` | `systemctl --user restart sky-stars` |
| `bin/panel-*` | ничего: genmon перечитывает скрипт при следующем запуске команды |
| `config/gtk-3.0/gtk.css` | GTK читает при старте программы: панель — `xfce4-panel -r` (через i3 при пересоздании) |
| `config/kitty/kitty.conf` | `kill -USR1` работающим kitty или новое окно |
| `config/picom/picom.conf`, `config/rofi/*`, `config/touchegg/*` | при следующем запуске программы (`touchegg` — `systemctl restart touchegg` + клиент из сессии) |
| `share/light-year/*` | закрыть и открыть календарь (`Super+C`) |
| `xfconf/xfce4-panel.xml` | `make apply` ставит свойства живьём; шрифты genmon — только после перезапуска панели (`xfce4-panel -q; i3-msg 'exec --no-startup-id xfce4-panel'`) |
| `config/Thunar/*` | `thunar -q` **до** `make apply` (при выходе Thunar переписывает `accels.scm` из памяти), потом `i3-msg 'exec --no-startup-id Thunar --daemon'`; открытые окна Thunar закроются |
| `config/systemd/user/*` | `systemctl --user daemon-reload && systemctl --user restart <служба>` |
| `system/*` (сессия) | следующий вход |

Панель — только через i3: `xfce4-panel -q; i3-msg 'exec --no-startup-id xfce4-panel'`.
Шрифт genmon применяется только при старте плагина, а при выходе панель пишет настройки обратно
в xfconf — менять шрифт только пока панель остановлена (`-q` → xfconf → запуск).
Шрифт `Diablo.ttf` после правки: `make apply` и `fc-cache -f`.

## Восстановление на чистой машине

Пошагово — [BOOTSTRAP.md](BOOTSTRAP.md): пакеты (`packages.txt`, `packages-aur.txt`),
`make apply EXP=00-fresh-install` (дерево вместе со свойствами xfconf: панель, xsettings,
раскладки, power manager, Thunar), группа `autologin` и LightDM (drop-in из дерева), службы,
личные файлы вне дерева.

Снапшоты — Timeshift (rsync), последний рубеж — `before-lab-experiments`.

## Особенности этой машины (уже сделано, помнить при переустановке)

- **30-секундная задержка прошивки** лечится удалением мёртвых записей NVRAM про macOS
  (`efibootmgr -b 0080 -B …`) и своей записью `\EFI\systemd\systemd-bootx64.efi`; было 38 с,
  стало 9 с. Запасной вход — Option при включении. Резерв переменных — `/root/nvram-*.bak`.
- Звук при включении выключен через EFI-переменную `SystemAudioVolume` (байт громкости `00`).
- Wi-Fi BCM4360 — только `broadcom-wl-dkms`, без WPA3; предупреждения ядра безвредны.
- Fn ⇄ Ctrl: `options hid_apple swap_fn_leftctrl=1` в `/etc/modprobe.d/hid_apple.conf` + `mkinitcpio -P`.
- Батарея изношена: контроллер заканчивает заряд на ~97 %, панель показывает `100%`.
- Firefox Developer Edition закреплён (`IgnorePkg`), обычный Firefox удалён.

## Если что-то сломалось

| Симптом | Что делать |
|---|---|
| Не входит в сессию | `Ctrl+Alt+F2`, `autologin-session=xfce` в `lightdm.conf` возвращает чистый Xfce |
| Нет шапок/кнопок у окон | `systemctl --user restart deskd`, `journalctl --user -u deskd` |
| Панель пропала или без индикаторов | запустить через i3 (см. выше); `python3 -c` не нужен — genmon перечитает скрипты сам |
| Календарь: «Not connected to Google» / ошибка токена | **Connect Google** в окне; порт занят — `ss -ltnp \| grep 8412` |
| Не создаётся ссылка Zoom | приложение в Zoom Marketplace должно быть активно (Activation) |
| `make status` показывает расхождения | кто-то правил установленную копию: перенести правку в `desktop/` и `make apply`, либо `make apply` чтобы вернуть объявленное |
| Откат не проходит («conflicts with a later experiment») | откатывать начиная с последнего эксперимента, который трогал тот же файл |

## Известные хвосты

- Подключение/отключение HP по HDMI вживую не проверялось (логика проверена на подменённом i3).
- Zoom: `annotate_toolbar` и плавающее самовидео при демонстрации теперь плавают без рамки и
  не берут фокус (правило i3, 25.09); подтверждение от пользователя ожидается.
- Zoom, демонстрация экрана: композитор не выключать (`unredir-if-possible-exclude` для окон Zoom),
  `showZoomWindowInSharing=true` в `zoomus.conf` — проверка с другим учеником ожидается (25.09).
  Разрыв кадра у зрителя — от захвата экрана в самом Zoom, picom его не лечит (`use-damage`
  выключать нельзя: 8 % CPU в простое).
- Питание: профили TLP настраиваются в `desktop/system/etc/tlp.d/50-sky-desktop.conf`; выбор из меню
  батареи — `~/.config/sky-desktop/power-mode`, текущий профиль — `/run/tlp/last_pwr` (0/1/2).
- Большие страницы памяти только по запросу: `transparent_hugepage=madvise` там же (30.09).
- Своп без сжатия: `zswap.enabled=0` в `/boot/loader/entries/arch-lts.conf` (через lab, 30.09, решение
  пользователя; было zstd, пул 20 %). Вернуть: `lab/lab rollback` или правка строки загрузчика.
- Firefox: `user.js` профиля (`~/.config/mozilla/firefox/<profile>/`) держит настройки памяти и
  видео (VA-API, без VP9/AV1 — на Haswell в железе только H.264); файл вне дерева, записан через lab.
- Звонки: эхоподавление — переключатель в меню динамика (модуль PipeWire по требованию). Если в
  программе выбран не «Default», а физический микрофон, выбрать «Microphone-echo-cancelled».
- Приложение в Zoom Marketplace всё ещё называется `mini-calendar`.
- У окон во вкладках (tabbed/stacked) цветных кнопок в шапке нет — заголовки там служат вкладками.
- Правый клик в терминале ничего не делает; альтернативы (меню пути и т. п.) — решение за пользователем.
- Шумоподавление микрофона по голосу отложено пользователем.
- `~/.codex/AGENTS.md` дублирует правила из README для Codex — при смене правил править в двух местах.
