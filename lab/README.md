# lab — тестовая песочница

Здесь записывается каждое изменение системы. Главная цель (уточнено 18.09) —
не страховка, а **точный дифф в конце**: увидеть всё, что поменялось, убрать мусор
и, возможно, выпустить набор как open source для пользователей XFCE + i3.
Откат по-прежнему работает, если эксперимент не понравится.

## Как это работает
Каждое изменение записывается в `journal.tsv` через скрипт `./lab`:

| Действие | Что записывается | Как откатывается |
|---|---|---|
| `lab pkg <эксп> <пакет>` | пакет, если его не было | `pacman -Rns` |
| `lab write <эксп> <путь>` | новый файл или копия старого в `backups/` | удаление или восстановление копии |
| `lab undo <эксп> '<команда>'` | команда отката | выполняется как есть |

## Команды
```bash
lab status              # что сейчас применено
lab rollback 01-memory  # откатить один эксперимент
lab rollback all        # откатить всё
```

## Страховка
Перед началом снят снапшот Timeshift **`before-lab-experiments`**
(`sudo timeshift --list`). Это последний рубеж, если что-то пойдёт не так.

## Эксперименты

### 01-memory — память
- Своп-файл `/swapfile` на 16 ГБ на SSD, запись в `/etc/fstab`,
  исключение из снапшотов Timeshift.
- zram отключён (`systemd-zram-setup@zram0.service` замаскирован).
- zswap включён: сжимает страницы в оперативке, самые холодные вытесняет на SSD.
  Параметры прописаны в загрузчике (`/boot/loader/entries/arch-lts.conf`).
- `vm.swappiness = 80` в `/etc/sysctl.d/99-lab-memory.conf`.
- `~/.local/bin/firefox-limited` — Firefox запускается в systemd-области
  с мягким лимитом (по умолчанию 4 ГБ). Ярлык и помощник XFCE указывают на него.
- `~/.local/bin/firefox-mem` — показать и поменять лимит на лету, без перезапуска
  и без кнопки «Save»: `firefox-mem`, `firefox-mem set 3G`, `firefox-mem off`.
  Настройки в `~/.config/firefox-memory.conf`.
- `user.js` в основном профиле: потолок кэша распакованных картинок 128 МБ,
  меньше страниц в памяти для кнопки «Назад».

### 02-clock — часы
- Шрифт `ttf-dseg` (пока не используется, оставлен на случай, если захочется
  сменить вид цифр).
- `~/.config/gtk-3.0/gtk.css`: цифры часов в цвете **#48daf9**,
  селектор `#clock-button` (имя из исходников xfce4-panel).

## Файлы для браузера (ставятся вручную, в систему ничего не пишут)
- `browser/light-images-hover.user.js` — скрипт для Violentmonkey: картинки
  грузятся в самом маленьком из предложенных сайтом размеров, полное качество —
  при наведении.
- `browser/ublock-youtube-thumbnails.txt` — фильтры для uBlock Origin,
  полностью отключают превью на YouTube.

### 03-osd — всплывашки
- `~/.local/bin/osd-daemon` — окно поверх всего (в том числе поверх полноэкранного),
  сверху справа. Показывает громкость и яркость полоской, раскладку — бейджем.
- `~/.local/bin/osd` — клиент, шлёт сообщения демону.
- `osd.service` — пользовательская служба, стартует сама.
- Раскладку отслеживает `xkb-switch -W` (пакет `xkb-switch`), без опроса.
- В `~/.config/i3/config`: клавиши громкости и яркости вызывают `osd`,
  добавлено `focus_on_window_activation focus` (клик по окну в панели задач
  переключает на его рабочую область). Откат — `revert-i3-config.py`.

### 04-panel — панель
Нижняя панель убрана, всё сверху в одну строку: меню, kitty, файлы, Firefox,
задачи, рабочие области, трей, Telegram, сеть, CPU/RAM/SWAP, погода, батарея,
громкость, раскладка, часы, выключение.

Скрипты-индикаторы (genmon), все в едином стиле и цвете `#48daf9`:

| Скрипт | Что показывает |
|---|---|
| `panel-battery` | «заряжена» вместо вечных 97%, износ — в подсказке |
| `panel-telegram` | значок и число непрочитанных (из заголовка окна Telegram) |
| `panel-sys` | загрузка процессора, занятая память, объём в свопе |
| `panel-net` | скорость на интерфейсе с маршрутом по умолчанию |
| `panel-weather` | Open-Meteo с кэшем; без сети — последнее значение, тускло |
| `panel-workspaces` | 1…5 всегда на месте (i3 удаляет пустые, поэтому не pager) |

`app-focus-or-launch` — кнопки переключают на открытое окно, а с Ctrl или Shift
открывают новое. Кнопка «Файлы» сразу открывает домашнюю папку.

Важно: genmon берёт команду из настроек, записанных через его диалог; файлы
`genmon-*.rc` пишутся плагином. Панель целиком — в `xfce4-panel.xml`, копия
исходной лежит в `backups/`.

### 05-calendar — мини-календарь
`~/.local/share/mini-calendar/` — локальный сервер на стандартной библиотеке
Python плюс страница: месяц, создание, редактирование, перенос перетаскиванием,
ссылка Zoom. Открывается по **Super+C** (`~/.local/bin/mini-calendar`),
служба `mini-calendar.service`.
Ключи доступа и порядок подключения — `~/.local/share/mini-calendar/ИНСТРУКЦИЯ.md`.
Старое приложение Google Calendar не удалено.

**Настроено 18.09.2026:** Google (проект `calendar-508922`, OAuth-клиент Desktop,
статус приложения **In production**, чтобы доступ не отзывался раз в 7 дней; для этого
в Branding указаны `https://fanatic.space` и `https://fanatic.space/privacy`) и Zoom
(Server-to-Server OAuth приложение `mini-calendar` с правами на создание, изменение
и удаление встреч). Серверу добавлен часовой пояс `Europe/Kyiv` — Google без него
отказывался создавать события. Удаление события теперь удаляет и встречу в Zoom.
Подробности и что делать при сбоях — `~/.local/share/mini-calendar/ИНСТРУКЦИЯ.md`.

### 06-osd-keyboard — OSD и раскладки
- `~/.local/bin/osd-daemon` переписан: фиксированная ширина, непрозрачность 90%, снятие mute,
  громкость/яркость меняет сам; плюс переключатель раскладок (XRecord, срабатывает при отпускании).
- `~/.local/bin/osd` — клиент: `osd vol up|down|mute`, `osd bright up|down`, `osd layout next`.
- `~/.local/bin/panel-layout` + genmon-55 вместо плагина xkb (xfconf `/plugins/plugin-55`).
- Снята опция `grp:alt_shift_toggle` (xfconf `keyboard-layout`, `localectl`).

### 06-quickfixes — быстрые правки
- Перевод `panel-*` на английский, батарея `100%`, фиксированная ширина чисел.
- `btop` (Ctrl+Shift+Esc), Sublime по умолчанию для текста (`~/.config/mimeapps.list`), Mousepad удалён.
- `~/.config/i3/generated/` + `include` в конфиге i3.

### 07-firefox-reclaim — выгрузка заранее
- `~/.local/bin/firefox-memd` + `firefox-memd.service`, настройки в `~/.config/firefox-memory.conf`
  (`TARGET`, `STEP`, `INTERVAL`, `RECLAIM`), `firefox-mem target|early`.

### 08-net — качество связи
- `~/.local/bin/netqd` + `netqd.service` → `$XDG_RUNTIME_DIR/netq.txt`; `panel-net` его читает;
  `~/.local/bin/net-menu` — меню и тест скорости. Интервалы индикаторов в xfconf.

### 09-light-year — календарь
- `~/.local/share/light-year/` (`app.py`, `api.py`, `ИНСТРУКЦИЯ.md`), `~/.local/bin/light-year`,
  ярлык, иконки в `~/.local/share/icons/hicolor/*/apps/`. Ключи — `~/.config/light-year/`
  (в журнал не пишутся). Старый mini-calendar в `backups/` (без ключей).

### 10-favorites — меню под «яблоком»
- `~/.local/bin/deskd-favorites`, `~/.config/deskd/apps.conf`, launcher-56 вместо applicationsmenu.

### 11-deskd — окна как в Windows
- `~/.local/share/deskd/` (`deskd.py`, `i3ipc.py`), `deskd.service` (запускает i3),
  `~/.local/bin/deskd-ctl` (команды через i3 tick, для жестов), `panel-workspaces` читает
  `$XDG_RUNTIME_DIR/deskd-workspaces.txt`. Конфиг i3: шапки, цвета, привязки `nop deskd …`,
  режим `passthrough`. touchegg: 4 пальца → `deskd-ctl`. Firefox `user.js`: `inTitlebar=0`.

### 12-monitors — экраны
- `autorandr` (пакет), профили в `~/.config/autorandr/` сохраняет deskd; xfconf `displays`:
  `Notify=0`, `AutoEnableProfiles=0`.
