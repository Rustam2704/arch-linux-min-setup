# F. Editor-like text selection in the terminal (read-only research, 2026-10-15)

Method: docs + changelog + binary strings/bundled JS + upstream source, plus live tests in an **isolated** Xvfb display `:97`
(second kitty 0.48.2 with the owner's `kitty.conf`, scratch `HOME`, `kitten @`/`xdotool`, pty probes). Nothing in the real `$HOME` or
config was touched (mtimes checked); rig killed afterwards. **V** = verified (seen or measured), **I** = inferred.

## 1. Claude Code 2.1.300 prompt
- **No selection in the prompt buffer. V** The bundled JS key handler (binary strings) treats Shift+Left/Right/Home/End exactly like the plain keys
  (shift ignored), ignores Shift+Up/Down, and the Ctrl map is only a,b,c,d,e,f,h,k,n,p,u,w,y. Docs "Text editing" table: Ctrl+A = start of current
  logical line (https://code.claude.com/docs/en/interactive-mode). Ctrl+Shift+Left/Right = backward/forward word, still no selection.
- **Keybindings. V** (docs/keybindings + binary action inventory). File `~/.claude/keybindings.json`, hot-reloaded, owner already has
  `{"bindings":[{"context":"Chat","bindings":{"ctrl+z":"chat:undo"}}]}`; `null` unbinds; chords like `"ctrl+x ctrl+k"`. Chat actions: cancel, clearInput,
  clearScreen, killAgents, cycleMode, modelPicker, fastMode, thinkingToggle, submit, queueSubmit, sendNow, newline, undo, externalEditor, stash, imagePaste.
  **No cursor, selection or select-all action**; docs: the text-editing shortcuts "can't be remapped, the file has no actions for them".
  `selection:extendLeft/Right/Up/Down/LineStart/LineEnd/copy/clear` exist only in context `Scroll` and act on the mouse (screen) selection.
  Ctrl+A is not reserved (reserved: Ctrl+C/D/M/[/I/H) so it can be bound to another action, but nothing useful. settings: no selection setting
  (`editorMode`, `tui`, `copyOnSelect` in `~/.claude.json`, env `CLAUDE_CODE_DISABLE_MOUSE[_CLICKS]`; `keybindingFlavor` deprecated). Mods cannot hook prompt keys (docs: "your mod never reads the keyboard"). I
- **Mouse. V (docs/fullscreen)** Fullscreen renderer captures the mouse: click in the prompt places the cursor; drag selects screen text, copied on release;
  double-click word, triple-click line; Shift+arrows/Shift+Home/End extend that mouse selection. It is **screen text, not the edit buffer**: plain arrows, Enter
  and typed characters just clear it (typing does not replace it; Backspace then deletes one char, I). Ctrl+C with a selection copies instead of cancelling;
  Ctrl+X does nothing (prefix of `ctrl+x ctrl+e` etc.). Fullscreen is default for users who started after May 2026 (docs table; Anthropic's comment in
  issue #27561); owner's first start 2026-09-15, no `tui` setting, so fullscreen I (`/tui` prints the truth). Without mouse capture (classic) no click-to-position.
- **Only keyboard selection: vim mode** (`/config` Editor mode): Esc, `v`/`V` + motions, `d/y/c`; modal, no Ctrl+A. Ctrl+C on a non-empty idle prompt clears it, Up restores (docs).
- **Upstream. V** #80734 (open, filed 2026-07-24) asks exactly for Shift/Ctrl+Shift selection in Chat; #27561 closed 2026-08-17 as "available in fullscreen" (mouse only);
  comments there still ask for Ctrl+A, Ctrl+Shift+arrows, Cmd+Z. No changelog line to 2.1.300 adds prompt selection (grep of CHANGELOG.md).
- **What arrives. V** Claude pushes `CSI>5u` (binary string; flags 1+4). Measured in kitty: Ctrl+A `ESC[97;5u`, Shift+Left `ESC[1;2D`, Ctrl+Left `ESC[1;5D`,
  Ctrl+Shift+Left `ESC[1;6D`, Home `ESC[H`, Shift+Home `ESC[1;2H`; RU layout Ctrl+physical-A `ESC[1092::97;5u` (base key 97 so `ctrl+a` still matches).

## 2. Codex CLI 0.162.1 composer
- **Config. V** `[tui.keymap.<context>] action = "ctrl-a" | ["..",".."]`, `[]` unbinds, `/keymap` edits interactively (config-reference at learn.chatgpt.com + binary
  strings "Invalid `tui.keymap` configuration"). Contexts (binary): global, chat, composer, editor, vim_normal/operator/search/text_object, pager, list, approval, agents.
  `editor` actions (upstream keymap.rs + binary): insert_newline, move_left/right/up/down, move_word_left/right, move_line_start/end, delete_backward/forward(_word),
  kill_line_start, kill_whole_line, kill_line_end, yank. **No selection/select-all/undo action.** Defaults: Ctrl+A/Home = move_line_start, Ctrl+Left/Right = word;
  Shift+Left/Right in `chat` = edit_queued_message/prompt_stack_back. Owner's `config.toml` has no keymap, only `[tui] screen_reader_detection_done`.
- **Mouse. I** (upstream `main` ~0.163-alpha source; the 0.162.1 binary has the same files `textarea/mouse.rs`, `text_selection.rs`, keys `copy_on_select`,
  `right_click_paste`, `fullscreen_transcript`, and enables `?1000/1002/1003/1006h`): `fullscreen_transcript` defaults true, so Codex owns the screen and grabs the mouse.
  In the composer a left click places the cursor, drag selects, double-click = word, triple-click = logical line (400 ms); Shift/Ctrl/Alt+click ignored. **The selection is editable:
  typing and paste replace it**; Backspace/Delete ignore it (delete one grapheme). `tui.copy_on_select` auto = on for kitty on Linux; Ctrl+C / Ctrl+Shift+C / Super+C copy.
- Keyboard selection: none V (editor keymap above; textarea only accepts Shift for plain characters). `/raw` or Alt+R = raw scrollback mode for native selection (docs).

## 3. bash 5.3 / readline 8.3
- **Sequences. V** (legacy mode, what bash sees; `kitten show-key` + xdotool): Shift+Left `ESC[1;2D`, Shift+Right `1;2C`, Shift+Home `1;2H`, Shift+End `1;2F`,
  Ctrl+Left `1;5D`, Ctrl+Shift+Left `1;6D`, Home `ESC[H` (`ESC OH` in keypad mode), Ctrl+A `0x01` (also on the RU layout, physical key). **kitty swallows Ctrl+Shift+Left/Right
  (previous/next_tab) and Ctrl+Shift+Home/End (scroll)** by default (never reached the program). Readline: `/etc/inputrc` binds `\e[1;5C/D`, Home/End only; the Shift ones are unbound
  and leak: pty test, `echo abc` + Shift+Left leaves `echo abcD`, Shift+Home leaves `H`.
- **(a) plain readline: not viable. V** `enable-active-region` highlights only bracketed-paste text and history-search hits (`man readline`). `bind -x` can set `READLINE_POINT/MARK`
  but readline never emitted the highlight (pty test, no `ESC[7m`) and every `bind -x` call redraws the prompt; `set-mark` + arrows also no highlight. No maintained snippet found.
- **(b) ble.sh: yes, out of the box. V** (nightly = master, tested inside kitty): Shift+Left/Right/Home/End/Up/Down highlight; Ctrl+Shift+Left/Right select words (after unmapping in kitty);
  typing replaces, Backspace deletes, End/plain arrows drop the selection (plain Left moves one extra char instead of collapsing to the left edge). Source: `src/edit.sh` keymap `selection`,
  `bleopt delete_selection_mode=1` default. Not default: **select-all** and clipboard copy/cut. A custom Ctrl+A widget, Ctrl+C copy (xclip) and Ctrl+X cut worked (snippet below);
  Ctrl+V pastes but **does not replace** a selection. Widgets use internal `_ble_edit_*` vars (may break on update, I). kitty prompt marks and click-to-move still work with ble.sh (tested).
  **Cost, measured here:** first prompt after `source` +520 ms (872 ms cold cache) vs <1 ms; RSS 21.5 MB vs 5.5 MB per shell (owner's idle bash: 3.9 MB). Packages: AUR `blesh-git`
  (author-maintained, builds master; needs make+gawk) or `blesh` 0.3.4 (2023; has the selection keymap by grep, 3 vs 21 "kitty" mentions in the code, not run). Repo alive (last commit 2026-09-08, 4.8k stars, 86 open issues).
- **(c)** zsh 5.9.2 is in extra; `zsh-shift-select` (jirutka: Shift+arrows/Home/End, Shift+Ctrl+arrows, typing replaces) is a source-only plugin, last push 2022-07, no clipboard integration, same kitty unmap needed.
  fish 4.9.3: Shift+Left/Right move by word, selection only in vi visual mode (docs). Neither beats ble.sh on gain and both cost the `claude()`/`codex()` bashrc functions.

## 4. kitty 0.48.2
- **Click-to-move at the prompt: on by default. V** `mouse_map left click ungrabbed mouse_handle_click selection link prompt` and the same for `shift+left click grabbed,ungrabbed` (local conf.html).
  Needs OSC 133 marks: owner's shells run `bash --posix` + `ENV=kitty.bash`, `KITTY_SHELL_INTEGRATION=enabled` (`/proc/3823/environ`). Tested: plain bash and bash+ble.sh both move the cursor on click
  (kitty sends fake arrow keys; bash integration has no `click_events`). Only inside the marked current prompt.
- **Inside Claude/Codex: no. V** They grab the mouse (owner's own kitty.conf comment, Claude docs, Codex `?1003h`), so `ungrabbed` rules never fire and there are no prompt marks; their own click handling applies (sections 1-2).
- **Shift+click today.** At a bash prompt it moves the cursor (tested) and the owner's `shift+left press ... mouse_selection extend` fires too; in a grabbed TUI it bypasses the app and extends a kitty selection (owner's map, I).
  Click-drag at a prompt = kitty text selection, copied to the clipboard (`copy_on_select clipboard`), **no editing meaning**: typing appends at the cursor, Backspace deletes one char (tested). No kitty option turns it into a line-editor selection.
- **Helpful options.** A bare `map ctrl+shift+left` (maps to nothing = pass to program, docs/mapping) frees word selection; tab switching keeps `ctrl+tab`/`ctrl+shift+tab` (default maps). `send_text`/`send_key` can remap keys but cannot add a selection model to programs without one.

## 5. Impossible, stated plainly
- **Claude Code and Codex: keyboard selection (Shift+arrows, Ctrl+A select-all) cannot be configured.** Neither has an action for it; only an upstream change helps (#80734). Codex has editable *mouse* selection; Claude Code has only a screen-text selection.
- **Plain bash (readline) cannot show a selection** without ble.sh. Native kitty selection can never be edited by typing.

## Recommended plan
1. **bash**: install ble.sh and accept +0.5 s per new shell and ~16 MB more RAM per shell. `yay -S blesh-git` (or the nightly tarball under `~/.local/share/blesh`), then in `~/.bashrc`:
   first line after the interactive guard `source /usr/share/blesh/ble.sh --noattach --rcfile ~/.blerc`, last line `[[ ${BLE_VERSION-} ]] && ble-attach`.
2. **kitty.conf** (also in `desktop/config/kitty/kitty.conf`, then `make apply`): `map ctrl+shift+left` and `map ctrl+shift+right` (optional: `ctrl+shift+home`, `ctrl+shift+end`). Cost: lose Ctrl+Shift+arrows tab switching, keep Ctrl+Tab.
3. **`~/.blerc`** (tested):
```bash
function ble/widget/my/select-all { _ble_edit_mark=0; _ble_edit_ind=${#_ble_edit_str}; _ble_edit_mark_active=S; ble/decode/keymap/push selection; }
function ble/widget/my/copy-selection { local b=$_ble_edit_mark e=$_ble_edit_ind t; ((b>e)) && t=$b b=$e e=$t
  printf %s "${_ble_edit_str:b:e-b}" | xclip -selection clipboard -i; }
function ble/widget/my/copy-and-exit { ble/widget/my/copy-selection; _ble_edit_mark_active=; ble/decode/keymap/pop; }
function ble/widget/my/cut-selection { ble/widget/my/copy-selection; ble/widget/delete-region; ble/decode/keymap/pop; }
ble-bind -m emacs -f C-a my/select-all
ble-bind -m selection -f C-c my/copy-and-exit      # no selection: Ctrl+C still interrupts (kitty copy_and_clear_or_interrupt only acts on a kitty selection)
ble-bind -m selection -f C-x my/cut-selection
```
   Not covered: paste over a selection (needs a small wrapper, untested); Wayland would need `wl-copy` instead of `xclip`.
4. **Claude Code**: change nothing; keep fullscreen (click to position, drag to copy). Closest tools: vim mode, Ctrl+C then Up. Do not rebind Ctrl+A. Comment on #80734.
5. **Codex**: change nothing; use drag, double-click, triple-click (editable) and typing. No keymap change gains selection; Ctrl+A stays move_line_start.
6. **Conflicts**: Ctrl+A becomes select-all only in bash (Home still goes to the line start, Ctrl+E/End to the end) while it stays beginning-of-line in Claude/Codex, so the
   shortcut is inconsistent across programs. Ctrl+Shift+A is not an alternative (kitty chord prefix). A stale kitty mouse selection makes Ctrl+C copy instead of reaching ble.sh.
