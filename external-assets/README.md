# external-assets — материалы Diablo I для рабочего стола

Скачано 23.09.2026 по просьбе пользователя: горящие буквы главного меню, вращающиеся
пентаграммы, звуки и шрифты Diablo I — для эффектов панели (горящая цифра активной области).

## Откуда

| Что | Источник |
|---|---|
| `devilutionx-assets/spawn.mpq` (не в git, 25 МБ) | shareware-данные Diablo, релиз **v5** репозитория [diasurgical/devilutionx-assets](https://github.com/diasurgical/devilutionx-assets/releases/tag/v5) |
| `devilutionx-assets/fonts.mpq`, `devilutionx.mpq` (не в git) | там же: шрифтовые атласы DevilutionX (формат CLX) и его дополнительная графика |
| `devilutionx-source/` | `Source/DiabloUI/{title,mainmenu,diabloui}.cpp` и `LICENSE.md` из [diasurgical/DevilutionX](https://github.com/diasurgical/DevilutionX): как движок грузит и анимирует логотип (`smlogo`, 15 кадров) и пентаграммы (`focus16/focus/focus42`, 8 кадров), `GetAnimationFrame(frames, fps = 60)` |
| `diablo-spawn/` | распаковано из `spawn.mpq` утилитой `smpq` (AUR): `ui_art/` (логотипы, пентаграммы, шрифты `font16/24/30/42` PCX + `.bin`, кнопки), `sfx/` (все 256 звуков, mp3), `ctrlpan/smaltext.cel`, `data/medtexts.cel`, `data/bigtgold.cel` (игровые шрифты CEL) |

Восстановить архивы: `curl -LO https://github.com/diasurgical/devilutionx-assets/releases/download/v5/spawn.mpq`
(и `fonts.mpq`, `devilutionx.mpq`); распаковать: `smpq -x spawn.mpq <файлы>`.

Полезные звуки: меню — `sfx/items/titlemov.mp3`, `titlslct.mp3`; монеты — `sfx/items/gold.mp3`,
`gold1.mp3`; падение предметов — `sfx/items/flip*.mp3`; надевание — `sfx/items/inv*.mp3`;
зелья — `sfx/items/invpot.mp3`, `sfx/misc/invpot.mp3`; портал — `sfx/misc/portal.mp3`.

## Инструменты (`tools/`)

- `pcx.py` — читалка 8-битных PCX Diablo (кадры спрайт-листа лежат друг под другом,
  прозрачный индекс 250).
- `fire-digits.py` — режет `ui_art/smlogo.pcx` на шесть огоньков (буквы D‑i‑a‑b‑l‑O найдены
  по пикселям, неподвижным во всех 15 кадрах: столбцы 17–71, 98–114, 142–176, 202–232,
  260–287, 313–364) и накладывает маски цифр 1–9 в шрифте полосы областей (xfconf
  `plugin-45`, DPI из `xrdb`, жирный, `tnum`). Результат — `fire-digits/`:
  `flames/flame{k}/frame{i}.png` (огоньки без букв), `flame{k}-digit{d}.png` (15 кадров
  столбиком, размер цифры, тёмно-красное тело цифры + огонь из плотной части пламени),
  `preview.png`, `index.json`. Перегенерация: `python3 external-assets/tools/fire-digits.py`.

- `diablo-font.py` — собирает из `ui_art/font30s.pcx` + `font30.bin` TrueType-шрифт
  `desktop/share/fonts/Diablo.ttf` (семейство `Diablo`): тело буквы (светлые индексы 227–236
  серой рампы; тёмная кромка 237–239 отброшена — панель красит текст сама) превращается в
  квадратные контуры, 32 единицы на пиксель, em = 30 px, так что `Diablo 15` при 144 dpi
  рисуется пиксель в пиксель. Межбуквенный интервал 1 px как в `DrawArtStr`; в таблице только
  ASCII и `°` (остальные ячейки листа — не Latin-1). Цифры получают `tnum`-варианты на общей
  ширине (самая широкая, ноль, плюс по пикселю). Перегенерация: `python3 external-assets/tools/diablo-font.py`.

## Где используется

`deskd` (`FireDigits`, константы `FIRE_DIR`, `FIRE_FPS`, `PANEL_WS_COUNT = 6` на время теста)
рисует над цифрами 1–6 полосы областей шесть разных огоньков — для выбора.
