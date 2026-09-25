# Воспроизведение на чистом Arch — инструкция для агента

Этот файл рассчитан на то, что его выполняет ИИ-агент (Claude Code, Codex и т. п.) на свежей
установке Arch Linux. Цель — тот же рабочий стол, что описан в [README.md](README.md) и
[ARCHITECTURE.md](ARCHITECTURE.md): инфраструктура Xfce + i3 + свои инструменты из `desktop/`.
Всё, что стоит в системе, объявлено в дереве `desktop/` и ставится одной командой; ниже —
только то, что дереву не подвластно (пакеты, группы, ключи), и порядок.

## Что должно быть до начала

- Arch Linux установлен, есть сеть, `sudo` для обычного пользователя, `git`, `python3`, `base-devel`.
- Ядро — **LTS** (`linux-lts`, `linux-lts-headers`); это осознанный выбор, не менять.
- Имя пользователя любое: дерево подставляет `@USER@`/`@HOME@` при установке.
- Проект клонируется в `~/ai/claude/setup` (пути в документах и в `@PROJECT@` считают так;
  другое место тоже работает, но `README`/`MAINTENANCE` ссылаются на этот путь).

## Порядок

1. **Клонировать**: `git clone https://github.com/Rustam2704/arch-linux-min-setup ~/ai/claude/setup && cd ~/ai/claude/setup`.
2. **Пакеты из официальных репозиториев**: `make packages` печатает недостающие из
   [packages.txt](packages.txt); поставить `sudo pacman -S --needed <список>` (там же шрифты и
   инструменты сборки: `inter-font`, `xorg-server-xvfb`, `python-fonttools`).
3. **AUR**: поставить `yay` (клон `yay-bin` + `makepkg -si`), затем `yay -S --needed` по
   [packages-aur.txt](packages-aur.txt). Вторая группа там — только для MacBookPro11,1.
4. **Установка дерева**: `make apply EXP=00-fresh-install`. Это `test` (нужны `xvfb-run`,
   `python-gobject`) + рендер + запись каждого файла через `lab/lab write` в журнал
   `lab/journal.tsv`. Системные файлы (`desktop/system/` → `/usr/local/bin/xfce-i3-session`,
   `/usr/share/xsessions/xfce-i3.desktop`, `/etc/lightdm/lightdm.conf.d/50-sky-desktop.conf`)
   пишутся через `sudo`. Свойства xfconf из `desktop/xfconf/*.xml` ставятся живьём через
   `xfconf-query` — для этого должен работать `xfconfd` (в чистой консоли: `dbus-run-session`
   или выполнить шаг после первого входа в сессию и повторить `make apply`).
5. **Группы и вход**: `sudo groupadd -r autologin; sudo gpasswd -a $USER autologin;
   sudo systemctl enable lightdm`. Автовход настроен drop-in-файлом из дерева: сессия
   `xfce-i3`, без выбора сессии. `/boot/loader/loader.conf` — `timeout 0` (systemd-boot).
6. **Службы**: `systemctl --user enable netqd firefox-memd sky-stars`; `deskd` и `osd`
   запускает i3 (`exec` в конфиге, юниты `desktop/config/systemd/user/`). Touchégg:
   `sudo systemctl enable --now touchegg` (системная часть; клиент стартует из сессии).
7. **Шрифты**: `fc-cache -f` после установки (в дереве лежит `Diablo.ttf`; Inter, JetBrainsMono
   Nerd Font и DSEG7 приходят пакетами).
8. **GTK-модуль дока**: собранный `libdock-rtl.so` лежит в дереве (x86_64). На другой
   архитектуре или после смены GTK — `make -C assets/dock-rtl` и `make apply`.
9. **Плагин Qt для жестов**: `assets/qt-scroll-phases/install.sh` (cmake; пересобирать после
   обновления Qt).
10. **Личное, вне дерева** (создать руками):
    - `~/.config/sky-desktop/weather` — `"<lat> <lon>"` для погоды (иначе центр Житомира);
    - `~/.config/sky-desktop/keysound` — `off`, чтобы выключить звуки клавиш (по умолчанию включены);
    - ключи календаря `~/.config/light-year/` (Google OAuth Desktop, Zoom Server-to-Server) и
      кнопка **Connect Google** в календаре;
    - `~/.config/zoomus.conf`: `showZoomWindowInSharing=true` в `[General]` (Zoom не штрихует
      свои окна у зрителя демонстрации).
11. **Перезагрузка** в сессию. Проверка: `make status` должен печатать
    `0 files and 0 xfconf properties differ from the declared desktop`.

## Что ещё знать агенту

- Правила проекта — в [README.md](README.md) («Как добавить фикс»): править только `desktop/`,
  цвета и шрифты только токенами темы, каждое изменение системы — через `make apply EXP=…` или
  `lab/lab`, абзац в `CHANGELOG.md`, коммит. Никогда не редактировать установленные копии в `~`.
- Что перезапускать после правки какого файла — таблица в [MAINTENANCE.md](MAINTENANCE.md).
- Проверять визуальное — на вложенном X (`Xephyr`/`Xvfb`), не на экране пользователя;
  клавиши проверять и в русской раскладке.
- Особенности именно этого MacBook (прошивка, Wi-Fi, Fn/Ctrl) — раздел «Особенности этой
  машины» в MAINTENANCE.md; на другом железе они не нужны.
- Данные Diablo для огня, пентаграмм, звуков и шрифта лежат в `external-assets/` (см. его README);
  архивы `.mpq` в git не входят, скачиваются по ссылке оттуда только для перегенерации.
