# Desktop setup status

Updated 2026-09-22. This file is the hand-off point for the next continuation.

## Finished in this checkpoint

- Native Qt two-finger photo swipe is installed and verified by the user in Telegram.
- Volume icons use the requested colored arc treatment; the icon cache was rebuilt.
- `light-year` now has Daily, Weekly, Custom days, Monthly and Yearly recurrence controls. Custom weekday buttons start with only the event weekday selected. Monthly and Yearly are under `More`.
- Calendar event lists calculate visible rows from the allocated day-cell height, expose a clickable `+N more` control, expand into a scrollable area, and recalculate after resize. Google event listing is paginated.
- Recurring-event edits preserve advanced RRULEs and create a new series before cutting the old one when editing following occurrences.
- Focused managed windows are restacked by `deskd` after i3 refreshes; active workspace marking no longer stops at a fullscreen workspace on another output.
- Network indicator changes are split into Wi-Fi and latency controls. Background link status uses `--rescan no`; the Wi-Fi menu owns the toggle, cached network list, and explicit refresh action.
- CPU, memory and swap indicators use icons placed after their values. Panel widget style values are centralized in `desktop/share/sky-desktop/theme.json`.
- Power actions use a GTK menu anchored at the pointer/panel button.
- Codex terminal remains on its native editing semantics (`Ctrl+A` is line start). `Ctrl+G` now opens the external editor with normal select-all, Shift-selection and mouse-caret behavior; the editor saves continuously.
- The Astra starfield algorithm is reproduced as a black desktop background in `sky-stars`, with the same deterministic density, phases, brightness curve and 150 ms cadence. It is running as a user service.
- The starfield is explicitly an X11 `DESKTOP` window below the Xfce dock; the earlier popup type hid the top panel and was corrected during hand-off.
- Desktop sources, tests, and an idempotent `Makefile`/`tools/desktop.py` build-and-apply path are now versioned. System writes continue through `lab/lab`; rollback now detects later-file conflicts, uses unique backups, and keeps failed records.

## Current verification

- `make check` passed (49 declared source files).
- Six focused calendar/API unit tests passed.
- GTK smoke test passed for recurrence controls, 20-event overflow, expansion, scrolling, resize recalculation, and five-event fit.
- Python compilation and `bash -n lab/lab` passed.
- `deskd.service`, `netqd.service`, `osd.service`, and `sky-stars.service` are active with zero restarts at hand-off.
- `python tools/desktop.py status` reports zero differences between declared desktop sources and installed files.

## Continue later

- Do a short visual/manual pass only: open the calendar, network Wi-Fi menu, power menu, and Codex external editor; verify pointer placement and labels on the physical panel.
- Confirm the starfield density/brightness by eye and adjust only if needed. The implementation deliberately follows the Codex source algorithm rather than inventing a second effect.
- Exercise one real recurring calendar event only after the UI pass; do not create synthetic events in the user's calendar.
- Review and clean historical `lab/backups`/old logs as an archival task. They are intentionally retained for rollback at this checkpoint.

## Canonical commands

```sh
make check
make test
make diff
make apply
python tools/desktop.py status
```

`desktop/` is the declared source tree. `desktop/share/sky-desktop/theme.json` is the shared palette and icon/layout source.
