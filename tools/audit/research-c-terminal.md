# Research C-terminal: editor-like text selection in the terminal (read-only)

Owner request (translated): "In the terminal Ctrl+A must select all the text I typed. Holding Shift and
moving with the arrows, or clicking with the mouse, must select that part of the text — as usual in text
editors. Not only in the Claude chat."

Machine: Arch, X11, terminal **kitty 0.48.2** (config: `~/.config/kitty/kitty.conf`, source in
`/home/fanatic/ai/claude/setup/desktop/config/kitty/`), shell **bash 5.3** (readline 8.3, no
`~/.inputrc` yet, `~/.bashrc` exists), **Claude Code 2.1.300** (`claude`), **Codex CLI 0.162.1**
(`codex`). The owner spends most terminal time typing into Claude Code and Codex prompts and the bash
prompt. Shortcuts must work in US, Russian and Ukrainian layouts.

READ-ONLY: change nothing on the machine (no config edits, no installs, no `make apply`). You may read
any file, run `--help`/`--version`, `strings` on binaries, read local docs, and search/fetch the web.
Never `pkill -f`/`pgrep -f`. Do not type into or screenshot the owner's screen.

Answer, with evidence (doc URL, changelog line, local file:line or binary string) and "verified" vs
"inferred" for each claim:
1. **Claude Code 2.1.300 prompt input**: does it support a text selection at all (Shift+arrows,
   Shift+Home/End, select-all, mouse click to place the cursor, mouse drag/Shift+click to select), and
   what do typing / Backspace / Ctrl+C / Ctrl+X do with a selection? What does Ctrl+A do today? Is it
   configurable through `~/.claude/keybindings.json` (list the relevant action names and contexts, the
   exact file format, and whether Ctrl+A can be rebound) or settings.json? Check
   https://code.claude.com/docs (keybindings, interactive mode, terminal setup) and the changelog.
2. **Codex CLI 0.162.1 composer**: the same questions; any keymap config in `~/.codex/config.toml`?
3. **bash 5.3 / readline 8.3**: the best way to get editor-like selection on the command line —
   Shift+Left/Right/Home/End (and Ctrl+Shift+Left/Right by word) extend a highlighted region, Ctrl+A
   selects the whole line, typing replaces the region, Backspace/Delete delete it, plain arrows drop
   it, a copy key puts it on the clipboard. Compare: (a) plain readline (`enable-active-region`,
   `set-mark`, `bind -x` with `READLINE_LINE/POINT/MARK`) — is there a maintained snippet/project?;
   (b) **ble.sh** (does it do all of the above out of the box? startup time and RAM per shell, stability,
   Arch package); (c) zsh + zsh-shift-select / fish — only note what switching would give.
   What escape sequences does kitty 0.48 send for Shift+Left, Shift+Home, Ctrl+Shift+Left, Ctrl+A
   (legacy vs kitty keyboard protocol) and does readline see them distinctly?
4. **kitty 0.48.2**: shell-integration "click to move the cursor at the prompt"
   (`mouse_map ... mouse_handle_click ... prompt`): is it on by default, does it work with bash, does it
   work inside Claude Code / Codex (they are full-screen TUIs — do they enable mouse reporting?); can
   Shift+click or click-drag at a prompt become a line-editor selection anywhere; what does Shift+click
   do in kitty today. Any kitty option that would help the TUIs (e.g. `map` to send other sequences).
5. Anything that makes this impossible for some program (and which programs), stated plainly.

Report (English, markdown, under 120 lines) to
`/home/fanatic/ai/claude/setup/research/audit-2026-10-15/f-terminal-selection.md`, ending with a
recommended plan: per program what can be done, the exact config snippets/commands, what each costs
(RAM/startup), what will not work, and conflicts (e.g. Ctrl+A = beginning-of-line today; Home still
works for that). Final message: the path and a 10-line summary.
