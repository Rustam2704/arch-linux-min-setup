## Common rules for the audit fix tasks (15.10.2026)
Project `/home/fanatic/ai/claude/setup`. Read `tools/audit/common.md` (context + deliberate design
decisions that must be kept) and the audit report named in your task. Fix ONLY the files of your task
(listed there) — other agents fix other files in parallel. Do not run `make apply`, do not restart or
touch the live session/display :0, do not commit, never `pkill -f`/`pgrep -f`. Keep the surrounding
code style and comment density; English UI text. Each fix minimal and local; if a finding turns out to
be wrong or not worth it, say so instead of changing code. Run `make test` (must pass) and the tests
relevant to your files. Final message (English, under 50 lines): per finding id — fixed (file:line) /
skipped (why); tests run and results; anything the coordinator must do when applying (restarts etc.).
