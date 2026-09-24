# Обслуживание и восстановление

## Ежедневное

```bash
make status                         # система совпадает с деревом? (норма: 0 files differ)
lab/lab status                      # что применено, по экспериментам
systemctl --user status deskd osd netqd firefox-memd sky-stars
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
| `bin/osd-daemon` | `systemctl --user restart osd` |
| `bin/netqd` | `systemctl --user restart netqd` |
| `bin/sky-stars` | `systemctl --user restart sky-stars` |
| `bin/panel-*` | ничего: genmon перечитывает скрипт при следующем запуске команды |
| `config/gtk-3.0/gtk.css` | GTK читает при старте программы: панель — `xfce4-panel -r` (через i3 при пересоздании) |
| `config/kitty/kitty.conf` | `kill -USR1` работающим kitty или новое окно |
| `config/picom/picom.conf`, `config/rofi/*`, `config/touchegg/*` | при следующем запуске программы (`touchegg` — `systemctl restart touchegg` + клиент из сессии) |
| `share/light-year/*` | закрыть и открыть календарь (`Super+C`) |
| `config/Thunar/*` | `thunar -q` **до** `make apply` (при выходе Thunar переписывает `accels.scm` из памяти), потом `i3-msg 'exec --no-startup-id Thunar --daemon'`; открытые окна Thunar закроются |
| `config/systemd/user/*` | `systemctl --user daemon-reload && systemctl --user restart <служба>` |
| `system/*` (сессия) | следующий вход |

Панель — только через i3: `xfce4-panel -q; i3-msg 'exec --no-startup-id xfce4-panel'`.
Шрифт genmon применяется только при старте плагина, а при выходе панель пишет настройки обратно
в xfconf — менять шрифт только пока панель остановлена (`-q` → xfconf → запуск).
Шрифт `Diablo.ttf` после правки: `make apply` и `fc-cache -f`.

## Восстановление на чистой машине

1. Arch с ядром LTS, пользователь `fanatic` (или заменить в `desktop/config/deskd/apps.conf` и
   тестах), `git clone` в `~/ai/claude/setup`.
2. `make packages` → `sudo pacman -S --needed <недостающие>`; из AUR — `touchegg`, `zoom`,
   `xfce4-docklike-plugin`, `mbpfan`, `facetimehd-dkms`, `broadcom-wl-dkms`.
3. `make apply EXP=00-fresh-install` — ставит дерево (системные файлы через `sudo`).
4. Панель: раскладка хранится в xfconf и деревом не описана — скопировать
   `xfce4-panel.xml` с рабочей машины (`~/.config/xfce4/xfconf/xfce-perchannel-xml/`) при
   остановленной панели, либо собрать по списку плагинов из [ARCHITECTURE.md](ARCHITECTURE.md#панель-xfce-одна-строка-сверху-66-px-144-dpi).
   Прочие свойства xfconf: `xsettings` (тема Sky-Dark, Inter 10, DPI), `keyboard-layout`
   (us,ru,ua без `grp:` опций — их делает OSD), `displays` (`Notify=0`, `AutoEnableProfiles=0`),
   `xfce4-power-manager` (уведомления выключены).
5. `systemctl --user enable netqd firefox-memd sky-stars`; `deskd` и `osd` запускает i3.
6. LightDM: в `/etc/lightdm/lightdm.conf` `[Seat:*]` → `autologin-user=fanatic`,
   `autologin-session=xfce-i3`, группа `autologin`. `/boot/loader/loader.conf` — `timeout 0`.
7. Плагин Qt: `assets/qt-scroll-phases/install.sh` (сборка cmake, udev-правило, пересобирать
   после обновления Qt — при несовпадении версии плагин просто не загружается).
8. Календарь: положить ключи в `~/.config/light-year/` (Google OAuth-клиент Desktop,
   Zoom Server-to-Server), нажать **Connect Google** в окне.

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
- Раскладка панели (xfconf) не объявлена деревом — восстанавливается копией XML.
- Zoom: `annotate_toolbar` сбоит, когда экран демонстрируют пользователю (не исследовано).
- Приложение в Zoom Marketplace всё ещё называется `mini-calendar`.
- У окон во вкладках (tabbed/stacked) цветных кнопок в шапке нет — заголовки там служат вкладками.
- Правый клик в терминале ничего не делает; альтернативы (меню пути и т. п.) — решение за пользователем.
- Шумоподавление микрофона по голосу отложено пользователем.
- `~/.codex/AGENTS.md` дублирует правила из README для Codex — при смене правил править в двух местах.
